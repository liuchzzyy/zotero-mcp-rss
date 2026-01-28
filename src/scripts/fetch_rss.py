#!/usr/bin/env python3
"""
RSS Feed Fetcher with AI Filtering and Zotero Import

This script is designed to run in GitHub Actions on a schedule.
It fetches RSS feeds from an OPML file, filters them using DeepSeek-powered
keyword matching, and imports relevant items to Zotero:

1. Reads OPML file containing journal RSS feeds
2. Fetches all RSS feeds
3. Extracts keywords from research interest prompt using DeepSeek
4. Filters articles by matching keywords against titles
5. Imports ONLY relevant articles to Zotero staging collection (00_INBOXS)

Requirements:
    - ZOTERO_LIBRARY_ID (env)
    - ZOTERO_API_KEY (env)
    - DEEPSEEK_API_KEY (env) - for AI filtering
    - ZOTERO_LOCAL=false (to use Web API)

Usage:
    python src/scripts/fetch_rss.py

Reference:
    https://github.com/liuchzzyy/RSS_Papers
"""

import asyncio
from datetime import datetime, timedelta
import logging
import os
from pathlib import Path
import sys

# Setup path to import zotero_mcp modules
sys.path.insert(0, str(Path(__file__).parent.parent))

from zotero_mcp.services.data_access import get_data_service
from zotero_mcp.services.rss import RSSFilter, RSSService

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


# Configuration
OPML_FILE_PATH = "RSS/RSS_official.opml"
PROMPT_FILE_PATH = "RSS/prompt.txt"
STAGING_COLLECTION_NAME = "00_INBOXS"
DAYS_BACK = 7  # Only import articles from the last 7 days

# Runtime options from environment variables
_max_items_env = os.getenv("MAX_ITEMS", "").strip()
MAX_ITEMS: int | None = int(_max_items_env) if _max_items_env else None
DRY_RUN = os.getenv("DRY_RUN", "false").lower() == "true"
DEBUG = os.getenv("DEBUG", "false").lower() == "true"

# Adjust logging level for debug mode
if DEBUG:
    logging.getLogger().setLevel(logging.DEBUG)
    logger.setLevel(logging.DEBUG)


async def create_zotero_item_from_rss(data_service, rss_item, collection_key: str):
    """
    Create a Zotero item from an RSS feed item.

    Args:
        data_service: DataAccessService instance
        rss_item: RSSItem object
        collection_key: Target collection key

    Returns:
        Created item key or None if failed
    """
    try:
        # Check if item already exists (by URL)
        # This is a simple check - in production you might want more sophisticated deduplication
        existing = await data_service.search_items(query=rss_item.link, limit=1)
        if existing and len(existing) > 0:
            logger.info(f"  ⊘ Item already exists: {rss_item.title[:50]}")
            return None

        # Create item data structure for Zotero
        item_data = {
            "itemType": "journalArticle",
            "title": rss_item.title,
            "url": rss_item.link,
            "abstractNote": rss_item.description or "",
            "publicationTitle": rss_item.source_title,
            "date": rss_item.pub_date.strftime("%Y-%m-%d") if rss_item.pub_date else "",
            "accessDate": datetime.now().strftime("%Y-%m-%d"),
            "collections": [collection_key],
            "tags": [
                {"tag": "from-rss"},
                {"tag": "ai-filtered"},
            ],
        }

        # Add author if available
        if rss_item.author:
            item_data["creators"] = [
                {
                    "creatorType": "author",
                    "name": rss_item.author,
                }
            ]

        # Create item in Zotero
        # Note: The current API doesn't have a direct create_item method exposed
        # We'll need to use the underlying client
        client = data_service.api_client
        result = await client._run_sync(
            None, lambda: client.client.create_items([item_data])
        )

        if result and len(result.get("success", {})) > 0:
            item_key = list(result["success"].keys())[0]
            logger.info(f"  ✓ Created: {rss_item.title[:50]} (key: {item_key})")
            return item_key
        else:
            logger.warning(f"  ✗ Failed to create: {rss_item.title[:50]}")
            return None

    except Exception as e:
        logger.error(f"  ✗ Error creating item '{rss_item.title[:50]}': {e}")
        return None


async def main():
    """Main execution function"""

    logger.info("=" * 70)
    logger.info("RSS Feed Fetcher with AI Filtering and Zotero Import")
    logger.info("=" * 70)

    # Show runtime options
    logger.info(
        f"Mode: {'DRY RUN (preview only)' if DRY_RUN else 'LIVE (will import)'}"
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

    # Check required files exist
    opml_path = Path(OPML_FILE_PATH)
    prompt_path = Path(PROMPT_FILE_PATH)

    if not opml_path.exists():
        logger.error(f"OPML file not found: {OPML_FILE_PATH}")
        sys.exit(1)

    if not prompt_path.exists():
        logger.error(f"Prompt file not found: {PROMPT_FILE_PATH}")
        sys.exit(1)

    logger.info(f"Using OPML file: {OPML_FILE_PATH}")
    logger.info(f"Using prompt file: {PROMPT_FILE_PATH}")

    try:
        # Initialize services
        logger.info("Initializing services...")
        data_service = get_data_service()
        rss_service = RSSService()
        rss_filter = RSSFilter(prompt_file=str(prompt_path))
        logger.info("Services initialized successfully")

        # Find staging collection
        logger.info(f"Searching for staging collection: '{STAGING_COLLECTION_NAME}'...")
        staging_matches = await data_service.find_collection_by_name(
            STAGING_COLLECTION_NAME
        )

        if not staging_matches:
            logger.error(f"Staging collection not found: '{STAGING_COLLECTION_NAME}'")
            sys.exit(1)

        staging_collection = staging_matches[0]
        staging_collection_data = staging_collection.get("data", {})
        staging_collection_name = staging_collection_data.get("name", "Unknown")
        staging_collection_key = staging_collection_data.get("key", "")

        logger.info(
            f"Found staging collection: '{staging_collection_name}' (key: {staging_collection_key})"
        )

        # Fetch RSS feeds from OPML
        logger.info("")
        logger.info("=" * 70)
        logger.info("Fetching RSS Feeds")
        logger.info("=" * 70)
        logger.info(f"Reading OPML file: {OPML_FILE_PATH}")

        feeds = await rss_service.fetch_feeds_from_opml(str(opml_path.absolute()))
        logger.info(f"Successfully fetched {len(feeds)} feeds")

        # Collect all recent items
        cutoff_date = datetime.now() - timedelta(days=DAYS_BACK)
        all_recent_items = []

        for feed in feeds:
            recent_items = [
                item
                for item in feed.items
                if item.pub_date and item.pub_date >= cutoff_date
            ]
            all_recent_items.extend(recent_items)
            logger.info(
                f"  {feed.title}: {len(recent_items)} recent items (total: {len(feed.items)})"
            )

        logger.info(
            f"Total recent items (last {DAYS_BACK} days): {len(all_recent_items)}"
        )

        if not all_recent_items:
            logger.info("No recent items to process. Exiting.")
            return

        # Sort by publication date (newest first)
        all_recent_items.sort(key=lambda x: x.pub_date or datetime.min, reverse=True)

        # AI-powered filtering
        logger.info("")
        logger.info("=" * 70)
        logger.info("AI-Powered Keyword Filtering")
        logger.info("=" * 70)

        (
            relevant_items,
            irrelevant_items,
            keywords,
        ) = await rss_filter.filter_with_keywords(all_recent_items, str(prompt_path))

        logger.info(f"Keywords used: {keywords}")
        logger.info(f"Relevant items: {len(relevant_items)}")
        logger.info(f"Irrelevant items (filtered out): {len(irrelevant_items)}")

        if not relevant_items:
            logger.info("No relevant items found after filtering. Exiting.")
            return

        # Log some relevant titles for verification
        logger.info("")
        logger.info("Sample relevant articles:")
        for item in relevant_items[:5]:
            logger.info(f"  • {item.title[:70]}...")

        # Import items to Zotero
        logger.info("")
        logger.info("=" * 70)
        logger.info("Importing to Zotero" + (" (DRY RUN)" if DRY_RUN else ""))
        logger.info("=" * 70)

        # Apply MAX_ITEMS limit
        items_to_import = relevant_items
        if MAX_ITEMS and len(relevant_items) > MAX_ITEMS:
            items_to_import = relevant_items[:MAX_ITEMS]
            logger.info(
                f"Limiting to {MAX_ITEMS} items (out of {len(relevant_items)} relevant)"
            )

        logger.info(
            f"{'Would import' if DRY_RUN else 'Importing'} {len(items_to_import)} items to '{staging_collection_name}'"
        )

        created_count = 0
        skipped_count = 0
        failed_count = 0

        for idx, item in enumerate(items_to_import, 1):
            logger.info(f"[{idx}/{len(items_to_import)}] Processing: {item.title[:50]}")

            if DRY_RUN:
                logger.info(f"  [DRY RUN] Would create: {item.title[:60]}")
                created_count += 1
                continue

            result = await create_zotero_item_from_rss(
                data_service, item, staging_collection_key
            )

            if result:
                created_count += 1
            elif result is None:
                skipped_count += 1
            else:
                failed_count += 1

            # Small delay to avoid rate limiting
            await asyncio.sleep(0.5)

        # Summary
        logger.info("")
        logger.info("=" * 70)
        logger.info("Import Complete" + (" (DRY RUN)" if DRY_RUN else ""))
        logger.info("=" * 70)
        logger.info(f"Total items fetched: {len(all_recent_items)}")
        logger.info(f"Items passed AI filter: {len(relevant_items)}")
        logger.info(f"Items filtered out: {len(irrelevant_items)}")
        logger.info(
            f"{'Would create' if DRY_RUN else 'Successfully created'}: {created_count}"
        )
        logger.info(f"Skipped (duplicates): {skipped_count}")
        logger.info(f"Failed: {failed_count}")
        logger.info("")
        logger.info("✓ RSS feed import with AI filtering completed successfully")

    except Exception as e:
        logger.exception(f"Fatal error during execution: {e}")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
