"""
Zotero module integration.

Wraps zotero-core services for use in the MCP integration layer.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from zotero_mcp.config import Config


class ZoteroIntegration:
    """Bridges zotero-core module into zotero-mcp."""

    def __init__(self, config: Config):
        from zotero_core.clients.zotero_client import ZoteroClient
        from zotero_core.services.item_service import ItemService
        from zotero_core.services.search_service import SearchService

        client = ZoteroClient(
            library_id=config.zotero_library_id,
            api_key=config.zotero_api_key,
            library_type=config.zotero_library_type,
        )
        self.item_service = ItemService(client)
        self.search_service = SearchService(client)
        self._client = client

    # ---- Items ----

    async def get_items(
        self,
        limit: int = 25,
        collection_key: Optional[str] = None,
        tag: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """Get items list."""
        return await self.item_service.get_all_items(
            limit=limit,
            collection_key=collection_key,
            tag=tag,
        )

    async def get_item(self, item_key: str) -> Dict[str, Any]:
        """Get single item."""
        return await self.item_service.get_item(item_key)

    async def create_item(
        self,
        item_type: str,
        title: str,
        creators: Optional[List[str]] = None,
        abstract: Optional[str] = None,
        doi: Optional[str] = None,
        url: Optional[str] = None,
        collection_keys: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """Create a new item."""
        item_data: Dict[str, Any] = {
            "itemType": item_type,
            "title": title,
        }
        if creators:
            item_data["creators"] = [
                {"creatorType": "author", "name": name}
                for name in creators
            ]
        if abstract:
            item_data["abstractNote"] = abstract
        if doi:
            item_data["DOI"] = doi
        if url:
            item_data["url"] = url
        if collection_keys:
            item_data["collections"] = collection_keys

        return await self.item_service.create_item(item_data)

    async def search(
        self, query: str, limit: int = 25
    ) -> List[Dict[str, Any]]:
        """Search items by keyword."""
        return await self.search_service.keyword_search(
            query=query, limit=limit
        )

    # ---- Collections ----

    async def get_collections(self) -> List[Dict[str, Any]]:
        """Get all collections."""
        return await self._client.get_collections()

    async def create_collection(
        self,
        name: str,
        parent_collection_key: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Create a collection."""
        return await self._client.create_collection(
            name=name,
            parent_key=parent_collection_key,
        )

    # ---- Formatting ----

    @staticmethod
    def format_items(items: List[Dict[str, Any]]) -> str:
        """Format items list as Markdown."""
        lines = [f"## Found {len(items)} items\n"]
        for item in items:
            title = item.get("title", "Untitled")
            key = item.get("key", "")
            creators = item.get("creators", [])
            authors = ", ".join(
                c.get("name", f"{c.get('firstName', '')} {c.get('lastName', '')}").strip()
                for c in creators[:3]
            )
            date = item.get("date", "N/A")
            doi = item.get("DOI", "N/A")

            lines.append(f"### {title}")
            lines.append(f"- **Key**: {key}")
            lines.append(f"- **Authors**: {authors or 'N/A'}")
            lines.append(f"- **Date**: {date}")
            lines.append(f"- **DOI**: {doi}")
            lines.append("")
        return "\n".join(lines)

    @staticmethod
    def format_item(item: Dict[str, Any]) -> str:
        """Format single item as Markdown."""
        title = item.get("title", "Untitled")
        key = item.get("key", "")
        item_type = item.get("itemType", "")
        creators = item.get("creators", [])
        authors = ", ".join(
            c.get("name", f"{c.get('firstName', '')} {c.get('lastName', '')}").strip()
            for c in creators
        )
        abstract = item.get("abstractNote", "No abstract available")
        tags = item.get("tags", [])
        tag_str = ", ".join(
            t.get("tag", "") for t in tags
        ) if tags else "No tags"

        return "\n".join([
            f"## {title}",
            "",
            f"**Key**: {key}",
            f"**Type**: {item_type}",
            f"**Authors**: {authors or 'N/A'}",
            f"**Date**: {item.get('date', 'N/A')}",
            f"**DOI**: {item.get('DOI', 'N/A')}",
            f"**URL**: {item.get('url', 'N/A')}",
            "",
            "### Abstract",
            abstract,
            "",
            "### Tags",
            tag_str,
        ])

    def format_collections(self, collections: List[Dict[str, Any]]) -> str:
        """Format collections as Markdown."""
        lines = [f"## {len(collections)} collections\n"]
        for coll in collections:
            name = coll.get("name", "Untitled")
            key = coll.get("key", "")
            count = coll.get("numItems", 0)
            lines.append(f"- **{name}** (key: {key}, items: {count})")
        return "\n".join(lines)
