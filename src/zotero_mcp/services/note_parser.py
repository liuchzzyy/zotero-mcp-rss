"""
Parser for LLM-generated analysis content.

Supports both structured JSON and Markdown formats, with fallback logic.
"""

import json
import re
from typing import Any

from zotero_mcp.models.zotero import (
    AnyBlock,
    BulletListBlock,
    Citation,
    CodeBlock,
    ContentBlock,
    HeadingBlock,
    HorizontalRuleBlock,
    ListItemWithCitation,
    NumberedListBlock,
    ParagraphBlock,
    QuoteBlock,
    TableBlock,
)
from zotero_mcp.utils.config.logging import get_logger

logger = get_logger(__name__)


class StructuredNoteParser:
    """Parse LLM output into structured note blocks."""

    def parse(self, content: str) -> list[AnyBlock]:
        """
        Parse LLM output into structured blocks.

        Args:
            content: Raw LLM output (JSON or Markdown)

        Returns:
            List of AnyBlock objects (union of all block types)

        Raises:
            ValueError: If content cannot be parsed
        """
        # Check if content is wrapped in markdown code blocks with JSON
        # Pattern: ```json ... ``` or ``` ... ``` containing JSON
        json_code_block_match = re.search(
            r"```(?:json)?\s*\n(\{[\s\S]*?)\n```", content
        )
        if json_code_block_match:
            logger.info("Detected JSON in markdown code block, extracting...")
            json_str = json_code_block_match.group(1).strip()
            blocks = self._try_parse_json_str(json_str)
            if blocks:
                return blocks

        # Try direct JSON format
        try:
            return self._parse_json(content)
        except (json.JSONDecodeError, ValueError) as e:
            logger.debug(f"JSON parsing failed: {e}, falling back to Markdown")
            return self._parse_markdown(content)

    def _try_parse_json_str(self, json_str: str) -> list[AnyBlock] | None:
        """
        Try to parse a JSON string into blocks, with repair attempts.

        Returns parsed blocks on success, or None if all attempts fail.
        """
        # Attempt 1: Direct parse
        data = self._try_json_loads(json_str)

        # Attempt 2: Repair common LLM JSON errors
        if data is None:
            repaired = self._repair_json(json_str)
            if repaired != json_str:
                logger.info("Attempting to parse repaired JSON...")
                data = self._try_json_loads(repaired)

        # Attempt 3: Truncated JSON - try to close open brackets
        if data is None:
            closed = self._close_truncated_json(json_str)
            if closed != json_str:
                logger.info(
                    "Attempting to parse truncated JSON with closed brackets..."
                )
                data = self._try_json_loads(closed)

        if data is None:
            return None

        # Extract sections from parsed data
        sections_data = self._extract_sections(data)
        if not sections_data:
            return None

        # Convert to blocks
        blocks = []
        for section in sections_data:
            block = self._parse_json_section(section)
            if block:
                blocks.append(block)
        if blocks:
            logger.info(f"Successfully parsed {len(blocks)} blocks from JSON")
            return blocks
        return None

    @staticmethod
    def _try_json_loads(s: str) -> dict | list | None:
        """Try json.loads, return None on failure."""
        try:
            return json.loads(s)
        except (json.JSONDecodeError, ValueError):
            return None

    @staticmethod
    def _extract_sections(data: Any) -> list[dict]:
        """Extract sections list from parsed JSON data."""
        if isinstance(data, dict):
            sections = data.get("sections", [])
            if not sections and "analysis" in data:
                sections = data.get("analysis", {}).get("sections", [])
            return sections
        elif isinstance(data, list):
            return data
        return []

    @staticmethod
    def _repair_json(json_str: str) -> str:
        """
        Attempt to repair common JSON errors from LLM output.

        Fixes:
        - Trailing commas before ] or }
        - Missing commas between objects/properties
        - Unescaped control characters
        """
        s = json_str

        # Remove trailing commas before } or ]
        s = re.sub(r",\s*([}\]])", r"\1", s)

        # Fix missing commas between } and { (common in arrays)
        s = re.sub(r"}\s*\n\s*{", "},\n{", s)

        # Fix missing commas between "value" and "key":
        # e.g., "text": "foo"\n      "text": "bar" -> add comma
        s = re.sub(r'"\s*\n(\s*")', '",\n\\1', s)

        # Fix missing commas between ] and { or "
        s = re.sub(r"]\s*\n(\s*[{\"])", "],\n\\1", s)

        # Fix missing commas between } and "
        s = re.sub(r"}\s*\n(\s*\")", "},\n\\1", s)

        # Remove trailing commas again (the above fixes might introduce them)
        s = re.sub(r",\s*([}\]])", r"\1", s)

        return s

    @staticmethod
    def _close_truncated_json(json_str: str) -> str:
        """
        Try to close a truncated JSON string by balancing brackets.

        LLMs sometimes hit token limits and produce incomplete JSON.
        """
        # Count open/close brackets
        open_braces = json_str.count("{") - json_str.count("}")
        open_brackets = json_str.count("[") - json_str.count("]")

        if open_braces <= 0 and open_brackets <= 0:
            return json_str

        s = json_str.rstrip()

        # Remove trailing incomplete content:
        # 1. Unclosed string literal (odd number of unescaped quotes at end)
        # 2. Partial key-value pair
        # 3. Trailing comma
        # Strategy: find the last complete JSON element and truncate after it
        # A complete element ends with }, ], ", a number, true, false, or null

        # Try progressively trimming from the end to find valid truncation point
        for pattern in [
            r'[,\s]*"[^"]*$',  # trailing partial string
            r'[,\s]*"[^"]*":\s*"[^"]*$',  # partial key: "partial value
            r'[,\s]*"[^"]*":\s*$',  # partial key: (no value)
            r",\s*$",  # trailing comma
        ]:
            s = re.sub(pattern, "", s)

        # Recount after cleanup
        open_braces = s.count("{") - s.count("}")
        open_brackets = s.count("[") - s.count("]")

        # Build closing sequence by scanning bracket order
        # We need to close in the reverse order they were opened
        stack = []
        in_string = False
        escape = False
        for ch in s:
            if escape:
                escape = False
                continue
            if ch == "\\":
                escape = True
                continue
            if ch == '"':
                in_string = not in_string
                continue
            if in_string:
                continue
            if ch in "{[":
                stack.append("}" if ch == "{" else "]")
            elif ch in "}]":
                if stack:
                    stack.pop()

        # Close in reverse order
        s += "".join(reversed(stack))

        return s

    def _parse_json(self, content: str) -> list[AnyBlock]:
        """Parse structured JSON format."""
        # Try to extract JSON from markdown code blocks first
        code_block_match = re.search(r"```(?:json)?\s*\n([\s\S]*?)\n```", content)
        if code_block_match:
            # JSON is in a code block
            json_str = code_block_match.group(1).strip()
            logger.debug("Found JSON in markdown code block")
        else:
            # Try direct JSON extraction
            json_match = re.search(r"\{[\s\S]*\}", content)
            if not json_match:
                raise ValueError("No JSON found in content")
            json_str = json_match.group(0)

        # Try parsing with repair attempts
        blocks = self._try_parse_json_str(json_str)
        if blocks:
            return blocks

        raise ValueError("Failed to parse JSON even after repair attempts")

    def _parse_json_section(self, section: dict[str, Any]) -> ContentBlock | None:
        """Parse a single JSON section into ContentBlock."""

        # Helper function to get content from either "content" or "text" field
        def get_content(key: str = "", default: str = "") -> str:
            return section.get("content") or section.get("text", default)

        block_type = section.get("type")

        if block_type == "heading":
            return HeadingBlock(level=section.get("level", 2), content=get_content())
        elif block_type == "paragraph":
            # Parse paragraph with optional citations
            citations_data = section.get("citations", [])
            citations = [
                Citation(
                    location=cit.get("location", ""),
                    content=cit.get("content", ""),
                )
                for cit in citations_data
            ]
            return ParagraphBlock(content=get_content(), citations=citations)
        elif block_type == "bullet_list":
            # Parse bullet list with optional citations per item
            items_data = section.get("items", [])
            if isinstance(items_data, str):
                items_data = [items_data]

            items = []
            for item_data in items_data:
                if isinstance(item_data, str):
                    # Simple string item without citations
                    items.append(ListItemWithCitation(text=item_data, citations=[]))
                else:
                    # Dict with text and optional citations
                    citations_data = item_data.get("citations", [])
                    citations = [
                        Citation(
                            location=cit.get("location", ""),
                            content=cit.get("content", ""),
                        )
                        for cit in citations_data
                    ]
                    items.append(
                        ListItemWithCitation(
                            text=item_data.get("text", ""), citations=citations
                        )
                    )
            return BulletListBlock(items=items)
        elif block_type == "numbered_list":
            items = section.get("items", [])
            if isinstance(items, str):
                items = [items]
            return NumberedListBlock(items=items)
        elif block_type == "quote":
            return QuoteBlock(content=get_content())
        elif block_type == "code":
            return CodeBlock(
                language=section.get("language"),
                content=get_content(),
            )
        elif block_type == "table":
            return TableBlock(
                headers=section.get("headers", []),
                rows=section.get("rows", []),
            )
        elif block_type == "hr":
            return HorizontalRuleBlock()
        else:
            logger.warning(f"Unknown block type: {block_type}")
            return None

    def _parse_markdown(self, content: str) -> list[AnyBlock]:
        """
        Parse Markdown format as fallback.

        Simple regex-based parser for common Markdown patterns.
        """
        blocks = []

        # Split by common patterns
        lines = content.split("\n")
        i = 0

        while i < len(lines):
            line = lines[i].strip()

            # Skip empty lines
            if not line:
                i += 1
                continue

            # Headings
            heading_match = re.match(r"^(#{1,4})\s+(.+)$", line)
            if heading_match:
                level = len(heading_match.group(1))
                content = heading_match.group(2)
                blocks.append(HeadingBlock(level=level, content=content))
                i += 1
                continue

            # Horizontal rules
            if re.match(r"^[-*_]{3,}\s*$", line):
                blocks.append(HorizontalRuleBlock())
                i += 1
                continue

            # Bullet lists
            if re.match(r"^[\*\-]\s+", line):
                items = []
                while i < len(lines) and re.match(r"^[\*\-]\s+", lines[i].strip()):
                    items.append(re.sub(r"^[\*\-]\s+", "", lines[i].strip()))
                    i += 1
                blocks.append(BulletListBlock(items=items))
                continue

            # Numbered lists
            if re.match(r"^\d+\.\s+", line):
                items = []
                while i < len(lines) and re.match(r"^\d+\.\s+", lines[i].strip()):
                    items.append(re.sub(r"^\d+\.\s+", "", lines[i].strip()))
                    i += 1
                blocks.append(NumberedListBlock(items=items))
                continue

            # Code blocks
            if line.startswith("```"):
                language = line[3:].strip() or None
                i += 1
                code_lines = []
                while i < len(lines) and not lines[i].strip().startswith("```"):
                    code_lines.append(lines[i])
                    i += 1
                i += 1  # skip closing ```
                blocks.append(
                    CodeBlock(language=language, content="\n".join(code_lines))
                )
                continue

            # Blockquotes
            if line.startswith(">"):
                quote_lines = []
                while i < len(lines) and lines[i].strip().startswith(">"):
                    quote_lines.append(re.sub(r"^>\s*", "", lines[i].strip()))
                    i += 1
                blocks.append(QuoteBlock(content="\n".join(quote_lines)))
                continue

            # Default: paragraph
            para_lines = []
            while i < len(lines) and lines[i].strip():
                line = lines[i].strip()
                # Stop if we hit a new block type
                if (
                    line.startswith("#")
                    or line.startswith(">")
                    or line.startswith("```")
                    or re.match(r"^[-*_]{3,}\s*$", line)
                    or re.match(r"^[\*\-]\s+", line)
                    or re.match(r"^\d+\.\s+", line)
                ):
                    break
                para_lines.append(line)
                i += 1
            if para_lines:
                blocks.append(ParagraphBlock(content="\n".join(para_lines)))

        return blocks


# Singleton instance
_parser: StructuredNoteParser | None = None


def get_structured_note_parser() -> StructuredNoteParser:
    """Get singleton parser instance."""
    global _parser
    if _parser is None:
        _parser = StructuredNoteParser()
    return _parser
