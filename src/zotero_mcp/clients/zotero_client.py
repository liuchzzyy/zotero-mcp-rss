"""
Zotero API client wrapper.

Provides async-compatible wrapper around pyzotero with proper types
and unified error handling.
"""

import asyncio
from dataclasses import dataclass
from functools import lru_cache
import os
from typing import Any, Literal

from pyzotero import zotero
from zotero_mcp.utils.errors import (
    ConfigurationError,
    NotFoundError,
)
from zotero_mcp.utils.helpers import is_local_mode


@dataclass
class AttachmentInfo:
    """Details about a Zotero attachment."""

    key: str
    title: str
    filename: str
    content_type: str
    parent_key: str | None = None


class ZoteroAPIClient:
    """
    Async-compatible wrapper around pyzotero.

    Provides typed methods for common Zotero operations with
    proper error handling and caching.
    """

    def __init__(
        self,
        library_id: str | int,
        library_type: Literal["user", "group"] = "user",
        api_key: str | None = None,
        local: bool = False,
    ):
        """
        Initialize Zotero API client.

        Args:
            library_id: Zotero library ID
            library_type: Type of library ("user" or "group")
            api_key: API key for web access (not needed for local)
            local: Whether to use local API
        """
        self.library_id = str(library_id)
        self.library_type = library_type
        self.api_key = api_key
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

    # -------------------- Search Methods --------------------

    async def search_items(
        self,
        query: str,
        qmode: Literal["titleCreatorYear", "everything"] = "titleCreatorYear",
        limit: int = 25,
        start: int = 0,
    ) -> list[dict[str, Any]]:
        """
        Search items in the library.

        Args:
            query: Search query
            qmode: Search mode
            limit: Maximum results
            start: Offset for pagination

        Returns:
            List of matching items
        """
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(
            None,
            lambda: self.client.items(
                q=query,
                qmode=qmode,
                limit=limit,
                start=start,
            ),
        )

    async def get_all_items(
        self,
        limit: int = 100,
        start: int = 0,
        item_type: str | None = None,
    ) -> list[dict[str, Any]]:
        """
        Get all items in the library.

        Args:
            limit: Maximum results
            start: Offset for pagination
            item_type: Filter by item type

        Returns:
            List of items
        """
        loop = asyncio.get_event_loop()
        kwargs: dict[str, Any] = {"limit": limit, "start": start}
        if item_type:
            kwargs["itemType"] = item_type
        return await loop.run_in_executor(
            None,
            lambda: self.client.items(**kwargs),
        )

    async def get_recent_items(
        self,
        limit: int = 10,
        days: int = 7,
    ) -> list[dict[str, Any]]:
        """
        Get recently added items.

        Args:
            limit: Maximum results
            days: Number of days to look back

        Returns:
            List of recent items
        """
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(
            None,
            lambda: self.client.items(
                sort="dateAdded",
                direction="desc",
                limit=limit,
            ),
        )

    # -------------------- Item Methods --------------------

    async def get_item(self, item_key: str) -> dict[str, Any]:
        """
        Get a single item by key.

        Args:
            item_key: Zotero item key

        Returns:
            Item data

        Raises:
            NotFoundError: If item not found
        """
        loop = asyncio.get_event_loop()
        try:
            return await loop.run_in_executor(
                None,
                lambda: self.client.item(item_key),
            )
        except Exception as e:
            if "404" in str(e).lower() or "not found" in str(e).lower():
                raise NotFoundError(f"Item not found: {item_key}")
            raise

    async def get_item_children(
        self,
        item_key: str,
        item_type: str | None = None,
    ) -> list[dict[str, Any]]:
        """
        Get child items (attachments, notes).

        Args:
            item_key: Parent item key
            item_type: Filter by child type

        Returns:
            List of child items
        """
        loop = asyncio.get_event_loop()
        children = await loop.run_in_executor(
            None,
            lambda: self.client.children(item_key),
        )

        if item_type:
            children = [
                c for c in children if c.get("data", {}).get("itemType") == item_type
            ]

        return children

    async def get_fulltext(self, item_key: str) -> str | None:
        """
        Get full-text content for an item.

        If the item is a parent, attempts to find the PDF attachment first.

        Args:
            item_key: Item key

        Returns:
            Full-text content if available
        """
        loop = asyncio.get_event_loop()

        # Helper to fetch text for a specific key
        async def fetch_text(key: str) -> str | None:
            try:
                result = await loop.run_in_executor(
                    None,
                    lambda: self.client.fulltext_item(key),
                )
                if isinstance(result, dict):
                    return result.get("content", "")
                return str(result) if result else None
            except Exception:
                return None

        # 1. Try direct fetch (works if item_key IS the attachment)
        text = await fetch_text(item_key)
        if text:
            return text

        # 2. If no text, assume it might be a parent item and look for PDF attachment
        try:
            # Get item children
            children = await self.get_item_children(item_key)
            pdf_key = None

            # Find PDF attachment
            for child in children:
                data = child.get("data", {})
                if (
                    data.get("itemType") == "attachment"
                    and data.get("contentType") == "application/pdf"
                ):
                    pdf_key = data.get("key")
                    break

            if pdf_key:
                return await fetch_text(pdf_key)

        except Exception:
            pass

        return None

    # -------------------- Collection Methods --------------------

    async def get_collections(self) -> list[dict[str, Any]]:
        """Get all collections in the library."""
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(
            None,
            lambda: self.client.collections(),
        )

    async def get_collection_items(
        self,
        collection_key: str,
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        """
        Get items in a collection.

        Args:
            collection_key: Collection key
            limit: Maximum results

        Returns:
            List of items in collection
        """
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(
            None,
            lambda: self.client.collection_items(collection_key, limit=limit),
        )

    # -------------------- Tag Methods --------------------

    async def get_tags(self, limit: int = 100) -> list[dict[str, Any]]:
        """Get all tags in the library."""
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(
            None,
            lambda: self.client.tags(limit=limit),
        )

    async def get_items_by_tag(
        self,
        tag: str,
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        """
        Get items with a specific tag.

        Args:
            tag: Tag name
            limit: Maximum results

        Returns:
            List of items with the tag
        """
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(
            None,
            lambda: self.client.items(tag=tag, limit=limit),
        )

    # -------------------- Attachment Methods --------------------

    async def get_attachment_info(
        self,
        item: dict[str, Any],
    ) -> AttachmentInfo | None:
        """
        Get attachment information for an item.

        Args:
            item: Zotero item data

        Returns:
            AttachmentInfo if item has attachment
        """
        data = item.get("data", {})
        item_type = data.get("itemType")
        item_key = data.get("key")

        # Direct attachment
        if item_type == "attachment":
            return AttachmentInfo(
                key=item_key,
                title=data.get("title", "Untitled"),
                filename=data.get("filename", ""),
                content_type=data.get("contentType", ""),
                parent_key=data.get("parentItem"),
            )

        # Look for child attachments
        children = await self.get_item_children(item_key)

        # Prioritize PDFs, then HTML, then others
        pdfs = []
        htmls = []
        others = []

        for child in children:
            child_data = child.get("data", {})
            if child_data.get("itemType") == "attachment":
                content_type = child_data.get("contentType", "")
                attachment = AttachmentInfo(
                    key=child_data.get("key", ""),
                    title=child_data.get("title", "Untitled"),
                    filename=child_data.get("filename", ""),
                    content_type=content_type,
                    parent_key=item_key,
                )

                if content_type == "application/pdf":
                    pdfs.append(attachment)
                elif content_type.startswith("text/html"):
                    htmls.append(attachment)
                else:
                    others.append(attachment)

        # Return first match in priority order
        for category in [pdfs, htmls, others]:
            if category:
                return category[0]

        return None

    # -------------------- Write Methods --------------------

    async def create_note(
        self,
        parent_key: str,
        note_content: str,
        tags: list[str] | None = None,
    ) -> dict[str, Any]:
        """
        Create a note attached to an item.

        Args:
            parent_key: Parent item key
            note_content: HTML note content
            tags: Optional tags for the note

        Returns:
            Created note data
        """
        loop = asyncio.get_event_loop()

        note_template = {
            "itemType": "note",
            "parentItem": parent_key,
            "note": note_content,
            "tags": [{"tag": t} for t in (tags or [])],
        }

        return await loop.run_in_executor(
            None,
            lambda: self.client.create_items([note_template]),
        )

    # -------------------- Collection Management --------------------

    async def add_to_collection(
        self, collection_key: str, item_key: str
    ) -> dict[str, Any]:
        """
        Add an item to a collection.

        Args:
            collection_key: Collection key
            item_key: Item key to add

        Returns:
            Updated item data
        """
        loop = asyncio.get_event_loop()
        item = await self.get_item(item_key)
        return await loop.run_in_executor(
            None, lambda: self.client.addto_collection(collection_key, item)
        )

    async def remove_from_collection(
        self, collection_key: str, item_key: str
    ) -> dict[str, Any]:
        """
        Remove an item from a collection.

        Args:
            collection_key: Collection key
            item_key: Item key to remove

        Returns:
            Updated item data
        """
        loop = asyncio.get_event_loop()
        item = await self.get_item(item_key)
        return await loop.run_in_executor(
            None, lambda: self.client.deletefrom_collection(collection_key, item)
        )

    async def delete_item(self, item_key: str) -> dict[str, Any]:
        """
        Delete an item (moves to trash).

        Args:
            item_key: Item key to delete

        Returns:
            Deletion result
        """
        loop = asyncio.get_event_loop()
        item = await self.get_item(item_key)
        payload = {"key": item_key, "version": item.get("version", 0)}
        return await loop.run_in_executor(
            None, lambda: self.client.delete_item(payload)
        )

    async def add_tags(self, item_key: str, tags: list[str]) -> dict[str, Any]:
        """
        Add tags to an item (preserves existing tags).

        Args:
            item_key: Item key
            tags: List of tag names to add

        Returns:
            Updated item data
        """
        loop = asyncio.get_event_loop()
        item = await self.get_item(item_key)

        # Get existing tags
        existing_tags = {t.get("tag", "") for t in item.get("data", {}).get("tags", [])}

        # Add new tags (deduplicate)
        for tag in tags:
            if tag and tag not in existing_tags:
                item["data"]["tags"].append({"tag": tag})

        return await loop.run_in_executor(None, lambda: self.client.update_item(item))

    async def update_item(self, item: dict[str, Any]) -> dict[str, Any]:
        """
        Update an item's data.

        Args:
            item: Complete item object with modifications

        Returns:
            Updated item data
        """
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, lambda: self.client.update_item(item))


@lru_cache(maxsize=1)
def get_zotero_client() -> ZoteroAPIClient:
    """
    Get a configured Zotero client using environment variables.

    Environment Variables:
        ZOTERO_LOCAL: Set to "true" for local API
        ZOTERO_LIBRARY_ID: Library ID (default: "0" for local)
        ZOTERO_LIBRARY_TYPE: "user" or "group" (default: "user")
        ZOTERO_API_KEY: API key for web access

    Returns:
        Configured ZoteroAPIClient

    Raises:
        ConfigurationError: If required config is missing
    """
    local = is_local_mode()
    library_id = os.getenv("ZOTERO_LIBRARY_ID", "0" if local else "")
    library_type = os.getenv("ZOTERO_LIBRARY_TYPE", "user")
    api_key = os.getenv("ZOTERO_API_KEY")

    if not local and not library_id:
        raise ConfigurationError(
            "ZOTERO_LIBRARY_ID is required for web API access",
            suggestion="Set ZOTERO_LOCAL=true for local access, or provide ZOTERO_LIBRARY_ID",
        )

    if not local and not api_key:
        raise ConfigurationError(
            "ZOTERO_API_KEY is required for web API access",
            suggestion="Set ZOTERO_LOCAL=true for local access, or provide ZOTERO_API_KEY",
        )

    if library_type not in ("user", "group"):
        library_type = "user"

    return ZoteroAPIClient(
        library_id=library_id,
        library_type=library_type,  # type: ignore
        api_key=api_key,
        local=local,
    )
