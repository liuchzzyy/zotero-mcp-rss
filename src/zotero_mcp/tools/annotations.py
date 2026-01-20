"""
Annotation tools for Zotero MCP.

Provides tools for working with annotations and notes:
- zotero_get_annotations: Get PDF annotations
- zotero_get_notes: Get notes
- zotero_search_notes: Search in notes and annotations
- zotero_create_note: Create a new note
"""

from typing import Literal

from fastmcp import FastMCP, Context

from zotero_mcp.models.common import ResponseFormat
from zotero_mcp.services import get_data_service
from zotero_mcp.utils.errors import handle_error


def register_annotation_tools(mcp: FastMCP) -> None:
    """Register all annotation tools with the MCP server."""

    @mcp.tool(
        name="zotero_get_annotations",
        description="Get PDF annotations (highlights, notes, comments) for a Zotero item. "
        "Requires Better BibTeX plugin for best results.",
    )
    async def zotero_get_annotations(
        item_key: str,
        annotation_type: Literal["all", "highlight", "note", "underline"] = "all",
        response_format: Literal["markdown", "json"] = "markdown",
        *,
        ctx: Context,
    ) -> str:
        """
        Get PDF annotations for an item.

        Args:
            item_key: Zotero item key
            annotation_type: Filter by annotation type
            response_format: Output format

        Returns:
            Annotations for the item
        """
        try:
            service = get_data_service()
            annotations = await service.get_annotations(item_key.strip().upper())

            if not annotations:
                return f"No annotations found for item {item_key}."

            # Filter by type if specified
            if annotation_type != "all":
                annotations = [
                    a
                    for a in annotations
                    if a.get("type", a.get("annotationType", "")).lower()
                    == annotation_type
                ]

            formatter = service.get_formatter(ResponseFormat(response_format))

            if hasattr(formatter, "format_annotations"):
                return formatter.format_annotations(annotations, item_key=item_key)

            # Fallback formatting
            if response_format == "json":
                return formatter.format_items(annotations)

            # Markdown format
            lines = [
                f"# Annotations for {item_key}",
                "",
                f"Found {len(annotations)} annotation(s).",
                "",
            ]

            for ann in annotations:
                ann_type = ann.get("type", ann.get("annotationType", "note"))
                text = ann.get("text", ann.get("annotationText", ""))
                comment = ann.get("comment", ann.get("annotationComment", ""))
                page = ann.get("page", ann.get("annotationPageLabel", ""))
                color = ann.get("color", ann.get("annotationColor", ""))

                lines.append(
                    f"### {ann_type.title()}" + (f" (Page {page})" if page else "")
                )

                if color:
                    lines.append(f"*Color: {color}*")

                if text:
                    lines.append(f"> {text}")

                if comment:
                    lines.append(f"\n**Comment:** {comment}")

                lines.append("")

            return "\n".join(lines)

        except Exception as e:
            return handle_error(e, ctx, "get annotations")

    @mcp.tool(
        name="zotero_get_notes", description="Get notes attached to a Zotero item."
    )
    async def zotero_get_notes(
        item_key: str,
        response_format: Literal["markdown", "json"] = "markdown",
        *,
        ctx: Context,
    ) -> str:
        """
        Get notes for an item.

        Args:
            item_key: Zotero item key
            response_format: Output format

        Returns:
            Notes attached to the item
        """
        try:
            service = get_data_service()
            notes = await service.get_notes(item_key.strip().upper())

            if not notes:
                return f"No notes found for item {item_key}."

            formatter = service.get_formatter(ResponseFormat(response_format))

            if response_format == "json":
                return formatter.format_items(notes)

            # Markdown format
            lines = [
                f"# Notes for {item_key}",
                "",
                f"Found {len(notes)} note(s).",
                "",
            ]

            for i, note in enumerate(notes, 1):
                data = note.get("data", {})
                note_key = data.get("key", "")
                note_content = data.get("note", "")

                # Clean HTML from note content for display
                # Basic HTML stripping (notes are stored as HTML)
                import re

                clean_content = re.sub(r"<[^>]+>", "", note_content)
                clean_content = clean_content.replace("&nbsp;", " ").strip()

                lines.extend(
                    [
                        f"## Note {i} (`{note_key}`)",
                        "",
                        clean_content[:2000]
                        + ("..." if len(clean_content) > 2000 else ""),
                        "",
                    ]
                )

            return "\n".join(lines)

        except Exception as e:
            return handle_error(e, ctx, "get notes")

    @mcp.tool(
        name="zotero_search_notes",
        description="Search through notes and annotations in your Zotero library.",
    )
    async def zotero_search_notes(
        query: str,
        limit: int = 20,
        response_format: Literal["markdown", "json"] = "markdown",
        *,
        ctx: Context,
    ) -> str:
        """
        Search in notes and annotations.

        Args:
            query: Search query
            limit: Maximum results
            response_format: Output format

        Returns:
            Matching notes and annotations
        """
        try:
            service = get_data_service()

            # Search for items with matching notes
            # This is a simplified implementation that searches item content
            results = await service.search_items(
                query=query,
                limit=50,  # Get more to filter
                qmode="everything",
            )

            matches = []
            query_lower = query.lower()

            for result in results:
                # Get notes for this item
                try:
                    notes = await service.get_notes(result.key)
                    for note in notes:
                        data = note.get("data", {})
                        note_content = data.get("note", "")

                        if query_lower in note_content.lower():
                            # Extract matching context
                            import re

                            clean = re.sub(r"<[^>]+>", "", note_content)
                            idx = clean.lower().find(query_lower)
                            start = max(0, idx - 100)
                            end = min(len(clean), idx + len(query) + 100)
                            context = clean[start:end]

                            matches.append(
                                {
                                    "type": "note",
                                    "item_key": result.key,
                                    "item_title": result.title,
                                    "note_key": data.get("key", ""),
                                    "context": context,
                                }
                            )

                            if len(matches) >= limit:
                                break
                except Exception:
                    continue

                if len(matches) >= limit:
                    break

            formatter = service.get_formatter(ResponseFormat(response_format))

            if response_format == "json":
                return formatter.format_items(matches)

            if not matches:
                return f"No notes or annotations found matching '{query}'."

            # Markdown format
            lines = [
                f"# Search Results in Notes: '{query}'",
                "",
                f"Found {len(matches)} matching note(s).",
                "",
            ]

            for match in matches:
                lines.extend(
                    [
                        f"## {match['item_title']}",
                        f"*Item: `{match['item_key']}` | Note: `{match['note_key']}`*",
                        "",
                        f"> ...{match['context']}...",
                        "",
                    ]
                )

            return "\n".join(lines)

        except Exception as e:
            return handle_error(e, ctx, "search notes")

    @mcp.tool(
        name="zotero_create_note",
        description="Create a new note attached to a Zotero item. (Beta feature)",
    )
    async def zotero_create_note(
        item_key: str,
        content: str,
        tags: str = "",
        *,
        ctx: Context,
    ) -> str:
        """
        Create a note attached to an item.

        Args:
            item_key: Parent item key
            content: Note content (plain text, will be converted to HTML)
            tags: Comma-separated tags for the note

        Returns:
            Confirmation message with note key
        """
        try:
            service = get_data_service()

            # Convert plain text to basic HTML
            html_content = f"<p>{content}</p>"
            html_content = html_content.replace("\n\n", "</p><p>")
            html_content = html_content.replace("\n", "<br/>")

            # Parse tags
            tag_list = (
                [t.strip() for t in tags.split(",") if t.strip()] if tags else None
            )

            result = await service.create_note(
                parent_key=item_key.strip().upper(),
                content=html_content,
                tags=tag_list,
            )

            if result:
                # Extract note key from result
                if isinstance(result, dict):
                    success = result.get("successful", {})
                    if success:
                        note_data = list(success.values())[0] if success else {}
                        note_key = note_data.get("key", "unknown")
                        return f"✅ Note created successfully!\n\n**Note Key:** `{note_key}`\n**Parent Item:** `{item_key}`"

                return f"✅ Note created for item `{item_key}`."

            return "❌ Failed to create note. Please check the item key and try again."

        except Exception as e:
            return handle_error(e, ctx, "create note")
