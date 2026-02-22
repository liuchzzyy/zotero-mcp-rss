"""
Item and Collection Service.

Handles CRUD operations for Zotero items, collections, and tags.
"""

import asyncio
import logging
import os
import re
from typing import Any
from urllib.parse import urlsplit, urlunsplit

from zotero_mcp.clients.zotero import LocalDatabaseClient, ZoteroAPIClient
from zotero_mcp.models.common import SearchResultItem
from zotero_mcp.services.zotero.result_mapper import (
    api_item_to_search_result,
    zotero_item_to_search_result,
)
from zotero_mcp.utils.async_helpers.cache import ResponseCache
from zotero_mcp.utils.formatting.helpers import clean_title

logger = logging.getLogger(__name__)


def _normalize_doi(raw_doi: str | None) -> str:
    """Normalize DOI for exact duplicate matching."""
    if not raw_doi:
        return ""
    doi = raw_doi.strip().lower()
    doi = doi.replace("https://doi.org/", "").replace("http://doi.org/", "")
    doi = doi.replace("doi:", "").strip()
    return doi


def _normalize_url(raw_url: str | None) -> str:
    """Normalize URL for duplicate matching."""
    if not raw_url:
        return ""
    url = raw_url.strip()
    if not url:
        return ""
    if url.startswith("//"):
        url = f"https:{url}"
    elif "://" not in url:
        url = f"https://{url}"
    try:
        parts = urlsplit(url)
    except Exception:
        return url.rstrip("/").lower()

    if not parts.netloc:
        # Keep fallback predictable for malformed values (e.g. local file-ish strings).
        return url.rstrip("/").lower()

    scheme = (parts.scheme or "https").lower()
    netloc = parts.netloc.lower()
    path = re.sub(r"/+$", "", parts.path or "")
    # Ignore query/fragment to reduce noisy URL variants from feeds.
    return urlunsplit((scheme, netloc, path, "", ""))


def _normalize_title(raw_title: str | None) -> str:
    """Normalize title for duplicate matching."""
    if not raw_title:
        return ""
    title = clean_title(raw_title).lower()
    title = re.sub(r"\s+", " ", title).strip()
    return title


def _extract_year(raw_date: str | None) -> str:
    """Extract publication year from Zotero date string."""
    if not raw_date:
        return ""
    match = re.search(r"\b(19|20)\d{2}\b", raw_date)
    return match.group(0) if match else ""


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
            return [zotero_item_to_search_result(item) for item in local_items]

        api_items = await self.api_client.get_all_items(
            limit=limit, start=start, item_type=item_type
        )
        return [api_item_to_search_result(item) for item in api_items]

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

    async def download_attachment(self, item_key: str) -> bytes | None:
        """Download attachment file bytes via Zotero Web API.

        Args:
            item_key: Attachment item key

        Returns:
            Raw file bytes, or None on error
        """
        return await self.api_client.download_attachment(item_key)

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
        return [api_item_to_search_result(item) for item in items]

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
        if not items:
            return {
                "successful": {},
                "failed": {},
                "created": 0,
                "failed_count": 0,
                "skipped_duplicates": 0,
            }

        dedup_enabled = os.getenv("ZOTERO_PRECREATE_DEDUP", "true").lower() in {
            "1",
            "true",
            "yes",
        }
        if not dedup_enabled:
            return await self.api_client.create_items(items)

        filtered_items, skipped_count = await self._filter_items_before_create(items)
        if not filtered_items:
            logger.info(
                f"Skipped all {len(items)} items as duplicates before create"
            )
            return {
                "successful": {},
                "failed": {},
                "created": 0,
                "failed_count": 0,
                "skipped_duplicates": skipped_count,
            }

        result = await self.api_client.create_items(filtered_items)
        if not isinstance(result, dict):
            return {
                "successful": {},
                "failed": {},
                "created": len(filtered_items),
                "failed_count": 0,
                "skipped_duplicates": skipped_count,
            }

        successful = result.get("successful", {})
        failed = result.get("failed", {})
        created = len(successful) if isinstance(successful, dict) else 0
        failed_count = len(failed) if isinstance(failed, dict) else 0

        result["created"] = created
        result["failed_count"] = failed_count
        result["skipped_duplicates"] = skipped_count

        logger.info(
            f"Create items summary: created={created}, failed={failed_count}, "
            f"skipped_duplicates={skipped_count}"
        )
        return result

    async def create_item(self, item: dict[str, Any]) -> dict[str, Any]:
        """Create a single item."""
        if not isinstance(item, dict) or not item:
            raise ValueError("Item payload must be a non-empty dict")
        return await self.create_items([item])

    async def _filter_items_before_create(
        self, items: list[dict[str, Any]]
    ) -> tuple[list[dict[str, Any]], int]:
        """
        Filter out probable duplicates before creating new items.

        Priority: DOI > URL > title (+year when available).
        """
        filtered: list[dict[str, Any]] = []
        skipped_count = 0

        seen_doi: set[str] = set()
        seen_url: set[str] = set()
        seen_title_year: set[tuple[str, str]] = set()
        search_cache: dict[tuple[str, str, int], list[dict[str, Any]]] = {}

        for item in items:
            data = item.get("data", item) if isinstance(item, dict) else {}

            doi = _normalize_doi(data.get("DOI"))
            url = _normalize_url(data.get("url"))
            title = _normalize_title(data.get("title"))
            year = _extract_year(data.get("date"))

            # Intra-batch duplicate check.
            if doi and doi in seen_doi:
                skipped_count += 1
                continue
            if url and url in seen_url:
                skipped_count += 1
                continue
            if title and (title, year) in seen_title_year:
                skipped_count += 1
                continue

            # Library-level duplicate check.
            if await self._exists_duplicate_in_library(
                doi, url, title, year, search_cache
            ):
                skipped_count += 1
                continue

            filtered.append(item)
            if doi:
                seen_doi.add(doi)
            if url:
                seen_url.add(url)
            if title:
                seen_title_year.add((title, year))

        return filtered, skipped_count

    async def _exists_duplicate_in_library(
        self,
        doi: str,
        url: str,
        title: str,
        year: str,
        search_cache: dict[tuple[str, str, int], list[dict[str, Any]]],
    ) -> bool:
        """Check if a likely duplicate already exists in the library."""
        if doi:
            found = await self._search_items_cached(
                query=doi,
                qmode="everything",
                limit=25,
                search_cache=search_cache,
            )
            for entry in found:
                entry_data = entry.get("data", {})
                if _normalize_doi(entry_data.get("DOI")) == doi:
                    return True

        if url:
            found = await self._search_items_cached(
                query=url,
                qmode="everything",
                limit=25,
                search_cache=search_cache,
            )
            for entry in found:
                entry_data = entry.get("data", {})
                if _normalize_url(entry_data.get("url")) == url:
                    return True

        if title:
            found = await self._search_items_cached(
                query=title,
                qmode="titleCreatorYear",
                limit=25,
                search_cache=search_cache,
            )
            for entry in found:
                entry_data = entry.get("data", {})
                if _normalize_title(entry_data.get("title")) != title:
                    continue
                existing_year = _extract_year(entry_data.get("date"))
                # If both sides have year, require equality to reduce false positives.
                if year and existing_year and year != existing_year:
                    continue
                return True

        return False

    async def _search_items_cached(
        self,
        query: str,
        qmode: str,
        limit: int,
        search_cache: dict[tuple[str, str, int], list[dict[str, Any]]],
    ) -> list[dict[str, Any]]:
        """Search items with a per-batch cache to avoid duplicate API calls."""
        cache_key = (query, qmode, limit)
        cached = search_cache.get(cache_key)
        if cached is not None:
            return cached

        result = await self.api_client.search_items(query, qmode=qmode, limit=limit)
        if isinstance(result, list):
            search_cache[cache_key] = result
            return result

        search_cache[cache_key] = []
        return []

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

