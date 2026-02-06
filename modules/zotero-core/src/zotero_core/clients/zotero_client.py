"""
Zotero API client wrapper.

Provides async-compatible wrapper around pyzotero with proper types
and unified error handling for the zotero-core module.
"""

import asyncio
from typing import Any, Literal

from pyzotero import zotero


class ZoteroClientError(Exception):
    """Base exception for Zotero client errors."""

    pass


class ZoteroClient:
    """
    Async-compatible wrapper around pyzotero.

    Provides typed methods for common Zotero operations with
    proper error handling and async support via asyncio.to_thread.
    """

    def __init__(
        self,
        library_id: str,
        api_key: str,
        library_type: Literal["user", "group"] = "user",
        local: bool = False,
    ):
        """
        Initialize Zotero client.

        Args:
            library_id: Zotero library ID
            api_key: Zotero API key
            library_type: Type of library ("user" or "group")
            local: Whether to use local Zotero API
        """
        self.library_id = library_id
        self.api_key = api_key
        self.library_type = library_type
        self.local = local
        self._client: zotero.Zotero | None = None

    @property
    def client(self) -> zotero.Zotero:
        """Get or create the pyzotero client."""
        if self._client is None:
            self._client = zotero.Zotero(
                library_id=self.library_id,
                library_type=self.library_type,
                api_key=self.api_key,
                local=self.local,
            )
        return self._client

    async def get_item(self, item_key: str) -> dict[str, Any] | None:
        """
        Get a single item by key.

        Args:
            item_key: The unique item key

        Returns:
            Item data dict, or None if not found

        Raises:
            ZoteroClientError: If API request fails
        """
        try:
            result = await asyncio.to_thread(self.client.item, item_key)

            # pyzotero can return int status codes instead of data
            if isinstance(result, int):
                if result == 404:
                    return None
                raise ZoteroClientError(
                    f"Zotero API returned HTTP {result} for item {item_key}"
                )

            return result
        except Exception as e:
            if isinstance(e, ZoteroClientError):
                raise
            raise ZoteroClientError(f"Failed to get item {item_key}: {e}") from e

    async def get_items(
        self,
        limit: int = 100,
        start: int = 0,
        item_type: str | None = None,
    ) -> list[dict[str, Any]]:
        """
        Get multiple items from the library.

        Args:
            limit: Maximum number of items to return
            start: Offset for pagination
            item_type: Filter by item type (e.g., "journalArticle")

        Returns:
            List of item data dicts

        Raises:
            ZoteroClientError: If API request fails
        """
        try:
            items = await asyncio.to_thread(
                self.client.items,
                limit=limit,
                start=start,
                itemType=item_type,
            )

            # pyzotero can return int status codes instead of data
            if isinstance(items, int):
                raise ZoteroClientError(
                    f"Zotero API returned HTTP {items} when fetching items"
                )

            return items
        except Exception as e:
            if isinstance(e, ZoteroClientError):
                raise
            raise ZoteroClientError(f"Failed to fetch items: {e}") from e

    async def create_item(self, item_data: dict[str, Any]) -> dict[str, Any]:
        """
        Create a new item.

        Args:
            item_data: Item data dict (must include 'itemType' field)

        Returns:
            Created item data dict

        Raises:
            ZoteroClientError: If API request fails
        """
        try:
            # pyzotero expects a list of items
            result = await asyncio.to_thread(
                self.client.create_items,
                [item_data],
            )

            # pyzotero can return int status codes instead of data
            if isinstance(result, int):
                raise ZoteroClientError(
                    f"Zotero API returned HTTP {result} when creating item"
                )

            # create_items returns a list of results
            if isinstance(result, list) and len(result) > 0:
                return result[0]

            raise ZoteroClientError("Unexpected empty response from create_items")
        except Exception as e:
            if isinstance(e, ZoteroClientError):
                raise
            raise ZoteroClientError(f"Failed to create item: {e}") from e

    async def update_item(
        self, item_key: str, item_data: dict[str, Any]
    ) -> dict[str, Any]:
        """
        Update an existing item.

        Args:
            item_key: The unique item key
            item_data: Updated item data dict

        Returns:
            Updated item data dict

        Raises:
            ZoteroClientError: If API request fails
        """
        try:
            # Ensure item has key and version for optimistic locking
            item_data["key"] = item_key
            if "version" not in item_data:
                # Fetch current item to get version
                current = await self.get_item(item_key)
                if current and "version" in current:
                    item_data["version"] = current["version"]

            result = await asyncio.to_thread(self.client.update_item, item_data)

            # pyzotero can return int status codes instead of data
            if isinstance(result, int):
                if result == 404:
                    raise ZoteroClientError(f"Item {item_key} not found")
                if result == 412:
                    raise ZoteroClientError(
                        f"Item {item_key} was modified by another client "
                        "(version conflict)"
                    )
                raise ZoteroClientError(
                    f"Zotero API returned HTTP {result} when updating item {item_key}"
                )

            return result
        except Exception as e:
            if isinstance(e, ZoteroClientError):
                raise
            raise ZoteroClientError(f"Failed to update item {item_key}: {e}") from e

    async def delete_item(self, item_key: str) -> bool:
        """
        Delete an item.

        Args:
            item_key: The unique item key

        Returns:
            True if deleted successfully

        Raises:
            ZoteroClientError: If API request fails
        """
        try:
            result = await asyncio.to_thread(self.client.delete_item, item_key)

            # pyzotero returns True on success, or int status code on failure
            if isinstance(result, int):
                if result == 404:
                    raise ZoteroClientError(f"Item {item_key} not found")
                raise ZoteroClientError(
                    f"Zotero API returned HTTP {result} when deleting item {item_key}"
                )

            return result
        except Exception as e:
            if isinstance(e, ZoteroClientError):
                raise
            raise ZoteroClientError(f"Failed to delete item {item_key}: {e}") from e

    async def add_tags(self, item_key: str, tags: list[str]) -> dict[str, Any] | None:
        """
        Add tags to an item.

        Args:
            item_key: The unique item key
            tags: List of tag names to add

        Returns:
            Updated item data dict, or None if item not found

        Raises:
            ZoteroClientError: If API request fails
        """
        try:
            # Fetch current item
            current = await self.get_item(item_key)
            if not current:
                return None

            # Get existing tags
            data = current.get("data", current)
            existing_tags = data.get("tags", [])

            # Extract existing tag names
            existing_tag_names = {tag.get("tag", "") for tag in existing_tags}

            # Add new tags (avoiding duplicates)
            for tag in tags:
                if tag and tag not in existing_tag_names:
                    existing_tags.append({"tag": tag})

            # Update item with new tags
            data["tags"] = existing_tags
            result = await self.update_item(item_key, data)

            return result
        except Exception as e:
            if isinstance(e, ZoteroClientError):
                raise
            raise ZoteroClientError(
                f"Failed to add tags to item {item_key}: {e}"
            ) from e

    async def remove_tags(
        self, item_key: str, tags: list[str]
    ) -> dict[str, Any] | None:
        """
        Remove tags from an item.

        Args:
            item_key: The unique item key
            tags: List of tag names to remove

        Returns:
            Updated item data dict, or None if item not found

        Raises:
            ZoteroClientError: If API request fails
        """
        try:
            # Fetch current item
            current = await self.get_item(item_key)
            if not current:
                return None

            # Get existing tags
            data = current.get("data", current)
            existing_tags = data.get("tags", [])

            # Remove specified tags (case-insensitive)
            tags_lower = {tag.lower() for tag in tags}
            filtered_tags = [
                tag
                for tag in existing_tags
                if tag.get("tag", "").lower() not in tags_lower
            ]

            # Update item with filtered tags
            data["tags"] = filtered_tags
            result = await self.update_item(item_key, data)

            return result
        except Exception as e:
            if isinstance(e, ZoteroClientError):
                raise
            raise ZoteroClientError(
                f"Failed to remove tags from item {item_key}: {e}"
            ) from e
