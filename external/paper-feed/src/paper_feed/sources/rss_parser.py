"""RSS feed parser for converting feed entries to PaperItem objects."""

import logging
import re
import time
from datetime import date, datetime
from typing import Any, Dict, List, Optional

from paper_feed.core.models import PaperItem

logger = logging.getLogger(__name__)

# DOI pattern for extraction
DOI_PATTERN = re.compile(r"\b10\.\d{4,9}/[-._;()/:A-Z0-9]+\b", re.IGNORECASE)


class RSSParser:
    """Parser for RSS feed entries to PaperItem objects.

    Handles extraction of authors, dates, tags, DOIs, and PDF URLs from
    various RSS feed formats (arXiv, bioRxiv, Nature, Science, etc.).
    """

    def parse(self, entry: Dict[str, Any], source_name: str) -> PaperItem:
        """Parse an RSS feed entry into a PaperItem.

        Args:
            entry: Feedparser entry object (dict-like)
            source_name: Name of the RSS source (e.g., "arXiv", "Nature")

        Returns:
            PaperItem with extracted metadata

        Raises:
            ValueError: If required fields (title) are missing
        """
        # Extract required fields
        title = self._get_field(entry, "title")
        if not title:
            raise ValueError("Entry missing required field: title")

        # Extract optional fields
        authors = self._extract_authors(entry)
        published_date = self._extract_published_date(entry)
        tags = self._extract_tags(entry)
        doi = self._extract_doi(entry)
        pdf_url = self._extract_pdf_url(entry)

        # Extract standard fields
        abstract = (
            self._get_field(entry, "summary")
            or self._get_field(entry, "description")
            or ""
        )
        url = self._get_field(entry, "link") or ""
        source_id = self._get_field(entry, "id") or url

        # Extract categories
        categories = self._extract_categories(entry)

        return PaperItem(
            title=str(title),
            authors=authors,
            abstract=str(abstract) if abstract else "",
            published_date=published_date,
            doi=doi,
            url=url if url else None,
            pdf_url=pdf_url,
            source=source_name,
            source_id=source_id if source_id else None,
            source_type="rss",
            categories=categories,
            tags=tags,
            metadata={},  # Could add raw entry data here if needed
        )

    def _get_field(self, entry: Any, key: str, default: Any = None) -> Any:
        """Safely get value from entry (dict or object).

        Args:
            entry: Feedparser entry (may be dict or object)
            key: Field name to retrieve
            default: Default value if field not found

        Returns:
            Field value or default
        """
        if isinstance(entry, dict):
            return entry.get(key, default)
        return getattr(entry, key, default)

    def _extract_authors(self, entry: Any) -> List[str]:
        """Extract authors from entry.

        Handles multiple formats:
        - entry.authors (list of objects with .name or .email)
        - entry.author (string)

        Args:
            entry: Feedparser entry

        Returns:
            List of author names
        """
        authors = []

        # Try entry.authors (list format)
        authors_field = self._get_field(entry, "authors")
        if authors_field:
            if isinstance(authors_field, list):
                for author_obj in authors_field:
                    if hasattr(author_obj, "name"):
                        authors.append(str(author_obj.name))
                    elif hasattr(author_obj, "email"):
                        authors.append(str(author_obj.email))
                    elif isinstance(author_obj, dict):
                        name = author_obj.get("name")
                        if name:
                            authors.append(str(name))

        # Fallback to entry.author (string format)
        if not authors:
            author_field = self._get_field(entry, "author")
            if author_field:
                # Handle common formats: "Name", "Name1, Name2", etc.
                author_str = str(author_field)
                # Split by common separators
                for sep in [",", ";", " and "]:
                    if sep in author_str:
                        authors = [a.strip() for a in author_str.split(sep)]
                        break
                else:
                    authors = [author_str]

        return authors

    def _extract_published_date(self, entry: Any) -> Optional[date]:
        """Extract publication date from entry.

        Handles time.struct_time from feedparser.

        Args:
            entry: Feedparser entry

        Returns:
            Publication date as date object or None
        """
        # Try published_parsed first
        published_parsed = self._get_field(entry, "published_parsed")
        if published_parsed and isinstance(published_parsed, time.struct_time):
            try:
                dt = datetime.fromtimestamp(time.mktime(published_parsed))
                return dt.date()
            except (ValueError, OSError):
                pass

        # Try updated_parsed as fallback
        updated_parsed = self._get_field(entry, "updated_parsed")
        if updated_parsed and isinstance(updated_parsed, time.struct_time):
            try:
                dt = datetime.fromtimestamp(time.mktime(updated_parsed))
                return dt.date()
            except (ValueError, OSError):
                pass

        return None

    def _extract_tags(self, entry: Any) -> List[str]:
        """Extract tags from entry.

        Handles entry.tags (list of objects with .term attribute).

        Args:
            entry: Feedparser entry

        Returns:
            List of tag strings
        """
        tags = []

        tags_field = self._get_field(entry, "tags")
        if tags_field and isinstance(tags_field, list):
            for tag_obj in tags_field:
                if hasattr(tag_obj, "term"):
                    term = str(tag_obj.term)
                    if term:
                        tags.append(term)
                elif isinstance(tag_obj, dict):
                    term = tag_obj.get("term")
                    if term:
                        tags.append(str(term))

        return tags

    def _extract_doi(self, entry: Any) -> Optional[str]:
        """Extract DOI from entry metadata or links.

        Checks:
        1. dc_identifier field
        2. prism_doi field
        3. Links/guid containing doi.org URLs

        Args:
            entry: Feedparser entry

        Returns:
            DOI string or None
        """
        # Try common DOI fields
        for key in ["dc_identifier", "prism_doi"]:
            val = self._get_field(entry, key)
            if val and isinstance(val, str):
                # Clean up doi: prefix
                if val.lower().startswith("doi:"):
                    val = val[4:].strip()
                if DOI_PATTERN.match(val):
                    return val

        # Try to find DOI in links
        for key in ["link", "id"]:
            val = self._get_field(entry, key)
            if val and isinstance(val, str):
                match = DOI_PATTERN.search(val)
                if match:
                    return match.group(0)

        return None

    def _extract_pdf_url(self, entry: Any) -> Optional[str]:
        """Extract direct PDF URL from entry.

        Handles:
        1. Links with type="application/pdf"
        2. arXiv /abs/ URLs → convert to /pdf/
        3. pdf_url field (some publishers)

        Args:
            entry: Feedparser entry

        Returns:
            Direct PDF URL or None
        """
        # Check for links with PDF type
        links = self._get_field(entry, "links")
        if links and isinstance(links, list):
            for link in links:
                if isinstance(link, dict):
                    link_type = link.get("type", "")
                    href = link.get("href", "")
                    if link_type == "application/pdf" and href:
                        return str(href)
                elif hasattr(link, "type") and link.type == "application/pdf":
                    if hasattr(link, "href"):
                        return str(link.href)

        # Check for pdf_url field
        pdf_url_field = self._get_field(entry, "pdf_url")
        if pdf_url_field:
            return str(pdf_url_field)

        # Convert arXiv /abs/ URLs to /pdf/
        link = self._get_field(entry, "link")
        if link and isinstance(link, str):
            if "arxiv.org/abs/" in link:
                return link.replace("/abs/", "/pdf/") + ".pdf"

        return None

    def _extract_categories(self, entry: Any) -> List[str]:
        """Extract category information from entry.

        Handles entry.tags or entry.categories.

        Args:
            entry: Feedparser entry

        Returns:
            List of category strings
        """
        categories = []

        # Try tags first
        tags_field = self._get_field(entry, "tags")
        if tags_field and isinstance(tags_field, list):
            for tag_obj in tags_field:
                if hasattr(tag_obj, "term"):
                    term = str(tag_obj.term)
                    if term and term not in categories:
                        categories.append(term)
                elif isinstance(tag_obj, dict):
                    term = tag_obj.get("term")
                    if term and term not in categories:
                        categories.append(str(term))

        # Try categories field
        if not categories:
            cats_field = self._get_field(entry, "categories")
            if cats_field:
                if isinstance(cats_field, list):
                    categories = [str(cat) for cat in cats_field]
                elif isinstance(cats_field, str):
                    categories = [cats_field]

        return categories
