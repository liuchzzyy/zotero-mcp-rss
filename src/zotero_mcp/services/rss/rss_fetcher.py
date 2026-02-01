"""RSS feed fetching and parsing module."""

import asyncio
from datetime import datetime
import logging
import time
from typing import Any
from xml.etree import ElementTree as ET

import feedparser

from zotero_mcp.models.rss import RSSFeed, RSSItem
from zotero_mcp.utils.helpers import DOI_PATTERN

logger = logging.getLogger(__name__)

USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
MAX_RETRIES = 5


class RSSFetcher:
    """Handles RSS feed fetching and parsing operations."""

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
        """Helper to safely get value from entry which might be dict or object."""
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
        """Synchronously fetch and parse RSS feed."""
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
