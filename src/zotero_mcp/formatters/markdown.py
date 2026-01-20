"""
Markdown formatter for Zotero MCP responses.
"""

from typing import Any

from zotero_mcp.utils.helpers import format_creators, clean_html, truncate_text
from .base import BaseFormatter


class MarkdownFormatter(BaseFormatter):
    """Formatter for Markdown output."""

    def format_items(
        self,
        items: list[dict[str, Any]],
        title: str = "Items",
        show_index: bool = True,
        **kwargs: Any,
    ) -> str:
        """
        Format a list of Zotero items as Markdown.

        Args:
            items: List of Zotero item data
            title: Section title
            show_index: Whether to show item numbers
            **kwargs: Additional options

        Returns:
            Markdown-formatted string
        """
        if not items:
            return f"# {title}\n\nNo items found."

        lines = [f"# {title}", "", f"Found {len(items)} item(s).", ""]

        for i, item in enumerate(items, 1):
            prefix = f"{i}. " if show_index else "- "
            item_text = self._format_item_summary(item)
            lines.append(f"{prefix}{item_text}")

        return "\n".join(lines)

    def format_item(
        self,
        item: dict[str, Any],
        include_abstract: bool = True,
        include_tags: bool = True,
        **kwargs: Any,
    ) -> str:
        """
        Format a single Zotero item with full details.

        Args:
            item: Zotero item data
            include_abstract: Whether to include abstract
            include_tags: Whether to include tags
            **kwargs: Additional options

        Returns:
            Markdown-formatted string
        """
        data = item.get("data", item)
        title = data.get("title", "Untitled")
        item_type = data.get("itemType", "unknown")
        key = data.get("key", item.get("key", "unknown"))

        lines = [
            f"# {title}",
            "",
            f"**Key:** `{key}`",
            f"**Type:** {item_type}",
        ]

        # Authors
        creators = data.get("creators", [])
        if creators:
            lines.append(f"**Authors:** {format_creators(creators)}")

        # Date
        date = data.get("date", "")
        if date:
            lines.append(f"**Date:** {date}")

        # Publication info
        publication = data.get("publicationTitle") or data.get(
            "journalAbbreviation", ""
        )
        if publication:
            lines.append(f"**Publication:** {publication}")

        # DOI/URL
        doi = data.get("DOI", "")
        if doi:
            lines.append(f"**DOI:** [{doi}](https://doi.org/{doi})")

        url = data.get("url", "")
        if url and not doi:
            lines.append(f"**URL:** {url}")

        # Tags
        if include_tags:
            tags = data.get("tags", [])
            if tags:
                tag_names = [t.get("tag", "") for t in tags if t.get("tag")]
                if tag_names:
                    lines.append(f"**Tags:** {', '.join(tag_names)}")

        # Abstract
        if include_abstract:
            abstract = data.get("abstractNote", "")
            if abstract:
                lines.extend(["", "## Abstract", "", clean_html(abstract)])

        return "\n".join(lines)

    def format_error(self, message: str, suggestion: str = "", **kwargs: Any) -> str:
        """
        Format an error message.

        Args:
            message: Error message
            suggestion: Optional suggestion for fixing the error
            **kwargs: Additional options

        Returns:
            Markdown-formatted error string
        """
        lines = [f"❌ **Error:** {message}"]
        if suggestion:
            lines.append(f"\n💡 **Suggestion:** {suggestion}")
        return "\n".join(lines)

    def format_search_results(
        self,
        items: list[dict[str, Any]],
        query: str,
        total: int,
        offset: int = 0,
        limit: int = 20,
        **kwargs: Any,
    ) -> str:
        """
        Format search results.

        Args:
            items: List of matching items
            query: Search query
            total: Total number of matches
            offset: Current offset
            limit: Results per page
            **kwargs: Additional options

        Returns:
            Markdown-formatted search results
        """
        lines = [
            f"# Search Results for '{query}'",
            "",
            f"Showing {len(items)} of {total} results",
        ]

        if offset > 0 or len(items) < total:
            lines.append(f"(offset: {offset}, limit: {limit})")

        lines.append("")

        for i, item in enumerate(items, offset + 1):
            item_text = self._format_item_summary(item)
            lines.append(f"{i}. {item_text}")

        if len(items) < total:
            remaining = total - offset - len(items)
            lines.extend(["", f"*{remaining} more result(s) available*"])

        return "\n".join(lines)

    def format_semantic_results(
        self,
        items: list[dict[str, Any]],
        query: str,
        **kwargs: Any,
    ) -> str:
        """
        Format semantic search results with similarity scores.

        Args:
            items: List of items with similarity scores
            query: Search query
            **kwargs: Additional options

        Returns:
            Markdown-formatted semantic search results
        """
        lines = [
            f"# Semantic Search Results for '{query}'",
            "",
            f"Found {len(items)} conceptually similar item(s).",
            "",
        ]

        for i, item in enumerate(items, 1):
            score = item.get("similarity_score", 0)
            score_pct = f"{score * 100:.1f}%" if isinstance(score, float) else "N/A"

            data = item.get("data", item)
            title = data.get("title", "Untitled")
            key = data.get("key", item.get("key", "unknown"))
            authors = format_creators(data.get("creators", []))

            lines.append(f"## {i}. {title}")
            lines.append(f"**Key:** `{key}` | **Similarity:** {score_pct}")
            lines.append(f"**Authors:** {authors}")

            # Matched text if available
            matched = item.get("matched_text", "")
            if matched:
                lines.extend(["", f"> {truncate_text(matched, 200)}"])

            lines.append("")

        return "\n".join(lines)

    def format_annotations(
        self,
        annotations: list[dict[str, Any]],
        item_title: str = "",
        **kwargs: Any,
    ) -> str:
        """
        Format PDF annotations.

        Args:
            annotations: List of annotation data
            item_title: Title of the parent item
            **kwargs: Additional options

        Returns:
            Markdown-formatted annotations
        """
        title = f"Annotations from '{item_title}'" if item_title else "Annotations"
        if not annotations:
            return f"# {title}\n\nNo annotations found."

        lines = [f"# {title}", "", f"Found {len(annotations)} annotation(s).", ""]

        for ann in annotations:
            ann_type = ann.get("type", ann.get("annotationType", "note"))
            text = ann.get("text", ann.get("annotationText", ""))
            comment = ann.get("comment", ann.get("annotationComment", ""))
            page = ann.get("page", ann.get("annotationPageLabel", ""))

            lines.append(
                f"### {ann_type.title()}" + (f" (Page {page})" if page else "")
            )

            if text:
                lines.append(f"> {text}")
            if comment:
                lines.append(f"\n*Comment:* {comment}")

            lines.append("")

        return "\n".join(lines)

    def format_collections(
        self,
        collections: list[dict[str, Any]],
        **kwargs: Any,
    ) -> str:
        """
        Format collections list.

        Args:
            collections: List of collection data
            **kwargs: Additional options

        Returns:
            Markdown-formatted collections
        """
        if not collections:
            return "# Collections\n\nNo collections found."

        lines = ["# Collections", "", f"Found {len(collections)} collection(s).", ""]

        for coll in collections:
            data = coll.get("data", coll)
            name = data.get("name", "Unnamed")
            key = data.get("key", coll.get("key", "unknown"))
            item_count = data.get("numItems", data.get("numberOfItems", "?"))

            lines.append(f"- **{name}** (`{key}`) - {item_count} items")

        return "\n".join(lines)

    def _format_item_summary(self, item: dict[str, Any]) -> str:
        """Format a single item as a one-line summary."""
        data = item.get("data", item)
        title = data.get("title", "Untitled")
        key = data.get("key", item.get("key", "unknown"))
        creators = data.get("creators", [])
        date = data.get("date", "")

        author_str = format_creators(creators) if creators else ""
        year = date[:4] if date else ""

        parts = [f"**{title}**", f"[`{key}`]"]
        if author_str and author_str != "No authors listed":
            parts.insert(1, f"by {author_str}")
        if year:
            parts.insert(-1, f"({year})")

        return " ".join(parts)
