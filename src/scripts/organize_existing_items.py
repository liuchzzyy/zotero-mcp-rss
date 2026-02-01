#!/usr/bin/env python3
"""
Automated Existing Item Re-analysis Script

This script is designed to run in GitHub Actions on a schedule.
It processes existing items in all collections (excluding staging collection):
1. Filters for items with both PDF and notes but no tags
2. Deletes old notes (moves to trash)
3. Re-analyzes with AI via WorkflowService
4. Adds tags to processed items

Requirements:
    - ZOTERO_LIBRARY_ID (env)
    - ZOTERO_API_KEY (env)
    - DEEPSEEK_API_KEY (env)
    - ZOTERO_LOCAL=false (to use Web API)

Usage:
    python src/scripts/organize_existing_items.py
"""

import asyncio
import logging
import os
from pathlib import Path
import sys

# Setup path to import zotero_mcp modules
sys.path.insert(0, str(Path(__file__).parent.parent))

from zotero_mcp.services.analysis_status import AnalysisStatusService
from zotero_mcp.services.data_access import get_data_service
from zotero_mcp.services.workflow import WorkflowService
from zotero_mcp.utils.formatting.helpers import check_has_pdf

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


# Configuration
EXCLUDED_COLLECTION_NAME = "00_INBOXS"  # Don't process items here
TAG_TO_ADD = "AI分析"  # Tag to add after successful analysis

# Runtime options from environment variables
_max_items_env = os.getenv("MAX_ITEMS", "").strip()
MAX_ITEMS: int | None = int(_max_items_env) if _max_items_env else None
DRY_RUN = os.getenv("DRY_RUN", "false").lower() == "true"
DEBUG = os.getenv("DEBUG", "false").lower() == "true"

# Adjust logging level for debug mode
if DEBUG:
    logging.getLogger().setLevel(logging.DEBUG)
    logger.setLevel(logging.DEBUG)


async def delete_item_notes(data_service, item_key: str):
    """
    Delete all notes for an item (moves to trash).

    Args:
        data_service: DataAccessService instance
        item_key: Zotero item key
    """
    try:
        notes = await data_service.get_notes(item_key)
        for note in notes:
            note_key = note.get("key", "")
            if note_key:
                await data_service.delete_item(note_key)
                logger.info(f"    Deleted note {note_key}")
        logger.info(f"  Deleted {len(notes)} notes for item {item_key}")
    except Exception as e:
        logger.error(f"  Error deleting notes for item {item_key}: {e}")


async def filter_items_for_reanalysis(data_service, items):
    """
    Filter items to only include those with PDF, notes, but no tags.

    Args:
        data_service: DataAccessService instance
        items: List of item objects (SearchResult objects with raw_data)

    Returns:
        List of items that need re-analysis
    """
    items_to_reanalyze = []
    logger.info(f"Filtering {len(items)} items...")

    # Initialize status service
    status_service = AnalysisStatusService(data_service.item_service)

    for item in items:
        # Extract raw_data from SearchResult
        raw_item = item.raw_data if hasattr(item, "raw_data") else item
        item_key = item.key if hasattr(item, "key") else raw_item.get("key", "")
        item_title = (
            item.title
            if hasattr(item, "title")
            else raw_item.get("data", {}).get("title", "Untitled")
        )

        # Check analysis status
        # We want items that are NOT fully analyzed (no tag)
        is_analyzed = await status_service.is_analyzed(item_key)
        if is_analyzed:
            logger.info(f"  ⊘ {item_title[:50]} - Already analyzed (has tag), skipping")
            continue

        # Check for PDF
        has_pdf = await check_has_pdf(data_service, item_key)
        if not has_pdf:
            logger.info(f"  ✗ {item_title[:50]} - No PDF, skipping")
            continue

        # Check for notes
        # We target items that HAVE notes but NO tag (legacy state)
        has_notes = await status_service.has_notes(item_key)
        if not has_notes:
            logger.info(f"  ✗ {item_title[:50]} - No notes, skipping")
            continue

        items_to_reanalyze.append(raw_item)
        logger.info(f"  ✓ {item_title[:50]} - Ready for re-analysis")

    logger.info(
        f"Found {len(items_to_reanalyze)} items ready for re-analysis out of {len(items)} total"
    )
    return items_to_reanalyze


async def add_tags_to_items(data_service, item_keys: list[str], tags: list[str]):
    """
    Add tags to items.

    Args:
        data_service: DataAccessService instance
        item_keys: List of item keys
        tags: List of tags to add
    """
    logger.info(f"Adding tags to {len(item_keys)} items...")
    success_count = 0
    error_count = 0

    for item_key in item_keys:
        try:
            await data_service.add_tags_to_item(item_key, tags)
            success_count += 1
            logger.info(f"  ✓ Added tags to item {item_key}")
        except Exception as e:
            error_count += 1
            logger.error(f"  ✗ Failed to add tags to item {item_key}: {e}")

    logger.info(f"Successfully tagged {success_count} items, {error_count} errors")


async def get_all_items_except_excluded(data_service, excluded_collection_key: str):
    """
    Get all library items except those in excluded collection.

    Args:
        data_service: DataAccessService instance
        excluded_collection_key: Collection key to exclude

    Returns:
        List of items not in excluded collection
    """
    logger.info("Fetching all library items...")

    # Get all collections
    all_collections = await data_service.get_collections()

    # Filter out excluded collection
    collections_to_process = [
        coll
        for coll in all_collections
        if coll.get("data", {}).get("key", "") != excluded_collection_key
    ]

    logger.info(
        f"Found {len(collections_to_process)} collections to process (excluding staging)"
    )

    # Collect items from all collections
    all_items = []
    seen_keys = set()

    for coll in collections_to_process:
        coll_data = coll.get("data", {})
        coll_name = coll_data.get("name", "Unknown")
        coll_key = coll_data.get("key", "")

        logger.info(f"Fetching items from collection: '{coll_name}'...")
        items = await data_service.get_collection_items(coll_key, limit=1000)

        # Deduplicate items (same item can be in multiple collections)
        for item in items:
            item_key = item.key if hasattr(item, "key") else item.get("key", "")
            if item_key and item_key not in seen_keys:
                all_items.append(item)
                seen_keys.add(item_key)

    logger.info(f"Found {len(all_items)} unique items across all collections")
    return all_items


async def get_collection_key_for_item(data_service, item_key: str, collections):
    """
    Find which collection an item belongs to.

    Args:
        data_service: DataAccessService instance
        item_key: Zotero item key
        collections: List of collection dicts

    Returns:
        Collection key, or None if not found
    """
    try:
        item = await data_service.get_item(item_key)
        item_collections = item.get("data", {}).get("collections", [])
        if item_collections:
            return item_collections[0]
    except Exception:
        pass
    return None


async def main():
    """Main execution function"""

    logger.info("=" * 70)
    logger.info("Automated Existing Item Re-analysis")
    logger.info("=" * 70)

    # Show runtime options
    logger.info(
        f"Mode: {'DRY RUN (preview only)' if DRY_RUN else 'LIVE (will analyze)'}"
    )
    logger.info(f"Max items: {MAX_ITEMS if MAX_ITEMS else 'unlimited'}")
    logger.info(f"Debug: {DEBUG}")

    # Verify environment variables
    required_vars = {
        "ZOTERO_LIBRARY_ID": os.getenv("ZOTERO_LIBRARY_ID"),
        "ZOTERO_API_KEY": os.getenv("ZOTERO_API_KEY"),
        "DEEPSEEK_API_KEY": os.getenv("DEEPSEEK_API_KEY"),
    }

    missing = [k for k, v in required_vars.items() if not v]
    if missing:
        logger.error(f"Missing required environment variables: {', '.join(missing)}")
        sys.exit(1)

    # Ensure ZOTERO_LOCAL is false to use Web API
    os.environ["ZOTERO_LOCAL"] = "false"
    logger.info("Using Zotero Web API (ZOTERO_LOCAL=false)")

    try:
        # Initialize services
        logger.info("Initializing services...")
        data_service = get_data_service()
        workflow_service = WorkflowService()
        logger.info("Services initialized successfully")

        # Find excluded collection
        logger.info(
            f"Searching for excluded collection: '{EXCLUDED_COLLECTION_NAME}'..."
        )
        excluded_matches = await data_service.find_collection_by_name(
            EXCLUDED_COLLECTION_NAME
        )

        excluded_collection_key = None
        if excluded_matches:
            excluded_collection = excluded_matches[0]
            excluded_collection_data = excluded_collection.get("data", {})
            excluded_collection_name = excluded_collection_data.get("name", "Unknown")
            excluded_collection_key = excluded_collection_data.get("key", "")
            logger.info(
                f"Found excluded collection: '{excluded_collection_name}' (key: {excluded_collection_key})"
            )
        else:
            logger.warning(
                f"Excluded collection not found: '{EXCLUDED_COLLECTION_NAME}', processing all items"
            )

        # Get all items except excluded collection
        all_items = await get_all_items_except_excluded(
            data_service, excluded_collection_key or ""
        )

        if not all_items:
            logger.info("No items to process. Exiting.")
            return

        # Filter for items with PDF, notes, but no tags
        items_to_process = await filter_items_for_reanalysis(data_service, all_items)

        if not items_to_process:
            logger.info("No items need re-analysis. Exiting.")
            return

        # Limit items if MAX_ITEMS is set
        if MAX_ITEMS and len(items_to_process) > MAX_ITEMS:
            logger.info(f"Limiting to {MAX_ITEMS} items")
            items_to_process = items_to_process[:MAX_ITEMS]

        # Delete old notes before re-analysis (skip in DRY_RUN)
        logger.info("")
        logger.info("=" * 70)
        logger.info("Deleting old notes" + (" (DRY RUN - skipping)" if DRY_RUN else ""))
        logger.info("=" * 70)

        for item in items_to_process:
            item_key = item.get("key", "")
            item_title = item.get("data", {}).get("title", "Untitled")
            if DRY_RUN:
                logger.info(f"  [DRY RUN] Would delete notes for: {item_title[:50]}")
            else:
                logger.info(f"Processing: {item_title[:50]}")
                await delete_item_notes(data_service, item_key)

        # Group items by collection for batch_analyze
        # Build a map: collection_key -> list of item_keys
        collection_items: dict[str, list[str]] = {}
        for item in items_to_process:
            item_key = item.get("key", "")
            item_collections = item.get("data", {}).get("collections", [])
            if item_collections:
                coll_key = item_collections[0]
                collection_items.setdefault(coll_key, []).append(item_key)
            else:
                logger.warning(f"  Item {item_key} has no collection, skipping")

        # Progress callback
        async def progress_callback(current: int, total: int, item_title: str):
            percentage = (current / total * 100) if total > 0 else 0
            logger.info(
                f"Progress: [{current}/{total}] ({percentage:.1f}%) - {item_title[:50]}"
            )

        # Run batch re-analysis per collection using WorkflowService
        logger.info("")
        logger.info("=" * 70)
        logger.info(
            "Starting batch re-analysis with DeepSeek AI"
            + (" (DRY RUN)" if DRY_RUN else "")
        )
        logger.info("=" * 70)
        logger.info(f"Items to re-analyze: {len(items_to_process)}")
        logger.info(f"Across {len(collection_items)} collections")
        logger.info("LLM Provider: DeepSeek")
        logger.info("")

        all_processed_keys = []
        total_processed = 0
        total_skipped = 0
        total_failed = 0

        for coll_key, item_keys in collection_items.items():
            logger.info(f"Processing collection {coll_key} ({len(item_keys)} items)...")

            result = await workflow_service.batch_analyze(
                source="collection",
                collection_key=coll_key,
                limit=len(item_keys),
                skip_existing=False,  # Notes were already deleted
                include_annotations=True,
                llm_provider="deepseek",
                llm_model=None,
                template=None,
                dry_run=DRY_RUN,
                progress_callback=progress_callback,
            )

            # Collect successfully processed item keys
            for r in result.results:
                if r.success and not r.skipped:
                    all_processed_keys.append(r.item_key)

            total_processed += result.processed
            total_skipped += result.skipped
            total_failed += result.failed

            if result.error:
                logger.error(f"  Error in collection {coll_key}: {result.error}")

        # Display analysis results
        logger.info("")
        logger.info("=" * 70)
        logger.info("Re-analysis Complete" + (" (DRY RUN)" if DRY_RUN else ""))
        logger.info("=" * 70)
        logger.info(f"Total items: {len(items_to_process)}")
        logger.info(
            f"{'Would process' if DRY_RUN else 'Successfully processed'}: {total_processed}"
        )
        logger.info(f"Skipped: {total_skipped}")
        logger.info(f"Failed: {total_failed}")

        # Add tags to successfully processed items (skip in DRY_RUN)
        if all_processed_keys and not DRY_RUN:
            logger.info("")
            logger.info("=" * 70)
            logger.info("Adding tags to processed items")
            logger.info("=" * 70)

            await add_tags_to_items(data_service, all_processed_keys, [TAG_TO_ADD])
        elif all_processed_keys and DRY_RUN:
            logger.info("")
            logger.info(
                f"[DRY RUN] Would add '{TAG_TO_ADD}' tag to {len(all_processed_keys)} items"
            )

        logger.info("")
        logger.info("✓ Automated re-analysis and organization completed successfully")

    except Exception as e:
        logger.exception(f"Fatal error during execution: {e}")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
