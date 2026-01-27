#!/usr/bin/env python3
"""
RSS Feed Fetcher and Zotero Importer

This script is designed to run in GitHub Actions on a schedule.
It fetches RSS feeds from an OPML file and imports new items to Zotero:
1. Reads OPML file containing journal RSS feeds
2. Fetches all RSS feeds
3. Imports new articles to Zotero staging collection (00_INBOXS)

Requirements:
    - ZOTERO_LIBRARY_ID (env)
    - ZOTERO_API_KEY (env)
    - DEEPSEEK_API_KEY (env) - for potential AI filtering
    - ZOTERO_LOCAL=false (to use Web API)

Usage:
    python src/scripts/fetch_rss.py
"""

import asyncio
import logging
import os
import sys
from datetime import datetime, timedelta
from pathlib import Path

# Setup path to import zotero_mcp modules
sys.path.insert(0, str(Path(__file__).parent.parent))

from zotero_mcp.services.data_access import get_data_service
from zotero_mcp.services.rss import RSSService

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


# Configuration
OPML_FILE_PATH = "RSS/RSS_official.opml"
STAGING_COLLECTION_NAME = "00_INBOXS"
DAYS_BACK = 7  # Only import articles from the last 7 days


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
                {"tag": "unprocessed"},
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
    logger.info("RSS Feed Fetcher and Zotero Importer")
    logger.info("=" * 70)

    # Verify environment variables
    required_vars = {
        "ZOTERO_LIBRARY_ID": os.getenv("ZOTERO_LIBRARY_ID"),
        "ZOTERO_API_KEY": os.getenv("ZOTERO_API_KEY"),
    }

    missing = [k for k, v in required_vars.items() if not v]
    if missing:
        logger.error(f"Missing required environment variables: {', '.join(missing)}")
        sys.exit(1)

    # Ensure ZOTERO_LOCAL is false to use Web API
    os.environ["ZOTERO_LOCAL"] = "false"
    logger.info("Using Zotero Web API (ZOTERO_LOCAL=false)")

    # Check OPML file exists
    opml_path = Path(OPML_FILE_PATH)
    if not opml_path.exists():
        logger.error(f"OPML file not found: {OPML_FILE_PATH}")
        sys.exit(1)

    logger.info(f"Using OPML file: {OPML_FILE_PATH}")

    try:
        # Initialize services
        logger.info("Initializing services...")
        data_service = get_data_service()
        rss_service = RSSService()
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
            logger.info("No recent items to import. Exiting.")
            return

        # Sort by publication date (newest first)
        all_recent_items.sort(key=lambda x: x.pub_date or datetime.min, reverse=True)

        # Import items to Zotero
        logger.info("")
        logger.info("=" * 70)
        logger.info("Importing to Zotero")
        logger.info("=" * 70)
        logger.info(
            f"Importing {len(all_recent_items)} items to '{staging_collection_name}'"
        )

        created_count = 0
        skipped_count = 0
        failed_count = 0

        for idx, item in enumerate(all_recent_items, 1):
            logger.info(
                f"[{idx}/{len(all_recent_items)}] Processing: {item.title[:50]}"
            )

            result = await create_zotero_item_from_rss(
                data_service, item, staging_collection_key
            )

            if result:
                created_count += 1
            elif result is None and "already exists" in str(result):
                skipped_count += 1
            else:
                failed_count += 1

            # Small delay to avoid rate limiting
            await asyncio.sleep(0.5)

        # Summary
        logger.info("")
        logger.info("=" * 70)
        logger.info("Import Complete")
        logger.info("=" * 70)
        logger.info(f"Total items processed: {len(all_recent_items)}")
        logger.info(f"Successfully created: {created_count}")
        logger.info(f"Skipped (duplicates): {skipped_count}")
        logger.info(f"Failed: {failed_count}")
        logger.info("")
        logger.info("✓ RSS feed import completed successfully")

    except Exception as e:
        logger.exception(f"Fatal error during execution: {e}")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
