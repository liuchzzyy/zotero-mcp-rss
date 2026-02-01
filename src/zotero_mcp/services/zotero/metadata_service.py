"""
Metadata Service - Lookup academic metadata from Crossref and OpenAlex APIs.

This service provides methods to:
1. Lookup DOI by title/author
2. Get complete metadata (authors, journal, abstract, etc.) from external APIs
3. Convert metadata to Zotero item format

Features:
- Async API calls with retry mechanism
- Priority: Crossref > OpenAlex
- Unified error handling
"""

from dataclasses import dataclass, field
from datetime import datetime
import logging
from typing import Any

from zotero_mcp.clients.metadata import (
    CrossrefClient,
    CrossrefWork,
    OpenAlexClient,
    OpenAlexWork,
)

logger = logging.getLogger(__name__)


@dataclass
class ArticleMetadata:
    """Complete metadata for an academic article."""

    doi: str | None = None
    title: str = ""
    authors: list[str] = field(default_factory=list)
    journal: str | None = None
    publisher: str | None = None
    year: int | None = None
    volume: str | None = None
    issue: str | None = None
    pages: str | None = None
    abstract: str | None = None
    url: str | None = None
    issn: str | None = None
    item_type: str = "journalArticle"
    source: str = ""  # "crossref" or "openalex"
    raw_data: dict[str, Any] = field(default_factory=dict)

    def to_zotero_item(self, collection_key: str | None = None) -> dict[str, Any]:
        """
        Convert metadata to Zotero item template format.

        Args:
            collection_key: Optional collection key to add item to

        Returns:
            Zotero item data dict ready for API submission
        """
        item: dict[str, Any] = {
            "itemType": self.item_type,
            "title": self.title,
            "creators": [],
            "accessDate": datetime.now().strftime("%Y-%m-%d"),
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
            if ", " in author:
                # Format: "Last, First"
                parts = author.split(", ", 1)
                item["creators"].append(
                    {
                        "creatorType": "author",
                        "lastName": parts[0],
                        "firstName": parts[1] if len(parts) > 1 else "",
                    }
                )
            else:
                # Single name
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
            item["ISSN"] = self.issn

        # Add collection
        if collection_key:
            item["collections"] = [collection_key]

        return item


class MetadataService:
    """
    Service for looking up academic metadata (DOI, etc.) from external APIs.

    Features:
    - Async API calls with automatic retry
    - Priority: Crossref > OpenAlex
    - Unified error handling and logging
    """

    def __init__(self, mailto: str | None = None):
        """
        Initialize MetadataService.

        Args:
            mailto: Email address to include in API requests (polite pool).
        """
        self.mailto = mailto
        self.crossref_client = CrossrefClient(email=mailto)
        self.openalex_client = OpenAlexClient(email=mailto)

    async def close(self) -> None:
        """Close all API clients."""
        await self.crossref_client.close()
        await self.openalex_client.close()

    async def lookup_doi(
        self, title: str, author: str | None = None, return_metadata: bool = False
    ) -> str | dict[str, Any] | None:
        """
        Lookup DOI for a given title and author.

        Priority: DOI > title matching > URL matching

        Uses lenient threshold (0.6) to find matches for papers with
        slightly different titles or formatting variations.

        Args:
            title: Article title
            author: Optional author name
            return_metadata: If True, return dict with doi, title, url; otherwise just DOI

        Returns:
            - If return_metadata=False: DOI string or None
            - If return_metadata=True: Dict with 'doi', 'title', 'url' or None
        """
        # Try Crossref first with lenient threshold
        work = await self.crossref_client.find_best_match(title, threshold=0.6)
        if work and work.doi:
            logger.debug(f"  ✓ DOI found via Crossref: {work.doi}")
            if return_metadata:
                return {
                    "doi": work.doi,
                    "title": work.title,
                    "url": work.url,
                }
            return work.doi

        # Fallback to OpenAlex with lenient threshold
        work = await self.openalex_client.find_best_match(title, threshold=0.6)
        if work and work.doi:
            logger.debug(f"  ✓ DOI found via OpenAlex: {work.doi}")
            if return_metadata:
                return {
                    "doi": work.doi,
                    "title": work.title,
                    "url": work.url,
                }
            return work.doi

        logger.debug(f"  ✗ No DOI found for title: {title[:50]}...")
        return None

    async def lookup_metadata(
        self, title: str, author: str | None = None
    ) -> ArticleMetadata | None:
        """
        Lookup complete metadata for a given title and author.

        Priority: DOI > title matching > URL matching

        Uses lenient threshold (0.6) for better matching success rate.

        Args:
            title: Article title
            author: Optional author name

        Returns:
            ArticleMetadata object or None if not found
        """
        # Try Crossref first with lenient threshold
        work = await self.crossref_client.find_best_match(title, threshold=0.6)
        if work:
            return self._crossref_work_to_metadata(work)

        # Fallback to OpenAlex with lenient threshold
        work = await self.openalex_client.find_best_match(title, threshold=0.6)
        if work:
            return self._openalex_work_to_metadata(work)

        return None

    async def get_metadata_by_doi(self, doi: str) -> ArticleMetadata | None:
        """
        Get complete metadata by DOI.

        Args:
            doi: DOI string (e.g., "10.1000/xyz123")

        Returns:
            ArticleMetadata object or None if not found
        """
        # Clean DOI
        doi = self._clean_doi(doi)
        if not doi:
            return None

        # Try Crossref first
        work = await self.crossref_client.get_by_doi(doi)
        if work:
            return self._crossref_work_to_metadata(work)

        # Fallback to OpenAlex
        work = await self.openalex_client.get_by_doi(doi)
        if work:
            return self._openalex_work_to_metadata(work)

        return None

    def _clean_doi(self, doi: str) -> str:
        """Clean DOI string by removing URL prefix."""
        if doi.startswith("https://doi.org/"):
            doi = doi[16:]
        elif doi.startswith("http://doi.org/"):
            doi = doi[15:]
        elif doi.startswith("doi:"):
            doi = doi[4:]
        return doi.strip()

    def _crossref_work_to_metadata(self, work: CrossrefWork) -> ArticleMetadata:
        """Convert CrossrefWork to ArticleMetadata."""
        return ArticleMetadata(
            doi=work.doi,
            title=work.title,
            authors=work.authors,
            journal=work.journal,
            publisher=work.publisher,
            year=work.year,
            volume=work.volume,
            issue=work.issue,
            pages=work.pages,
            abstract=work.abstract,
            url=work.url,
            issn=work.issn[0] if work.issn else None,
            item_type=work.item_type,
            source="crossref",
            raw_data=work.raw_data,
        )

    def _openalex_work_to_metadata(self, work: OpenAlexWork) -> ArticleMetadata:
        """Convert OpenAlexWork to ArticleMetadata."""
        return ArticleMetadata(
            doi=work.doi,
            title=work.title,
            authors=work.authors,
            journal=work.journal,
            year=work.year,
            volume=work.volume,
            issue=work.issue,
            pages=work.pages,
            abstract=work.abstract,
            url=work.url,
            item_type=work.item_type,
            source="openalex",
            raw_data=work.raw_data,
        )
