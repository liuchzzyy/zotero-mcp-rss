"""
Service for detecting and removing duplicate Zotero items.

This service scans the Zotero library for duplicate items based on
DOI, title, and URL matching with configurable priority.

Note: Duplicate items are PERMANENTLY deleted (not moved to trash).
"""

from collections import defaultdict
from dataclasses import dataclass, field
import logging
from typing import Any

from pydantic import ValidationError

from zotero_mcp.models.operations import DuplicateScanParams
from zotero_mcp.services.common.operation_result import (
    operation_error,
    operation_success,
)
from zotero_mcp.services.common.pagination import iter_offset_batches
from zotero_mcp.services.common.retry import async_retry_with_backoff
from zotero_mcp.services.zotero.item_service import ItemService
from zotero_mcp.utils.formatting.helpers import clean_title

logger = logging.getLogger(__name__)

_ZOTERO_API_MAX_PAGE_SIZE = 100


@dataclass
class DuplicateGroup:
    """A group of duplicate items."""

    primary_key: str  # Key of item to keep
    duplicate_keys: list[str] = field(default_factory=list)  # Keys of items to delete
    match_reason: str = ""  # "doi", "title", or "url"
    match_value: str = ""  # The DOI/title/URL that matched


def _item_to_dict(item: dict[str, Any]) -> dict[str, Any]:
    """Normalize raw Zotero API item payload for duplicate checking."""
    data = item.get("data", {})
    return {
        "key": data.get("key", item.get("key", "")),
        "data": {
            "itemType": data.get("itemType"),
            "parentItem": data.get("parentItem"),
            "DOI": data.get("DOI"),
            "title": data.get("title"),
            "url": data.get("url"),
            "creators": data.get("creators", []),
            "abstractNote": data.get("abstractNote"),
            "publicationTitle": data.get("publicationTitle"),
            "publisher": data.get("publisher"),
            "date": data.get("date"),
            "volume": data.get("volume"),
            "issue": data.get("issue"),
            "pages": data.get("pages"),
            "tags": data.get("tags", []),
            "journalAbbreviation": data.get("journalAbbreviation"),
            "language": data.get("language"),
            "rights": data.get("rights"),
            "series": data.get("series"),
            "edition": data.get("edition"),
            "place": data.get("place"),
            "extra": data.get("extra"),
            "ISSN": data.get("ISSN"),
        },
        "children": [],
    }


class DuplicateDetectionService:
    """
    Service for detecting and removing duplicate Zotero items.

    Features:
    - Scans full library or a specific collection
    - Groups duplicates by DOI > title > URL priority
    - Keeps most complete item (with attachments, notes)
    - Removes duplicates safely
    """

    def __init__(self, item_service: ItemService):
        self.item_service = item_service
        # Child records should not participate in duplicate grouping.
        self._excluded_item_types = {"note", "attachment", "annotation"}

    async def find_and_remove_duplicates(
        self,
        collection_key: str | None = None,
        scan_limit: int = 500,
        treated_limit: int = 1000,
        dry_run: bool = False,
    ) -> dict[str, Any]:
        """
        Find and remove duplicate items.

        Args:
            collection_key: Optional collection key to limit scan
            scan_limit: Number of items to fetch per batch from API
            treated_limit: Maximum total number of duplicate items to find
            dry_run: If True, don't actually delete items

        Returns:
            Dict with scan statistics and duplicate groups
        """
        try:
            params = DuplicateScanParams(
                collection_key=collection_key,
                scan_limit=scan_limit,
                treated_limit=treated_limit,
                dry_run=dry_run,
            )
        except ValidationError as e:
            logger.error(f"Invalid dedup parameters: {e}")
            return operation_error(
                "deduplicate",
                "invalid dedup parameters",
                status="validation_error",
                details=e.errors(),
                extra={
                    "total_scanned": 0,
                    "duplicates_found": 0,
                    "duplicates_removed": 0,
                    "cross_folder_copies": 0,
                    "groups": [],
                    "dry_run": False,
                },
            )

        logger.info("🔍 Starting duplicate detection...")

        if params.collection_key:
            logger.info(f"📚 Scanning collection: {params.collection_key}")
            all_items, total_scanned = await self._collect_collection_items(
                coll_key=params.collection_key,
                scan_limit=params.scan_limit,
            )
        else:
            logger.info("📚 Scanning full library...")
            all_items, total_scanned = await self._collect_library_items(
                scan_limit=params.scan_limit
            )

        group_result = await self._find_duplicate_groups(all_items)
        duplicate_groups = group_result["groups"]
        cross_folder_copies = group_result["cross_folder_copies"]
        total_duplicates_found = sum(len(g.duplicate_keys) for g in duplicate_groups)

        if total_duplicates_found > params.treated_limit:
            logger.info(
                f"⛔ Reached limit ({params.treated_limit} duplicates), trimming results"
            )
            duplicate_groups = self._limit_duplicate_groups(
                duplicate_groups, params.treated_limit
            )
            total_duplicates_found = sum(len(g.duplicate_keys) for g in duplicate_groups)

        logger.info(
            f"📊 Scan complete: {total_scanned} items scanned, "
            f"{total_duplicates_found} duplicates found in "
            f"{len(duplicate_groups)} groups"
        )

        if params.dry_run:
            logger.info("🔍 DRY RUN: No items will be deleted")
            for group in duplicate_groups:
                logger.info(
                    f"  → Would delete {len(group.duplicate_keys)} items "
                    f"({group.match_reason}: {group.match_value[:50]})"
                )
            metrics = {
                "scanned": total_scanned,
                "candidates": total_duplicates_found,
                "processed": 0,
                "updated": 0,
                "skipped": cross_folder_copies,
                "failed": 0,
                "removed": 0,
            }
            return operation_success(
                "deduplicate",
                metrics,
                message="Dry run completed",
                dry_run=True,
                extra={
                    "total_scanned": total_scanned,
                    "duplicates_found": total_duplicates_found,
                    "duplicates_removed": 0,
                    "cross_folder_copies": cross_folder_copies,
                    "groups": duplicate_groups,
                    "dry_run": True,
                },
            )

        # Remove duplicates (permanently delete)
        duplicates_removed = await self._remove_duplicates(duplicate_groups)

        logger.info(f"✅ Removed {duplicates_removed} duplicate ITEM(s)")

        metrics = {
            "scanned": total_scanned,
            "candidates": total_duplicates_found,
            "processed": total_duplicates_found,
            "updated": 0,
            "skipped": cross_folder_copies,
            "failed": 0,
            "removed": duplicates_removed,
        }
        return operation_success(
            "deduplicate",
            metrics,
            message=f"Removed {duplicates_removed} duplicate items",
            extra={
                "total_scanned": total_scanned,
                "duplicates_found": total_duplicates_found,
                "duplicates_removed": duplicates_removed,
                "cross_folder_copies": cross_folder_copies,
                "groups": duplicate_groups,
                "dry_run": False,
            },
        )

    async def _collect_collection_items(
        self,
        coll_key: str,
        scan_limit: int,
    ) -> tuple[list[dict[str, Any]], int]:
        """Collect all items from a collection across paginated batches."""
        scanned = 0
        collected: list[dict[str, Any]] = []
        batch_size = self._effective_batch_size(scan_limit)

        async for offset, items in iter_offset_batches(
            self._make_collection_batch_fetcher(coll_key),
            batch_size=batch_size,
        ):
            scanned += len(items)
            batch_items = [_item_to_dict(item) for item in items]
            collected.extend(batch_items)
            logger.info(
                f"  Batch: {len(batch_items)} items fetched from collection "
                f"(offset: {offset}, total: {scanned})"
            )

        return collected, scanned

    async def _collect_library_items(
        self,
        scan_limit: int,
    ) -> tuple[list[dict[str, Any]], int]:
        """Collect all items from the entire library across paginated batches."""
        scanned = 0
        collected: list[dict[str, Any]] = []
        batch_size = self._effective_batch_size(scan_limit)

        async for offset, items in iter_offset_batches(
            self._make_library_batch_fetcher(),
            batch_size=batch_size,
        ):
            scanned += len(items)
            batch_items = [_item_to_dict(item) for item in items]
            collected.extend(batch_items)
            logger.info(
                f"  Batch: {len(batch_items)} items fetched from library "
                f"(offset: {offset}, total: {scanned})"
            )

        return collected, scanned

    def _make_collection_batch_fetcher(self, coll_key: str):
        """Build a paged fetch function with retry for duplicate scans."""

        async def _fetch_page(offset: int, limit: int):
            def _fetch_items(
                collection_key: str = coll_key,
                page_limit: int = limit,
                page_offset: int = offset,
            ):
                return self.item_service.api_client.get_collection_items(
                    collection_key, limit=page_limit, start=page_offset
                )

            return await async_retry_with_backoff(
                _fetch_items,
                description=f"Scan collection {coll_key} (offset {offset})",
            )

        return _fetch_page

    def _make_library_batch_fetcher(self):
        """Build a paged fetch function with retry for whole-library scans."""

        async def _fetch_page(offset: int, limit: int):
            def _fetch_items(
                page_limit: int = limit,
                page_offset: int = offset,
            ):
                return self.item_service.api_client.get_all_items(
                    limit=page_limit,
                    start=page_offset,
                )

            return await async_retry_with_backoff(
                _fetch_items,
                description=f"Scan library (offset {offset})",
            )

        return _fetch_page

    def _limit_duplicate_groups(
        self,
        groups: list[DuplicateGroup],
        max_duplicates: int,
    ) -> list[DuplicateGroup]:
        """Limit duplicate groups by the total number of duplicate keys."""
        if max_duplicates <= 0:
            return []

        limited: list[DuplicateGroup] = []
        used = 0

        for group in groups:
            if used >= max_duplicates:
                break

            remaining = max_duplicates - used
            dup_count = len(group.duplicate_keys)
            if dup_count <= remaining:
                limited.append(group)
                used += dup_count
                continue

            limited.append(
                DuplicateGroup(
                    primary_key=group.primary_key,
                    duplicate_keys=group.duplicate_keys[:remaining],
                    match_reason=group.match_reason,
                    match_value=group.match_value,
                )
            )
            break

        return limited

    def _effective_batch_size(self, scan_limit: int) -> int:
        """
        Clamp scan batch size to Zotero API max page size.

        Some Zotero endpoints cap `limit` to 100 items. If batch_size is larger,
        iterators that stop on `len(page) < batch_size` can terminate early.
        """
        if scan_limit > _ZOTERO_API_MAX_PAGE_SIZE:
            logger.info(
                "Requested scan-limit %s exceeds API page max %s; "
                "using %s for pagination",
                scan_limit,
                _ZOTERO_API_MAX_PAGE_SIZE,
                _ZOTERO_API_MAX_PAGE_SIZE,
            )
        return max(1, min(scan_limit, _ZOTERO_API_MAX_PAGE_SIZE))

    async def _find_duplicate_groups(
        self,
        items: list[dict[str, Any]],
        existing_groups: list[DuplicateGroup] | None = None,
    ) -> dict[str, Any]:
        """
        Find groups of duplicate items.

        Returns dict with:
            - groups: list of DuplicateGroup (only items with different metadata)
            - cross_folder_copies: int (count of skipped groups with identical metadata)

        Priority: DOI > title > URL
        """
        all_duplicate_groups = existing_groups or []
        existing_primary_keys = {g.primary_key for g in all_duplicate_groups}
        existing_duplicate_keys: set[str] = set()
        for g in all_duplicate_groups:
            existing_duplicate_keys.update(g.duplicate_keys)

        already_grouped = existing_primary_keys | existing_duplicate_keys
        candidate_items = [item for item in items if self._is_parent_item(item)]

        # Group by DOI (highest priority)
        doi_groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
        for item in candidate_items:
            item_key = item.get("key", "")
            if item_key in already_grouped:
                continue
            doi = (item.get("data", {}).get("DOI") or "").strip()
            if doi:
                doi_groups[doi.lower()].append(item)

        # Track keys already matched by DOI
        processed_keys = set(already_grouped)
        for items_list in doi_groups.values():
            if len(items_list) > 1:
                for item in items_list:
                    processed_keys.add(item.get("key", ""))

        # Group by title (second priority)
        title_groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
        for item in candidate_items:
            item_key = item.get("key", "")
            if item_key in processed_keys:
                continue
            title = clean_title(item.get("data", {}).get("title", "")).lower()
            if title:
                title_groups[title].append(item)

        # Track keys matched by title
        for items_list in title_groups.values():
            if len(items_list) > 1:
                for item in items_list:
                    processed_keys.add(item.get("key", ""))

        # Group by URL (lowest priority)
        url_groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
        for item in candidate_items:
            item_key = item.get("key", "")
            if item_key in processed_keys:
                continue
            url = (item.get("data", {}).get("url") or "").strip()
            if url:
                url_groups[url].append(item)

        # Convert to DuplicateGroup objects
        duplicate_groups: list[DuplicateGroup] = []
        cross_folder_copies = 0

        for match_reason, groups in [
            ("doi", doi_groups),
            ("title", title_groups),
            ("url", url_groups),
        ]:
            for match_value, items_list in groups.items():
                if len(items_list) <= 1:
                    continue
                group = self._create_duplicate_group(
                    items_list, match_reason=match_reason, match_value=match_value
                )
                if group:
                    duplicate_groups.append(group)
                else:
                    cross_folder_copies += 1

        return {
            "groups": duplicate_groups,
            "cross_folder_copies": cross_folder_copies,
        }

    def _is_parent_item(self, item: dict[str, Any]) -> bool:
        """Only include top-level bibliographic items in deduplication."""
        item_data = item.get("data", {})
        item_type = (item_data.get("itemType") or "").strip().lower()
        parent_item = (item_data.get("parentItem") or "").strip()
        return item_type not in self._excluded_item_types and not parent_item

    def _create_duplicate_group(
        self, items: list[dict[str, Any]], match_reason: str, match_value: str
    ) -> DuplicateGroup | None:
        """
        Create a DuplicateGroup from a list of duplicate items.

        Checks if items have identical metadata (cross-folder copies) first.
        If all metadata is identical, returns None (skip processing).
        If metadata differs, keeps the most complete item as primary.
        """
        if len(items) < 2:
            return None

        if self._all_metadata_identical(items):
            logger.debug(
                f"  Skipping {len(items)} items with identical {match_reason} "
                f"(cross-folder copies, not true duplicates)"
            )
            return None

        # Score each item by completeness and sort (highest first)
        scored_items = sorted(
            items,
            key=lambda item: self._score_item_completeness(item),
            reverse=True,
        )

        primary_key = scored_items[0].get("key", "")
        duplicate_keys = [item.get("key", "") for item in scored_items[1:]]

        return DuplicateGroup(
            primary_key=primary_key,
            duplicate_keys=duplicate_keys,
            match_reason=match_reason,
            match_value=match_value,
        )

    def _score_item_completeness(self, item: dict[str, Any]) -> int:
        """
        Score an item by its completeness. Higher score = more complete item.
        """
        score = 0
        item_data = item.get("data", {})

        # Has children (attachments, notes)
        children = item.get("children", [])
        if children:
            score += 100 + len(children) * 10

        # Has DOI
        if item_data.get("DOI"):
            score += 50

        # Has authors/creators
        creators = item_data.get("creators", [])
        if creators:
            score += 30 + len(creators) * 2

        # Has abstract
        if item_data.get("abstractNote"):
            score += 20

        # Has publication title
        if item_data.get("publicationTitle"):
            score += 15

        # Has date
        if item_data.get("date"):
            score += 10

        # Has volume/issue/pages
        for field_name in ("volume", "issue", "pages"):
            if item_data.get(field_name):
                score += 5

        # Has tags
        tags = item_data.get("tags", [])
        if tags:
            score += len(tags) * 2

        return score

    # Fields to compare when checking for cross-folder copies
    _COMPARABLE_FIELDS = [
        "DOI",
        "title",
        "url",
        "creators",
        "abstractNote",
        "publicationTitle",
        "publisher",
        "date",
        "volume",
        "issue",
        "pages",
        "tags",
        "journalAbbreviation",
        "language",
        "rights",
        "series",
        "edition",
        "place",
        "extra",
        "ISSN",
        "itemType",
    ]

    # Fields that contain lists and need special comparison
    _LIST_FIELDS = {"creators", "tags"}

    def _all_metadata_identical(self, items: list[dict[str, Any]]) -> bool:
        """
        Check if all items have identical metadata (excluding collections and version).

        Used to detect cross-folder copies vs true duplicates.
        """
        if len(items) < 2:
            return True

        first_item_data = items[0].get("data", {})

        for item in items[1:]:
            item_data = item.get("data", {})
            for comparable_field in self._COMPARABLE_FIELDS:
                first_value = first_item_data.get(comparable_field)
                item_value = item_data.get(comparable_field)

                if comparable_field in self._LIST_FIELDS:
                    if not self._lists_equal(first_value, item_value):
                        return False
                elif first_value != item_value:
                    return False

        return True

    def _lists_equal(self, list1: list | None, list2: list | None) -> bool:
        """Compare two lists for equality, handling dict formats."""
        if list1 is None and list2 is None:
            return True
        if list1 is None or list2 is None:
            return False
        if len(list1) != len(list2):
            return False

        # For dict-format lists (tags or creators)
        if list1 and isinstance(list1[0], dict):
            if "tag" in list1[0]:
                # Tags: compare by tag name
                tags1 = sorted(t.get("tag", "") for t in list1)
                tags2 = sorted(t.get("tag", "") for t in list2)
                return tags1 == tags2
            # Creators or other dicts: compare as strings
            return str(list1) == str(list2)

        return list1 == list2

    async def _remove_duplicates(
        self,
        duplicate_groups: list[DuplicateGroup],
    ) -> int:
        """Remove duplicate items by permanently deleting them."""
        deleted_count = 0

        for group in duplicate_groups:
            for dup_key in group.duplicate_keys:
                try:
                    item = await self.item_service.api_client.get_item(dup_key)
                    item_type = item.get("data", {}).get("itemType", "")

                    if item_type in ("note", "attachment"):
                        logger.info(
                            f"  ⊘ Skipping {item_type.upper()} {dup_key} "
                            f"({item_type}s are preserved)"
                        )
                        continue

                    await async_retry_with_backoff(
                        lambda k=dup_key: self.item_service.api_client.delete_item(k),
                        description=f"Delete duplicate item {dup_key}",
                    )
                    logger.info(
                        f"  ✓ Deleted ITEM {dup_key} (matched by {group.match_reason})"
                    )
                    deleted_count += 1
                except Exception as e:
                    logger.error(f"  Failed to delete {dup_key}: {e}")

        return deleted_count
