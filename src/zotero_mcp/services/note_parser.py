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
from zotero_mcp.utils.logging_config import get_logger

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
            try:
                data = json.loads(json_str)
                # Handle different JSON structures
                # Option 1: {"sections": [...]} (direct format)
                # Option 2: {"analysis": {"sections": [...]}} (wrapped format)
                sections_data = data.get("sections", [])
                if not sections_data and "analysis" in data:
                    sections_data = data.get("analysis", {}).get("sections", [])

                # Convert to blocks
                blocks = []
                for section in sections_data:
                    block = self._parse_json_section(section)
                    if block:
                        blocks.append(block)
                if blocks:
                    logger.info(f"Successfully parsed {len(blocks)} blocks from JSON")
                    return blocks
            except (json.JSONDecodeError, KeyError, TypeError) as e:
                logger.warning(f"Failed to parse JSON from code block: {e}")

        # Try direct JSON format
        try:
            return self._parse_json(content)
        except (json.JSONDecodeError, ValueError) as e:
            logger.debug(f"JSON parsing failed: {e}, falling back to Markdown")
            return self._parse_markdown(content)

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

        data = json.loads(json_str)

        # Handle both direct array and wrapped response
        # Option 1: {"sections": [...]}
        # Option 2: {"analysis": {"sections": [...]}}
        if isinstance(data, dict) and "sections" in data:
            sections = data["sections"]
        elif isinstance(data, dict) and "analysis" in data:
            sections = data.get("analysis", {}).get("sections", [])
        elif isinstance(data, list):
            sections = data
        else:
            raise ValueError("Invalid JSON structure")

        # Convert to ContentBlock objects
        blocks = []
        for section in sections:
            block = self._parse_json_section(section)
            if block:
                blocks.append(block)

        return blocks

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
