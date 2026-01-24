"""
Batch operation tools for Zotero MCP.
"""

from fastmcp import Context, FastMCP
from mcp.types import ToolAnnotations

from zotero_mcp.models.batch import (
    BatchGetMetadataInput,
    BatchGetMetadataResponse,
    BatchItemResult,
)
from zotero_mcp.models.common import ItemDetailResponse
from zotero_mcp.services import get_data_service
from zotero_mcp.utils.helpers import format_creators


def register_batch_tools(mcp: FastMCP) -> None:
    """Register batch operation tools."""

    @mcp.tool(
        name="zotero_batch_get_metadata",
        annotations=ToolAnnotations(
            title="Batch Get Metadata",
            readOnlyHint=True,
            destructiveHint=False,
            idempotentHint=True,
            openWorldHint=False,
        ),
    )
    async def batch_get_metadata(
        params: BatchGetMetadataInput, ctx: Context
    ) -> BatchGetMetadataResponse:
        """
        Get metadata for multiple items in a single call.

        More efficient than calling get_metadata multiple times.

        Args:
            params: Batch input with list of item keys

        Returns:
            BatchGetMetadataResponse with results for each item

        Example:
            Use when: "Get metadata for items ABC12345, DEF67890, GHI11121"
        """
        service = get_data_service()
        results = []
        successful = 0
        failed = 0

        for item_key in params.item_keys:
            try:
                # Get metadata for single item
                item = await service.get_item(item_key.strip().upper())

                if item:
                    data = item.get("data", {})
                    tags = [
                        t.get("tag", "") for t in data.get("tags", []) if t.get("tag")
                    ]

                    # Convert to ItemDetailResponse
                    item_data = ItemDetailResponse(
                        key=data.get("key", item_key),
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
                        raw_data=item if params.output_format == "json" else None,
                    )

                    results.append(
                        BatchItemResult(
                            item_key=item_key,
                            success=True,
                            data=item_data,
                        )
                    )
                    successful += 1
                else:
                    results.append(
                        BatchItemResult(
                            item_key=item_key,
                            success=False,
                            error="Item not found",
                        )
                    )
                    failed += 1

            except Exception as e:
                results.append(
                    BatchItemResult(
                        item_key=item_key,
                        success=False,
                        error=str(e),
                    )
                )
                failed += 1

        return BatchGetMetadataResponse(
            total_requested=len(params.item_keys),
            successful=successful,
            failed=failed,
            results=results,
        )
