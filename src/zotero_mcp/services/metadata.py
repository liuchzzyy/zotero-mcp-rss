"""
Metadata Service - Lookup academic metadata from Crossref and OpenAlex APIs.

This service provides methods to:
1. Lookup DOI by title/author
2. Get complete metadata (authors, journal, abstract, etc.) from external APIs
3. Convert metadata to Zotero item format
"""

from dataclasses import dataclass, field
from datetime import datetime
import logging
import re
from typing import Any

import requests

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
    """Service for looking up academic metadata (DOI, etc.) from external APIs."""

    def __init__(self, mailto: str | None = None):
        """
        Initialize MetadataService.

        Args:
            mailto: Email address to include in API requests (polite pool for Crossref).
        """
        self.mailto = mailto
        self.crossref_base_url = "https://api.crossref.org/works"
        self.openalex_base_url = "https://api.openalex.org/works"

    def lookup_doi(self, title: str, author: str | None = None) -> str | None:
        """
        Lookup DOI for a given title and author.
        Tries Crossref first, then OpenAlex.

        Args:
            title: Article title
            author: Optional author name

        Returns:
            DOI string or None if not found
        """
        doi = self.lookup_crossref(title, author)
        if not doi:
            doi = self.lookup_openalex(title, author)
        return doi

    def lookup_crossref(self, title: str, author: str | None = None) -> str | None:
        """Lookup DOI using Crossref API."""
        try:
            params: dict[str, Any] = {
                "query.title": title,
                "rows": 1,
            }
            if author:
                params["query.author"] = author
            if self.mailto:
                params["mailto"] = self.mailto

            response = requests.get(self.crossref_base_url, params=params, timeout=10)
            response.raise_for_status()
            data = response.json()

            items = data.get("message", {}).get("items", [])
            if not items:
                return None

            # Check similarity (basic check: first item's title should be similar)
            best_match = items[0]
            item_title = best_match.get("title", [""])[0]

            # Very basic check - can be improved
            if (
                title.lower() in item_title.lower()
                or item_title.lower() in title.lower()
            ):
                return best_match.get("DOI")

            return None
        except Exception as e:
            logger.warning(f"Crossref lookup failed for '{title}': {e}")
            return None

    def lookup_openalex(self, title: str, author: str | None = None) -> str | None:
        """Lookup DOI using OpenAlex API."""
        try:
            # OpenAlex filter syntax
            search_query = f"title.search:{title}"
            if author:
                search_query += f",author.search:{author}"

            params = {
                "filter": search_query,
                "per_page": 1,
            }
            if self.mailto:
                params["mailto"] = self.mailto

            response = requests.get(self.openalex_base_url, params=params, timeout=10)
            response.raise_for_status()
            data = response.json()

            results = data.get("results", [])
            if not results:
                return None

            best_match = results[0]
            # OpenAlex returns DOI as a URL, we want just the DOI string
            doi_url = best_match.get("doi")
            if doi_url and "doi.org/" in doi_url:
                return doi_url.split("doi.org/")[-1]

            return None
        except Exception as e:
            logger.warning(f"OpenAlex lookup failed for '{title}': {e}")
            return None

    def lookup_metadata(
        self, title: str, author: str | None = None
    ) -> ArticleMetadata | None:
        """
        Lookup complete metadata for a given title and author.
        Tries Crossref first, then OpenAlex.

        Args:
            title: Article title
            author: Optional author name

        Returns:
            ArticleMetadata object or None if not found
        """
        metadata = self._lookup_crossref_metadata(title, author)
        if not metadata:
            metadata = self._lookup_openalex_metadata(title, author)
        return metadata

    def get_metadata_by_doi(self, doi: str) -> ArticleMetadata | None:
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

        metadata = self._get_crossref_by_doi(doi)
        if not metadata:
            metadata = self._get_openalex_by_doi(doi)
        return metadata

    def _clean_doi(self, doi: str) -> str:
        """Clean DOI string by removing URL prefix."""
        if doi.startswith("https://doi.org/"):
            doi = doi[16:]
        elif doi.startswith("http://doi.org/"):
            doi = doi[15:]
        elif doi.startswith("doi:"):
            doi = doi[4:]
        return doi.strip()

    def _normalize_title(self, title: str) -> str:
        """Normalize title for comparison."""
        title = title.lower()
        title = re.sub(r"[^\w\s]", "", title)
        title = re.sub(r"\s+", " ", title).strip()
        return title

    def _calculate_similarity(self, s1: str, s2: str) -> float:
        """Calculate word-based similarity between two strings."""
        words1 = set(self._normalize_title(s1).split())
        words2 = set(self._normalize_title(s2).split())
        if not words1 or not words2:
            return 0.0
        intersection = words1 & words2
        union = words1 | words2
        return len(intersection) / len(union)

    def _parse_crossref_response(self, data: dict[str, Any]) -> ArticleMetadata:
        """Parse Crossref API response into ArticleMetadata."""
        # Extract DOI
        doi = data.get("DOI", "")

        # Extract title
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
        journal = container_titles[0] if container_titles else None

        # Extract year from published date
        year = None
        for date_field in ["published", "published-print", "published-online"]:
            published = data.get(date_field)
            if published and "date-parts" in published:
                date_parts = published["date-parts"]
                if date_parts and date_parts[0]:
                    year = date_parts[0][0]
                    break

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
        issn_list = data.get("ISSN", [])
        issn = issn_list[0] if issn_list else None

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

        return ArticleMetadata(
            doi=doi,
            title=title,
            authors=authors,
            journal=journal,
            publisher=publisher,
            year=year,
            volume=volume,
            issue=issue,
            pages=pages,
            abstract=abstract,
            url=url,
            issn=issn,
            item_type=item_type,
            source="crossref",
            raw_data=data,
        )

    def _parse_openalex_response(self, data: dict[str, Any]) -> ArticleMetadata:
        """Parse OpenAlex API response into ArticleMetadata."""
        # Extract DOI
        doi_url = data.get("doi", "")
        doi = doi_url.split("doi.org/")[-1] if "doi.org/" in doi_url else None

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

        # Extract abstract
        abstract = None
        abstract_inverted_index = data.get("abstract_inverted_index")
        if abstract_inverted_index:
            # Reconstruct abstract from inverted index
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

        return ArticleMetadata(
            doi=doi,
            title=title,
            authors=authors,
            journal=journal,
            year=year,
            abstract=abstract,
            url=url,
            item_type=item_type,
            source="openalex",
            raw_data=data,
        )

    def _lookup_crossref_metadata(
        self, title: str, author: str | None = None, threshold: float = 0.6
    ) -> ArticleMetadata | None:
        """Lookup complete metadata using Crossref API."""
        try:
            params: dict[str, Any] = {
                "query.title": title,
                "rows": 5,
            }
            if author:
                params["query.author"] = author
            if self.mailto:
                params["mailto"] = self.mailto

            response = requests.get(self.crossref_base_url, params=params, timeout=15)
            response.raise_for_status()
            data = response.json()

            items = data.get("message", {}).get("items", [])
            if not items:
                logger.debug(f"Crossref: No results for '{title[:50]}...'")
                return None

            # Find best match by title similarity
            best_match = None
            best_score = 0.0

            for item in items:
                item_titles = item.get("title", [])
                if not item_titles:
                    continue
                item_title = item_titles[0]
                score = self._calculate_similarity(title, item_title)
                if score > best_score:
                    best_score = score
                    best_match = item

            if best_match and best_score >= threshold:
                metadata = self._parse_crossref_response(best_match)
                logger.info(
                    f"Crossref: Found '{metadata.title[:50]}...' "
                    f"(score: {best_score:.2f}, DOI: {metadata.doi})"
                )
                return metadata

            logger.debug(
                f"Crossref: No good match for '{title[:50]}...' "
                f"(best score: {best_score:.2f})"
            )
            return None

        except Exception as e:
            logger.warning(f"Crossref metadata lookup failed for '{title[:50]}': {e}")
            return None

    def _lookup_openalex_metadata(
        self, title: str, author: str | None = None, threshold: float = 0.6
    ) -> ArticleMetadata | None:
        """Lookup complete metadata using OpenAlex API."""
        try:
            # OpenAlex uses different filter syntax
            params: dict[str, Any] = {
                "search": title,
                "per_page": 5,
            }
            if self.mailto:
                params["mailto"] = self.mailto

            response = requests.get(self.openalex_base_url, params=params, timeout=15)
            response.raise_for_status()
            data = response.json()

            results = data.get("results", [])
            if not results:
                logger.debug(f"OpenAlex: No results for '{title[:50]}...'")
                return None

            # Find best match by title similarity
            best_match = None
            best_score = 0.0

            for item in results:
                item_title = item.get("title", "") or item.get("display_name", "")
                if not item_title:
                    continue
                score = self._calculate_similarity(title, item_title)
                if score > best_score:
                    best_score = score
                    best_match = item

            if best_match and best_score >= threshold:
                metadata = self._parse_openalex_response(best_match)
                logger.info(
                    f"OpenAlex: Found '{metadata.title[:50]}...' "
                    f"(score: {best_score:.2f}, DOI: {metadata.doi})"
                )
                return metadata

            logger.debug(
                f"OpenAlex: No good match for '{title[:50]}...' "
                f"(best score: {best_score:.2f})"
            )
            return None

        except Exception as e:
            logger.warning(f"OpenAlex metadata lookup failed for '{title[:50]}': {e}")
            return None

    def _get_crossref_by_doi(self, doi: str) -> ArticleMetadata | None:
        """Get complete metadata from Crossref by DOI."""
        try:
            url = f"{self.crossref_base_url}/{doi}"
            params = {}
            if self.mailto:
                params["mailto"] = self.mailto

            response = requests.get(url, params=params, timeout=10)
            if response.status_code == 404:
                logger.debug(f"Crossref: DOI not found: {doi}")
                return None
            response.raise_for_status()
            data = response.json()

            work_data = data.get("message", {})
            if work_data:
                metadata = self._parse_crossref_response(work_data)
                logger.info(f"Crossref: Retrieved metadata for DOI {doi}")
                return metadata
            return None

        except Exception as e:
            logger.warning(f"Crossref DOI lookup failed for '{doi}': {e}")
            return None

    def _get_openalex_by_doi(self, doi: str) -> ArticleMetadata | None:
        """Get complete metadata from OpenAlex by DOI."""
        try:
            # OpenAlex expects DOI in URL format
            doi_url = f"https://doi.org/{doi}"
            url = f"{self.openalex_base_url}/{doi_url}"
            params = {}
            if self.mailto:
                params["mailto"] = self.mailto

            response = requests.get(url, params=params, timeout=10)
            if response.status_code == 404:
                logger.debug(f"OpenAlex: DOI not found: {doi}")
                return None
            response.raise_for_status()
            data = response.json()

            if data:
                metadata = self._parse_openalex_response(data)
                logger.info(f"OpenAlex: Retrieved metadata for DOI {doi}")
                return metadata
            return None

        except Exception as e:
            logger.warning(f"OpenAlex DOI lookup failed for '{doi}': {e}")
            return None
