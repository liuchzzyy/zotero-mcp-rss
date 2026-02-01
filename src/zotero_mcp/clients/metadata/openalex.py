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

from zotero_mcp.utils.formatting.helpers import clean_abstract

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
    """Represents a work (article) from OpenAlex.

    Enhanced with additional fields from OpenAlex API.
    """

    doi: str
    title: str
    authors: list[str]
    journal: str | None
    journal_abbrev: str | None  # Abbreviated journal title
    year: int | None
    volume: str | None
    issue: str | None
    pages: str | None
    abstract: str | None
    url: str | None
    item_type: str
    raw_data: dict[str, Any]

    # Additional fields
    language: str | None
    rights: str | None
    short_title: str | None
    series: str | None
    edition: str | None
    place: str | None

    # Extra metadata
    citation_count: int | None  # OpenAlex provides this directly
    subjects: list[str]
    funders: list[str]
    pdf_url: str | None

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
        journal_abbrev = None
        primary_location = data.get("primary_location", {})
        if primary_location:
            source = primary_location.get("source", {})
            if source:
                journal = source.get("display_name")
                # Extract abbreviated title if available
                abbrevs = source.get("abbreviated_title", [])
                if abbrevs and isinstance(abbrevs, list):
                    journal_abbrev = abbrevs[0] if abbrevs else None

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

        # Extract abstract from inverted index and clean
        abstract = None
        abstract_inverted_index = data.get("abstract_inverted_index")
        if abstract_inverted_index:
            try:
                word_positions = []
                for word, positions in abstract_inverted_index.items():
                    for pos in positions:
                        word_positions.append((pos, word))
                word_positions.sort(key=lambda x: x[0])
                abstract_text = " ".join([wp[1] for wp in word_positions])
                abstract = clean_abstract(abstract_text)
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

        # Extract additional fields
        language = data.get("language")

        # Extract citation count (OpenAlex provides this directly)
        citation_count = data.get("cited_by_count")
        if citation_count == 0:
            citation_count = None  # Only store if > 0

        # Extract concepts (subjects/keywords)
        subjects = []
        for concept in data.get("concepts", []):
            if isinstance(concept, dict) and concept.get("score", 0) > 0.3:  # Filter by relevance
                subjects.append(concept.get("display_name", ""))

        # Extract funders from grants
        funders = []
        for grant in data.get("grants", []):
            if isinstance(grant, dict):
                funder = grant.get("funder")
                if isinstance(funder, dict):
                    funder_name = funder.get("display_name")
                    if funder_name:
                        funder_str = funder_name
                        # Add award number if available
                        award_id = grant.get("award_id")
                        if award_id:
                            funder_str += f" (Award: {award_id})"
                        funders.append(funder_str)

        # PDF URL - OpenAlex doesn't typically provide direct PDF links
        pdf_url = None
        locations = data.get("locations", [])
        for location in locations:
            if isinstance(location, dict):
                source = location.get("source")
                if isinstance(source, dict) and source.get("type") == "pdf":
                    landing_url = location.get("landing_url") or location.get("pdf_url")
                    if landing_url:
                        pdf_url = landing_url
                        break

        return cls(
            doi=doi,
            title=title,
            authors=authors,
            journal=journal,
            journal_abbrev=journal_abbrev,
            year=year,
            volume=volume,
            issue=issue,
            pages=pages,
            abstract=abstract,
            url=url,
            item_type=item_type,
            raw_data=data,
            language=language,
            rights=None,  # Not typically provided by OpenAlex
            short_title=None,  # Not available
            series=None,  # Not available for journal articles
            edition=None,  # Not available
            place=None,  # Not available
            citation_count=citation_count,
            subjects=subjects,
            funders=funders,
            pdf_url=pdf_url,
        )

    def to_zotero_item(self) -> dict[str, Any]:
        """Convert to Zotero item template format with enhanced fields."""
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
        if self.journal_abbrev:
            item["journalAbbreviation"] = self.journal_abbrev
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

        # Additional Zotero fields
        if self.language:
            item["language"] = self.language
        if self.rights:
            item["rights"] = self.rights
        if self.series:
            item["series"] = self.series

        # Build "Extra" field for additional metadata
        extra_parts = []
        if self.citation_count is not None:
            extra_parts.append(f"Citation Count: {self.citation_count}")
        for subject in self.subjects:
            extra_parts.append(f"Subject: {subject}")
        for funder in self.funders:
            extra_parts.append(f"Funder: {funder}")
        if self.pdf_url:
            extra_parts.append(f"Full-text PDF: {self.pdf_url}")
        if extra_parts:
            item["extra"] = "\n".join(extra_parts)

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
