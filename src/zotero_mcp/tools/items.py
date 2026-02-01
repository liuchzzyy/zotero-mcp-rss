"""
Item tools for Zotero MCP.

Provides tools for accessing item data:
- zotero_get_metadata: Get detailed metadata (with optional BibTeX)
- zotero_get_fulltext: Get full-text content
- zotero_get_children: Get attachments and notes
- zotero_get_collections: List collections and items
- zotero_get_bundle: Get comprehensive item data bundle
"""

from fastmcp import Context, FastMCP
from mcp.types import ToolAnnotations

from zotero_mcp.models.common import (
    AnnotationItem,
    BundleResponse,
    CollectionItem,
    CollectionsResponse,
    FulltextResponse,
    ItemDetailResponse,
    SearchResponse,
    SearchResultItem,
)
from zotero_mcp.models.zotero import (
    GetBundleInput,
    GetChildrenInput,
    GetCollectionsInput,
    GetFulltextInput,
    GetMetadataInput,
)
from zotero_mcp.services import get_data_service
from zotero_mcp.utils.helpers import format_creators


def register_item_tools(mcp: FastMCP) -> None:
    """Register all item tools with the MCP server."""

    @mcp.tool(
        name="zotero_get_metadata",
        annotations=ToolAnnotations(
            title="Get Item Metadata",
            readOnlyHint=True,
            destructiveHint=False,
            idempotentHint=True,
            openWorldHint=False,
        ),
    )
    async def zotero_get_metadata(
        params: GetMetadataInput, ctx: Context
    ) -> ItemDetailResponse:
        """
        Get detailed metadata for a Zotero item.

        Retrieves comprehensive bibliographic information including title, authors,
        publication details, DOI, abstract, and tags. Supports BibTeX export.

        Args:
            params: Input parameters containing:
                - item_key (str): Zotero item key (8-character alphanumeric)
                - include_abstract (bool): Whether to include abstract (default: True)
                - format: Export format - 'markdown', 'bibtex', or 'json'
                - response_format: Legacy parameter (structured output returned)

        Returns:
            ItemDetailResponse: Structured item metadata.

            For BibTeX format, returns special response with raw_data containing bibtex.

        Example:
            Use when: "Get details for item ABC12345"
            Use when: "Show me metadata for this paper"
            Use when: "Export item as BibTeX"
        """
        try:
            service = get_data_service()
            item = await service.get_item(params.item_key.strip().upper())

            # Special handling for BibTeX format
            if params.output_format.value == "bibtex":
                bibtex = await service.get_bibtex(params.item_key)
                if not bibtex:
                    return ItemDetailResponse(
                        success=False,
                        error="Could not generate BibTeX for this item",
                        key=params.item_key,
                        title="Error",
                        item_type="unknown",
                    )
                # Return as special response
                return ItemDetailResponse(
                    key=params.item_key,
                    title="BibTeX Citation",
                    item_type="citation",
                    raw_data={"bibtex": bibtex},
                )

            # Extract metadata
            data = item.get("data", {})
            tags = [t.get("tag", "") for t in data.get("tags", []) if t.get("tag")]

            return ItemDetailResponse(
                key=data.get("key", params.item_key),
                title=data.get("title", "Untitled"),
                item_type=data.get("itemType", "unknown"),
                authors=format_creators(data.get("creators", [])),
                date=data.get("date"),
                publication=data.get("publicationTitle")
                or data.get("journalAbbreviation"),
                doi=data.get("DOI"),
                url=data.get("url"),
                abstract=data.get("abstractNote") if params.include_abstract else None,
                tags=tags,
                raw_data=item if params.output_format.value == "json" else None,
            )

        except Exception as e:
            await ctx.error(f"Failed to get metadata: {str(e)}")
            return ItemDetailResponse(
                success=False,
                error=f"Metadata retrieval error: {str(e)}",
                key=params.item_key,
                title="Error",
                item_type="unknown",
            )

    @mcp.tool(
        name="zotero_get_fulltext",
        annotations=ToolAnnotations(
            title="Get Full Text",
            readOnlyHint=True,
            destructiveHint=False,
            idempotentHint=True,
            openWorldHint=False,
        ),
    )
    async def zotero_get_fulltext(
        params: GetFulltextInput, ctx: Context
    ) -> FulltextResponse:
        """
        Get full-text content of a Zotero item from PDF or HTML attachment.

        Args:
            params: Input containing:
                - item_key (str): Zotero item key
                - max_length (int): Maximum characters to return (100-100000)

        Returns:
            FulltextResponse: Full-text content with metadata.

        Example:
            Use when: "Get the full text of this paper"
            Use when: "Extract content from PDF"
        """
        try:
            service = get_data_service()
            fulltext = await service.get_fulltext(params.item_key.strip().upper())

            if not fulltext:
                return FulltextResponse(
                    success=False,
                    error=(
                        f"No full-text content available for item {params.item_key}. "
                        "This may be because the item has no attachment, "
                        "or the content hasn't been indexed by Zotero."
                    ),
                    item_key=params.item_key,
                    fulltext=None,
                    length=0,
                    truncated=False,
                )

            # Truncate if needed
            truncated = (
                params.max_length is not None and len(fulltext) > params.max_length
            )
            if truncated and params.max_length is not None:
                fulltext = fulltext[: params.max_length]

            return FulltextResponse(
                item_key=params.item_key,
                fulltext=fulltext,
                length=len(fulltext),
                truncated=truncated,
            )

        except Exception as e:
            await ctx.error(f"Failed to get fulltext: {str(e)}")
            return FulltextResponse(
                success=False,
                error=f"Fulltext retrieval error: {str(e)}",
                item_key=params.item_key,
                fulltext=None,
                length=0,
                truncated=False,
            )

    @mcp.tool(
        name="zotero_get_children",
        annotations=ToolAnnotations(
            title="Get Child Items",
            readOnlyHint=True,
            destructiveHint=False,
            idempotentHint=True,
            openWorldHint=False,
        ),
    )
    async def zotero_get_children(params: GetChildrenInput, ctx: Context) -> dict:
        """
        Get child items (attachments and notes) for a Zotero item.

        Args:
            params: Input containing:
                - item_key (str): Parent item key
                - item_type: Filter by type ('all', 'attachment', or 'note')
                - response_format: Output format

        Returns:
            dict: Child items with metadata.

        Example:
            Use when: "Show attachments for this item"
            Use when: "Get notes for item ABC12345"
        """
        try:
            service = get_data_service()

            type_filter = None if params.child_type == "all" else params.child_type
            children = await service.get_item_children(
                params.item_key.strip().upper(),
                item_type=type_filter,
            )

            if not children:
                return {
                    "success": True,
                    "item_key": params.item_key,
                    "count": 0,
                    "children": [],
                    "message": f"No child items found for {params.item_key}.",
                }

            return {
                "success": True,
                "item_key": params.item_key,
                "count": len(children),
                "children": children,
            }

        except Exception as e:
            await ctx.error(f"Failed to get children: {str(e)}")
            return {
                "success": False,
                "error": f"Get children error: {str(e)}",
                "item_key": params.item_key,
                "count": 0,
                "children": [],
            }

    @mcp.tool(
        name="zotero_get_collections",
        annotations=ToolAnnotations(
            title="Get Collections",
            readOnlyHint=True,
            destructiveHint=False,
            idempotentHint=True,
            openWorldHint=False,
        ),
    )
    async def zotero_get_collections(
        params: GetCollectionsInput, ctx: Context
    ) -> CollectionsResponse | SearchResponse:
        """
        List all collections in your Zotero library, or get items in a specific collection.

        Args:
            params: Input containing:
                - collection_key (str): If provided, get items in this collection
                - limit: Maximum items when retrieving collection contents
                - response_format: Output format

        Returns:
            CollectionsResponse if listing collections, SearchResponse if getting items.

        Example:
            Use when: "List my collections"
            Use when: "Show items in collection XYZ"
        """
        try:
            service = get_data_service()

            if params.collection_key:
                # Get items in collection
                results = await service.get_collection_items(
                    params.collection_key.strip().upper(),
                    limit=params.limit,
                )

                items = [
                    SearchResultItem(
                        key=r.key,
                        title=r.title,
                        authors=r.authors,
                        date=r.date,
                        item_type=r.item_type,
                    )
                    for r in results
                ]

                return SearchResponse(
                    query=f"collection:{params.collection_key}",
                    total=len(results),
                    count=len(items),
                    offset=0,
                    limit=params.limit,
                    has_more=False,
                    items=items,
                )

            # List all collections
            collections = await service.get_collections()

            collection_items = []
            for coll in collections:
                data = coll.get("data", {})
                parent_coll = data.get("parentCollection")

                # Handle Zotero API quirk where parentCollection is False for root items
                if parent_coll is False:
                    parent_coll = None

                collection_items.append(
                    CollectionItem(
                        key=data.get("key", coll.get("key", "")),
                        name=data.get("name", "Unnamed"),
                        item_count=data.get("numItems"),
                        parent_key=parent_coll,
                    )
                )

            return CollectionsResponse(
                count=len(collection_items),
                collections=collection_items,
            )

        except Exception as e:
            await ctx.error(f"Failed to get collections: {str(e)}")
            if params.collection_key:
                return SearchResponse(
                    success=False,
                    error=f"Get collection items error: {str(e)}",
                    query=f"collection:{params.collection_key}",
                    total=0,
                    count=0,
                    offset=0,
                    limit=params.limit,
                    has_more=False,
                    items=[],
                )
            else:
                return CollectionsResponse(
                    success=False,
                    error=f"Get collections error: {str(e)}",
                    count=0,
                    collections=[],
                )

    @mcp.tool(
        name="zotero_get_bundle",
        annotations=ToolAnnotations(
            title="Get Comprehensive Item Bundle",
            readOnlyHint=True,
            destructiveHint=False,
            idempotentHint=True,
            openWorldHint=False,
        ),
    )
    async def zotero_get_bundle(params: GetBundleInput, ctx: Context) -> BundleResponse:
        """
        Get comprehensive bundle of item data including metadata, attachments, notes,
        annotations, and optionally full text and BibTeX.

        Args:
            params: Input containing:
                - item_key (str): Zotero item key
                - include_fulltext (bool): Include full-text content
                - include_annotations (bool): Include PDF annotations
                - include_notes (bool): Include notes
                - include_bibtex (bool): Include BibTeX citation

        Returns:
            BundleResponse: Comprehensive item bundle.

        Example:
            Use when: "Get everything for this item"
            Use when: "Full details with annotations and notes"
        """
        try:
            service = get_data_service()
            bundle = await service.get_item_bundle(
                params.item_key.strip().upper(),
                include_fulltext=params.include_fulltext,
                include_annotations=params.include_annotations,
                include_notes=params.include_notes,
                include_bibtex=params.include_bibtex,
            )

            # Extract metadata
            metadata_raw = bundle.get("metadata", {})
            data = metadata_raw.get("data", {})
            tags = [t.get("tag", "") for t in data.get("tags", []) if t.get("tag")]

            metadata = ItemDetailResponse(
                key=data.get("key", params.item_key),
                title=data.get("title", "Untitled"),
                item_type=data.get("itemType", "unknown"),
                authors=format_creators(data.get("creators", [])),
                date=data.get("date"),
                publication=data.get("publicationTitle")
                or data.get("journalAbbreviation"),
                doi=data.get("DOI"),
                url=data.get("url"),
                abstract=data.get("abstractNote"),
                tags=tags,
            )

            # Process annotations
            annotations_raw = bundle.get("annotations", [])
            annotations = [
                AnnotationItem(
                    type=ann.get("type", ann.get("annotationType", "note")),
                    text=ann.get("text", ann.get("annotationText")),
                    comment=ann.get("comment", ann.get("annotationComment")),
                    page=ann.get("page", ann.get("annotationPageLabel")),
                    color=ann.get("color", ann.get("annotationColor")),
                )
                for ann in annotations_raw
            ]

            return BundleResponse(
                metadata=metadata,
                attachments=bundle.get("attachments", []),
                notes=bundle.get("notes", []),
                annotations=annotations,
                fulltext=bundle.get("fulltext"),
                bibtex=bundle.get("bibtex"),
            )

        except Exception as e:
            await ctx.error(f"Failed to get bundle: {str(e)}")
            return BundleResponse(
                success=False,
                error=f"Bundle retrieval error: {str(e)}",
                metadata=ItemDetailResponse(
                    key=params.item_key,
                    title="Error",
                    item_type="unknown",
                ),
                attachments=[],
                notes=[],
                annotations=[],
            )
