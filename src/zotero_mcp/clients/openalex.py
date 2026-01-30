"""
OpenAlex API Client - Query academic metadata by title or DOI.

OpenAlex is an open catalog of the global research system.
This client provides async access to their free API.

API Docs: https://docs.openalex.org/
"""

from dataclasses import dataclass
import logging
import re
from typing import Any
from urllib.parse import quote

import httpx

logger = logging.getLogger(__name__)

# OpenAlex API base URL
OPENALEX_API_BASE = "https://api.openalex.org"

# Request timeout in seconds (increased to handle slow network conditions)
REQUEST_TIMEOUT = 45.0

# User-Agent for polite pool
USER_AGENT = (
    "zotero-mcp/1.0 (https://github.com/liuchzzyy/zotero-mcp-rss; "
    "mailto:support@example.com)"
)

# API configuration
MAX_RETRIES = 3
RETRY_DELAY = 1.0


@dataclass
class OpenAlexWork:
    """Represents a work (article) from OpenAlex."""

    doi: str
    title: str
    authors: list[str]
    journal: str | None
    year: int | None
    volume: str | None
    issue: str | None
    pages: str | None
    abstract: str | None
    url: str | None
    item_type: str
    raw_data: dict[str, Any]

    @classmethod
    def from_api_response(cls, data: dict[str, Any]) -> "OpenAlexWork":
        """Parse an OpenAlex API response into an OpenAlexWork object."""
        # Extract DOI
        doi_url = data.get("doi", "")
        doi = doi_url.split("doi.org/")[-1] if "doi.org/" in doi_url else ""

        # Extract title
        title = data.get("title", "") or data.get("display_name", "")

        # Extract authors
        authors = []
        for authorship in data.get("authorships", []):
            author_data = authorship.get("author", {})
            name = author_data.get("display_name", "")
            if name:
                authors.append(name)

        # Extract journal from primary_location
        journal = None
        primary_location = data.get("primary_location", {})
        if primary_location:
            source = primary_location.get("source", {})
            if source:
                journal = source.get("display_name")

        # Extract year
        year = data.get("publication_year")

        # Extract volume, issue, pages from primary_location
        volume = None
        issue = None
        pages = None
        if primary_location:
            volume = primary_location.get("volume")
            issue = primary_location.get("issue")
            pages = primary_location.get("pages")

        # Extract abstract from inverted index
        abstract = None
        abstract_inverted_index = data.get("abstract_inverted_index")
        if abstract_inverted_index:
            try:
                word_positions = []
                for word, positions in abstract_inverted_index.items():
                    for pos in positions:
                        word_positions.append((pos, word))
                word_positions.sort(key=lambda x: x[0])
                abstract = " ".join([wp[1] for wp in word_positions])
            except Exception:
                pass

        # Extract URL
        url = data.get("doi") or data.get("id")

        # Map OpenAlex type to Zotero type
        openalex_type = data.get("type", "")
        type_mapping = {
            "article": "journalArticle",
            "book": "book",
            "book-chapter": "bookSection",
            "dissertation": "thesis",
            "proceedings": "conferencePaper",
            "proceedings-article": "conferencePaper",
            "report": "report",
            "dataset": "dataset",
        }
        item_type = type_mapping.get(openalex_type, "journalArticle")

        return cls(
            doi=doi,
            title=title,
            authors=authors,
            journal=journal,
            year=year,
            volume=volume,
            issue=issue,
            pages=pages,
            abstract=abstract,
            url=url,
            item_type=item_type,
            raw_data=data,
        )

    def to_zotero_item(self) -> dict[str, Any]:
        """Convert to Zotero item template format."""
        creators: list[dict[str, str]] = []
        item = {
            "itemType": self.item_type,
            "title": self.title,
            "creators": creators,
        }

        # Add DOI
        if self.doi:
            item["DOI"] = self.doi
            if not self.url:
                item["url"] = f"https://doi.org/{self.doi}"

        # Add URL
        if self.url:
            item["url"] = self.url

        # Add authors
        for author in self.authors:
            # Try to parse "Last, First" format
            if ", " in author:
                parts = author.split(", ", 1)
                creators.append(
                    {
                        "creatorType": "author",
                        "lastName": parts[0],
                        "firstName": parts[1] if len(parts) > 1 else "",
                    }
                )
            else:
                creators.append(
                    {
                        "creatorType": "author",
                        "name": author,
                    }
                )

        # Add optional fields
        if self.journal:
            item["publicationTitle"] = self.journal
        if self.year:
            item["date"] = str(self.year)
        if self.volume:
            item["volume"] = self.volume
        if self.issue:
            item["issue"] = self.issue
        if self.pages:
            item["pages"] = self.pages
        if self.abstract:
            item["abstractNote"] = self.abstract

        return item


class OpenAlexClient:
    """Client for querying the OpenAlex API."""

    def __init__(self, email: str | None = None):
        """
        Initialize the OpenAlex client.

        Args:
            email: Optional email for polite pool access
        """
        self.email = email
        self._client: httpx.AsyncClient | None = None

    @property
    def headers(self) -> dict[str, str]:
        """Build request headers."""
        headers = {"User-Agent": USER_AGENT}
        if self.email:
            headers["mailto"] = self.email
        return headers

    async def _get_client(self) -> httpx.AsyncClient:
        """Get or create the HTTP client."""
        if self._client is None:
            self._client = httpx.AsyncClient(
                base_url=OPENALEX_API_BASE,
                headers=self.headers,
                timeout=REQUEST_TIMEOUT,
            )
        return self._client

    async def close(self) -> None:
        """Close the HTTP client."""
        if self._client:
            await self._client.aclose()
            self._client = None

    async def search_by_title(
        self,
        title: str,
        per_page: int = 5,
    ) -> list[OpenAlexWork]:
        """
        Search for works by title.

        Args:
            title: Title to search for
            per_page: Maximum number of results to return

        Returns:
            List of OpenAlexWork objects
        """
        client = await self._get_client()

        try:
            response = await client.get(
                "/works",
                params={
                    "search": title,
                    "per_page": per_page,
                },
            )
            response.raise_for_status()
            data = response.json()

            results = data.get("results", [])
            works = [OpenAlexWork.from_api_response(item) for item in results]

            logger.info(
                f"OpenAlex search for '{title[:50]}...' returned {len(works)} results"
            )
            return works

        except httpx.HTTPError as e:
            logger.error(f"OpenAlex API error: {e}")
            return []
        except Exception as e:
            logger.error(f"Error parsing OpenAlex response: {e}")
            return []

    async def get_by_doi(self, doi: str) -> OpenAlexWork | None:
        """
        Get work metadata by DOI.

        Args:
            doi: DOI to lookup (e.g., "10.1000/xyz123")

        Returns:
            OpenAlexWork object or None if not found
        """
        client = await self._get_client()

        # Clean DOI (remove URL prefix if present)
        if doi.startswith("https://doi.org/"):
            doi = doi[16:]
        elif doi.startswith("http://doi.org/"):
            doi = doi[15:]
        elif doi.startswith("doi:"):
            doi = doi[4:]

        # OpenAlex expects DOI in URL format
        doi_url = f"https://doi.org/{doi}"

        try:
            response = await client.get(f"/works/{quote(doi_url, safe='')}")
            response.raise_for_status()
            data = response.json()

            if data:
                work = OpenAlexWork.from_api_response(data)
                logger.info(f"OpenAlex DOI lookup for '{doi}' successful")
                return work
            return None

        except httpx.HTTPStatusError as e:
            if e.response.status_code == 404:
                logger.warning(f"DOI not found in OpenAlex: {doi}")
            else:
                logger.error(f"OpenAlex API error: {e}")
            return None
        except Exception as e:
            logger.error(f"Error parsing OpenAlex response: {e}")
            return None

    async def find_best_match(
        self,
        title: str,
        threshold: float = 0.8,
    ) -> OpenAlexWork | None:
        """
        Find the best matching work for a title.

        Uses fuzzy title matching to find the most relevant result.

        Args:
            title: Title to search for
            threshold: Minimum similarity threshold (0-1)

        Returns:
            Best matching OpenAlexWork or None if no good match
        """
        works = await self.search_by_title(title, per_page=5)

        if not works:
            return None

        # Simple similarity check: normalize and compare
        def normalize(s: str) -> str:
            """Normalize string for comparison."""
            s = s.lower()
            s = re.sub(r"[^\w\s]", "", s)
            s = re.sub(r"\s+", " ", s).strip()
            return s

        def similarity(s1: str, s2: str) -> float:
            """Calculate simple word-based similarity."""
            words1 = set(normalize(s1).split())
            words2 = set(normalize(s2).split())
            if not words1 or not words2:
                return 0.0
            intersection = words1 & words2
            union = words1 | words2
            return len(intersection) / len(union)

        # Find best match
        best_work = None
        best_score = 0.0

        for work in works:
            score = similarity(title, work.title)
            if score > best_score:
                best_score = score
                best_work = work

        if best_work and best_score >= threshold:
            logger.info(
                f"Best OpenAlex match: '{best_work.title[:50]}...' (score: {best_score:.2f})"
            )
            return best_work

        logger.warning(
            f"No good OpenAlex match for '{title[:50]}...' (best score: {best_score:.2f})"
        )
        return None
