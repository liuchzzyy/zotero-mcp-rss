"""
Crossref API Client - Query academic metadata by title or DOI.

Crossref is a DOI registration agency that provides comprehensive
metadata for scholarly publications. This client uses their free API.

API Docs: https://api.crossref.org/swagger-ui/index.html
"""

from dataclasses import dataclass
import logging
import re
from typing import Any
from urllib.parse import quote

import httpx

logger = logging.getLogger(__name__)

# Crossref API base URL
CROSSREF_API_BASE = "https://api.crossref.org"

# Request timeout in seconds
REQUEST_TIMEOUT = 30.0

# User-Agent for polite pool (faster rate limits)
# See: https://github.com/CrossRef/rest-api-doc#good-manners--more-reliable-service
USER_AGENT = (
    "zotero-mcp/1.0 (https://github.com/54yyyu/zotero-mcp; mailto:support@example.com)"
)


@dataclass
class CrossrefWork:
    """Represents a work (article) from Crossref."""

    doi: str
    title: str
    authors: list[str]
    journal: str
    year: int | None
    volume: str | None
    issue: str | None
    pages: str | None
    abstract: str | None
    url: str | None
    issn: list[str]
    publisher: str | None
    item_type: str
    raw_data: dict[str, Any]

    @classmethod
    def from_api_response(cls, data: dict[str, Any]) -> "CrossrefWork":
        """Parse a Crossref API response into a CrossrefWork object."""
        # Extract DOI
        doi = data.get("DOI", "")

        # Extract title (list of titles, take first)
        titles = data.get("title", [])
        title = titles[0] if titles else ""

        # Extract authors
        authors = []
        for author in data.get("author", []):
            given = author.get("given", "")
            family = author.get("family", "")
            if given and family:
                authors.append(f"{family}, {given}")
            elif family:
                authors.append(family)
            elif author.get("name"):
                authors.append(author.get("name"))

        # Extract journal/container title
        container_titles = data.get("container-title", [])
        journal = container_titles[0] if container_titles else ""

        # Extract year from published date
        year = None
        published = (
            data.get("published")
            or data.get("published-print")
            or data.get("published-online")
        )
        if published and "date-parts" in published:
            date_parts = published["date-parts"]
            if date_parts and date_parts[0]:
                year = date_parts[0][0]

        # Extract volume, issue, pages
        volume = data.get("volume")
        issue = data.get("issue")
        pages = data.get("page")

        # Extract abstract (may contain HTML/XML tags)
        abstract = data.get("abstract", "")
        if abstract:
            # Simple cleanup of JATS XML tags
            abstract = re.sub(r"<[^>]+>", "", abstract).strip()

        # Extract URL
        url = data.get("URL") or (f"https://doi.org/{doi}" if doi else None)

        # Extract ISSN
        issn = data.get("ISSN", [])

        # Extract publisher
        publisher = data.get("publisher")

        # Map Crossref type to Zotero type
        crossref_type = data.get("type", "")
        type_mapping = {
            "journal-article": "journalArticle",
            "proceedings-article": "conferencePaper",
            "book-chapter": "bookSection",
            "book": "book",
            "report": "report",
            "dataset": "dataset",
            "dissertation": "thesis",
            "posted-content": "preprint",
        }
        item_type = type_mapping.get(crossref_type, "journalArticle")

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
            issn=issn,
            publisher=publisher,
            item_type=item_type,
            raw_data=data,
        )

    def to_zotero_item(self) -> dict[str, Any]:
        """Convert to Zotero item template format."""
        item = {
            "itemType": self.item_type,
            "title": self.title,
            "DOI": self.doi,
            "url": self.url,
            "creators": [],
        }

        # Add authors
        for author in self.authors:
            if ", " in author:
                parts = author.split(", ", 1)
                item["creators"].append(
                    {
                        "creatorType": "author",
                        "lastName": parts[0],
                        "firstName": parts[1] if len(parts) > 1 else "",
                    }
                )
            else:
                item["creators"].append(
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
        if self.publisher:
            item["publisher"] = self.publisher
        if self.issn:
            item["ISSN"] = self.issn[0]

        return item


class CrossrefClient:
    """Client for querying the Crossref API."""

    def __init__(self, email: str | None = None):
        """
        Initialize the Crossref client.

        Args:
            email: Optional email for polite pool access (faster rate limits)
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
                base_url=CROSSREF_API_BASE,
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
        rows: int = 5,
    ) -> list[CrossrefWork]:
        """
        Search for works by title.

        Args:
            title: Title to search for
            rows: Maximum number of results to return

        Returns:
            List of CrossrefWork objects
        """
        client = await self._get_client()

        try:
            response = await client.get(
                "/works",
                params={
                    "query.title": title,
                    "rows": rows,
                    "select": "DOI,title,author,container-title,published,volume,issue,page,abstract,URL,ISSN,publisher,type",
                },
            )
            response.raise_for_status()
            data = response.json()

            items = data.get("message", {}).get("items", [])
            works = [CrossrefWork.from_api_response(item) for item in items]

            logger.info(
                f"Crossref search for '{title[:50]}...' returned {len(works)} results"
            )
            return works

        except httpx.HTTPError as e:
            logger.error(f"Crossref API error: {e}")
            return []
        except Exception as e:
            logger.error(f"Error parsing Crossref response: {e}")
            return []

    async def get_by_doi(self, doi: str) -> CrossrefWork | None:
        """
        Get work metadata by DOI.

        Args:
            doi: DOI to lookup (e.g., "10.1000/xyz123")

        Returns:
            CrossrefWork object or None if not found
        """
        client = await self._get_client()

        # Clean DOI (remove URL prefix if present)
        if doi.startswith("https://doi.org/"):
            doi = doi[16:]
        elif doi.startswith("http://doi.org/"):
            doi = doi[15:]
        elif doi.startswith("doi:"):
            doi = doi[4:]

        try:
            response = await client.get(f"/works/{quote(doi, safe='')}")
            response.raise_for_status()
            data = response.json()

            work_data = data.get("message", {})
            if work_data:
                work = CrossrefWork.from_api_response(work_data)
                logger.info(f"Crossref DOI lookup for '{doi}' successful")
                return work
            return None

        except httpx.HTTPStatusError as e:
            if e.response.status_code == 404:
                logger.warning(f"DOI not found in Crossref: {doi}")
            else:
                logger.error(f"Crossref API error: {e}")
            return None
        except Exception as e:
            logger.error(f"Error parsing Crossref response: {e}")
            return None

    async def find_best_match(
        self,
        title: str,
        threshold: float = 0.8,
    ) -> CrossrefWork | None:
        """
        Find the best matching work for a title.

        Uses fuzzy title matching to find the most relevant result.

        Args:
            title: Title to search for
            threshold: Minimum similarity threshold (0-1)

        Returns:
            Best matching CrossrefWork or None if no good match
        """
        works = await self.search_by_title(title, rows=5)

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
                f"Best Crossref match: '{best_work.title[:50]}...' (score: {best_score:.2f})"
            )
            return best_work

        logger.warning(
            f"No good Crossref match for '{title[:50]}...' (best score: {best_score:.2f})"
        )
        return None
