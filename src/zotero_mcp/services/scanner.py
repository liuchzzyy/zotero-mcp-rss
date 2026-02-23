"""
Global scanner service for Phase 3 of Task#1.

Scans library for items needing AI analysis with priority strategy:
1. First scan 00_INBOXS (or specified source collection)
2. If need more items, scan entire library
3. Process items with PDFs but lacking "AI分析" tag
"""

import logging
from typing import Any

from pydantic import ValidationError

from zotero_mcp.models.operations import ScannerRunParams
from zotero_mcp.services.common.operation_result import (
    operation_error,
    operation_success,
)
from zotero_mcp.services.common.pagination import iter_offset_batches
from zotero_mcp.services.data_access import get_data_service
from zotero_mcp.services.workflow import get_workflow_service
from zotero_mcp.utils.async_helpers.batch_loader import BatchLoader

logger = logging.getLogger(__name__)

# Tag applied to items after successful AI analysis
AI_ANALYSIS_TAG = "AI分析"
NON_ANALYZABLE_ITEM_TYPES = {"attachment", "note", "annotation"}


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
        # Skip child/non-library items early to avoid invalid children requests.
        item_type = ""
        if hasattr(item, "data") and isinstance(item.data, dict):
            item_type = str(item.data.get("itemType") or "").strip().lower()
        if item_type in NON_ANALYZABLE_ITEM_TYPES:
            return False

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
            # "/children" on non-attachment items may fail with 400.
            # If so, treat as no PDF attachment.
            logger.debug(f"  ⊘ Skipping {item.key}: cannot fetch children ({e})")
            return False

    async def scan_and_process(
        self,
        scan_limit: int = 100,
        treated_limit: int = 20,
        target_collection: str = "",
        dry_run: bool = False,
        llm_provider: str = "auto",
        source_collection: str | None = "00_INBOXS",
        include_multimodal: bool = True,
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
            target_collection: Collection name to move items after analysis
            dry_run: Preview only, no changes
            llm_provider: LLM provider for analysis (auto/claude-cli)
            source_collection: Priority collection to scan first (default: 00_INBOXS)

        Returns:
            Scan results with statistics
        """
        try:
            params = ScannerRunParams(
                scan_limit=scan_limit,
                treated_limit=treated_limit,
                target_collection=target_collection,
                dry_run=dry_run,
                llm_provider=llm_provider,
                source_collection=source_collection,
                include_multimodal=include_multimodal,
            )
            if not params.target_collection:
                metrics = {
                    "scanned": 0,
                    "candidates": 0,
                    "processed": 0,
                    "updated": 0,
                    "skipped": 0,
                    "failed": 0,
                    "removed": 0,
                }
                return operation_error(
                    "global_scan",
                    "target_collection is required",
                    metrics=metrics,
                    status="validation_error",
                    extra={
                        "total_scanned": 0,
                        "candidates": 0,
                        "processed": 0,
                        "failed": 0,
                    },
                )

            candidates = []
            total_scanned = 0
            scanned_keys = set()  # Track already scanned items to avoid duplicates
            collections: list[dict[str, Any]] = []

            # Stage 1: Scan source collection (e.g., 00_INBOXS)
            if params.source_collection:
                logger.info(
                    f"Stage 1: Scanning collection '{params.source_collection}'"
                )
                collections = await self.data_service.find_collection_by_name(
                    params.source_collection, exact_match=True
                )

                if collections:
                    collection_key = collections[0]["key"]
                    coll_name = collections[0].get("data", {}).get("name", "")

                    # Fetch from source collection until exhausted or reaching cap.
                    async for offset, items in iter_offset_batches(
                        lambda start, limit: self.data_service.get_collection_items(
                            collection_key, limit=limit, start=start
                        ),
                        batch_size=params.scan_limit,
                    ):
                        if len(candidates) >= params.treated_limit:
                            break
                        total_scanned += len(items)
                        logger.info(
                            "Fetched "
                            f"{len(items)} items from '{coll_name}' (offset: {offset})"
                        )

                        # Find candidates in this batch
                        for item in items:
                            scanned_keys.add(item.key)
                            if await self._check_item_needs_analysis(item):
                                candidates.append(item)
                                logger.info(
                                    "  ✓ Candidate: "
                                    f"{item.title[:60]}... (key: {item.key})"
                                )
                                if len(candidates) >= params.treated_limit:
                                    break
                    if len(candidates) < params.treated_limit:
                        logger.info(f"  Collection '{coll_name}' fully scanned")
                else:
                    logger.warning(
                        f"Collection '{params.source_collection}' not found, "
                        "skipping to Stage 2"
                    )
            else:
                logger.info("No source collection specified, skipping to Stage 2")

            # Stage 2: If need more candidates, scan other collections in order
            if len(candidates) < params.treated_limit:
                remaining_needed = params.treated_limit - len(candidates)
                logger.info(
                    "Stage 2: Need "
                    f"{remaining_needed} more items, scanning collections in order"
                )

                # Get collections sorted by name (00_INBOXS, 01_*, 02_*, etc.)
                sorted_collections = await self.data_service.get_sorted_collections()

                # Skip source_collection if specified
                source_key = None
                if params.source_collection and collections:
                    source_key = collections[0]["key"]

                for coll in sorted_collections:
                    # Check if we've reached the limit
                    if len(candidates) >= params.treated_limit:
                        break

                    coll_key = coll["key"]
                    coll_name = coll.get("data", {}).get("name", "")

                    # Skip source collection (already scanned)
                    if coll_key == source_key:
                        continue

                    logger.info(f"Scanning collection: {coll_name}")

                    # Fetch this collection until exhausted or reaching cap.
                    collection_candidates = 0
                    collection_scanned = 0

                    async def _fetch_collection_page(
                        start: int,
                        limit: int,
                        collection_key: str = coll_key,
                    ):
                        return await self.data_service.get_collection_items(
                            collection_key, limit=limit, start=start
                        )

                    async for _, items in iter_offset_batches(
                        _fetch_collection_page,
                        batch_size=params.scan_limit,
                    ):
                        if len(candidates) >= params.treated_limit:
                            break
                        collection_scanned += len(items)
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
                                    "  ✓ Candidate: "
                                    f"{item.title[:60]}... (key: {item.key})"
                                )
                                if len(candidates) >= params.treated_limit:
                                    break

                    logger.info(
                        f"  Collection '{coll_name}': "
                        f"{collection_scanned} items scanned, "
                        f"{collection_candidates} candidates"
                    )

            logger.info(
                "Scan complete: found "
                f"{len(candidates)} candidates out of {total_scanned} total items"
            )

            if not candidates:
                metrics = {
                    "scanned": total_scanned,
                    "candidates": 0,
                    "processed": 0,
                    "updated": 0,
                    "skipped": 0,
                    "failed": 0,
                    "removed": 0,
                }
                return operation_success(
                    "global_scan",
                    metrics,
                    message="No items need analysis (all have AI分析 tag or no PDF)",
                    extra={
                        "total_scanned": total_scanned,
                        "candidates": 0,
                        "processed": 0,
                        "failed": 0,
                    },
                )

            if params.dry_run:
                titles = [item.title for item in candidates]
                metrics = {
                    "scanned": total_scanned,
                    "candidates": len(candidates),
                    "processed": 0,
                    "updated": 0,
                    "skipped": 0,
                    "failed": 0,
                    "removed": 0,
                }
                return operation_success(
                    "global_scan",
                    metrics,
                    message=f"[DRY RUN] Would process {len(candidates)} items",
                    dry_run=True,
                    extra={
                        "total_scanned": total_scanned,
                        "candidates": len(candidates),
                        "processed": 0,
                        "failed": 0,
                        "dry_run": True,
                        "items": titles,
                    },
                )

            # Stage 3: Process candidates
            logger.info(f"Starting AI analysis of {len(candidates)} items...")
            from zotero_mcp.clients.llm import get_llm_client
            from zotero_mcp.clients.llm.capabilities import get_provider_capability

            llm_client = get_llm_client(provider=params.llm_provider)
            provider_name = getattr(llm_client, "provider", None)
            provider_name = provider_name if isinstance(provider_name, str) else None

            # For text-only providers (e.g. deepseek), skip expensive multi-modal
            # extraction initially and only backfill it for items lacking fulltext.
            can_handle_images = True
            if provider_name:
                try:
                    can_handle_images = get_provider_capability(
                        provider_name
                    ).can_handle_images()
                except ValueError:
                    # Unknown provider: keep previous behavior (extract multimodal).
                    can_handle_images = True
            initial_include_multimodal = params.include_multimodal and can_handle_images

            processed_count = 0
            failed_count = 0
            skipped_no_fulltext = 0

            # Fetch full bundles for candidates
            candidate_keys = [item.key for item in candidates]
            full_bundles = await self.batch_loader.fetch_many_bundles(
                candidate_keys,
                include_fulltext=True,
                include_annotations=True,
                include_multimodal=initial_include_multimodal,
            )
            full_bundle_map = {b["metadata"]["key"]: b for b in full_bundles}

            # Backfill multimodal only where fulltext is missing
            # for text-only providers.
            if params.include_multimodal and not initial_include_multimodal:
                missing_fulltext_keys = [
                    key
                    for key, bundle in full_bundle_map.items()
                    if not bool(bundle.get("fulltext"))
                ]
                if missing_fulltext_keys:
                    logger.info(
                        "Backfilling multimodal for "
                        f"{len(missing_fulltext_keys)} items without fulltext"
                    )
                    fallback_bundles = await self.batch_loader.fetch_many_bundles(
                        missing_fulltext_keys,
                        include_fulltext=False,
                        include_annotations=False,
                        include_notes=False,
                        include_multimodal=True,
                    )
                    fallback_map = {
                        b["metadata"]["key"]: b.get("multimodal", {})
                        for b in fallback_bundles
                    }
                    for key in missing_fulltext_keys:
                        if key in fallback_map and key in full_bundle_map:
                            full_bundle_map[key]["multimodal"] = fallback_map[key]

            for i, item in enumerate(candidates, 1):
                logger.info(f"Processing {i}/{len(candidates)}: {item.title[:60]}...")
                bundle = full_bundle_map.get(item.key)
                if not bundle:
                    failed_count += 1
                    logger.warning(f"  ✗ Failed to fetch bundle for {item.key}")
                    continue
                has_fulltext = bool(bundle.get("fulltext"))
                has_multimodal_text = bool(
                    bundle.get("multimodal", {}).get("text_blocks")
                )
                if not has_fulltext and not has_multimodal_text:
                    skipped_no_fulltext += 1
                    logger.info(
                        f"  ⊘ Skipped {item.key}: no fulltext available for analysis"
                    )
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
                        move_to_collection=params.target_collection,
                        include_multimodal=params.include_multimodal,
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

            metrics = {
                "scanned": total_scanned,
                "candidates": len(candidates),
                "processed": processed_count,
                "updated": processed_count,
                "skipped": skipped_no_fulltext,
                "failed": failed_count,
                "removed": 0,
            }
            return operation_success(
                "global_scan",
                metrics,
                message=(
                    f"Processed {processed_count}, "
                    f"failed {failed_count}, "
                    f"skipped_no_fulltext {skipped_no_fulltext} "
                    f"out of {len(candidates)} candidates"
                ),
                extra={
                    "total_scanned": total_scanned,
                    "candidates": len(candidates),
                    "processed": processed_count,
                    "failed": failed_count,
                    "skipped_no_fulltext": skipped_no_fulltext,
                },
            )

        except ValidationError as e:
            logger.error(f"Invalid scanner parameters: {e}")
            return operation_error(
                "global_scan",
                "invalid scanner parameters",
                status="validation_error",
                details=e.errors(),
                extra={
                    "total_scanned": 0,
                    "candidates": 0,
                    "processed": 0,
                    "failed": 0,
                },
            )
        except Exception as e:
            logger.error(f"Error during scan: {e}")
            return operation_error(
                "global_scan",
                str(e),
                extra={
                    "total_scanned": 0,
                    "candidates": 0,
                    "processed": 0,
                    "failed": 0,
                },
            )
