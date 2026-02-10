"""
Search Service.

Handles search operations for Zotero items using API and Local DB.
"""

import logging
from typing import Literal

from zotero_mcp.clients.zotero import (
    LocalDatabaseClient,
    ZoteroAPIClient,
    ZoteroItem,
)
from zotero_mcp.models.common import SearchResultItem
from zotero_mcp.utils.formatting.helpers import format_creators

logger = logging.getLogger(__name__)


class SearchService:
    """
    Service for searching Zotero items.
    """

    def __init__(
        self,
        api_client: ZoteroAPIClient,
        local_client: LocalDatabaseClient | None = None,
    ):
        """
        Initialize SearchService.

        Args:
            api_client: Zotero API client
            local_client: Local database client (optional)
        """
        self.api_client = api_client
        self.local_client = local_client

    async def search_items(
        self,
        query: str,
        limit: int = 25,
        offset: int = 0,
        qmode: Literal["titleCreatorYear", "everything"] = "titleCreatorYear",
    ) -> list[SearchResultItem]:
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
                if offset >= len(items):
                    return []
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
        if isinstance(items, int):
            logger.warning(f"Search API returned HTTP status {items}")
            return []
        return [self._api_item_to_result(item) for item in items]

    async def get_recent_items(
        self,
        limit: int = 10,
        days: int = 7,
    ) -> list[SearchResultItem]:
        """
        Get recently added items.

        Args:
            limit: Maximum results
            days: Days to look back

        Returns:
            List of recent items
        """
        items = await self.api_client.get_recent_items(limit=limit, days=days)
        if isinstance(items, int):
            logger.warning(f"Recent items API returned HTTP status {items}")
            return []
        return [self._api_item_to_result(item) for item in items]

    async def search_by_tag(
        self,
        tags: list[str],
        exclude_tags: list[str] | None = None,
        limit: int = 25,
    ) -> list[SearchResultItem]:
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
        if isinstance(items, int):
            logger.warning(f"Tag search API returned HTTP status {items}")
            return []

        # Filter by additional tags
        for tag in tags[1:]:
            items = [
                i
                for i in items
                if tag
                in {
                    t.get("tag", "")
                    for t in i.get("data", {}).get("tags", [])
                    if t.get("tag")
                }
            ]

        # Exclude tags
        if exclude_tags:
            for tag in exclude_tags:
                items = [
                    i
                    for i in items
                    if tag
                    not in {
                        t.get("tag", "")
                        for t in i.get("data", {}).get("tags", [])
                        if t.get("tag")
                    }
                ]

        return [self._api_item_to_result(item) for item in items[:limit]]

    # -------------------- Helper Methods --------------------

    def _api_item_to_result(self, item: dict) -> SearchResultItem:
        """Convert API item to SearchResultItem."""
        data = item.get("data", {})
        tags = [t.get("tag", "") for t in data.get("tags", []) if t.get("tag")]

        return SearchResultItem(
            key=data.get("key", item.get("key", "")),
            title=data.get("title", "Untitled"),
            authors=format_creators(data.get("creators", [])),
            date=data.get("date"),
            item_type=data.get("itemType", "unknown"),
            abstract=data.get("abstractNote"),
            doi=data.get("DOI"),
            tags=tags or [],
        )

    def _zotero_item_to_result(self, item: ZoteroItem) -> SearchResultItem:
        """Convert ZoteroItem to SearchResultItem."""
        return SearchResultItem(
            key=item.key,
            title=item.title or "Untitled",
            authors=item.creators or "",
            date=item.date_added,
            item_type=item.item_type or "unknown",
            abstract=item.abstract,
            doi=item.doi,
            tags=item.tags or [],
        )
