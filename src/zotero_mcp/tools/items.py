"""
Item tools for Zotero MCP.

Provides tools for accessing item data:
- zotero_get_metadata: Get detailed metadata (with optional BibTeX)
- zotero_get_fulltext: Get full-text content
- zotero_get_children: Get attachments and notes
- zotero_get_collections: List collections and items
- zotero_get_bundle: Get comprehensive item data bundle
"""

from typing import Literal

from fastmcp import FastMCP, Context

from zotero_mcp.models.common import ResponseFormat, OutputFormat
from zotero_mcp.services import get_data_service
from zotero_mcp.formatters import MarkdownFormatter, BibTeXFormatter
from zotero_mcp.utils.errors import handle_error
from zotero_mcp.utils.helpers import format_creators


def register_item_tools(mcp: FastMCP) -> None:
    """Register all item tools with the MCP server."""

    @mcp.tool(
        name="zotero_get_metadata",
        description="Get detailed metadata for a Zotero item. "
        "Supports markdown, JSON, or BibTeX output formats.",
    )
    async def zotero_get_metadata(
        item_key: str,
        output_format: Literal["markdown", "json", "bibtex"] = "markdown",
        include_abstract: bool = True,
        *,
        ctx: Context,
    ) -> str:
        """
        Get detailed metadata for an item.

        Args:
            item_key: Zotero item key (e.g., 'ABC12345')
            output_format: Output format ('markdown', 'json', or 'bibtex')
            include_abstract: Include abstract in output

        Returns:
            Item metadata in requested format
        """
        try:
            service = get_data_service()
            item = await service.get_item(item_key.strip().upper())

            if output_format == "bibtex":
                bibtex = await service.get_bibtex(item_key)
                return (
                    bibtex
                    if bibtex
                    else "Error: Could not generate BibTeX for this item."
                )

            if output_format == "json":
                formatter = service.get_formatter(ResponseFormat.JSON)
            else:
                formatter = service.get_formatter(ResponseFormat.MARKDOWN)

            return formatter.format_item(
                item,
                include_abstract=include_abstract,
            )

        except Exception as e:
            return handle_error(e, ctx, "get metadata")

    @mcp.tool(
        name="zotero_get_fulltext",
        description="Get the full-text content of a Zotero item (from PDF or HTML attachment).",
    )
    async def zotero_get_fulltext(
        item_key: str,
        max_length: int = 10000,
        *,
        ctx: Context,
    ) -> str:
        """
        Get full-text content for an item.

        Args:
            item_key: Zotero item key
            max_length: Maximum characters to return

        Returns:
            Full-text content if available
        """
        try:
            service = get_data_service()
            fulltext = await service.get_fulltext(item_key.strip().upper())

            if not fulltext:
                return (
                    f"No full-text content available for item {item_key}. "
                    "This may be because the item has no attachment, "
                    "or the content hasn't been indexed by Zotero."
                )

            # Truncate if needed
            if len(fulltext) > max_length:
                fulltext = (
                    fulltext[:max_length]
                    + f"\n\n[Truncated at {max_length} characters]"
                )

            return f"# Full Text for {item_key}\n\n{fulltext}"

        except Exception as e:
            return handle_error(e, ctx, "get fulltext")

    @mcp.tool(
        name="zotero_get_children",
        description="Get child items (attachments and notes) for a Zotero item.",
    )
    async def zotero_get_children(
        item_key: str,
        item_type: Literal["all", "attachment", "note"] = "all",
        response_format: Literal["markdown", "json"] = "markdown",
        *,
        ctx: Context,
    ) -> str:
        """
        Get child items for an item.

        Args:
            item_key: Parent item key
            item_type: Filter by type ('all', 'attachment', or 'note')
            response_format: Output format

        Returns:
            Child items
        """
        try:
            service = get_data_service()

            type_filter = None if item_type == "all" else item_type
            children = await service.get_item_children(
                item_key.strip().upper(),
                item_type=type_filter,
            )

            formatter = service.get_formatter(ResponseFormat(response_format))

            if not children:
                return f"No child items found for {item_key}."

            # Format children
            if response_format == "json":
                return formatter.format_items(children)

            # Markdown format
            lines = [
                f"# Children of {item_key}",
                "",
                f"Found {len(children)} child item(s).",
                "",
            ]

            for child in children:
                data = child.get("data", {})
                child_type = data.get("itemType", "unknown")
                child_key = data.get("key", "")
                title = data.get("title", "Untitled")

                if child_type == "attachment":
                    filename = data.get("filename", "")
                    content_type = data.get("contentType", "")
                    lines.append(f"- **Attachment** `{child_key}`: {title}")
                    if filename:
                        lines.append(f"  - File: {filename} ({content_type})")
                elif child_type == "note":
                    note_text = data.get("note", "")[:200]
                    lines.append(f"- **Note** `{child_key}`: {title}")
                    if note_text:
                        lines.append(f"  > {note_text}...")
                else:
                    lines.append(f"- **{child_type}** `{child_key}`: {title}")

                lines.append("")

            return "\n".join(lines)

        except Exception as e:
            return handle_error(e, ctx, "get children")

    @mcp.tool(
        name="zotero_get_collections",
        description="List all collections in your Zotero library, or get items in a specific collection.",
    )
    async def zotero_get_collections(
        collection_key: str = "",
        limit: int = 50,
        response_format: Literal["markdown", "json"] = "markdown",
        *,
        ctx: Context,
    ) -> str:
        """
        List collections or get items in a collection.

        Args:
            collection_key: If provided, get items in this collection. Otherwise list all collections.
            limit: Maximum items when retrieving collection contents
            response_format: Output format

        Returns:
            Collections list or collection items
        """
        try:
            service = get_data_service()
            formatter = service.get_formatter(ResponseFormat(response_format))

            if collection_key:
                # Get items in collection
                results = await service.get_collection_items(
                    collection_key.strip().upper(),
                    limit=limit,
                )

                items_data = [
                    {
                        "key": r.key,
                        "title": r.title,
                        "authors": r.authors,
                        "date": r.date,
                        "item_type": r.item_type,
                    }
                    for r in results
                ]

                return formatter.format_search_results(
                    items=items_data,
                    query=f"collection:{collection_key}",
                    total=len(results),
                )

            # List all collections
            collections = await service.get_collections()

            if hasattr(formatter, "format_collections"):
                return formatter.format_collections(collections)

            # Fallback for JSON formatter
            if response_format == "json":
                return formatter.format_items(collections)

            # Markdown format
            if not collections:
                return "# Collections\n\nNo collections found in your library."

            lines = [
                "# Collections",
                "",
                f"Found {len(collections)} collection(s).",
                "",
            ]

            for coll in collections:
                data = coll.get("data", {})
                name = data.get("name", "Unnamed")
                key = data.get("key", "")
                num_items = data.get("numItems", "?")

                lines.append(f"- **{name}** (`{key}`) - {num_items} items")

            lines.append("")
            lines.append(
                "*Use `collection_key` parameter to get items in a specific collection.*"
            )

            return "\n".join(lines)

        except Exception as e:
            return handle_error(e, ctx, "get collections")

    @mcp.tool(
        name="zotero_get_bundle",
        description="Get comprehensive bundle of item data including metadata, attachments, notes, "
        "annotations, and optionally full text and BibTeX.",
    )
    async def zotero_get_bundle(
        item_key: str,
        include_fulltext: bool = False,
        include_annotations: bool = True,
        include_notes: bool = True,
        include_bibtex: bool = False,
        response_format: Literal["markdown", "json"] = "markdown",
        *,
        ctx: Context,
    ) -> str:
        """
        Get comprehensive bundle of item data.

        Args:
            item_key: Zotero item key
            include_fulltext: Include full-text content
            include_annotations: Include PDF annotations
            include_notes: Include notes
            include_bibtex: Include BibTeX citation
            response_format: Output format

        Returns:
            Comprehensive item bundle
        """
        try:
            service = get_data_service()
            bundle = await service.get_item_bundle(
                item_key.strip().upper(),
                include_fulltext=include_fulltext,
                include_annotations=include_annotations,
                include_notes=include_notes,
                include_bibtex=include_bibtex,
            )

            formatter = service.get_formatter(ResponseFormat(response_format))

            if response_format == "json":
                return formatter.format_item(bundle)

            # Build markdown output
            lines = []

            # Metadata section
            metadata = bundle.get("metadata", {})
            data = metadata.get("data", {})
            title = data.get("title", "Untitled")

            lines.extend(
                [
                    f"# {title}",
                    "",
                    f"**Key:** `{item_key}`",
                    f"**Type:** {data.get('itemType', 'unknown')}",
                ]
            )

            if creators := data.get("creators", []):
                lines.append(f"**Authors:** {format_creators(creators)}")

            if date := data.get("date"):
                lines.append(f"**Date:** {date}")

            if doi := data.get("DOI"):
                lines.append(f"**DOI:** [{doi}](https://doi.org/{doi})")

            # Tags
            if tags := data.get("tags", []):
                tag_names = [t.get("tag", "") for t in tags if t.get("tag")]
                if tag_names:
                    lines.append(f"**Tags:** {', '.join(tag_names)}")

            # Abstract
            if abstract := data.get("abstractNote"):
                lines.extend(["", "## Abstract", "", abstract])

            # Attachments
            attachments = bundle.get("attachments", [])
            if attachments:
                lines.extend(["", "## Attachments", ""])
                for att in attachments:
                    att_data = att.get("data", {})
                    lines.append(
                        f"- {att_data.get('title', 'Untitled')} ({att_data.get('contentType', 'unknown')})"
                    )

            # Notes
            if include_notes:
                notes = bundle.get("notes", [])
                if notes:
                    lines.extend(["", "## Notes", ""])
                    for note in notes:
                        note_data = note.get("data", {})
                        note_text = note_data.get("note", "")[:500]
                        lines.append(f"> {note_text}...")
                        lines.append("")

            # Annotations
            if include_annotations:
                annotations = bundle.get("annotations", [])
                if annotations:
                    lines.extend(["", "## Annotations", ""])
                    for ann in annotations[:10]:  # Limit to first 10
                        ann_type = ann.get("type", "note")
                        text = ann.get("text", ann.get("annotationText", ""))
                        page = ann.get("page", ann.get("annotationPageLabel", ""))
                        if text:
                            lines.append(f'- [{ann_type}] p.{page}: "{text[:200]}"')
                    if len(annotations) > 10:
                        lines.append(
                            f"  *... and {len(annotations) - 10} more annotations*"
                        )

            # Full text
            if include_fulltext:
                fulltext = bundle.get("fulltext")
                if fulltext:
                    lines.extend(
                        ["", "## Full Text (excerpt)", "", fulltext[:2000] + "..."]
                    )

            # BibTeX
            if include_bibtex:
                bibtex = bundle.get("bibtex")
                if bibtex:
                    lines.extend(["", "## BibTeX", "", "```bibtex", bibtex, "```"])

            return "\n".join(lines)

        except Exception as e:
            return handle_error(e, ctx, "get bundle")
