"""
Global scanner service for Phase 3 of Task#1.

Scans entire library for items needing AI analysis.
"""

import logging
from typing import Any

from zotero_mcp.services.data_access import get_data_service
from zotero_mcp.services.workflow import get_workflow_service

logger = logging.getLogger(__name__)


class GlobalScanner:
    """Service for scanning library and triggering analysis."""

    def __init__(self):
        """Initialize global scanner service."""
        self.data_service = get_data_service()
        self.workflow_service = get_workflow_service()

    async def scan_and_process(
        self, limit: int = 20, collection_override: str | None = None
    ) -> dict[str, Any]:
        """
        Scan library and process items needing analysis.

        Args:
            limit: Maximum number of items to process
            collection_override: Override target collection name

        Returns:
            Scan results with statistics
        """
        try:
            # Get all items
            all_items = await self.data_service.get_all_items()

            if not all_items:
                return {
                    "total": 0,
                    "processed": 0,
                    "skipped": 0,
                    "message": "No items found in library",
                }

            processed_count = 0
            skipped_count = 0

            for item in all_items[:limit]:
                # Check if item has PDF
                children = await self.data_service.get_item_children(item.key)
                has_pdf = any(
                    child.get("data", {}).get("contentType") == "application/pdf"
                    for child in children
                )

                # Check if already analyzed
                notes = await self.data_service.get_notes(item.key)
                is_analyzed = any("AI分析" in str(note) for note in notes)

                if has_pdf and not is_analyzed:
                    # Trigger analysis
                    result = await self.workflow_service.batch_analyze(
                        source="collection",
                        collection_key="",  # Will use inbox collection
                        days=0,
                        limit=1,
                        llm_provider="auto",
                        dry_run=False,
                    )

                    if result.success:
                        processed_count += 1
                    else:
                        skipped_count += 1
                else:
                    skipped_count += 1

            return {
                "total": len(all_items[:limit]),
                "processed": processed_count,
                "skipped": skipped_count,
                "message": f"Processed {processed_count}, skipped {skipped_count}",
            }

        except Exception as e:
            logger.error(f"Error during scan: {e}")
            return {"total": 0, "processed": 0, "skipped": 0, "error": str(e)}
