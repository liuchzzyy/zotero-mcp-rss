"""
Zotero module integration.

Wraps internal Zotero services for use in the MCP integration layer.
"""

from __future__ import annotations

from typing import Any, Literal, cast

from zotero_mcp.config import Config


class ZoteroIntegration:
    """Bridges Zotero services into zotero-mcp."""

    def __init__(self, config: Config):
        from zotero_mcp.clients.zotero import ZoteroAPIClient
        from zotero_mcp.services.zotero.item_service import ItemService
        from zotero_mcp.services.zotero.search_service import SearchService

        library_type = (
            config.zotero_library_type
            if config.zotero_library_type in ("user", "group")
            else "user"
        )
        client = ZoteroAPIClient(
            library_id=config.zotero_library_id or "0",
            library_type=cast(Literal["user", "group"], library_type),
            api_key=config.zotero_api_key or None,
            local=False,
        )
        self.item_service: ItemService = ItemService(api_client=client)
        self.search_service: SearchService = SearchService(api_client=client)
        self._client: ZoteroAPIClient = client

    # ---- Items ----

    async def get_items(
        self,
        limit: int = 25,
        collection_key: str | None = None,
        tag: str | None = None,
    ) -> list[dict[str, Any]]:
        """Get items list."""
        if collection_key:
            return await self._client.get_collection_items(
                collection_key=collection_key, limit=limit
            )
        if tag:
            return await self._client.get_items_by_tag(tag=tag, limit=limit)
        return await self._client.get_all_items(limit=limit)

    async def get_item(self, item_key: str) -> dict[str, Any]:
        """Get single item."""
        return await self.item_service.get_item(item_key)

    async def create_item(
        self,
        item_type: str,
        title: str,
        creators: list[str] | None = None,
        abstract: str | None = None,
        doi: str | None = None,
        url: str | None = None,
        collection_keys: list[str] | None = None,
    ) -> dict[str, Any]:
        """Create a new item."""
        item_data: dict[str, Any] = {
            "itemType": item_type,
            "title": title,
        }
        if creators:
            item_data["creators"] = [
                {"creatorType": "author", "name": name} for name in creators
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

    async def search(self, query: str, limit: int = 25) -> list[dict[str, Any]]:
        """Search items by keyword."""
        return await self._client.search_items(query=query, limit=limit)

    # ---- Collections ----

    async def get_collections(self) -> list[dict[str, Any]]:
        """Get all collections."""
        return await self._client.get_collections()

    async def create_collection(
        self,
        name: str,
        parent_collection_key: str | None = None,
    ) -> dict[str, Any]:
        """Create a collection."""
        return await self._client.create_collection(
            name=name,
            parent_key=parent_collection_key,
        )

    # ---- Formatting ----

    @staticmethod
    def format_items(items: list[dict[str, Any]]) -> str:
        """Format items list as Markdown."""
        lines = [f"## Found {len(items)} items\n"]
        for item in items:
            data = item.get("data", item)
            title = data.get("title", "Untitled")
            key = data.get("key", item.get("key", ""))
            creators = data.get("creators", [])
            authors = ", ".join(
                c.get(
                    "name", f"{c.get('firstName', '')} {c.get('lastName', '')}"
                ).strip()
                for c in creators[:3]
            )
            date = data.get("date", "N/A")
            doi = data.get("DOI", "N/A")

            lines.append(f"### {title}")
            lines.append(f"- **Key**: {key}")
            lines.append(f"- **Authors**: {authors or 'N/A'}")
            lines.append(f"- **Date**: {date}")
            lines.append(f"- **DOI**: {doi}")
            lines.append("")
        return "\n".join(lines)

    @staticmethod
    def format_item(item: dict[str, Any]) -> str:
        """Format single item as Markdown."""
        data = item.get("data", item)
        title = data.get("title", "Untitled")
        key = data.get("key", item.get("key", ""))
        item_type = data.get("itemType", "")
        creators = data.get("creators", [])
        authors = ", ".join(
            c.get("name", f"{c.get('firstName', '')} {c.get('lastName', '')}").strip()
            for c in creators
        )
        abstract = data.get("abstractNote", "No abstract available")
        tags = data.get("tags", [])
        tag_str = ", ".join(t.get("tag", "") for t in tags) if tags else "No tags"

        return "\n".join(
            [
                f"## {title}",
                "",
                f"**Key**: {key}",
                f"**Type**: {item_type}",
                f"**Authors**: {authors or 'N/A'}",
                f"**Date**: {data.get('date', 'N/A')}",
                f"**DOI**: {data.get('DOI', 'N/A')}",
                f"**URL**: {data.get('url', 'N/A')}",
                "",
                "### Abstract",
                abstract,
                "",
                "### Tags",
                tag_str,
            ]
        )

    def format_collections(self, collections: list[dict[str, Any]]) -> str:
        """Format collections as Markdown."""
        lines = [f"## {len(collections)} collections\n"]
        for coll in collections:
            data = coll.get("data", coll)
            name = data.get("name", "Untitled")
            key = data.get("key", coll.get("key", ""))
            count = data.get("numItems", 0)
            lines.append(f"- **{name}** (key: {key}, items: {count})")
        return "\n".join(lines)
