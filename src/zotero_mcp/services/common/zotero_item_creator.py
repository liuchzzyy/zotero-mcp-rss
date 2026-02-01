"""Common Zotero item creation logic for RSS and Gmail workflows."""

from datetime import datetime
import logging
from typing import Any

from zotero_mcp.models.ingestion import RSSItem
from zotero_mcp.services.common.retry import async_retry_with_backoff
from zotero_mcp.utils.formatting.helpers import clean_title

logger = logging.getLogger(__name__)

# Zotero limits
MAX_CREATOR_NAME_LENGTH = 210
MAX_CREATORS = 10


class ZoteroItemCreator:
    """
    Centralized service for creating Zotero items from external sources.

    Used by both RSS and Gmail workflows to avoid code duplication.
    """

    def __init__(self, data_service, metadata_service):
        """
        Initialize item creator.

        Args:
            data_service: DataAccessService instance
            metadata_service: MetadataService instance for DOI lookup
        """
        self.data_service = data_service
        self.metadata_service = metadata_service

    async def create_item(
        self,
        item: RSSItem,
        collection_key: str,
    ) -> str | None:
        """
        Create a Zotero item from an RSS/email item.

        Args:
            item: RSSItem with paper metadata
            collection_key: Target collection key

        Returns:
            Zotero item key if created, None if duplicate or failed
        """
        cleaned_title = clean_title(item.title)

        # Lookup DOI if not available (this also enhances title/URL metadata)
        doi = item.doi
        enhanced_title = cleaned_title
        enhanced_url = item.link

        if not doi:
            logger.info(f"  ? Looking up DOI for: {cleaned_title[:50]}")
            doi_result = await self.metadata_service.lookup_doi(
                cleaned_title, item.author, return_metadata=True
            )
            if doi_result:
                if isinstance(doi_result, dict):
                    doi = doi_result.get("doi")
                    # Use enhanced metadata if available
                    enhanced_title = clean_title(doi_result.get("title", cleaned_title))
                    enhanced_url = doi_result.get("url", item.link)
                    logger.info(f"  + Found DOI: {doi}")
                    logger.debug(f"    Enhanced title: {enhanced_title[:50]}")
                    logger.debug(f"    Enhanced URL: {enhanced_url}")
                else:
                    doi = doi_result
                    logger.info(f"  + Found DOI: {doi}")

        # Check for duplicates using enhanced metadata (priority: DOI > title > URL)
        duplicate_reason = await self._check_duplicates_with_priority(
            doi=doi,
            title=enhanced_title,
            url=enhanced_url,
        )
        if duplicate_reason:
            logger.info(
                f"  ⊘ Duplicate ({duplicate_reason}): {enhanced_title[:50]}"
            )
            return None

        # Build item data with enhanced metadata
        item_data = self._build_item_data(
            item, enhanced_title, doi, collection_key, enhanced_url
        )

        # Create item with retry
        try:
            def do_create():
                result = self.data_service.create_items([item_data])
                # Handle HTTP status codes returned by pyzotero
                if isinstance(result, int):
                    if result == 429:
                        raise RuntimeError(f"Rate limit exceeded (429)")
                    else:
                        raise RuntimeError(f"HTTP error {result}")
                return result

            result = await async_retry_with_backoff(
                do_create,
                description=f"Create item '{enhanced_title[:30]}'",
            )

            if self._is_successful_result(result):
                item_key = self._extract_item_key(result)
                logger.info(f"  ✓ Created: {enhanced_title[:50]} (key: {item_key})")
                return item_key
            else:
                logger.warning(f"  ✗ Failed to create: {enhanced_title[:50]}")
                return None

        except Exception as e:
            logger.error(f"  ✗ Error creating item '{enhanced_title[:50]}': {e}")
            return None

    async def _check_duplicates_with_priority(
        self,
        doi: str | None,
        title: str,
        url: str,
    ) -> str | None:
        """
        Check if item already exists with priority: DOI > title > URL.

        Args:
            doi: DOI from metadata lookup
            title: Enhanced title from metadata lookup
            url: Enhanced URL from metadata lookup

        Returns:
            Match type ("doi", "title", "url") if duplicate found, None otherwise
        """
        # Priority 1: Check by DOI (most reliable)
        if doi:
            existing_by_doi = await async_retry_with_backoff(
                lambda: self.data_service.search_items(
                    query=doi, limit=1, qmode="everything"
                ),
                description=f"Search DOI '{doi[:30]}'",
            )
            if existing_by_doi and len(existing_by_doi) > 0:
                logger.debug(f"  → Found duplicate by DOI: {doi}")
                return "doi"

        # Priority 2: Check by title (case-insensitive exact match)
        existing_by_title = await async_retry_with_backoff(
            lambda: self.data_service.search_items(
                query=title, qmode="titleCreatorYear", limit=5
            ),
            description=f"Search title '{title[:30]}'",
        )
        if existing_by_title and len(existing_by_title) > 0:
            # Check for exact title match (case-insensitive)
            for existing_item in existing_by_title:
                if existing_item.title and existing_item.title.lower() == title.lower():
                    logger.debug(f"  → Found duplicate by title: {title}")
                    return "title"

        # Priority 3: Check by URL (least reliable, may change)
        # Only check URL if it's a valid URL (not empty)
        if url:
            existing_by_url = await async_retry_with_backoff(
                lambda: self.data_service.search_items(
                    query=url, limit=1, qmode="everything"
                ),
                description=f"Search URL '{url[:30]}'",
            )
            if existing_by_url and len(existing_by_url) > 0:
                logger.debug(f"  → Found duplicate by URL: {url}")
                return "url"

        return None

    async def _check_duplicates(self, item: RSSItem, cleaned_title: str) -> str | None:
        """
        Check if item already exists by URL or title.

        DEPRECATED: Use _check_duplicates_with_priority instead.
        This method is kept for backward compatibility.
        """
        # Check by URL
        existing_by_url = await async_retry_with_backoff(
            lambda: self.data_service.search_items(
                query=item.link, limit=1, qmode="everything"
            ),
            description=f"Search URL '{cleaned_title[:30]}'",
        )
        if existing_by_url and len(existing_by_url) > 0:
            return "url"

        # Check by title
        existing_by_title = await async_retry_with_backoff(
            lambda: self.data_service.search_items(
                query=cleaned_title, qmode="titleCreatorYear", limit=1
            ),
            description=f"Search title '{cleaned_title[:30]}'",
        )
        if existing_by_title and len(existing_by_title) > 0:
            found_title = existing_by_title[0].title
            if found_title.lower() == cleaned_title.lower():
                return "title"

        return None

    def _build_item_data(
        self,
        item: RSSItem,
        cleaned_title: str,
        doi: str | None,
        collection_key: str,
        enhanced_url: str | None = None,
    ) -> dict:
        """Build Zotero item data dict."""
        item_data = {
            "itemType": "journalArticle",
            "title": cleaned_title,
            "url": enhanced_url or item.link,
            "publicationTitle": item.source_title,
            "date": item.pub_date.strftime("%Y-%m-%d") if item.pub_date else "",
            "accessDate": datetime.now().strftime("%Y-%m-%d"),
            "collections": [collection_key],
            "DOI": doi or "",
            "tags": [],
        }

        if item.author:
            item_data["creators"] = parse_creator_string(item.author)

        return item_data

    def _is_successful_result(self, result: dict | int) -> bool:
        """Check if creation result indicates success."""
        # Handle integer status codes (HTTP errors)
        if isinstance(result, int):
            logger.debug(f"  ! Received status code: {result}")
            return False
        if not isinstance(result, dict):
            return False

        return (
            len(result.get("successful", {})) > 0 or len(result.get("success", {})) > 0
        )

    def _extract_item_key(self, result: dict | int) -> str | None:
        """Extract item key from creation result."""
        # Handle integer status codes (HTTP errors)
        if isinstance(result, int):
            logger.warning(f"  ! Cannot extract key from status code: {result}")
            return None
        if not isinstance(result, dict):
            return None

        if "successful" in result and result["successful"]:
            return list(result["successful"].keys())[0]
        if "success" in result and result["success"]:
            return list(result["success"].keys())[0]
        return None


def parse_creator_string(author_string: str) -> list[dict[str, str]]:
    """
    Parse author string and split into individual creators.

    Handles comma-separated author lists and truncates if necessary
    to avoid Zotero HTTP 413 errors.

    Args:
        author_string: Raw author string from feed/email

    Returns:
        List of creator dicts with 'creatorType' and 'name' keys
    """
    if not author_string:
        return []

    creators = []

    # Try to split by common separators
    parts = []
    for sep in [", ", "; ", "\n", ","]:
        if sep in author_string:
            parts = [p.strip() for p in author_string.split(sep) if p.strip()]
            break

    if not parts:
        parts = [author_string.strip()]

    # Limit number of creators
    if len(parts) > MAX_CREATORS:
        logger.warning(
            f"  ! Author list too long ({len(parts)} authors), "
            f"truncating to {MAX_CREATORS} + et al."
        )
        parts = parts[:MAX_CREATORS]

    # Create creator dicts
    for author in parts:
        author = author.strip()
        if len(author) > MAX_CREATOR_NAME_LENGTH:
            author = author[: MAX_CREATOR_NAME_LENGTH - 4] + "..."
            logger.warning(f"  ! Author name too long, truncated to: {author}")

        if author:
            creators.append({"creatorType": "author", "name": author})

    # Add "et al." if truncated
    if len(creators) == MAX_CREATORS:
        original_count = len(
            [p.strip() for p in author_string.split(",") if p.strip()]
            if "," in author_string or ";" in author_string
            else [author_string.strip()]
        )
        if original_count > MAX_CREATORS:
            creators[-1]["name"] = creators[-1]["name"] + " et al."

    return creators
