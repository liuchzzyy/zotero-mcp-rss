"""
Unified data access service for Zotero MCP.

Provides a single interface for accessing Zotero data through
multiple backends (API, local database, Better BibTeX).
"""

from dataclasses import dataclass
from functools import lru_cache
import logging
from typing import Any, Literal

from zotero_mcp.clients.better_bibtex import (
    BetterBibTeXClient,
    get_better_bibtex_client,
)
from zotero_mcp.clients.local_db import (
    LocalDatabaseClient,
    ZoteroItem,
    get_local_database_client,
)
from zotero_mcp.clients.zotero_client import ZoteroAPIClient, get_zotero_client
from zotero_mcp.formatters import BibTeXFormatter, JSONFormatter, MarkdownFormatter
from zotero_mcp.models.common import ResponseFormat
from zotero_mcp.utils.helpers import format_creators, is_local_mode

logger = logging.getLogger(__name__)


@dataclass
class SearchResult:
    """Unified search result."""

    key: str
    title: str
    authors: str
    date: str | None
    item_type: str
    abstract: str | None = None
    doi: str | None = None
    tags: list[str] | None = None
    similarity_score: float | None = None
    raw_data: dict[str, Any] | None = None


class DataAccessService:
    """
    Unified data access service.

    Automatically selects the best available backend for each operation:
    - Local database for fast reads when available
    - Better BibTeX for annotation and citation key access
    - Zotero API for write operations and when local access unavailable
    """

    def __init__(
        self,
        api_client: ZoteroAPIClient | None = None,
        local_client: LocalDatabaseClient | None = None,
        bibtex_client: BetterBibTeXClient | None = None,
    ):
        """
        Initialize data access service.

        Args:
            api_client: Zotero API client
            local_client: Local database client
            bibtex_client: Better BibTeX client
        """
        self._api_client = api_client
        self._local_client = local_client
        self._bibtex_client = bibtex_client
        self._formatters = {
            ResponseFormat.MARKDOWN: MarkdownFormatter(),
            ResponseFormat.JSON: JSONFormatter(),
        }
        self._bibtex_formatter = BibTeXFormatter()

    @property
    def api_client(self) -> ZoteroAPIClient:
        """Get or create API client."""
        if self._api_client is None:
            self._api_client = get_zotero_client()
        return self._api_client

    @property
    def local_client(self) -> LocalDatabaseClient | None:
        """Get local database client if available."""
        if self._local_client is None and is_local_mode():
            self._local_client = get_local_database_client()
        return self._local_client

    @property
    def bibtex_client(self) -> BetterBibTeXClient | None:
        """Get Better BibTeX client if available."""
        if self._bibtex_client is None:
            self._bibtex_client = get_better_bibtex_client()
        return self._bibtex_client

    def get_formatter(
        self, response_format: ResponseFormat
    ) -> MarkdownFormatter | JSONFormatter:
        """Get formatter for response format."""
        return self._formatters.get(
            response_format, self._formatters[ResponseFormat.MARKDOWN]
        )

    # -------------------- Search Operations --------------------

    async def search_items(
        self,
        query: str,
        limit: int = 25,
        offset: int = 0,
        qmode: Literal["titleCreatorYear", "everything"] = "titleCreatorYear",
    ) -> list[SearchResult]:
        """
        Search items in the library.

        Uses local database if available for faster results.

        Args:
            query: Search query
            limit: Maximum results
            offset: Pagination offset
            qmode: Search mode

        Returns:
            List of search results
        """
        # Try local database first for speed
        if self.local_client and qmode == "everything":
            try:
                items = self.local_client.search_items(query, limit=limit + offset)
                return [
                    self._zotero_item_to_result(item)
                    for item in items[offset : offset + limit]
                ]
            except Exception as e:
                logger.warning(f"Local search failed, falling back to API: {e}")

        # Fall back to API
        items = await self.api_client.search_items(
            query=query,
            qmode=qmode,
            limit=limit,
            start=offset,
        )
        return [self._api_item_to_result(item) for item in items]

    async def get_recent_items(
        self,
        limit: int = 10,
        days: int = 7,
    ) -> list[SearchResult]:
        """
        Get recently added items.

        Args:
            limit: Maximum results
            days: Days to look back

        Returns:
            List of recent items
        """
        items = await self.api_client.get_recent_items(limit=limit, days=days)
        return [self._api_item_to_result(item) for item in items]

    async def search_by_tag(
        self,
        tags: list[str],
        exclude_tags: list[str] | None = None,
        limit: int = 25,
    ) -> list[SearchResult]:
        """
        Search items by tags.

        Args:
            tags: Required tags (AND logic)
            exclude_tags: Tags to exclude
            limit: Maximum results

        Returns:
            Matching items
        """
        # Get items with first tag
        if not tags:
            return []

        items = await self.api_client.get_items_by_tag(tags[0], limit=100)

        # Filter by additional tags
        for tag in tags[1:]:
            items = [
                i
                for i in items
                if tag in [t.get("tag", "") for t in i.get("data", {}).get("tags", [])]
            ]

        # Exclude tags
        if exclude_tags:
            for tag in exclude_tags:
                items = [
                    i
                    for i in items
                    if tag
                    not in [t.get("tag", "") for t in i.get("data", {}).get("tags", [])]
                ]

        return [self._api_item_to_result(item) for item in items[:limit]]

    # -------------------- Item Operations --------------------

    async def get_item(
        self,
        item_key: str,
    ) -> dict[str, Any]:
        """
        Get item by key.

        Args:
            item_key: Zotero item key

        Returns:
            Full item data
        """
        return await self.api_client.get_item(item_key)

    async def get_item_children(
        self,
        item_key: str,
        item_type: str | None = None,
    ) -> list[dict[str, Any]]:
        """
        Get child items (attachments, notes).

        Args:
            item_key: Parent item key
            item_type: Filter by type

        Returns:
            Child items
        """
        return await self.api_client.get_item_children(item_key, item_type)

    async def get_fulltext(
        self,
        item_key: str,
    ) -> str | None:
        """
        Get full-text content for an item.

        Args:
            item_key: Item key

        Returns:
            Full-text content if available
        """
        return await self.api_client.get_fulltext(item_key)

    # -------------------- Collection Operations --------------------

    async def get_collections(self) -> list[dict[str, Any]]:
        """Get all collections."""
        return await self.api_client.get_collections()

    async def get_collection_items(
        self,
        collection_key: str,
        limit: int = 100,
    ) -> list[SearchResult]:
        """
        Get items in a collection.

        Args:
            collection_key: Collection key
            limit: Maximum results

        Returns:
            Items in collection
        """
        items = await self.api_client.get_collection_items(collection_key, limit)
        return [self._api_item_to_result(item) for item in items]

    # -------------------- Tag Operations --------------------

    async def get_tags(self, limit: int = 100) -> list[str]:
        """Get all tags in the library."""
        tags = await self.api_client.get_tags(limit)
        return [t.get("tag", "") for t in tags if t.get("tag")]

    # -------------------- Collection Search Operations --------------------

    async def find_collection_by_name(
        self,
        name: str,
        exact_match: bool = False,
    ) -> list[dict[str, Any]]:
        """
        Find collections by name.

        Args:
            name: Collection name to search for
            exact_match: Whether to require exact name match

        Returns:
            List of matching collections with match scores
        """
        all_collections = await self.get_collections()
        matches = []

        search_name = name.lower().strip()

        for coll in all_collections:
            data = coll.get("data", {})
            coll_name = data.get("name", "")
            coll_name_lower = coll_name.lower()

            # Calculate match score
            if exact_match:
                if coll_name_lower == search_name:
                    matches.append({**coll, "match_score": 1.0})
            else:
                # Fuzzy matching
                if search_name in coll_name_lower:
                    # Calculate score based on position and length
                    if coll_name_lower == search_name:
                        score = 1.0  # Exact match
                    elif coll_name_lower.startswith(search_name):
                        score = 0.9  # Starts with
                    else:
                        score = 0.7  # Contains
                    matches.append({**coll, "match_score": score})

        # Sort by match score (descending)
        matches.sort(key=lambda x: x.get("match_score", 0), reverse=True)

        return matches

    # -------------------- BibTeX Operations --------------------

    async def get_bibtex(
        self,
        item_key: str,
        library_id: int = 1,
    ) -> str:
        """
        Get BibTeX for an item.

        Tries Better BibTeX first, then falls back to generated BibTeX.

        Args:
            item_key: Item key
            library_id: Library ID

        Returns:
            BibTeX string
        """
        # Try Better BibTeX first
        if self.bibtex_client:
            try:
                bibtex = self.bibtex_client.export_bibtex(item_key, library_id)
                if bibtex:
                    return bibtex
            except Exception as e:
                logger.debug(f"Better BibTeX export failed: {e}")

        # Fall back to generated BibTeX
        item = await self.get_item(item_key)
        return self._bibtex_formatter.format_item(item)

    # -------------------- Annotation Operations --------------------

    async def get_annotations(
        self,
        item_key: str,
        library_id: int = 1,
    ) -> list[dict[str, Any]]:
        """
        Get annotations for an item.

        Uses Better BibTeX if available.

        Args:
            item_key: Item key
            library_id: Library ID

        Returns:
            List of annotations
        """
        if self.bibtex_client:
            try:
                # Get citekey first
                citekey = self.bibtex_client.get_citekey(item_key, library_id)
                if citekey:
                    return self.bibtex_client.get_annotations(citekey, library_id)
            except Exception as e:
                logger.debug(f"Better BibTeX annotations failed: {e}")

        # Fall back to getting child annotations via API
        children = await self.get_item_children(item_key, item_type="annotation")
        return children

    # -------------------- Note Operations --------------------

    async def get_notes(
        self,
        item_key: str,
    ) -> list[dict[str, Any]]:
        """
        Get notes for an item.

        Args:
            item_key: Item key

        Returns:
            List of notes
        """
        return await self.get_item_children(item_key, item_type="note")

    async def create_note(
        self,
        parent_key: str,
        content: str,
        tags: list[str] | None = None,
    ) -> dict[str, Any]:
        """
        Create a note attached to an item.

        Args:
            parent_key: Parent item key
            content: Note content (HTML)
            tags: Optional tags

        Returns:
            Created note data
        """
        return await self.api_client.create_note(parent_key, content, tags)

    # -------------------- Bundle Operations --------------------

    async def get_item_bundle(
        self,
        item_key: str,
        include_fulltext: bool = False,
        include_annotations: bool = True,
        include_notes: bool = True,
        include_bibtex: bool = False,
    ) -> dict[str, Any]:
        """
        Get comprehensive bundle of item data.

        Args:
            item_key: Item key
            include_fulltext: Include full text content
            include_annotations: Include annotations
            include_notes: Include notes
            include_bibtex: Include BibTeX

        Returns:
            Bundle with metadata, children, and optional content
        """
        bundle: dict[str, Any] = {}

        # Get base item
        item = await self.get_item(item_key)
        bundle["metadata"] = item

        # Get children
        children = await self.get_item_children(item_key)
        bundle["attachments"] = [
            c for c in children if c.get("data", {}).get("itemType") == "attachment"
        ]

        if include_notes:
            bundle["notes"] = [
                c for c in children if c.get("data", {}).get("itemType") == "note"
            ]

        if include_annotations:
            bundle["annotations"] = await self.get_annotations(item_key)

        if include_fulltext:
            bundle["fulltext"] = await self.get_fulltext(item_key)

        if include_bibtex:
            bundle["bibtex"] = await self.get_bibtex(item_key)

        return bundle

    # -------------------- Helper Methods --------------------

    def _api_item_to_result(self, item: dict[str, Any]) -> SearchResult:
        """Convert API item to SearchResult."""
        data = item.get("data", {})
        tags = [t.get("tag", "") for t in data.get("tags", []) if t.get("tag")]

        return SearchResult(
            key=data.get("key", item.get("key", "")),
            title=data.get("title", "Untitled"),
            authors=format_creators(data.get("creators", [])),
            date=data.get("date"),
            item_type=data.get("itemType", "unknown"),
            abstract=data.get("abstractNote"),
            doi=data.get("DOI"),
            tags=tags if tags else None,
            raw_data=item,
        )

    def _zotero_item_to_result(self, item: ZoteroItem) -> SearchResult:
        """Convert ZoteroItem to SearchResult."""
        return SearchResult(
            key=item.key,
            title=item.title or "Untitled",
            authors=item.creators or "",
            date=item.date_added,
            item_type=item.item_type or "unknown",
            abstract=item.abstract,
            doi=item.doi,
            tags=item.tags if item.tags else None,
        )


@lru_cache(maxsize=1)
def get_data_service() -> DataAccessService:
    """
    Get the singleton data access service.

    Returns:
        Configured DataAccessService
    """
    return DataAccessService()
