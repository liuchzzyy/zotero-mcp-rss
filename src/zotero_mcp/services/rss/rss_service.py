import asyncio
from datetime import datetime, timedelta
import logging
import time
from typing import TYPE_CHECKING, Any
from xml.etree import ElementTree as ET

import feedparser

from zotero_mcp.models.rss import RSSFeed, RSSItem, RSSProcessResult
from zotero_mcp.utils.helpers import DOI_PATTERN
from zotero_mcp.utils.helpers import clean_title as helper_clean_title

if TYPE_CHECKING:
    from zotero_mcp.services.data_access import DataAccessService
    from zotero_mcp.services.metadata import MetadataService

logger = logging.getLogger(__name__)


USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
MAX_RETRIES = 5

# Zotero limits
MAX_CREATOR_NAME_LENGTH = 210  # Zotero sync limit for single creator name
MAX_CREATORS = 10  # Maximum number of creators to include


def _parse_creator_string(author_string: str) -> list[dict[str, str]]:
    """
    Parse author string and split into individual creators.

    Handles comma-separated author lists and truncates if necessary
    to avoid Zotero HTTP 413 errors.

    Args:
        author_string: Raw author string from RSS feed

    Returns:
        List of creator dicts with 'creatorType' and 'name' keys
    """
    if not author_string:
        return []

    creators = []

    # Try to split by common separators (comma, semicolon, newline)
    # Handle both "Author1, Author2, Author3" and "Author1; Author2; Author3"
    parts = []
    for sep in [", ", "; ", "\n", ","]:
        if sep in author_string:
            parts = [p.strip() for p in author_string.split(sep) if p.strip()]
            break

    # If no separator found, treat as single author
    if not parts:
        parts = [author_string.strip()]

    # Limit number of creators
    if len(parts) > MAX_CREATORS:
        logger.warning(
            f"  ! Author list too long ({len(parts)} authors), "
            f"truncating to {MAX_CREATORS} + et al."
        )
        parts = parts[:MAX_CREATORS]

    # Create creator dicts, ensuring each name is within length limit
    for author in parts:
        author = author.strip()
        if len(author) > MAX_CREATOR_NAME_LENGTH:
            author = author[: MAX_CREATOR_NAME_LENGTH - 4] + "..."
            logger.warning(f"  ! Author name too long, truncated to: {author}")

        if author:  # Only add non-empty names
            creators.append({"creatorType": "author", "name": author})

    # Add "et al." if we truncated the list
    if len(creators) == MAX_CREATORS:
        # Check if original had more authors
        original_count = len(
            [p.strip() for p in author_string.split(",") if p.strip()]
            if "," in author_string or ";" in author_string
            else [author_string.strip()]
        )
        if original_count > MAX_CREATORS:
            # Add et al. as last creator
            creators[-1]["name"] = creators[-1]["name"] + " et al."

    return creators


class RSSService:
    """Service for fetching and parsing RSS feeds."""

    async def fetch_feed(self, url: str) -> RSSFeed | None:
        """Fetch and parse a single RSS feed asynchronously."""
        for attempt in range(1, MAX_RETRIES + 1):
            feed = await asyncio.to_thread(self._fetch_sync, url)

            if feed:
                return feed

            # If feed is None, it means an exception occurred.
            if attempt < MAX_RETRIES:
                wait_time = attempt * 1  # Linear backoff: 1s, 2s, 3s, 4s
                logger.warning(
                    f"Attempt {attempt}/{MAX_RETRIES} failed for {url}. Retrying in {wait_time}s..."
                )
                await asyncio.sleep(wait_time)
            else:
                logger.error(f"Failed to fetch {url} after {MAX_RETRIES} attempts")

        return None

    def _get_entry_value(self, entry: Any, key: str, default: Any = None) -> Any:
        """Helper to safely get value from entry which might be dict or object"""
        if isinstance(entry, dict):
            return entry.get(key, default)
        return getattr(entry, key, default)

    def _extract_doi(self, entry: Any) -> str | None:
        """Extract DOI from entry metadata or link."""
        # 1. Try common feedparser fields for DOI
        for key in ["prism_doi", "dc_identifier"]:
            val = self._get_entry_value(entry, key)
            if val and isinstance(val, str):
                # Clean up if it contains doi: prefix
                if val.lower().startswith("doi:"):
                    val = val[4:].strip()
                if DOI_PATTERN.match(val):
                    return val

        # 2. Try to find DOI in link or guid
        for key in ["link", "id"]:
            val = self._get_entry_value(entry, key)
            if val and isinstance(val, str):
                match = DOI_PATTERN.search(val)
                if match:
                    return match.group(0)

        return None

    def _fetch_sync(self, url: str) -> RSSFeed | None:
        try:
            # Type ignore because feedparser returns a complex object
            # Use browser User-Agent to avoid IncompleteRead and SSL errors with some publishers
            feed: Any = feedparser.parse(url, agent=USER_AGENT)

            # Check for bozo bit (malformed XML), but feedparser often recovers
            if hasattr(feed, "bozo") and feed.bozo:
                logger.warning(
                    f"Potential issue parsing feed {url}: {getattr(feed, 'bozo_exception', 'Unknown error')}"
                )

            items = []
            entries = getattr(feed, "entries", [])

            for entry in entries:
                pub_date = None
                published_parsed = self._get_entry_value(entry, "published_parsed")

                # feedparser.parsed returns a time.struct_time, but type checker might not know
                if published_parsed and isinstance(published_parsed, time.struct_time):
                    pub_date = datetime.fromtimestamp(time.mktime(published_parsed))
                else:
                    updated_parsed = self._get_entry_value(entry, "updated_parsed")
                    if updated_parsed and isinstance(updated_parsed, time.struct_time):
                        pub_date = datetime.fromtimestamp(time.mktime(updated_parsed))

                # Extract simple content
                summary = self._get_entry_value(entry, "summary")
                description = self._get_entry_value(entry, "description")
                content_val = (
                    summary if summary else (description if description else "")
                )

                # Extract link, id, author
                title_val = self._get_entry_value(entry, "title", "No Title")
                link_val = self._get_entry_value(entry, "link", "")
                author_val = self._get_entry_value(entry, "author")
                guid_val = self._get_entry_value(entry, "id", link_val)
                doi_val = self._extract_doi(entry)

                # Get feed title safely
                feed_title = "Unknown Feed"
                feed_obj = getattr(feed, "feed", None)
                if feed_obj:
                    feed_title = self._get_entry_value(feed_obj, "title", feed_title)

                items.append(
                    RSSItem(
                        title=str(title_val),
                        link=str(link_val),
                        description=str(content_val) if content_val else None,
                        pub_date=pub_date,
                        author=str(author_val) if author_val else None,
                        guid=str(guid_val),
                        source_url=url,
                        source_title=str(feed_title),
                        doi=doi_val,
                    )
                )

            # Get feed metadata safely
            feed_title = "Unknown Feed"
            feed_link = url
            feed_desc = None

            feed_obj = getattr(feed, "feed", None)
            if feed_obj:
                feed_title = str(self._get_entry_value(feed_obj, "title", feed_title))
                feed_link = str(self._get_entry_value(feed_obj, "link", url))
                desc_val = self._get_entry_value(feed_obj, "description")
                if desc_val:
                    feed_desc = str(desc_val)

            return RSSFeed(
                title=feed_title,
                link=feed_link,
                description=feed_desc,
                items=items,
                last_updated=datetime.now(),
            )
        except Exception as e:
            logger.error(f"Error fetching RSS feed {url}: {e}")
            return None

    async def parse_opml(self, content: str) -> list[str]:
        """Parse OPML content to extract feed URLs."""
        try:
            urls = []
            root = ET.fromstring(content)
            # Find all outline elements with xmlUrl attribute
            for outline in root.findall(".//outline[@xmlUrl]"):
                url = outline.get("xmlUrl")
                if url:
                    urls.append(url)
            return urls
        except Exception as e:
            logger.error(f"Error parsing OPML: {e}")
            return []

    async def fetch_feeds_from_opml(self, opml_path: str) -> list[RSSFeed]:
        """Read OPML file and fetch all feeds."""
        try:
            with open(opml_path, encoding="utf-8") as f:
                content = f.read()

            urls = await self.parse_opml(content)
            tasks = [self.fetch_feed(url) for url in urls]
            results = await asyncio.gather(*tasks, return_exceptions=True)

            feeds = []
            for res in results:
                if isinstance(res, RSSFeed):
                    feeds.append(res)
                elif isinstance(res, Exception):
                    logger.error(f"Task failed: {res}")

            return feeds
        except Exception as e:
            logger.error(f"Error processing OPML file {opml_path}: {e}")
            return []

    @staticmethod
    def clean_title(title: str) -> str:
        """
        Clean article title by removing common prefixes.

        Delegates to utils.helpers.clean_title for backward compatibility.
        """
        return helper_clean_title(title)

    async def _zotero_api_call_with_retry(
        self,
        func,
        *,
        max_retries: int = 3,
        base_delay: float = 2.0,
        description: str = "Zotero API call",
    ):
        """Execute a Zotero API call with retry and exponential backoff."""
        for attempt in range(max_retries):
            try:
                return await func()
            except Exception as e:
                error_msg = str(e).lower()
                is_retryable = any(
                    keyword in error_msg
                    for keyword in ["timed out", "timeout", "503", "429", "connection"]
                )
                if not is_retryable or attempt == max_retries - 1:
                    raise
                delay = base_delay * (2**attempt)
                logger.warning(
                    f"  ↻ {description} failed (attempt {attempt + 1}/{max_retries}): "
                    f"{e}. Retrying in {delay:.0f}s..."
                )
                await asyncio.sleep(delay)
        # Unreachable, but satisfies type checker
        raise RuntimeError(f"{description} failed after {max_retries} retries")

    async def create_zotero_item(
        self,
        data_service: "DataAccessService",
        metadata_service: "MetadataService",
        rss_item: RSSItem,
        collection_key: str,
    ) -> str | None:
        """Create a Zotero item from an RSS feed item."""
        log_title = rss_item.title
        try:
            cleaned_title = self.clean_title(rss_item.title)
            log_title = cleaned_title

            # 1. Check if item already exists by URL
            existing_by_url = await self._zotero_api_call_with_retry(
                lambda: data_service.search_items(
                    query=rss_item.link, limit=1, qmode="everything"
                ),
                description=f"Search URL '{cleaned_title[:30]}'",
            )
            if existing_by_url and len(existing_by_url) > 0:
                logger.info(f"  ⊘ Duplicate (URL): {cleaned_title[:50]}")
                return None

            # 2. Check if item already exists by Title (fallback)
            existing_by_title = await self._zotero_api_call_with_retry(
                lambda: data_service.search_items(
                    query=cleaned_title, qmode="titleCreatorYear", limit=1
                ),
                description=f"Search title '{cleaned_title[:30]}'",
            )
            if existing_by_title and len(existing_by_title) > 0:
                found_title = existing_by_title[0].title
                if found_title.lower() == cleaned_title.lower():
                    logger.info(f"  ⊘ Duplicate (Title): {cleaned_title[:50]}")
                    return None

            # Try to lookup DOI if not available in RSS
            doi = rss_item.doi
            if not doi:
                logger.info(f"  ? Looking up DOI for: {cleaned_title[:50]}")
                doi = await metadata_service.lookup_doi(cleaned_title, rss_item.author)
                if doi:
                    logger.info(f"  + Found DOI: {doi}")

            # Create item data structure for Zotero
            item_data = {
                "itemType": "journalArticle",
                "title": cleaned_title,
                "url": rss_item.link,
                "publicationTitle": rss_item.source_title,
                "date": rss_item.pub_date.strftime("%Y-%m-%d")
                if rss_item.pub_date
                else "",
                "accessDate": datetime.now().strftime("%Y-%m-%d"),
                "collections": [collection_key],
                "DOI": doi or "",
                "tags": [],
            }

            if rss_item.author:
                item_data["creators"] = _parse_creator_string(rss_item.author)

            result = await self._zotero_api_call_with_retry(
                lambda: data_service.create_items([item_data]),
                description=f"Create item '{cleaned_title[:30]}'",
            )

            # Handle case where result might be an int (HTTP status code) or other unexpected type
            if isinstance(result, int):
                logger.warning(
                    f"  ✗ Failed to create: {cleaned_title[:50]} - HTTP status: {result}"
                )
                return None

            # Ensure result is a dict before accessing dict methods
            if not isinstance(result, dict):
                logger.warning(
                    f"  ✗ Failed to create: {cleaned_title[:50]} - Unexpected result type: {type(result).__name__}"
                )
                return None

            if result and len(result.get("successful", {})) > 0:
                item_key = list(result["successful"].keys())[0]
                logger.info(f"  ✓ Created: {cleaned_title[:50]} (key: {item_key})")
                return item_key
            elif result and len(result.get("success", {})) > 0:
                item_key = list(result["success"].keys())[0]
                logger.info(f"  ✓ Created: {cleaned_title[:50]} (key: {item_key})")
                return item_key
            else:
                logger.warning(
                    f"  ✗ Failed to create: {cleaned_title[:50]} - Result: {result}"
                )
                return None

        except Exception as e:
            logger.error(f"  ✗ Error creating item '{log_title[:50]}': {e}")
            return None

    async def process_rss_workflow(
        self,
        opml_path: str,
        prompt_path: str | None = None,
        collection_name: str = "00_INBOXS",
        days_back: int = 15,
        max_items: int | None = None,
        dry_run: bool = False,
        llm_provider: str = "deepseek",
    ) -> RSSProcessResult:
        """Full RSS fetching and importing workflow."""
        from zotero_mcp.services.data_access import get_data_service
        from zotero_mcp.services.metadata import MetadataService
        from zotero_mcp.services.common import PaperFilter

        result = RSSProcessResult()

        data_service = get_data_service()
        rss_filter = PaperFilter(prompt_file=prompt_path)
        metadata_service = MetadataService()

        # Find collection
        matches = await data_service.find_collection_by_name(collection_name)
        if not matches:
            raise ValueError(f"Collection '{collection_name}' not found")
        collection_key = matches[0].get("data", {}).get("key")

        # Fetch feeds
        feeds = await self.fetch_feeds_from_opml(opml_path)
        result.feeds_fetched = len(feeds)

        # Count total items across all feeds
        total_items = sum(len(feed.items) for feed in feeds)
        result.items_found = total_items

        # Collect and filter by date
        cutoff = datetime.now() - timedelta(days=days_back) if days_back else None

        all_items = []
        for feed in feeds:
            all_items.extend(
                [
                    i
                    for i in feed.items
                    if not i.pub_date or (cutoff is None or i.pub_date >= cutoff)
                ]
            )
        result.items_after_date_filter = len(all_items)

        if not all_items:
            logger.info("No recent items found")
            return result

        # AI filter
        if llm_provider == "claude-cli":
            logger.info("Using Claude CLI for RSS filtering")
            relevant, _, _ = await rss_filter.filter_with_cli(all_items, prompt_path)
        else:
            relevant, _, _ = await rss_filter.filter_with_keywords(
                all_items, prompt_path
            )
        result.items_filtered = len(relevant)

        # Sort and limit
        relevant.sort(key=lambda x: x.pub_date or datetime.min, reverse=True)
        if max_items:
            relevant = relevant[:max_items]

        # Import
        for item in relevant:
            if dry_run:
                logger.info(f"[DRY RUN] Would import: {item.title}")
                continue
            item_key = await self.create_zotero_item(
                data_service, metadata_service, item, collection_key
            )
            if item_key:
                result.items_imported += 1
            else:
                result.items_duplicate += 1
            await asyncio.sleep(0.5)

        return result
