"""
Markdown formatter for Zotero MCP responses.
"""

from typing import Any

from zotero_mcp.utils.formatting.helpers import format_creators


class MarkdownFormatter:
    """Formatter for Markdown output."""

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
