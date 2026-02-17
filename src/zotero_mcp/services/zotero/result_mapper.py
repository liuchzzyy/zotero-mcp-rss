"""Shared mappers for Zotero search/list result shapes."""

from typing import Any

from zotero_mcp.clients.zotero import ZoteroItem
from zotero_mcp.models.common import SearchResultItem
from zotero_mcp.utils.formatting.helpers import format_creators


def api_item_to_search_result(item: dict[str, Any]) -> SearchResultItem:
    """Convert Zotero API item payload to SearchResultItem."""
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


def zotero_item_to_search_result(item: ZoteroItem) -> SearchResultItem:
    """Convert local ZoteroItem model to SearchResultItem."""
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
