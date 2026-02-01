"""
Global scanner service for Phase 3 of Task#1.

Scans library for items needing AI analysis with priority strategy:
1. First scan 00_INBOXS (or specified source collection)
2. If need more items, scan entire library
3. Process items with PDFs but lacking "AI分析" tag
"""

import logging
from typing import Any

from zotero_mcp.services.data_access import get_data_service
from zotero_mcp.services.workflow import get_workflow_service
from zotero_mcp.utils.async_helpers.batch_loader import BatchLoader

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

    async def _check_item_needs_analysis(self, item) -> bool:
        """
        Check if an item needs AI analysis.

        Returns True if:
        - Item has PDF attachment
        - Item lacks "AI分析" tag
        """
        # Check for AI分析 tag
        tags = item.data.get("tags", []) if hasattr(item, "data") else []
        has_ai_tag = any(
            tag.get("tag") == AI_ANALYSIS_TAG
            if isinstance(tag, dict)
            else tag == AI_ANALYSIS_TAG
            for tag in tags
        )
        if has_ai_tag:
            return False

        # Check for PDF attachment
        try:
            children = await self.data_service.get_item_children(item.key)
            has_pdf = any(
                child.get("data", {}).get("contentType") == "application/pdf"
                for child in children
            )
            return has_pdf
        except Exception as e:
            # Handle 400 error: "/children can only be called on PDF, EPUB, and snapshot attachments"
            # If we can't get children, the item likely doesn't have a PDF attachment
            logger.debug(f"  ⊘ Skipping {item.key}: cannot fetch children ({e})")
            return False

    async def scan_and_process(
        self,
        scan_limit: int = 100,
        treated_limit: int = 20,
        target_collection: str | None = "01_SHORTTERMS",
        dry_run: bool = False,
        llm_provider: str = "auto",
        source_collection: str | None = "00_INBOXS",
    ) -> dict[str, Any]:
        """
        Scan library and process items needing analysis.

        Multi-stage strategy:
        1. Scan items in source_collection (default: 00_INBOXS)
        2. If need more items, scan all other collections
        3. Accumulate candidates until reaching treated_limit
        4. Filter to items with PDFs but lacking "AI分析" tag
        5. Process up to `treated_limit` items

        Args:
            scan_limit: Number of items to fetch per batch from API
            treated_limit: Maximum total number of items to process
            target_collection: Collection name to move items after analysis (default: 01_SHORTTERMS)
            dry_run: Preview only, no changes
            llm_provider: LLM provider for analysis (auto/claude-cli)
            source_collection: Priority collection to scan first (default: 00_INBOXS)

        Returns:
            Scan results with statistics
        """
        try:
            candidates = []
            total_scanned = 0
            scanned_keys = set()  # Track already scanned items to avoid duplicates

            # Stage 1: Scan source collection (e.g., 00_INBOXS)
            if source_collection:
                logger.info(f"Stage 1: Scanning collection '{source_collection}'")
                collections = await self.data_service.find_collection_by_name(
                    source_collection, exact_match=True
                )

                if collections:
                    collection_key = collections[0]["key"]
                    coll_name = collections[0].get("data", {}).get("name", "")

                    # Keep fetching batches from this collection until treated_limit or exhausted
                    offset = 0
                    while len(candidates) < treated_limit:
                        items = await self.data_service.get_collection_items(
                            collection_key, limit=scan_limit, start=offset
                        )

                        if not items:
                            break  # No more items in this collection

                        total_scanned += len(items)
                        logger.info(
                            f"Fetched {len(items)} items from '{coll_name}' (offset: {offset})"
                        )

                        # Find candidates in this batch
                        for item in items:
                            scanned_keys.add(item.key)
                            if await self._check_item_needs_analysis(item):
                                candidates.append(item)
                                logger.info(
                                    f"  ✓ Candidate: {item.title[:60]}... (key: {item.key})"
                                )
                                if len(candidates) >= treated_limit:
                                    break

                        # If we got fewer items than scan_limit, we've exhausted the collection
                        if len(items) < scan_limit:
                            logger.info(f"  Collection '{coll_name}' fully scanned")
                            break

                        offset += scan_limit
                else:
                    logger.warning(
                        f"Collection '{source_collection}' not found, skipping to Stage 2"
                    )
            else:
                logger.info("No source collection specified, skipping to Stage 2")

            # Stage 2: If need more candidates, scan other collections in order
            if len(candidates) < treated_limit:
                remaining_needed = treated_limit - len(candidates)
                logger.info(
                    f"Stage 2: Need {remaining_needed} more items, scanning collections in order"
                )

                # Get collections sorted by name (00_INBOXS, 01_*, 02_*, etc.)
                sorted_collections = await self.data_service.get_sorted_collections()

                # Skip source_collection if specified
                source_key = None
                if source_collection and collections:
                    source_key = collections[0]["key"]

                for coll in sorted_collections:
                    # Check if we've reached the limit
                    if len(candidates) >= treated_limit:
                        break

                    coll_key = coll["key"]
                    coll_name = coll.get("data", {}).get("name", "")

                    # Skip source collection (already scanned)
                    if coll_key == source_key:
                        continue

                    logger.info(f"Scanning collection: {coll_name}")

                    # Keep fetching batches from this collection until treated_limit or exhausted
                    offset = 0
                    collection_candidates = 0
                    while len(candidates) < treated_limit:
                        items = await self.data_service.get_collection_items(
                            coll_key, limit=scan_limit, start=offset
                        )

                        if not items:
                            break  # No more items in this collection

                        total_scanned += len(items)

                        # Find candidates in this batch
                        for item in items:
                            # Skip already scanned items
                            if item.key in scanned_keys:
                                continue

                            scanned_keys.add(item.key)
                            if await self._check_item_needs_analysis(item):
                                candidates.append(item)
                                collection_candidates += 1
                                logger.info(
                                    f"  ✓ Candidate: {item.title[:60]}... (key: {item.key})"
                                )
                                if len(candidates) >= treated_limit:
                                    break

                        # If we got fewer items than scan_limit, we've exhausted this collection
                        if len(items) < scan_limit:
                            break

                        offset += scan_limit

                    logger.info(
                        f"  Collection '{coll_name}': {total_scanned} items scanned, "
                        f"{collection_candidates} candidates"
                    )

            logger.info(
                f"Scan complete: found {len(candidates)} candidates out of {total_scanned} total items"
            )

            if not candidates:
                return {
                    "total_scanned": total_scanned,
                    "candidates": 0,
                    "processed": 0,
                    "failed": 0,
                    "message": "No items need analysis (all have AI分析 tag or no PDF)",
                }

            if dry_run:
                titles = [item.title for item in candidates]
                return {
                    "total_scanned": total_scanned,
                    "candidates": len(candidates),
                    "processed": 0,
                    "failed": 0,
                    "dry_run": True,
                    "items": titles,
                    "message": f"[DRY RUN] Would process {len(candidates)} items",
                }

            # Stage 3: Process candidates
            logger.info(f"Starting AI analysis of {len(candidates)} items...")
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

            for i, item in enumerate(candidates, 1):
                logger.info(f"Processing {i}/{len(candidates)}: {item.title[:60]}...")
                bundle = full_bundle_map.get(item.key)
                if not bundle:
                    failed_count += 1
                    logger.warning(f"  ✗ Failed to fetch bundle for {item.key}")
                    continue

                try:
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
                        logger.info(f"  ✓ Successfully analyzed {item.key}")
                    elif result.skipped:
                        logger.info(f"  ⊘ Skipped {item.key} (already analyzed)")
                    else:
                        failed_count += 1
                        logger.warning(
                            f"  ✗ Failed to analyze {item.key}: {result.error}"
                        )
                except Exception as e:
                    failed_count += 1
                    logger.error(f"  ✗ Error analyzing {item.key}: {e}")

            return {
                "total_scanned": total_scanned,
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
