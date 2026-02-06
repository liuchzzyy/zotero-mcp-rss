"""RSS feed source for paper collection."""

import logging
from datetime import date
from typing import List, Optional
from urllib.parse import urlparse

import feedparser
import httpx

from paper_feed.core.base import PaperSource
from paper_feed.core.models import PaperItem
from paper_feed.sources.rss_parser import RSSParser

logger = logging.getLogger(__name__)


class RSSSource(PaperSource):
    """Paper source for RSS feeds.

    Fetches papers from RSS feeds (arXiv, bioRxiv, Nature, Science, etc.)
    and converts entries to PaperItem objects.

    Attributes:
        source_name: Name of the RSS source (auto-detected or provided)
        source_type: Always "rss" for this class
        feed_url: URL of the RSS feed
        user_agent: HTTP User-Agent header for requests
        timeout: Request timeout in seconds
    """

    source_name: str = "rss"
    source_type: str = "rss"

    def __init__(
        self,
        feed_url: str,
        source_name: Optional[str] = None,
        user_agent: str = "paper-feed/1.0",
        timeout: int = 30,
    ):
        """Initialize RSS source.

        Args:
            feed_url: URL of the RSS feed
            source_name: Optional source name (auto-detected from URL if not provided)
            user_agent: HTTP User-Agent header
            timeout: Request timeout in seconds
        """
        self.feed_url = feed_url
        self.user_agent = user_agent
        self.timeout = timeout
        self.parser = RSSParser()

        # Auto-detect source name if not provided
        if source_name:
            self.source_name = source_name
        else:
            self.source_name = self._detect_source_name(feed_url)

    def _detect_source_name(self, url: str) -> str:
        """Detect source name from feed URL.

        Args:
            url: RSS feed URL

        Returns:
            Detected source name (e.g., "arXiv", "Nature")
        """
        # Parse URL
        parsed = urlparse(url)
        netloc = parsed.netloc.lower()

        # Check for known sources
        if "arxiv.org" in netloc:
            return "arXiv"
        elif "biorxiv.org" in netloc:
            return "bioRxiv"
        elif "medrxiv.org" in netloc:
            return "medRxiv"
        elif "nature.com" in netloc:
            return "Nature"
        elif "science.org" in netloc:
            return "Science"
        elif "pnas.org" in netloc:
            return "PNAS"
        elif "acs.org" in netloc:
            return "ACS"
        elif "rsc.org" in netloc:
            return "RSC"
        elif "springer.com" in netloc or "springernature.com" in netloc:
            return "Springer"
        elif "wiley.com" in netloc:
            return "Wiley"
        elif "elsevier.com" in netloc:
            return "Elsevier"
        elif "cell.com" in netloc:
            return "Cell"
        elif "sciencedirect.com" in netloc:
            return "ScienceDirect"
        else:
            # Fallback to domain name
            return netloc.replace("www.", "").split(".")[0].capitalize()

    async def fetch_papers(
        self, limit: Optional[int] = None, since: Optional[date] = None
    ) -> List[PaperItem]:
        """Fetch papers from RSS feed.

        Args:
            limit: Maximum number of papers to return (None = no limit)
            since: Only return papers published after this date (None = no filter)

        Returns:
            List of PaperItem objects
        """
        papers = []

        try:
            # Fetch RSS feed content
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.get(
                    self.feed_url,
                    headers={"User-Agent": self.user_agent},
                    follow_redirects=True,
                )
                response.raise_for_status()
                feed_content = response.text

            # Parse RSS feed
            # Use asyncio.to_thread to run feedparser in a thread (it's synchronous)
            import asyncio

            feed = await asyncio.to_thread(feedparser.parse, feed_content)

            # Check for feed parsing errors
            if hasattr(feed, "bozo") and feed.bozo:
                logger.warning(
                    f"Potential issue parsing feed {self.feed_url}: "
                    f"{getattr(feed, 'bozo_exception', 'Unknown error')}"
                )

            # Process entries
            entries = getattr(feed, "entries", [])
            logger.info(
                f"Fetched {len(entries)} entries from {self.source_name} "
                f"(limit={limit}, since={since})"
            )

            for entry in entries:
                try:
                    # Parse entry to PaperItem
                    paper = self.parser.parse(entry, self.source_name)

                    # Apply date filter
                    if since and paper.published_date:
                        if paper.published_date < since:
                            continue  # Skip papers older than 'since'

                    papers.append(paper)

                    # Apply limit
                    if limit and len(papers) >= limit:
                        break

                except ValueError as e:
                    logger.warning(
                        f"Skipping invalid entry from {self.source_name}: {e}"
                    )
                    continue
                except Exception as e:
                    logger.error(
                        f"Error parsing entry from {self.source_name}: {e}",
                        exc_info=True,
                    )
                    continue

            logger.info(
                f"Successfully parsed {len(papers)} papers from {self.source_name}"
            )

        except httpx.HTTPStatusError as e:
            logger.error(
                f"HTTP error fetching {self.feed_url}: {e.response.status_code}"
            )
        except httpx.RequestError as e:
            logger.error(f"Request error fetching {self.feed_url}: {e}")
        except Exception as e:
            logger.error(
                f"Unexpected error fetching from {self.source_name}: {e}",
                exc_info=True,
            )

        return papers
