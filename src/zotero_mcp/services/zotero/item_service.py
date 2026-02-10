"""
Item and Collection Service.

Handles CRUD operations for Zotero items, collections, and tags.
"""

import asyncio
import logging
from typing import Any

from zotero_mcp.clients.zotero import LocalDatabaseClient, ZoteroAPIClient, ZoteroItem
from zotero_mcp.models.common import SearchResultItem
from zotero_mcp.utils.async_helpers.cache import ResponseCache
from zotero_mcp.utils.formatting.helpers import format_creators

logger = logging.getLogger(__name__)


class ItemService:
    """
    Service for managing Zotero items, collections, and tags.
    """

    def __init__(
        self,
        api_client: ZoteroAPIClient,
        local_client: LocalDatabaseClient | None = None,
    ):
        """
        Initialize ItemService.

        Args:
            api_client: Zotero API client
            local_client: Local database client (optional)
        """
        self.api_client = api_client
        self.local_client = local_client
        # Internal cache for slow, infrequent changing data (collections, tags)
        self._cache = ResponseCache(ttl_seconds=300)

    # -------------------- Item Operations --------------------

    async def get_item(self, item_key: str) -> dict[str, Any]:
        """Get item by key."""
        return await self.api_client.get_item(item_key)

    async def get_all_items(
        self,
        limit: int = 100,
        start: int = 0,
        item_type: str | None = None,
    ) -> list[SearchResultItem]:
        """Get all items in the library."""
        if self.local_client:
            fetch_limit = limit + max(start, 0) if start else limit
            local_items = self.local_client.get_items(
                limit=fetch_limit, include_fulltext=False
            )
            if item_type:
                local_items = [
                    item for item in local_items if item.item_type == item_type
                ]
            if start:
                local_items = local_items[start:]
            local_items = local_items[:limit]
            return [self._zotero_item_to_result(item) for item in local_items]

        api_items = await self.api_client.get_all_items(
            limit=limit, start=start, item_type=item_type
        )
        return [self._api_item_to_result(item) for item in api_items]

    async def get_item_children(
        self, item_key: str, item_type: str | None = None
    ) -> list[dict[str, Any]]:
        """Get child items (attachments, notes)."""
        return await self.api_client.get_item_children(item_key, item_type)

    async def get_fulltext(self, item_key: str) -> str | None:
        """Get full-text content for an item."""
        # Try API first (existing behavior)
        result = await self.api_client.get_fulltext(item_key)
        if result:
            return result

        # Fallback to local extraction if available
        if self.local_client:
            logger.info(f"API fulltext empty, trying local extraction for {item_key}")
            local_result = self.local_client.get_fulltext_by_key(item_key)
            if local_result:
                text, source = local_result
                logger.info(f"Local extraction succeeded from {source}")
                return text
            logger.warning(f"Local extraction also failed for {item_key}")

        return None

    # -------------------- Collection Operations --------------------

    async def get_collections(self) -> list[dict[str, Any]]:
        """Get all collections."""
        # Check cache first
        cache_key = "collections_list"
        cached = self._cache.get("get_collections", {"key": cache_key})
        if cached is not None:
            logger.debug("Returning cached collections list")
            return cached

        # Fetch from API
        collections = await self.api_client.get_collections()

        # Update cache
        self._cache.set("get_collections", {"key": cache_key}, collections)
        return collections

    async def get_sorted_collections(self) -> list[dict[str, Any]]:
        """
        Get all collections sorted by name (00_INBOXS, 01_*, 02_*, etc.).

        Returns:
            List of collections sorted alphabetically by name
        """
        all_collections = await self.get_collections()

        # Sort by collection name
        sorted_collections = sorted(
            all_collections,
            key=lambda coll: coll.get("data", {}).get("name", "").lower(),
        )

        logger.debug(
            f"Sorted {len(sorted_collections)} collections by name: "
            f"{[c.get('data', {}).get('name', '') for c in sorted_collections[:5]]}..."
        )

        return sorted_collections

    async def create_collection(
        self, name: str, parent_key: str | None = None
    ) -> dict[str, Any]:
        """Create a new collection."""
        result = await self.api_client.create_collection(name, parent_key)
        self._cache.invalidate("get_collections", {"key": "collections_list"})
        return result

    async def delete_collection(self, collection_key: str) -> None:
        """Delete a collection."""
        await self.api_client.delete_collection(collection_key)
        self._cache.invalidate("get_collections", {"key": "collections_list"})

    async def update_collection(
        self,
        collection_key: str,
        name: str | None = None,
        parent_key: str | None = None,
    ) -> None:
        """Update a collection."""
        await self.api_client.update_collection(collection_key, name, parent_key)
        self._cache.invalidate("get_collections", {"key": "collections_list"})

    async def get_collection_items(
        self, collection_key: str, limit: int = 100, start: int = 0
    ) -> list[SearchResultItem]:
        """Get items in a collection."""
        items = await self.api_client.get_collection_items(collection_key, limit, start)
        return [self._api_item_to_result(item) for item in items]

    async def find_collection_by_name(
        self, name: str, exact_match: bool = False
    ) -> list[dict[str, Any]]:
        """Find collections by name."""
        all_collections = await self.get_collections()
        matches = []
        search_name = name.lower().strip()

        for coll in all_collections:
            data = coll.get("data", {})
            coll_name = data.get("name", "")
            coll_name_lower = coll_name.lower()

            if exact_match:
                if coll_name_lower == search_name:
                    matches.append({**coll, "match_score": 1.0})
            else:
                if search_name in coll_name_lower:
                    if coll_name_lower == search_name:
                        score = 1.0
                    elif coll_name_lower.startswith(search_name):
                        score = 0.9
                    else:
                        score = 0.7
                    matches.append({**coll, "match_score": score})

        matches.sort(key=lambda x: x.get("match_score", 0), reverse=True)
        return matches

    # -------------------- Tag Operations --------------------

    async def get_tags(self, limit: int = 100) -> list[str]:
        """Get all tags in the library."""
        cache_params = {"limit": limit}
        cached = self._cache.get("get_tags", cache_params)
        if cached is not None:
            logger.debug("Returning cached tags list")
            return cached

        tags = await self.api_client.get_tags(limit)
        tag_list = [t.get("tag", "") for t in tags if t.get("tag")]

        self._cache.set("get_tags", cache_params, tag_list)
        return tag_list

    # -------------------- Annotation/Note --------------------

    async def get_annotations(
        self, item_key: str, library_id: int = 1
    ) -> list[dict[str, Any]]:
        """Get annotations for an item."""
        children = await self.get_item_children(item_key, item_type="annotation")
        return children

    async def get_notes(self, item_key: str) -> list[dict[str, Any]]:
        """Get notes for an item."""
        return await self.get_item_children(item_key, item_type="note")

    async def create_note(
        self, parent_key: str, content: str, tags: list[str] | None = None
    ) -> dict[str, Any]:
        """Create a note attached to an item."""
        return await self.api_client.create_note(parent_key, content, tags)

    # -------------------- Item Management --------------------

    async def add_item_to_collection(
        self, collection_key: str, item_key: str
    ) -> dict[str, Any]:
        """Add an item to a collection."""
        return await self.api_client.add_to_collection(collection_key, item_key)

    async def remove_item_from_collection(
        self, collection_key: str, item_key: str
    ) -> dict[str, Any]:
        """Remove an item from a collection."""
        return await self.api_client.remove_from_collection(collection_key, item_key)

    async def delete_item(self, item_key: str) -> dict[str, Any]:
        """Delete an item."""
        return await self.api_client.delete_item(item_key)

    async def add_tags_to_item(self, item_key: str, tags: list[str]) -> dict[str, Any]:
        """Add tags to an item."""
        result = await self.api_client.add_tags(item_key, tags)
        self._cache.invalidate("get_tags", {"limit": 100})
        return result

    async def upload_attachment(
        self, parent_key: str, file_path: str, title: str | None = None
    ) -> dict[str, Any]:
        """Upload a local file and attach it to an item."""
        return await self.api_client.upload_attachment(
            parent_key=parent_key,
            file_path=file_path,
            title=title,
        )

    async def update_item(self, item: dict[str, Any]) -> dict[str, Any]:
        """Update an item's data."""
        return await self.api_client.update_item(item)

    async def create_items(self, items: list[dict[str, Any]]) -> dict[str, Any]:
        """Create new items."""
        return await self.api_client.create_items(items)

    async def create_item(self, item: dict[str, Any]) -> dict[str, Any]:
        """Create a single item."""
        if not isinstance(item, dict) or not item:
            raise ValueError("Item payload must be a non-empty dict")
        return await self.api_client.create_items([item])

    async def get_item_bundle(
        self,
        item_key: str,
        include_fulltext: bool = False,
        include_annotations: bool = True,
        include_notes: bool = True,
    ) -> dict[str, Any]:
        """Get comprehensive bundle of item data."""
        bundle: dict[str, Any] = {}

        tasks: dict[str, Any] = {
            "metadata": self.get_item(item_key),
            "children": self.get_item_children(item_key),
        }
        if include_annotations:
            tasks["annotations"] = self.get_annotations(item_key)
        if include_fulltext:
            tasks["fulltext"] = self.get_fulltext(item_key)

        results = await asyncio.gather(*tasks.values(), return_exceptions=True)
        result_map = dict(zip(tasks.keys(), results, strict=False))

        metadata = result_map.get("metadata")
        if isinstance(metadata, Exception):
            raise metadata
        bundle["metadata"] = metadata

        children = result_map.get("children")
        if isinstance(children, Exception):
            logger.warning(f"Failed to load children for {item_key}: {children}")
            children = []
        bundle["attachments"] = [
            c for c in children if c.get("data", {}).get("itemType") == "attachment"
        ]

        if include_notes:
            bundle["notes"] = [
                c for c in children if c.get("data", {}).get("itemType") == "note"
            ]

        if include_annotations:
            annotations = result_map.get("annotations", [])
            if isinstance(annotations, Exception):
                logger.warning(
                    f"Failed to load annotations for {item_key}: {annotations}"
                )
                annotations = []
            bundle["annotations"] = annotations

        if include_fulltext:
            fulltext = result_map.get("fulltext")
            if isinstance(fulltext, Exception):
                logger.warning(f"Failed to load fulltext for {item_key}: {fulltext}")
                fulltext = None
            bundle["fulltext"] = fulltext

        return bundle

    # -------------------- Helpers --------------------

    def _api_item_to_result(self, item: dict[str, Any]) -> SearchResultItem:
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
