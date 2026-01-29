"""
Unified data access service for Zotero MCP.

Provides a single interface for accessing Zotero data through
multiple backends (API, local database, Better BibTeX).
"""

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
from zotero_mcp.formatters import JSONFormatter, MarkdownFormatter
from zotero_mcp.models.common import ResponseFormat, SearchResultItem
from zotero_mcp.services.item import ItemService
from zotero_mcp.services.search import SearchService
from zotero_mcp.utils.helpers import is_local_mode

logger = logging.getLogger(__name__)


class DataAccessService:
    """
    Unified data access service for Zotero MCP.

    Acts as a Facade delegating to specialized services:
    - ItemService: CRUD, collections, tags
    - SearchService: Search operations

    Automatically selects the best available backend for each operation:
    - Local Database: Used for fast reads and search when available.
    - Better BibTeX: Used for citation keys and annotation extraction.
    - Zotero API: Used for write operations and fallback when local access is unavailable.
    """

    def __init__(
        self,
        api_client: ZoteroAPIClient | None = None,
        local_client: LocalDatabaseClient | None = None,
        bibtex_client: BetterBibTeXClient | None = None,
    ):
        """
        Initialize the DataAccessService.

        Args:
            api_client: Optional pre-configured ZoteroAPIClient.
            local_client: Optional pre-configured LocalDatabaseClient.
            bibtex_client: Optional pre-configured BetterBibTeXClient.
        """
        self._api_client = api_client
        self._local_client = local_client
        self._bibtex_client = bibtex_client
        self._formatters = {
            ResponseFormat.MARKDOWN: MarkdownFormatter(),
            ResponseFormat.JSON: JSONFormatter(),
        }

        # Initialize sub-services (lazy loading clients)
        self._item_service: ItemService | None = None
        self._search_service: SearchService | None = None

        # Validate configuration
        self._validate_config()

    def _validate_config(self) -> None:
        """Validate configuration settings."""
        if not is_local_mode():
            # Check for API key and Library ID in web mode
            import os

            api_key = os.getenv("ZOTERO_API_KEY")
            library_id = os.getenv("ZOTERO_LIBRARY_ID")

            if not api_key:
                logger.warning("ZOTERO_API_KEY is missing. Web API calls will fail.")
            if not library_id:
                logger.warning("ZOTERO_LIBRARY_ID is missing. Web API calls will fail.")

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

    @property
    def item_service(self) -> ItemService:
        """Get ItemService instance."""
        if self._item_service is None:
            self._item_service = ItemService(
                api_client=self.api_client,
                local_client=self.local_client,
                bibtex_client=self.bibtex_client,
            )
        return self._item_service

    @property
    def search_service(self) -> SearchService:
        """Get SearchService instance."""
        if self._search_service is None:
            self._search_service = SearchService(
                api_client=self.api_client,
                local_client=self.local_client,
            )
        return self._search_service

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
    ) -> list[SearchResultItem]:
        """
        Search items in the library.
        Delegates to SearchService.
        """
        return await self.search_service.search_items(query, limit, offset, qmode)

    async def get_recent_items(
        self,
        limit: int = 10,
        days: int = 7,
    ) -> list[SearchResultItem]:
        """
        Get recently added items.
        Delegates to SearchService.
        """
        return await self.search_service.get_recent_items(limit, days)

    async def search_by_tag(
        self,
        tags: list[str],
        exclude_tags: list[str] | None = None,
        limit: int = 25,
    ) -> list[SearchResultItem]:
        """
        Search items by tags.
        Delegates to SearchService.
        """
        return await self.search_service.search_by_tag(tags, exclude_tags, limit)

    # -------------------- Item Operations --------------------

    async def get_item(
        self,
        item_key: str,
    ) -> dict[str, Any]:
        """Get item by key."""
        return await self.item_service.get_item(item_key)

    async def get_item_children(
        self,
        item_key: str,
        item_type: str | None = None,
    ) -> list[dict[str, Any]]:
        """Get child items."""
        return await self.item_service.get_item_children(item_key, item_type)

    async def get_fulltext(
        self,
        item_key: str,
    ) -> str | None:
        """Get full-text content."""
        return await self.item_service.get_fulltext(item_key)

    # -------------------- Collection Operations --------------------

    async def get_collections(self) -> list[dict[str, Any]]:
        """Get all collections."""
        return await self.item_service.get_collections()

    async def create_collection(
        self, name: str, parent_key: str | None = None
    ) -> dict[str, Any]:
        """Create a new collection."""
        return await self.item_service.create_collection(name, parent_key)

    async def delete_collection(self, collection_key: str) -> None:
        """Delete a collection."""
        await self.item_service.delete_collection(collection_key)

    async def update_collection(
        self,
        collection_key: str,
        name: str | None = None,
        parent_key: str | None = None,
    ) -> None:
        """Update a collection."""
        await self.item_service.update_collection(collection_key, name, parent_key)

    async def get_collection_items(
        self,
        collection_key: str,
        limit: int = 100,
    ) -> list[SearchResultItem]:
        """Get items in a collection."""
        return await self.item_service.get_collection_items(collection_key, limit)

    # -------------------- Tag Operations --------------------

    async def get_tags(self, limit: int = 100) -> list[str]:
        """Get all tags."""
        return await self.item_service.get_tags(limit)

    # -------------------- Collection Search Operations --------------------

    async def find_collection_by_name(
        self,
        name: str,
        exact_match: bool = False,
    ) -> list[dict[str, Any]]:
        """Find collections by name."""
        return await self.item_service.find_collection_by_name(name, exact_match)

    # -------------------- BibTeX Operations --------------------

    async def get_bibtex(
        self,
        item_key: str,
        library_id: int = 1,
    ) -> str:
        """Get BibTeX for an item."""
        return await self.item_service.get_bibtex(item_key, library_id)

    # -------------------- Annotation Operations --------------------

    async def get_annotations(
        self,
        item_key: str,
        library_id: int = 1,
    ) -> list[dict[str, Any]]:
        """Get annotations for an item."""
        return await self.item_service.get_annotations(item_key, library_id)

    # -------------------- Note Operations --------------------

    async def get_notes(
        self,
        item_key: str,
    ) -> list[dict[str, Any]]:
        """Get notes for an item."""
        return await self.item_service.get_notes(item_key)

    async def create_note(
        self,
        parent_key: str,
        content: str,
        tags: list[str] | None = None,
    ) -> dict[str, Any]:
        """Create a note attached to an item."""
        return await self.item_service.create_note(parent_key, content, tags)

    # -------------------- Item Management Operations --------------------

    async def add_item_to_collection(
        self, collection_key: str, item_key: str
    ) -> dict[str, Any]:
        """Add an item to a collection."""
        return await self.item_service.add_item_to_collection(collection_key, item_key)

    async def remove_item_from_collection(
        self, collection_key: str, item_key: str
    ) -> dict[str, Any]:
        """Remove an item from a collection."""
        return await self.item_service.remove_item_from_collection(
            collection_key, item_key
        )

    async def delete_item(self, item_key: str) -> dict[str, Any]:
        """Delete an item."""
        return await self.item_service.delete_item(item_key)

    async def add_tags_to_item(self, item_key: str, tags: list[str]) -> dict[str, Any]:
        """Add tags to an item."""
        return await self.item_service.add_tags_to_item(item_key, tags)

    async def update_item(self, item: dict[str, Any]) -> dict[str, Any]:
        """Update an item's data."""
        return await self.item_service.update_item(item)

    async def create_items(self, items: list[dict[str, Any]]) -> dict[str, Any]:
        """Create new items."""
        return await self.item_service.create_items(items)

    # -------------------- Bundle Operations --------------------

    async def get_item_bundle(
        self,
        item_key: str,
        include_fulltext: bool = False,
        include_annotations: bool = True,
        include_notes: bool = True,
        include_bibtex: bool = False,
    ) -> dict[str, Any]:
        """Get comprehensive bundle of item data."""
        return await self.item_service.get_item_bundle(
            item_key,
            include_fulltext,
            include_annotations,
            include_notes,
            include_bibtex,
        )

    # -------------------- Helper Methods (Legacy Support) --------------------

    def _api_item_to_result(self, item: dict[str, Any]) -> SearchResultItem:
        """Convert API item to SearchResultItem."""
        # Delegate to search service or item service (both have this helper)
        # We can expose it in ItemService public API if needed, or duplicate strictly for legacy
        # For now, it's safer to keep the private method here if it's used internally?
        # Actually, it's used by SearchService now.
        # But this class no longer implements logic, so we might not need it unless subclasses use it.
        # Let's keep a implementation that delegates to ItemService implementation
        return self.item_service._api_item_to_result(item)

    def _zotero_item_to_result(self, item: ZoteroItem) -> SearchResultItem:
        """Convert ZoteroItem to SearchResultItem."""
        return self.item_service._zotero_item_to_result(item)


@lru_cache(maxsize=1)
def get_data_service() -> DataAccessService:
    """
    Get the singleton data access service.

    Returns:
        Configured DataAccessService
    """
    return DataAccessService()
