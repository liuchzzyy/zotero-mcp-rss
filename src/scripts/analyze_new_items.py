#!/usr/bin/env python3
"""
Automated New Item Analysis and Organization Script

This script is designed to run in GitHub Actions on a schedule.
It processes new items in the staging collection:
1. Filters for items with PDF attachments but no tags
2. Analyzes them using DeepSeek AI
3. Moves processed items to the processing collection

Requirements:
    - ZOTERO_LIBRARY_ID (env)
    - ZOTERO_API_KEY (env)
    - DEEPSEEK_API_KEY (env)
    - ZOTERO_LOCAL=false (to use Web API)

Usage:
    python src/scripts/analyze_new_items.py
"""

import asyncio
import logging
import os
from pathlib import Path
import sys

# Setup path to import zotero_mcp modules
sys.path.insert(0, str(Path(__file__).parent.parent))

from zotero_mcp.services.data_access import get_data_service
from zotero_mcp.services.workflow import WorkflowService

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


# Configuration
SOURCE_COLLECTION_NAME = "00_INBOXS"
DEST_COLLECTION_NAME = "01_SHORTTERMS"

# Runtime options from environment variables
_max_items_env = os.getenv("MAX_ITEMS", "").strip()
MAX_ITEMS: int | None = int(_max_items_env) if _max_items_env else None
DRY_RUN = os.getenv("DRY_RUN", "false").lower() == "true"
DEBUG = os.getenv("DEBUG", "false").lower() == "true"

# Adjust logging level for debug mode
if DEBUG:
    logging.getLogger().setLevel(logging.DEBUG)
    logger.setLevel(logging.DEBUG)


async def check_has_pdf(data_service, item_key: str) -> bool:
    """
    Check if an item has at least one PDF attachment.

    Args:
        data_service: DataAccessService instance
        item_key: Zotero item key

    Returns:
        True if item has PDF attachment, False otherwise
    """
    try:
        children = await data_service.get_item_children(item_key)
        for child in children:
            child_data = child.get("data", {})
            if child_data.get("itemType") == "attachment":
                content_type = child_data.get("contentType", "")
                if content_type == "application/pdf":
                    return True
        return False
    except Exception as e:
        logger.warning(f"Error checking PDF for item {item_key}: {e}")
        return False


def check_has_tags(item) -> bool:
    """
    Check if an item has any tags.

    Args:
        item: Item object (can be SearchResultItem Pydantic model or dict)

    Returns:
        True if item has tags, False otherwise
    """
    # Handle Pydantic model (SearchResultItem)
    if hasattr(item, "tags"):
        return len(item.tags) > 0
    # Handle raw dict
    if isinstance(item, dict):
        item_data = item.get("data", {})
        tags = item_data.get("tags", [])
        return len(tags) > 0
    return False


async def filter_items_for_analysis(data_service, items):
    """
    Filter items to only include those with PDF attachments but no tags.

    Args:
        data_service: DataAccessService instance
        items: List of item objects (SearchResult objects with raw_data)

    Returns:
        List of items that need analysis
    """
    items_to_analyze = []
    logger.info(f"Filtering {len(items)} items...")

    for item in items:
        # Extract raw_data from SearchResult
        raw_item = item.raw_data if hasattr(item, "raw_data") else item
        item_key = item.key if hasattr(item, "key") else raw_item.get("key", "")
        item_title = (
            item.title
            if hasattr(item, "title")
            else raw_item.get("data", {}).get("title", "Untitled")
        )

        # Check for tags - use item directly as SearchResultItem has .tags attribute
        has_tags = check_has_tags(item)
        if has_tags:
            logger.info(f"  ⊘ {item_title[:50]} - Already has tags, skipping")
            continue

        # Check for PDF
        has_pdf = await check_has_pdf(data_service, item_key)
        if not has_pdf:
            logger.info(f"  ✗ {item_title[:50]} - No PDF, skipping")
            continue

        items_to_analyze.append(raw_item)
        logger.info(f"  ✓ {item_title[:50]} - Ready for analysis")

    logger.info(
        f"Found {len(items_to_analyze)} items ready for analysis out of {len(items)} total"
    )
    return items_to_analyze


async def move_items_to_collection(
    data_service, item_keys: list[str], dest_collection_key: str
):
    """
    Move items to destination collection.

    Args:
        data_service: DataAccessService instance
        item_keys: List of item keys to move
        dest_collection_key: Destination collection key
    """
    logger.info(f"Moving {len(item_keys)} items to destination collection...")
    success_count = 0
    error_count = 0

    for item_key in item_keys:
        try:
            await data_service.add_item_to_collection(dest_collection_key, item_key)
            success_count += 1
            logger.info(f"  ✓ Moved item {item_key}")
        except Exception as e:
            error_count += 1
            logger.error(f"  ✗ Failed to move item {item_key}: {e}")

    logger.info(f"Successfully moved {success_count} items, {error_count} errors")


async def main():
    """Main execution function"""

    logger.info("=" * 70)
    logger.info("Automated New Item Analysis and Organization")
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
        workflow_service = WorkflowService()
        data_service = get_data_service()
        logger.info("Services initialized successfully")

        # Find source collection
        logger.info(f"Searching for source collection: '{SOURCE_COLLECTION_NAME}'...")
        source_matches = await data_service.find_collection_by_name(
            SOURCE_COLLECTION_NAME
        )

        if not source_matches:
            logger.error(f"Source collection not found: '{SOURCE_COLLECTION_NAME}'")
            sys.exit(1)

        source_collection = source_matches[0]
        source_collection_data = source_collection.get("data", {})
        source_collection_name = source_collection_data.get("name", "Unknown")
        source_collection_key = source_collection_data.get("key", "")

        logger.info(
            f"Found source collection: '{source_collection_name}' (key: {source_collection_key})"
        )

        # Find destination collection
        logger.info(
            f"Searching for destination collection: '{DEST_COLLECTION_NAME}'..."
        )
        dest_matches = await data_service.find_collection_by_name(DEST_COLLECTION_NAME)

        if not dest_matches:
            logger.error(f"Destination collection not found: '{DEST_COLLECTION_NAME}'")
            sys.exit(1)

        dest_collection = dest_matches[0]
        dest_collection_data = dest_collection.get("data", {})
        dest_collection_name = dest_collection_data.get("name", "Unknown")
        dest_collection_key = dest_collection_data.get("key", "")

        logger.info(
            f"Found destination collection: '{dest_collection_name}' (key: {dest_collection_key})"
        )

        # Get collection items
        logger.info("Fetching collection items...")
        items_response = await data_service.get_collection_items(
            source_collection_key, limit=1000
        )

        all_items = items_response if isinstance(items_response, list) else []
        logger.info(f"Found {len(all_items)} items in source collection")

        if not all_items:
            logger.info("No items to process. Exiting.")
            return

        # Filter for items with PDF but no tags
        items_to_process = await filter_items_for_analysis(data_service, all_items)

        if not items_to_process:
            logger.info("No items need analysis. Exiting.")
            return

        # Limit items if MAX_ITEMS is set
        if MAX_ITEMS and len(items_to_process) > MAX_ITEMS:
            logger.info(f"Limiting to {MAX_ITEMS} items")
            items_to_process = items_to_process[:MAX_ITEMS]

        # Progress callback
        async def progress_callback(current: int, total: int, item_title: str):
            percentage = (current / total * 100) if total > 0 else 0
            logger.info(
                f"Progress: [{current}/{total}] ({percentage:.1f}%) - {item_title[:50]}"
            )

        # Run batch analysis
        logger.info("")
        logger.info("=" * 70)
        logger.info(
            "Starting batch analysis with DeepSeek AI"
            + (" (DRY RUN)" if DRY_RUN else "")
        )
        logger.info("=" * 70)
        logger.info(f"Items to analyze: {len(items_to_process)}")
        logger.info("LLM Provider: DeepSeek")
        logger.info("")

        result = await workflow_service.batch_analyze(
            source="collection",
            collection_key=source_collection_key,
            collection_name=None,  # Already have key
            limit=len(items_to_process),
            skip_existing=True,  # Skip items that already have analysis notes
            include_annotations=True,  # Include PDF annotations
            llm_provider="deepseek",
            llm_model=None,  # Use default model
            template=None,  # Use default Chinese academic template
            dry_run=DRY_RUN,  # Use environment variable
            progress_callback=progress_callback,
        )

        # Display analysis results
        logger.info("")
        logger.info("=" * 70)
        logger.info("Analysis Complete" + (" (DRY RUN)" if DRY_RUN else ""))
        logger.info("=" * 70)
        logger.info(f"Workflow ID: {result.workflow_id}")
        logger.info(f"Status: {result.status}")
        logger.info(f"Total items: {result.total_items}")
        logger.info(
            f"{'Would process' if DRY_RUN else 'Successfully processed'}: {result.processed}"
        )
        logger.info(f"Skipped: {result.skipped}")
        logger.info(f"Failed: {result.failed}")

        if result.error:
            logger.error(f"Error: {result.error}")

        # Move successfully processed items to destination collection (skip in DRY_RUN)
        if result.processed > 0 and not DRY_RUN:
            logger.info("")
            logger.info("=" * 70)
            logger.info("Moving processed items to destination collection")
            logger.info("=" * 70)

            # Extract item keys that were successfully processed
            # Note: WorkflowService doesn't return individual item results,
            # so we move all items that were in the batch
            processed_item_keys = [
                item.get("key", "") for item in items_to_process[: result.processed]
            ]

            await move_items_to_collection(
                data_service, processed_item_keys, dest_collection_key
            )
        elif result.processed > 0 and DRY_RUN:
            logger.info("")
            logger.info(
                f"[DRY RUN] Would move {result.processed} items to '{dest_collection_name}'"
            )

        logger.info("")
        logger.info("✓ Automated analysis and organization completed successfully")

    except Exception as e:
        logger.exception(f"Fatal error during execution: {e}")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
