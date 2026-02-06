"""
Item service for Zotero CRUD operations.

Provides high-level business logic for managing Zotero items,
including CRUD operations and tag management.
"""

import logging
from typing import Any, Literal

from zotero_core.clients.zotero_client import ZoteroClient, ZoteroClientError
from zotero_core.models import Item, ItemCreate, ItemUpdate

logger = logging.getLogger(__name__)


class ItemServiceError(Exception):
    """Base exception for ItemService errors."""

    pass


class ItemService:
    """
    Service for managing Zotero items.

    Provides high-level CRUD operations for Zotero items with
    proper error handling and type conversion.
    """

    def __init__(
        self,
        library_id: str,
        api_key: str,
        library_type: Literal["user", "group"] = "user",
        local: bool = False,
    ):
        """
        Initialize ItemService.

        Args:
            library_id: Zotero library ID
            api_key: Zotero API key
            library_type: Type of library ("user" or "group")
            local: Whether to use local Zotero API
        """
        self.client = ZoteroClient(
            library_id=library_id,
            api_key=api_key,
            library_type=library_type,
            local=local,
        )

    async def get_item(self, key: str) -> Item | None:
        """
        Get an item by key.

        Args:
            key: The unique item key

        Returns:
            Item object, or None if not found

        Raises:
            ItemServiceError: If operation fails
        """
        try:
            data = await self.client.get_item(key)
            if not data:
                return None

            # Normalize data structure (pyzotero can return different formats)
            normalized = self._normalize_item_data(data)
            return Item(**normalized)
        except ZoteroClientError as e:
            logger.error(f"Failed to get item {key}: {e}")
            raise ItemServiceError(f"Failed to get item {key}: {e}") from e
        except Exception as e:
            logger.error(f"Unexpected error getting item {key}: {e}")
            raise ItemServiceError(f"Unexpected error getting item {key}: {e}") from e

    async def get_all_items(
        self,
        limit: int = 100,
        start: int = 0,
        item_type: str | None = None,
    ) -> list[Item]:
        """
        Get all items from the library.

        Args:
            limit: Maximum number of items to return
            start: Offset for pagination
            item_type: Filter by item type (e.g., "journalArticle")

        Returns:
            List of Item objects

        Raises:
            ItemServiceError: If operation fails
        """
        try:
            items_data = await self.client.get_items(
                limit=limit, start=start, item_type=item_type
            )

            items = []
            for data in items_data:
                try:
                    normalized = self._normalize_item_data(data)
                    items.append(Item(**normalized))
                except Exception as e:
                    logger.warning(f"Failed to parse item data: {e}")
                    continue

            return items
        except ZoteroClientError as e:
            logger.error(f"Failed to fetch items: {e}")
            raise ItemServiceError(f"Failed to fetch items: {e}") from e
        except Exception as e:
            logger.error(f"Unexpected error fetching items: {e}")
            raise ItemServiceError(f"Unexpected error fetching items: {e}") from e

    async def create_item(self, item_data: ItemCreate) -> Item:
        """
        Create a new item.

        Args:
            item_data: ItemCreate model with item data

        Returns:
            Created Item object

        Raises:
            ItemServiceError: If operation fails
        """
        try:
            # Convert ItemCreate to dict format expected by pyzotero
            item_dict = self._item_create_to_dict(item_data)

            result = await self.client.create_item(item_dict)
            normalized = self._normalize_item_data(result)
            return Item(**normalized)
        except ZoteroClientError as e:
            logger.error(f"Failed to create item: {e}")
            raise ItemServiceError(f"Failed to create item: {e}") from e
        except Exception as e:
            logger.error(f"Unexpected error creating item: {e}")
            raise ItemServiceError(f"Unexpected error creating item: {e}") from e

    async def update_item(self, key: str, item_data: ItemUpdate) -> Item:
        """
        Update an existing item.

        Args:
            key: The unique item key
            item_data: ItemUpdate model with updated fields

        Returns:
            Updated Item object

        Raises:
            ItemServiceError: If operation fails
        """
        try:
            # Convert ItemUpdate to dict format expected by pyzotero
            item_dict = self._item_update_to_dict(item_data)

            result = await self.client.update_item(key, item_dict)
            normalized = self._normalize_item_data(result)
            return Item(**normalized)
        except ZoteroClientError as e:
            logger.error(f"Failed to update item {key}: {e}")
            raise ItemServiceError(f"Failed to update item {key}: {e}") from e
        except Exception as e:
            logger.error(f"Unexpected error updating item {key}: {e}")
            raise ItemServiceError(f"Unexpected error updating item {key}: {e}") from e

    async def delete_item(self, key: str) -> bool:
        """
        Delete an item.

        Args:
            key: The unique item key

        Returns:
            True if deleted successfully

        Raises:
            ItemServiceError: If operation fails
        """
        try:
            return await self.client.delete_item(key)
        except ZoteroClientError as e:
            logger.error(f"Failed to delete item {key}: {e}")
            raise ItemServiceError(f"Failed to delete item {key}: {e}") from e
        except Exception as e:
            logger.error(f"Unexpected error deleting item {key}: {e}")
            raise ItemServiceError(f"Unexpected error deleting item {key}: {e}") from e

    async def add_tags(self, key: str, tags: list[str]) -> Item:
        """
        Add tags to an item.

        Args:
            key: The unique item key
            tags: List of tag names to add

        Returns:
            Updated Item object

        Raises:
            ItemServiceError: If operation fails or item not found
        """
        try:
            result = await self.client.add_tags(key, tags)
            if not result:
                raise ItemServiceError(f"Item {key} not found")

            normalized = self._normalize_item_data(result)
            return Item(**normalized)
        except ZoteroClientError as e:
            logger.error(f"Failed to add tags to item {key}: {e}")
            raise ItemServiceError(f"Failed to add tags to item {key}: {e}") from e
        except ItemServiceError:
            raise
        except Exception as e:
            logger.error(f"Unexpected error adding tags to item {key}: {e}")
            raise ItemServiceError(
                f"Unexpected error adding tags to item {key}: {e}"
            ) from e

    async def remove_tags(self, key: str, tags: list[str]) -> Item:
        """
        Remove tags from an item.

        Args:
            key: The unique item key
            tags: List of tag names to remove

        Returns:
            Updated Item object

        Raises:
            ItemServiceError: If operation fails or item not found
        """
        try:
            result = await self.client.remove_tags(key, tags)
            if not result:
                raise ItemServiceError(f"Item {key} not found")

            normalized = self._normalize_item_data(result)
            return Item(**normalized)
        except ZoteroClientError as e:
            logger.error(f"Failed to remove tags from item {key}: {e}")
            raise ItemServiceError(f"Failed to remove tags from item {key}: {e}") from e
        except ItemServiceError:
            raise
        except Exception as e:
            logger.error(f"Unexpected error removing tags from item {key}: {e}")
            raise ItemServiceError(
                f"Unexpected error removing tags from item {key}: {e}"
            ) from e

    # -------------------- Helper Methods --------------------

    def _normalize_item_data(self, data: dict[str, Any]) -> dict[str, Any]:
        """
        Normalize item data from pyzotero to consistent format.

        pyzotero can return different formats:
        - {"key": "...", "version": ..., "data": {...}}
        - {"key": "...", "version": ..., "title": ..., ...}

        This method normalizes to a consistent structure for Item model.

        Args:
            data: Raw item data from pyzotero

        Returns:
            Normalized item data dict
        """
        # Check if data has nested "data" field
        if "data" in data:
            # Extract nested data but keep top-level fields
            inner = data["data"]
            normalized = {
                **inner,  # Use inner data as base
                "key": data.get("key", inner.get("key")),
                "version": data.get("version", inner.get("version")),
            }
        else:
            # Already flat
            normalized = data.copy()

        # Ensure required fields
        if "key" not in normalized:
            raise ValueError("Item data missing required 'key' field")

        # Map itemType to type if needed
        if "itemType" in normalized and "type" not in normalized:
            normalized["type"] = normalized.pop("itemType")

        # Normalize tags: extract tag names from [{"tag": "..."}] format
        if "tags" in normalized:
            tags = normalized["tags"]
            if isinstance(tags, list):
                # Extract tag names
                normalized["tags"] = [
                    tag.get("tag", tag) if isinstance(tag, dict) else tag
                    for tag in tags
                ]

        # Store raw data for reference
        normalized["raw_data"] = data

        return normalized

    def _item_create_to_dict(self, item: ItemCreate) -> dict[str, Any]:
        """
        Convert ItemCreate model to dict format for pyzotero.

        Args:
            item: ItemCreate model

        Returns:
            Dict in format expected by pyzotero
        """
        data = {
            "itemType": item.type,
            "title": item.title,
        }

        # Add optional fields
        if item.creators:
            data["creators"] = item.creators
        if item.abstract:
            data["abstractNote"] = item.abstract
        if item.date:
            data["date"] = item.date
        if item.doi:
            data["DOI"] = item.doi
        if item.url:
            data["url"] = item.url
        if item.collections:
            data["collections"] = item.collections
        if item.tags:
            data["tags"] = [{"tag": tag} for tag in item.tags]

        # Add type-specific fields
        if item.data:
            data.update(item.data)

        return data

    def _item_update_to_dict(self, item: ItemUpdate) -> dict[str, Any]:
        """
        Convert ItemUpdate model to dict format for pyzotero.

        Args:
            item: ItemUpdate model

        Returns:
            Dict in format expected by pyzotero
        """
        data = {}

        # Map field names to Zotero API format
        field_map = {
            "title": "title",
            "abstract": "abstractNote",
            "date": "date",
            "doi": "DOI",
            "url": "url",
        }

        for model_field, api_field in field_map.items():
            value = getattr(item, model_field, None)
            if value is not None:
                data[api_field] = value

        # Handle creators
        if item.creators is not None:
            data["creators"] = item.creators

        # Handle tags
        if item.tags is not None:
            data["tags"] = [{"tag": tag} for tag in item.tags]

        # Handle collections
        if item.collections is not None:
            data["collections"] = item.collections

        # Handle version (for optimistic locking)
        if item.version is not None:
            data["version"] = item.version

        # Add type-specific fields
        if item.data is not None:
            data.update(item.data)

        return data
