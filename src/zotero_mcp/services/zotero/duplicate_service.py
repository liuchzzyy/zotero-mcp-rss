"""
Service for detecting and removing duplicate Zotero items.

This service scans the Zotero library for duplicate items based on
DOI, title, and URL matching with configurable priority.
"""

from collections import defaultdict
from dataclasses import dataclass, field
import logging
from typing import Any

from zotero_mcp.models.common import SearchResultItem
from zotero_mcp.services.common.retry import async_retry_with_backoff
from zotero_mcp.services.zotero.item_service import ItemService
from zotero_mcp.utils.formatting.helpers import clean_title

logger = logging.getLogger(__name__)


@dataclass
class DuplicateGroup:
    """A group of duplicate items."""

    primary_key: str  # Key of item to keep
    duplicate_keys: list[str] = field(default_factory=list)  # Keys of items to delete
    match_reason: str = ""  # "doi", "title", or "url"
    match_value: str = ""  # The DOI/title/URL that matched


def _item_to_dict(item: SearchResultItem) -> dict[str, Any]:
    """Convert a SearchResultItem to a dict format for duplicate checking."""
    return {
        "key": item.key,
        "data": {
            "DOI": item.doi,
            "title": item.title,
            "url": getattr(item, "url", None),
            "creators": [],
            "abstractNote": item.abstract,
            "publicationTitle": None,
            "date": item.date,
            "volume": None,
            "issue": None,
            "pages": None,
            "tags": [{"tag": tag} for tag in (item.tags or [])],
        },
        "children": [],
    }


class DuplicateDetectionService:
    """
    Service for detecting and removing duplicate Zotero items.

    Features:
    - Scans all items in library or collection
    - Groups duplicates by DOI > title > URL priority
    - Keeps most complete item (with attachments, notes)
    - Removes duplicates safely
    """

    def __init__(self, item_service: ItemService):
        self.item_service = item_service

    async def find_and_remove_duplicates(
        self,
        collection_key: str | None = None,
        scan_limit: int = 500,
        treated_limit: int = 1000,
        dry_run: bool = False,
        trash_collection: str = "06_TRASHES",
    ) -> dict[str, Any]:
        """
        Find and remove duplicate items.

        Args:
            collection_key: Optional collection key to limit scan
            scan_limit: Number of items to fetch per batch from API
            treated_limit: Maximum total number of duplicate items to find
            dry_run: If True, don't actually delete items
            trash_collection: Name of collection to move duplicates to

        Returns:
            Dict with scan statistics and duplicate groups
        """
        logger.info("Starting duplicate detection...")

        duplicate_groups: list[DuplicateGroup] = []
        total_scanned = 0
        total_duplicates_found = 0
        cross_folder_copies = 0

        if collection_key:
            collection_keys = [collection_key]
        else:
            logger.info("Scanning all collections in name order...")
            collections = await self.item_service.get_sorted_collections()
            collection_keys = [coll["key"] for coll in collections]

        # Scan collections sequentially
        for coll_key in collection_keys:
            if total_duplicates_found >= treated_limit:
                logger.info(
                    f"Reached treated_limit ({treated_limit} duplicates), stopping scan"
                )
                break

            scanned, dups_found, cf_copies = await self._scan_collection_for_duplicates(
                coll_key=coll_key,
                scan_limit=scan_limit,
                treated_limit=treated_limit,
                total_duplicates_found=total_duplicates_found,
                duplicate_groups=duplicate_groups,
            )
            total_scanned += scanned
            total_duplicates_found += dups_found
            cross_folder_copies += cf_copies

        logger.info(
            f"Scanned {total_scanned} items, found {total_duplicates_found} duplicates "
            f"in {len(duplicate_groups)} groups"
        )

        if dry_run:
            logger.info("DRY RUN: No items will be deleted")
            for group in duplicate_groups:
                logger.info(
                    f"  -> Would delete {len(group.duplicate_keys)} items "
                    f"(matched by {group.match_reason}: {group.match_value[:50]})"
                )
            return {
                "total_scanned": total_scanned,
                "duplicates_found": total_duplicates_found,
                "duplicates_removed": 0,
                "cross_folder_copies": cross_folder_copies,
                "groups": duplicate_groups,
                "dry_run": True,
            }

        # Remove duplicates
        duplicates_removed = await self._remove_duplicates(
            duplicate_groups, trash_collection=trash_collection
        )

        logger.info(f"Removed {duplicates_removed} duplicate items")

        return {
            "total_scanned": total_scanned,
            "duplicates_found": total_duplicates_found,
            "duplicates_removed": duplicates_removed,
            "cross_folder_copies": cross_folder_copies,
            "groups": duplicate_groups,
            "dry_run": False,
        }

    async def _scan_collection_for_duplicates(
        self,
        coll_key: str,
        scan_limit: int,
        treated_limit: int,
        total_duplicates_found: int,
        duplicate_groups: list[DuplicateGroup],
    ) -> tuple[int, int, int]:
        """
        Scan a single collection for duplicates in batches.

        Mutates duplicate_groups in place by appending new groups.

        Returns:
            Tuple of (items_scanned, new_duplicates_found, cross_folder_copies)
        """
        scanned = 0
        dups_found = 0
        cf_copies = 0
        offset = 0

        while total_duplicates_found + dups_found < treated_limit:
            items = await async_retry_with_backoff(
                lambda: self.item_service.get_collection_items(
                    coll_key, limit=scan_limit, start=offset
                ),
                description=f"Scan collection {coll_key} (offset {offset})",
            )
            if not items:
                break

            scanned += len(items)
            batch_items = [_item_to_dict(item) for item in items]

            new_groups = await self._find_duplicate_groups(
                batch_items, existing_groups=duplicate_groups
            )

            duplicate_groups.extend(new_groups["groups"])
            cf_copies += new_groups["cross_folder_copies"]

            new_duplicates = sum(len(g.duplicate_keys) for g in new_groups["groups"])
            dups_found += new_duplicates

            logger.info(
                f"  Batch: {len(batch_items)} items, {new_duplicates} new duplicates, "
                f"{new_groups['cross_folder_copies']} cross-folder copies skipped, "
                f"{total_duplicates_found + dups_found} total duplicates found"
            )

            if len(items) < scan_limit:
                break

            offset += scan_limit

        return scanned, dups_found, cf_copies

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

        # Group by DOI (highest priority)
        doi_groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
        for item in items:
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
        for item in items:
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
        for item in items:
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
        trash_collection: str = "06_TRASHES",
    ) -> int:
        """Remove duplicate items by moving them to a trash collection."""
        trash_coll = await self._get_or_create_trash_collection(trash_collection)
        if not trash_coll:
            logger.error(
                f"Failed to find or create trash collection: {trash_collection}"
            )
            return 0

        trash_key = trash_coll.get("key", "")
        moved_count = 0

        for group in duplicate_groups:
            for dup_key in group.duplicate_keys:
                try:
                    item = await self.item_service.api_client.get_item(dup_key)
                    item_type = item.get("data", {}).get("itemType", "")

                    if item_type in ("note", "attachment"):
                        logger.info(
                            f"  Skipping {item_type} item {dup_key} "
                            f"(notes/attachments are not moved)"
                        )
                        continue

                    await async_retry_with_backoff(
                        lambda k=dup_key, tk=trash_key: self._move_item_to_collection(
                            k, tk
                        ),
                        description=f"Move duplicate item {dup_key} to {trash_collection}",
                    )
                    logger.info(
                        f"  Moved duplicate {dup_key} to '{trash_collection}' "
                        f"(matched by {group.match_reason})"
                    )
                    moved_count += 1
                except Exception as e:
                    logger.error(f"  Failed to move {dup_key}: {e}")

        return moved_count

    async def _get_or_create_trash_collection(
        self, collection_name: str
    ) -> dict[str, Any] | None:
        """Find or create a trash collection."""
        collections = await self.item_service.find_collection_by_name(
            collection_name, exact_match=True
        )

        if collections:
            logger.info(f"Using existing trash collection: {collection_name}")
            return collections[0]

        logger.info(f"Creating new trash collection: {collection_name}")
        try:
            result = await self.item_service.create_collection(collection_name)
            if isinstance(result, dict) and "success" in result:
                collections = await self.item_service.find_collection_by_name(
                    collection_name, exact_match=True
                )
                if collections:
                    return collections[0]
            return result
        except Exception as e:
            logger.error(f"Failed to create trash collection: {e}")
            return None

    async def _move_item_to_collection(
        self, item_key: str, target_collection_key: str
    ) -> dict[str, Any]:
        """Move an item to a target collection (remove from all current, add to target)."""
        item = await self.item_service.api_client.get_item(item_key)
        collections = item.get("data", {}).get("collections", [])

        if not isinstance(collections, list):
            logger.warning(
                f"Item {item_key}: collections is {type(collections)}, expected list"
            )
            collections = []

        for collection_key in collections or []:
            try:
                await self.item_service.remove_item_from_collection(
                    collection_key, item_key
                )
            except Exception as e:
                logger.warning(
                    f"Failed to remove {item_key} from collection {collection_key}: {e}"
                )

        return await self.item_service.add_item_to_collection(
            target_collection_key, item_key
        )
