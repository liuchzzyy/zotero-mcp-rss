"""
Global scanner service for Phase 3 of Task#1.

Scans entire library for items needing AI analysis,
filters out already-analyzed items, and processes in batch.
"""

import logging
from typing import Any

from zotero_mcp.services.data_access import get_data_service
from zotero_mcp.services.workflow import get_workflow_service
from zotero_mcp.utils.batch_loader import BatchLoader

logger = logging.getLogger(__name__)

# Tag applied to items after successful AI analysis
AI_ANALYSIS_TAG = "AI分析"


class GlobalScanner:
    """Service for scanning library and triggering batch analysis."""

    def __init__(self):
        """Initialize global scanner service."""
        self.data_service = get_data_service()
        self.workflow_service = get_workflow_service()
        self.batch_loader = BatchLoader(self.data_service.item_service)

    async def scan_and_process(
        self,
        limit: int = 20,
        target_collection: str | None = None,
        dry_run: bool = False,
        llm_provider: str = "auto",
        source_collection: str | None = "00_INBOXS",
    ) -> dict[str, Any]:
        """
        Scan library and process items needing analysis.

        Strategy:
        1. First scan items in source_collection (default: 00_INBOXS)
        2. If no candidates in source_collection, scan entire library
        3. Filter to items with PDFs but lacking "AI分析" tag
        4. Process up to `limit` items

        Args:
            limit: Maximum number of items to process
            target_collection: Collection name to move items after analysis
            dry_run: Preview only, no changes
            llm_provider: LLM provider for analysis (auto/claude-cli)
            source_collection: Priority collection to scan first (default: 00_INBOXS)

        Returns:
            Scan results with statistics
        """
        try:
            # 1. Try to get items from source collection first (e.g., 00_INBOXS)
            if source_collection:
                logger.info(f"Scanning collection: {source_collection}")
                # Find collection by name
                collections = await self.data_service.find_collection_by_name(
                    source_collection, exact_match=True
                )

                if collections:
                    # Use the first matching collection
                    collection_key = collections[0]["key"]
                    all_items = await self.data_service.get_collection_items(
                        collection_key, limit=500
                    )
                    logger.info(
                        f"Found {len(all_items)} items in collection '{source_collection}'"
                    )
                else:
                    logger.warning(
                        f"Collection '{source_collection}' not found, scanning entire library"
                    )
                    all_items = await self.data_service.get_all_items(limit=500)
            else:
                all_items = await self.data_service.get_all_items(limit=500)

            if not all_items:
                return {
                    "total_scanned": 0,
                    "candidates": 0,
                    "processed": 0,
                    "skipped": 0,
                    "message": "No items found in library",
                }

            # 2. Batch-fetch children to check for PDFs and AI分析 tag
            candidates = []
            item_keys = [item.key for item in all_items]

            # Fetch bundles in chunks for efficient parallel loading
            chunk_size = 10
            for i in range(0, len(item_keys), chunk_size):
                chunk_keys = item_keys[i : i + chunk_size]
                bundles = await self.batch_loader.fetch_many_bundles(
                    chunk_keys,
                    include_fulltext=False,
                    include_annotations=False,
                    include_bibtex=False,
                )

                bundle_map = {b["metadata"]["key"]: b for b in bundles}

                for item in all_items[i : i + chunk_size]:
                    bundle = bundle_map.get(item.key)
                    if not bundle:
                        continue

                    # Check if item has PDF content available
                    metadata = bundle.get("metadata", {})
                    data = metadata.get("data", {})

                    # Check for AI分析 tag — skip already analyzed
                    tags = data.get("tags", [])
                    has_ai_tag = any(tag.get("tag") == AI_ANALYSIS_TAG for tag in tags)
                    if has_ai_tag:
                        continue

                    # Check if item has PDF attachment via children
                    children = await self.data_service.get_item_children(item.key)
                    has_pdf = any(
                        child.get("data", {}).get("contentType") == "application/pdf"
                        for child in children
                    )
                    if not has_pdf:
                        continue

                    candidates.append(item)

                    if len(candidates) >= limit:
                        break

                if len(candidates) >= limit:
                    break

            if not candidates:
                return {
                    "total_scanned": len(all_items),
                    "candidates": 0,
                    "processed": 0,
                    "skipped": 0,
                    "message": "No items need analysis (all have AI分析 tag or no PDF)",
                }

            logger.info(
                f"Found {len(candidates)} items needing analysis "
                f"out of {len(all_items)} total"
            )

            if dry_run:
                titles = [item.title for item in candidates]
                return {
                    "total_scanned": len(all_items),
                    "candidates": len(candidates),
                    "processed": 0,
                    "skipped": 0,
                    "dry_run": True,
                    "items": titles,
                    "message": f"[DRY RUN] Would process {len(candidates)} items",
                }

            # 3. Use WorkflowService to analyze candidates
            #    We create a temporary collection-like context by passing item keys
            #    directly through batch_analyze with source="recent" and the items
            #    pre-filtered. However, batch_analyze fetches its own items.
            #    Instead, we call _analyze_single_item directly for each candidate.
            from zotero_mcp.clients.llm import get_llm_client

            llm_client = get_llm_client(provider=llm_provider)

            processed_count = 0
            failed_count = 0

            # Fetch full bundles for candidates
            candidate_keys = [item.key for item in candidates]
            full_bundles = await self.batch_loader.fetch_many_bundles(
                candidate_keys,
                include_fulltext=True,
                include_annotations=True,
                include_bibtex=False,
            )
            full_bundle_map = {b["metadata"]["key"]: b for b in full_bundles}

            for item in candidates:
                bundle = full_bundle_map.get(item.key)
                if not bundle:
                    failed_count += 1
                    continue

                result = await self.workflow_service._analyze_single_item(
                    item=item,
                    bundle=bundle,
                    llm_client=llm_client,
                    skip_existing=True,
                    template=None,
                    dry_run=False,
                    delete_old_notes=True,
                    move_to_collection=target_collection,
                )

                if result.success and not result.skipped:
                    processed_count += 1
                elif not result.success:
                    failed_count += 1
                    logger.warning(f"Failed to analyze {item.key}: {result.error}")

            return {
                "total_scanned": len(all_items),
                "candidates": len(candidates),
                "processed": processed_count,
                "failed": failed_count,
                "message": (
                    f"Processed {processed_count}, "
                    f"failed {failed_count} "
                    f"out of {len(candidates)} candidates"
                ),
            }

        except Exception as e:
            logger.error(f"Error during scan: {e}")
            return {
                "total_scanned": 0,
                "candidates": 0,
                "processed": 0,
                "failed": 0,
                "error": str(e),
            }
