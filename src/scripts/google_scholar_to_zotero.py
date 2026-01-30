#!/usr/bin/env python3
"""
Google Scholar Alerts to Zotero Import Script

This script fetches emails from Google Scholar Alerts, extracts article items,
filters them using RSS keywords, looks up complete metadata from Crossref/OpenAlex,
and imports to Zotero with rich metadata.

Requirements:
    - ZOTERO_LIBRARY_ID (env)
    - ZOTERO_API_KEY (env)
    - RSS_PROMPT (env) - for filtering articles
    - GMAIL_TOKEN_JSON or gmail_credentials.json (for Gmail auth)

Usage:
    python src/scripts/google_scholar_to_zotero.py
"""

import asyncio
from datetime import datetime
import logging
import os
from pathlib import Path
import re
import sys
from typing import TypedDict

# Setup path to import zotero_mcp modules
sys.path.insert(0, str(Path(__file__).parent.parent))

from zotero_mcp.clients.gmail import GmailClient
from zotero_mcp.services.data_access import get_data_service
from zotero_mcp.services.gmail import GmailService
from zotero_mcp.services.metadata import MetadataService
from zotero_mcp.services.rss import RSSFilter

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

# Configuration
GMAIL_SENDER = "scholaralerts-noreply@google.com"
# Google Scholar Alert subjects vary by topic, so we'll match by sender only
# Common patterns include: "- 新的结果", "- new results", etc.
GMAIL_SUBJECTS = []  # Empty means match all emails from this sender
ZOTERO_COLLECTION_NAME = "00_INBOXS"

# Runtime options from environment variables
_max_emails_env = os.getenv("MAX_EMAILS", "").strip()
MAX_EMAILS: int | None = int(_max_emails_env) if _max_emails_env else 50

_dry_run_env = os.getenv("DRY_RUN", "").strip()
DRY_RUN = _dry_run_env.lower() == "true"

_skip_dup_check_env = os.getenv("SKIP_DUP_CHECK", "").strip()
SKIP_DUP_CHECK = _skip_dup_check_env.lower() == "true"

_debug_env = os.getenv("DEBUG", "").strip()
DEBUG = _debug_env.lower() == "true"

# Adjust logging level for debug mode
if DEBUG:
    logging.getLogger().setLevel(logging.DEBUG)
    logger.setLevel(logging.DEBUG)


class ImportStats(TypedDict):
    """Type-safe stats dictionary for import operations."""

    emails_processed: int
    articles_extracted: int
    articles_imported: int
    articles_filtered: int
    metadata_found: int
    metadata_not_found: int
    errors: list[str]


def clean_title(title: str) -> str:
    """Clean article title by removing common prefixes and HTML entities."""
    if not title:
        return ""
    # Remove [PDF], [HTML], etc. prefixes
    cleaned = re.sub(r"^\[.*?\]\s*", "", title)
    # Remove HTML entities
    cleaned = cleaned.replace("&amp;", "&").replace("&lt;", "<").replace("&gt;", ">")
    return cleaned.strip()


async def fetch_google_scholar_emails(
    gmail_client: GmailClient,
) -> list[dict[str, str]]:
    """
    Fetch Google Scholar Alert emails.

    Search for emails matching:
    - From: scholaralerts-noreply@google.com
    - Subject contains: Google Scholar Alerts OR Google 学术搜索快讯

    Args:
        gmail_client: GmailClient instance

    Returns:
        List of message dicts with 'id' and 'threadId'
    """
    logger.info("=" * 70)
    logger.info("Fetching Google Scholar Alert emails...")
    logger.info("=" * 70)
    logger.info(f"Sender filter: {GMAIL_SENDER}")
    logger.info(f"Subject filters: {', '.join(GMAIL_SUBJECTS)}")
    logger.info(f"Max emails: {MAX_EMAILS if MAX_EMAILS else 'all'}")
    logger.info("")

    # Build Gmail query
    # Use sender filter only (since subjects vary by topic)
    if GMAIL_SUBJECTS:
        # If subject filters are specified, include them
        subject_query = " OR ".join([f'subject:"{s}' for s in GMAIL_SUBJECTS])
        query = f"from:{GMAIL_SENDER} ({subject_query})"
    else:
        # Match all emails from this sender
        query = f"from:{GMAIL_SENDER}"

    logger.info(f"Gmail search query: {query}")
    logger.info("")

    try:
        messages = await gmail_client.search_messages(
            query=query,
            max_results=MAX_EMAILS or 100,
        )

        logger.info(f"✅ Found {len(messages)} matching emails")
        logger.info("")
        return messages

    except Exception as e:
        logger.error(f"❌ Failed to fetch emails: {e}")
        return []


async def filter_and_import_articles(
    gmail_service: GmailService,
    data_service,
    metadata_service: MetadataService,
    message_ids: list[str],
):
    """
    Extract articles from emails, filter, lookup metadata, and import to Zotero.

    Args:
        gmail_service: GmailService instance
        data_service: DataAccessService instance
        metadata_service: MetadataService instance
        message_ids: List of Gmail message IDs

    Returns:
        Dictionary with import statistics
    """
    logger.info("=" * 70)
    logger.info("Processing emails and importing to Zotero...")
    logger.info("=" * 70)
    logger.info("")

    # Initialize RSS filter
    rss_filter = RSSFilter()

    # Extract keywords for filtering (async operation)
    logger.info("Extracting keywords from RSS_PROMPT...")
    keywords = None

    try:
        keywords = await rss_filter.extract_keywords()
        logger.info(f"✅ Extracted {len(keywords)} keywords")
        if DEBUG:
            logger.debug(f"   Keywords: {', '.join(keywords)}")
    except Exception as e:
        logger.error(f"❌ Failed to extract keywords: {e}")
        keywords = None

    stats: ImportStats = {
        "emails_processed": 0,
        "articles_extracted": 0,
        "articles_imported": 0,
        "articles_filtered": 0,
        "metadata_found": 0,
        "metadata_not_found": 0,
        "errors": [],
    }

    for msg_id in message_ids:
        stats["emails_processed"] += 1

        try:
            # Get message headers
            headers = await gmail_service.gmail_client.get_message_headers(msg_id)
            subject = headers.get("Subject", "(no subject)")
            date = headers.get("Date", "(no date)")

            logger.info(f"Processing email: {subject[:60]}...")
            logger.info(f"  Date: {date}")

            # Get message body
            html_body, _ = await gmail_service.gmail_client.get_message_body(msg_id)

            if not html_body:
                logger.warning("  ⚠️  No HTML content found, skipping")
                continue

            # Extract items from email
            email_items = gmail_service.parse_html_table(
                html_body, email_id=msg_id, email_subject=subject
            )

            if not email_items:
                logger.warning("  ⚠️  No articles found in email")
                continue

            logger.info(f"  Extracted {len(email_items)} articles")

            # Filter articles using RSS keywords
            if keywords:
                filtered_items = []
                for item in email_items:
                    # Convert EmailItem to RSSItem format for filtering
                    rss_item = gmail_service._email_item_to_rss_item(item)

                    # Filter using keywords
                    relevant, irrelevant = rss_filter.filter_items([rss_item], keywords)

                    if relevant:
                        filtered_items.append(item)
                        logger.info(f"    ✓ {item.title[:60]}...")
                    else:
                        stats["articles_filtered"] += 1
                        logger.debug(f"    ✗ {item.title[:60]}... (filtered out)")
            else:
                # No keywords, use all items
                filtered_items = email_items
                logger.info(
                    f"  Using all {len(email_items)} extracted articles (no keywords available)"
                )

            if not filtered_items:
                logger.info("  ⚠️  No articles passed filter, skipping email")
                continue

            # Import to Zotero with metadata lookup
            if not DRY_RUN:
                imported, meta_found, meta_not_found = await import_articles_to_zotero(
                    data_service, metadata_service, filtered_items, subject
                )
                stats["articles_imported"] += imported
                stats["metadata_found"] += meta_found
                stats["metadata_not_found"] += meta_not_found
            else:
                logger.info(f"  [DRY RUN] Would import {len(filtered_items)} articles")
                stats["articles_imported"] += len(filtered_items)

            stats["articles_extracted"] += len(email_items)

            logger.info("")

        except Exception as e:
            error_msg = f"Failed to process email {msg_id}: {e}"
            logger.error(f"  ❌ {error_msg}")
            stats["errors"].append(error_msg)

    return stats


async def import_articles_to_zotero(
    data_service,
    metadata_service: MetadataService,
    email_items: list,
    email_subject: str,
) -> tuple[int, int, int]:
    """
    Import articles to Zotero with metadata lookup from Crossref/OpenAlex.

    This follows the RSS data cleaning pattern:
    1. Clean the title
    2. Check for duplicates (by URL and title)
    3. Lookup complete metadata from Crossref/OpenAlex
    4. Create Zotero item with rich metadata

    Args:
        data_service: DataAccessService instance
        metadata_service: MetadataService instance
        email_items: List of EmailItem objects
        email_subject: Email subject for note reference

    Returns:
        Tuple of (imported_count, metadata_found_count, metadata_not_found_count)
    """
    # Find or create collection
    logger.info(f"Looking for collection: '{ZOTERO_COLLECTION_NAME}'...")
    collection_matches = await data_service.find_collection_by_name(
        ZOTERO_COLLECTION_NAME
    )

    if not collection_matches:
        logger.info(f"Collection not found, creating: '{ZOTERO_COLLECTION_NAME}'...")
        collection = await data_service.item_service.create_collection(
            ZOTERO_COLLECTION_NAME
        )
        collection_key = collection.get("key", "")
    else:
        collection = collection_matches[0]
        collection_data = collection.get("data", {})
        collection_key = collection_data.get("key", "")

    logger.info(f"  Collection key: {collection_key}")
    logger.info("")

    # Prepare items for Zotero
    imported_count = 0
    metadata_found = 0
    metadata_not_found = 0

    for email_item in email_items:
        try:
            # 1. Clean the title (following RSS pattern)
            cleaned_title = clean_title(email_item.title)
            logger.info(f"    Processing: {cleaned_title[:60]}...")

            # 2. Check for duplicates (can be skipped with SKIP_DUP_CHECK=true)
            if not SKIP_DUP_CHECK:
                try:
                    # Check by URL
                    existing_by_url = await data_service.search_items(
                        query=email_item.link, limit=1, qmode="everything"
                    )
                    if existing_by_url and len(existing_by_url) > 0:
                        logger.info("      ⊘ Duplicate (URL exists)")
                        continue

                    # Check by title
                    existing_by_title = await data_service.search_items(
                        query=cleaned_title, qmode="titleCreatorYear", limit=1
                    )
                    if existing_by_title and len(existing_by_title) > 0:
                        found_title = existing_by_title[0].title
                        if found_title.lower() == cleaned_title.lower():
                            logger.info("      ⊘ Duplicate (Title exists)")
                            continue
                except Exception as e:
                    logger.warning(f"      ⚠ Duplicate check failed: {e}")
                    # Continue with import even if dup check fails
            else:
                logger.debug("      (Skipping duplicate check)")

            # 3. Lookup complete metadata from Crossref/OpenAlex
            logger.info("      ? Looking up metadata...")
            metadata = await metadata_service.lookup_metadata(
                cleaned_title, email_item.authors
            )

            if metadata is not None:
                metadata_found += 1
                logger.info(
                    f"      + Found metadata (DOI: {metadata.doi}, "
                    f"Source: {metadata.source})"
                )

                # Use metadata to create Zotero item
                item_data = metadata.to_zotero_item(collection_key)

                # Add source info to extra field
                extra_info = (
                    f"Source: Google Scholar Alerts\nEmail Subject: {email_subject}"
                )
                if item_data.get("extra"):
                    item_data["extra"] = f"{item_data['extra']}\n{extra_info}"
                else:
                    item_data["extra"] = extra_info

                # Override URL with original link if metadata URL is just DOI
                if email_item.link and not email_item.link.startswith(
                    "https://doi.org"
                ):
                    item_data["url"] = email_item.link

            else:
                metadata_not_found += 1
                logger.info("      - Metadata not found, using email data")

                # Fallback: create item from email data
                creators: list[dict[str, str]] = []
                item_data = {
                    "itemType": "journalArticle",
                    "title": cleaned_title,
                    "url": email_item.link,
                    "abstractNote": email_item.abstract or "",
                    "accessDate": datetime.now().strftime("%Y-%m-%d"),
                    "collections": [collection_key],
                    "extra": f"Source: Google Scholar Alerts\nEmail Subject: {email_subject}",
                    "creators": creators,
                }

                # Parse authors if available
                if email_item.authors:
                    author_list = email_item.authors.split(";")
                    for author_name in author_list:
                        author_name = author_name.strip()
                        if author_name:
                            creators.append(
                                {"creatorType": "author", "name": author_name}
                            )

                # Add DOI if available in email
                if email_item.doi:
                    item_data["DOI"] = email_item.doi

            # 4. Create item in Zotero
            if not DRY_RUN:
                result = await data_service.create_items([item_data])

                # Debug: log the full result for analysis
                logger.debug(f"      Zotero API result: {result}")

                # Handle different response formats
                item_key = None
                if result:
                    if isinstance(result, dict):
                        # Format 1: {"successful": {"0": {"key": "ABC123", ...}}}
                        if "successful" in result:
                            successful = result.get("successful", {})
                            if isinstance(successful, dict) and successful:
                                first_key = list(successful.keys())[0]
                                item_data_result = successful[first_key]
                                if isinstance(item_data_result, dict):
                                    item_key = item_data_result.get("key")
                            elif isinstance(successful, list) and successful:
                                item_key = successful[0]
                        # Format 2: {"key": "ABC123", ...}
                        elif "key" in result:
                            item_key = result.get("key")
                        # Check for failures
                        elif "failed" in result:
                            failed = result.get("failed", {})
                            if failed:
                                first_fail = list(failed.values())[0]
                                error_msg = first_fail.get("message", "Unknown error")
                                logger.warning(f"      ✗ API error: {error_msg}")
                                continue

                if item_key:
                    imported_count += 1
                    logger.info(f"      ✓ Imported (key: {item_key})")
                else:
                    logger.warning(f"      ✗ No item key returned. Response: {result}")
            else:
                imported_count += 1
                logger.info("      [DRY RUN] Would import")

            # Rate limiting
            await asyncio.sleep(0.5)

        except Exception as e:
            logger.error(f"      ❌ Failed to import '{email_item.title[:40]}': {e}")

    return imported_count, metadata_found, metadata_not_found


async def main():
    """Main execution function."""
    logger.info("=" * 70)
    logger.info("Google Scholar Alerts → Zotero Import")
    logger.info("=" * 70)
    logger.info("")

    # Show runtime options
    logger.info(
        f"Mode: {'DRY RUN (preview only)' if DRY_RUN else 'LIVE (will import)'}"
    )
    logger.info(f"Debug: {DEBUG}")
    logger.info("")

    # Verify environment variables
    required_vars = {
        "ZOTERO_LIBRARY_ID": os.getenv("ZOTERO_LIBRARY_ID"),
        "ZOTERO_API_KEY": os.getenv("ZOTERO_API_KEY"),
        "RSS_PROMPT": os.getenv("RSS_PROMPT"),
    }

    missing = [k for k, v in required_vars.items() if not v]
    if missing:
        logger.error(f"Missing required environment variables: {', '.join(missing)}")
        sys.exit(1)

    # Ensure ZOTERO_LOCAL is false to use Web API
    os.environ["ZOTERO_LOCAL"] = "false"
    logger.info("Using Zotero Web API (ZOTERO_LOCAL=false)")
    logger.info("")

    try:
        # Initialize services
        logger.info("Initializing services...")
        gmail_client = GmailClient()
        gmail_service = GmailService()
        data_service = get_data_service()
        metadata_service = MetadataService()
        logger.info("Services initialized successfully")
        logger.info("")

        # Fetch Google Scholar emails
        messages = await fetch_google_scholar_emails(gmail_client)

        if not messages:
            logger.info("⚠️  No matching emails found")
            logger.info("")
            logger.info("Possible reasons:")
            logger.info("  1. No Google Scholar Alert emails in your inbox")
            logger.info("  2. Emails are in trash/spam folders")
            logger.info("  3. Subject or sender filters don't match")
            logger.info("")
            return

        # Extract message IDs
        message_ids = [msg["id"] for msg in messages]

        # Process and import articles
        stats = await filter_and_import_articles(
            gmail_service, data_service, metadata_service, message_ids
        )

        # Print summary
        logger.info("")
        logger.info("=" * 70)
        logger.info("Import Summary")
        logger.info("=" * 70)
        logger.info(f"Emails processed:      {stats['emails_processed']}")
        logger.info(f"Articles extracted:    {stats['articles_extracted']}")
        logger.info(f"Articles filtered:     {stats['articles_filtered']}")
        logger.info(f"Metadata found:        {stats['metadata_found']}")
        logger.info(f"Metadata not found:    {stats['metadata_not_found']}")
        logger.info(f"Articles imported:     {stats['articles_imported']}")
        logger.info(f"Errors encountered:    {len(stats['errors'])}")

        if stats["errors"]:
            logger.info("")
            logger.info("Errors:")
            for error in stats["errors"]:
                logger.info(f"  - {error}")

        logger.info("=" * 70)
        logger.info("")

        if stats["articles_imported"] > 0:
            logger.info(
                f"✅ Successfully imported {stats['articles_imported']} articles!"
            )
        else:
            logger.info("⚠️  No articles were imported")

        if DRY_RUN:
            logger.info("")
            logger.info("⚠️  DRY RUN MODE - No actual changes made to Zotero")
            logger.info(
                "    Remove DRY_RUN=true from .env or environment to import for real"
            )

    except Exception as e:
        logger.error(f"❌ Fatal error: {e}")
        logger.debug("Error details:", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
