#!/usr/bin/env python3
"""
Automated Zotero Collection Analysis Script

This script is designed to run in GitHub Actions on a schedule.
It analyzes PDF items in a specified Zotero collection using DeepSeek AI.

Requirements:
    - ZOTERO_LIBRARY_ID (env)
    - ZOTERO_API_KEY (env)
    - DEEPSEEK_API_KEY (env)
    - ZOTERO_LOCAL=false (to use Web API)

Usage:
    python src/scripts/auto_analyze.py
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
COLLECTION_NAME = "1 - 中转过滤：较短期"
MAX_ITEMS = None  # None = process all items
SKIP_NO_PDF = True  # Skip items without PDF attachments


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


async def filter_items_with_pdf(data_service, items):
    """
    Filter items to only include those with PDF attachments.

    Args:
        data_service: DataAccessService instance
        items: List of item objects

    Returns:
        List of items that have PDF attachments
    """
    pdf_items = []
    logger.info(f"Checking {len(items)} items for PDF attachments...")

    for item in items:
        item_key = item.get("key", "")
        item_title = item.get("data", {}).get("title", "Untitled")

        has_pdf = await check_has_pdf(data_service, item_key)
        if has_pdf:
            pdf_items.append(item)
            logger.info(f"  ✓ {item_title[:50]} - Has PDF")
        else:
            logger.info(f"  ✗ {item_title[:50]} - No PDF, skipping")

    logger.info(f"Found {len(pdf_items)} items with PDFs out of {len(items)} total")
    return pdf_items


async def main():
    """Main execution function"""

    logger.info("=" * 70)
    logger.info("Automated Zotero Collection Analysis")
    logger.info("=" * 70)

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

        # Find collection
        logger.info(f"Searching for collection: '{COLLECTION_NAME}'...")
        matches = await data_service.find_collection_by_name(COLLECTION_NAME)

        if not matches:
            logger.error(f"Collection not found: '{COLLECTION_NAME}'")
            sys.exit(1)

        collection = matches[0]
        collection_data = collection.get("data", {})
        collection_name = collection_data.get("name", "Unknown")
        collection_key = collection_data.get("key", "")

        logger.info(f"Found collection: '{collection_name}' (key: {collection_key})")

        # Get collection items
        logger.info("Fetching collection items...")
        items_response = await data_service.get_collection_items(
            collection_key, limit=MAX_ITEMS
        )

        all_items = items_response.get("results", [])
        logger.info(f"Found {len(all_items)} items in collection")

        if not all_items:
            logger.info("No items to process. Exiting.")
            return

        # Filter for items with PDFs if enabled
        if SKIP_NO_PDF:
            items_to_process = await filter_items_with_pdf(data_service, all_items)

            if not items_to_process:
                logger.info("No items with PDFs found. Exiting.")
                return
        else:
            items_to_process = all_items

        # Progress callback
        async def progress_callback(current: int, total: int, item_title: str):
            percentage = (current / total * 100) if total > 0 else 0
            logger.info(
                f"Progress: [{current}/{total}] ({percentage:.1f}%) - {item_title[:50]}"
            )

        # Run batch analysis
        logger.info("")
        logger.info("=" * 70)
        logger.info("Starting batch analysis with DeepSeek AI")
        logger.info("=" * 70)
        logger.info(f"Items to analyze: {len(items_to_process)}")
        logger.info("LLM Provider: DeepSeek")
        logger.info("Skip existing notes: Yes")
        logger.info("")

        result = await workflow_service.batch_analyze(
            source="collection",
            collection_key=collection_key,
            collection_name=None,  # Already have key
            limit=len(items_to_process) if SKIP_NO_PDF else MAX_ITEMS,
            skip_existing=True,  # Skip items that already have analysis notes
            include_annotations=True,  # Include PDF annotations
            llm_provider="deepseek",
            llm_model=None,  # Use default model
            template=None,  # Use default Chinese academic template
            dry_run=False,  # Actually execute
            progress_callback=progress_callback,
        )

        # Display results
        logger.info("")
        logger.info("=" * 70)
        logger.info("Analysis Complete")
        logger.info("=" * 70)
        logger.info(f"Workflow ID: {result.workflow_id}")
        logger.info(f"Status: {result.status}")
        logger.info(f"Total items: {result.total_items}")
        logger.info(f"Successfully processed: {result.processed}")
        logger.info(f"Skipped (already analyzed): {result.skipped}")
        logger.info(f"Failed: {result.failed}")

        if result.error:
            logger.error(f"Error: {result.error}")

        if result.can_resume:
            logger.info(f"Workflow can be resumed with ID: {result.workflow_id}")

        # Exit with error code if there were failures
        if result.failed > 0:
            logger.warning(f"{result.failed} items failed to process")
            # Don't exit with error code for failures - they might be expected
            # (e.g., items without full text)

        logger.info("")
        logger.info("✓ Automated analysis completed successfully")

    except Exception as e:
        logger.exception(f"Fatal error during execution: {e}")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
