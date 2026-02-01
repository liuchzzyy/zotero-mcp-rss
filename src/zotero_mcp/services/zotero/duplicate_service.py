"""
Service for detecting and removing duplicate Zotero items.

This service scans the Zotero library for duplicate items based on
DOI, title, and URL matching with configurable priority.
"""

from collections import defaultdict
from dataclasses import dataclass, field
import logging
from typing import Any

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
        """
        Initialize DuplicateDetectionService.

        Args:
            item_service: ItemService for Zotero item operations
        """
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
            scan_limit: Number of items to fetch per batch from API (default: 500)
            treated_limit: Maximum total number of items to scan (default: 1000)
            dry_run: If True, don't actually delete items
            trash_collection: Name of collection to move duplicates to (default: "06 - TRASHES")

        Returns:
            Dict with statistics:
                - total_scanned: int
                - duplicates_found: int (items with different metadata, true duplicates)
                - duplicates_removed: int
                - cross_folder_copies: int (items with identical metadata, skipped)
                - groups: list of DuplicateGroup
        """
        logger.info("Starting duplicate detection...")

        # Scan items incrementally, checking for duplicates as we go
        duplicate_groups = []
        total_scanned = 0
        total_duplicates_found = 0
        cross_folder_copies = 0  # Track groups with identical metadata (skipped)

        if collection_key:
            # Single collection mode
            offset = 0
            while total_duplicates_found < treated_limit:
                # Fetch batch from API
                items = await self.item_service.get_collection_items(
                    collection_key, limit=scan_limit, start=offset
                )

                if not items:
                    break  # No more items

                total_scanned += len(items)

                # Convert to dict format for duplicate checking
                batch_items = []
                for item in items:
                    batch_items.append(
                        {
                            "key": item.key,
                            "data": {
                                "DOI": item.doi,
                                "title": item.title,
                                "url": item.url,
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
                    )

                # Find duplicates in this batch (combined with previously found groups)
                new_groups = await self._find_duplicate_groups(
                    batch_items, existing_groups=duplicate_groups
                )

                # Add new groups to the cumulative list
                duplicate_groups.extend(new_groups["groups"])

                # Track cross-folder copies (items with identical metadata)
                cross_folder_copies += new_groups["cross_folder_copies"]

                new_duplicates = sum(
                    len(g.duplicate_keys) for g in new_groups["groups"]
                )
                total_duplicates_found += new_duplicates

                logger.info(
                    f"  Batch: {len(batch_items)} items, {new_duplicates} new duplicates, "
                    f"{new_groups['cross_folder_copies']} cross-folder copies skipped, "
                    f"{total_duplicates_found} total duplicates found"
                )

                # If we got fewer items than scan_limit, we've exhausted the collection
                if len(items) < scan_limit:
                    break

                offset += scan_limit
        else:
            # Scan all collections in order
            logger.info("Scanning all collections in name order...")
            collections = await self.item_service.get_sorted_collections()

            for coll in collections:
                # Check if we've found enough duplicates
                if total_duplicates_found >= treated_limit:
                    break

                coll_key = coll["key"]
                coll_name = coll.get("data", {}).get("name", "")
                logger.info(f"Scanning collection: {coll_name}")

                # Keep fetching batches from this collection
                offset = 0
                while total_duplicates_found < treated_limit:
                    # Fetch batch from API
                    items = await self.item_service.get_collection_items(
                        coll_key, limit=scan_limit, start=offset
                    )

                    if not items:
                        break  # No more items in this collection

                    total_scanned += len(items)

                    # Convert to dict format for duplicate checking
                    batch_items = []
                    for item in items:
                        batch_items.append(
                            {
                                "key": item.key,
                                "data": {
                                    "DOI": item.doi,
                                    "title": item.title,
                                    "url": item.url,
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
                        )

                    # Find duplicates in this batch
                    new_groups = await self._find_duplicate_groups(
                        batch_items, existing_groups=duplicate_groups
                    )

                    # Add new groups to the cumulative list
                    duplicate_groups.extend(new_groups["groups"])

                    # Track cross-folder copies
                    cross_folder_copies += new_groups["cross_folder_copies"]

                    new_duplicates = sum(
                        len(g.duplicate_keys) for g in new_groups["groups"]
                    )
                    total_duplicates_found += new_duplicates

                    logger.info(
                        f"  Collection '{coll_name}': {len(batch_items)} items, "
                        f"{new_duplicates} new duplicates, {new_groups['cross_folder_copies']} cross-folder copies, "
                        f"{total_duplicates_found} total"
                    )

                    # If we got fewer items than scan_limit, we've exhausted this collection
                    if len(items) < scan_limit:
                        break

                    offset += scan_limit

                # Early exit if we've found enough duplicates
                if total_duplicates_found >= treated_limit:
                    logger.info(
                        f"Reached treated_limit ({treated_limit} duplicates), stopping scan"
                    )
                    break

        logger.info(
            f"Scanned {total_scanned} items, found {total_duplicates_found} duplicates "
            f"in {len(duplicate_groups)} groups"
        )

        if dry_run:
            logger.info("DRY RUN: No items will be deleted")
            for group in duplicate_groups:
                logger.info(
                    f"  → Would delete {len(group.duplicate_keys)} items "
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

        Args:
            items: Items to check for duplicates
            existing_groups: Previously found duplicate groups (for incremental checking)

        Priority: DOI > title > URL
        """
        # Start with existing groups (if any)
        all_duplicate_groups = existing_groups or []
        existing_primary_keys = {g.primary_key for g in all_duplicate_groups}
        existing_duplicate_keys = set()
        for g in all_duplicate_groups:
            existing_duplicate_keys.update(g.duplicate_keys)

        cross_folder_copies = 0  # Track groups with identical metadata (skipped)

        # Group by DOI (highest priority)
        doi_groups = defaultdict(list)
        for item in items:
            item_key = item.get("key", "")
            # Skip if already in a duplicate group
            if item_key in existing_primary_keys or item_key in existing_duplicate_keys:
                continue

            item_data = item.get("data", {})
            doi = (item_data.get("DOI") or "").strip()
            if doi:
                doi_groups[doi.lower()].append(item)

        # Group by title (second priority) - only for items without DOI match
        title_groups = defaultdict(list)
        processed_keys = set(existing_primary_keys) | existing_duplicate_keys

        for _doi, items_list in doi_groups.items():
            if len(items_list) > 1:
                # Already have DOI match, mark as processed
                for item in items_list:
                    processed_keys.add(item.get("key", ""))

        # Process remaining items by title
        for item in items:
            item_key = item.get("key", "")
            if item_key in processed_keys:
                continue

            item_data = item.get("data", {})
            title = clean_title(item_data.get("title", "")).lower()
            if title:
                title_groups[title].append(item)

        # Group by URL (lowest priority) - for items without DOI/title match
        url_groups = defaultdict(list)

        for _title, items_list in title_groups.items():
            if len(items_list) > 1:
                for item in items_list:
                    processed_keys.add(item.get("key", ""))

        for item in items:
            item_key = item.get("key", "")
            if item_key in processed_keys:
                continue

            item_data = item.get("data", {})
            url = (item_data.get("url") or "").strip()
            if url:
                url_groups[url].append(item)

        # Convert to DuplicateGroup objects
        duplicate_groups = []

        # DOI groups
        for doi, items_list in doi_groups.items():
            if len(items_list) > 1:
                group = self._create_duplicate_group(
                    items_list, match_reason="doi", match_value=doi
                )
                if group:  # Only add if metadata differs (not cross-folder copies)
                    duplicate_groups.append(group)
                else:
                    cross_folder_copies += 1

        # Title groups
        for title, items_list in title_groups.items():
            if len(items_list) > 1:
                group = self._create_duplicate_group(
                    items_list, match_reason="title", match_value=title
                )
                if group:  # Only add if metadata differs
                    duplicate_groups.append(group)
                else:
                    cross_folder_copies += 1

        # URL groups
        for url, items_list in url_groups.items():
            if len(items_list) > 1:
                group = self._create_duplicate_group(
                    items_list, match_reason="url", match_value=url
                )
                if group:  # Only add if metadata differs
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

        NEW LOGIC:
        - First checks if items have identical metadata (cross-folder copies)
        - If all metadata identical, returns None (skip processing)
        - If metadata differs, treats as duplicates and keeps most complete one

        Selects the most complete item as primary (keeps the one with
        attachments, notes, or most metadata).
        """
        if len(items) < 2:
            return None

        # Check if all items have identical metadata (cross-folder copies)
        if self._all_metadata_identical(items):
            logger.debug(
                f"  Skipping {len(items)} items with identical {match_reason} "
                f"(cross-folder copies, not true duplicates)"
            )
            return None

        # Metadata differs - these are true duplicates
        # Score each item by completeness
        scored_items = []
        for item in items:
            score = self._score_item_completeness(item)
            scored_items.append((score, item))

        # Sort by score (highest first)
        scored_items.sort(key=lambda x: x[0], reverse=True)

        # Primary item is the one with highest score
        primary_item = scored_items[0][1]
        primary_key = primary_item.get("key", "")

        # Rest are duplicates
        duplicate_keys = [item[1].get("key", "") for item in scored_items[1:]]

        return DuplicateGroup(
            primary_key=primary_key,
            duplicate_keys=duplicate_keys,
            match_reason=match_reason,
            match_value=match_value,
        )

    def _score_item_completeness(self, item: dict[str, Any]) -> int:
        """
        Score an item by its completeness.

        Higher score = more complete item.
        Considers:
        - Has attachments/note
        - Has DOI
        - Has authors
        - Has abstract
        - Has publication info
        """
        score = 0
        item_data = item.get("data", {})

        # Has children (attachments, notes)
        children = item.get("children", [])
        if children:
            score += 100
            score += len(children) * 10  # Bonus for more attachments

        # Has DOI
        if item_data.get("DOI"):
            score += 50

        # Has authors/creators
        creators = item_data.get("creators", [])
        if creators:
            score += 30
            score += len(creators) * 2

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
        if item_data.get("volume"):
            score += 5
        if item_data.get("issue"):
            score += 5
        if item_data.get("pages"):
            score += 5

        # Has tags
        tags = item_data.get("tags", [])
        if tags:
            score += len(tags) * 2

        return score

    def _all_metadata_identical(self, items: list[dict[str, Any]]) -> bool:
        """
        Check if all items have identical metadata (excluding collections and version).

        Used to detect cross-folder copies vs true duplicates.

        Compares key metadata fields:
        - DOI, title, url (identification)
        - creators (authors), abstractNote (abstract)
        - publicationTitle (journal), publisher, date
        - volume, issue, pages
        - tags

        Args:
            items: List of items to compare

        Returns:
            True if all items have identical metadata, False otherwise
        """
        if len(items) < 2:
            return True

        # Get the first item as reference
        first_item_data = items[0].get("data", {})

        # Fields to compare (excluding collections and version)
        comparable_fields = [
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

        # Compare each item with the first
        for item in items[1:]:
            item_data = item.get("data", {})

            # Check each comparable field
            for comparable_field in comparable_fields:
                first_value = first_item_data.get(comparable_field)
                item_value = item_data.get(comparable_field)

                # Special handling for creators and tags (lists)
                if field in ["creators", "tags"]:
                    if not self._lists_equal(first_value, item_value):
                        return False
                # Normal field comparison
                elif first_value != item_value:
                    return False

        # All metadata is identical
        return True

    def _lists_equal(self, list1: list | None, list2: list | None) -> bool:
        """
        Compare two lists for equality.

        Handles both dict format (tags: [{"tag": "name"}]) and
        other list formats.

        Args:
            list1: First list
            list2: Second list

        Returns:
            True if lists are equal, False otherwise
        """
        # Handle None values
        if list1 is None and list2 is None:
            return True
        if list1 is None or list2 is None:
            return False

        # Quick length check
        if len(list1) != len(list2):
            return False

        # For tags in dict format [{"tag": "name"}]
        if list1 and isinstance(list1[0], dict):
            # Extract tag names for comparison
            tags1 = sorted([t.get("tag", "") for t in list1])
            tags2 = sorted([t.get("tag", "") for t in list2])
            return tags1 == tags2

        # For creators in dict format [{"creatorType": "author", ...}]
        if list1 and isinstance(list1[0], dict) and "creatorType" in list1[0]:
            # Compare creators as strings for simplicity
            # (full comparison would require handling firstName/lastName vs name)
            return str(list1) == str(list2)

        # Default comparison
        return list1 == list2

    async def _remove_duplicates(
        self,
        duplicate_groups: list[DuplicateGroup],
        trash_collection: str = "06_TRASHES",
    ) -> int:
        """
        Remove duplicate items from Zotero by moving them to trash collection.

        Instead of deleting, this method moves duplicate items to a specified
        trash collection for manual review.

        Args:
            duplicate_groups: List of duplicate groups
            trash_collection: Name of collection to move duplicates to

        Returns:
            Number of items moved to trash collection
        """
        # Find or create trash collection
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
                    # Check if item is a note or attachment (skip these)
                    item = await self.item_service.api_client.get_item(dup_key)
                    item_type = item.get("data", {}).get("itemType", "")

                    if item_type in ["note", "attachment"]:
                        logger.info(
                            f"  ⊘ Skipping {item_type} item {dup_key} "
                            f"(notes/attachments are not moved)"
                        )
                        continue

                    # Move item to trash collection
                    await async_retry_with_backoff(
                        lambda k=dup_key, tk=trash_key: self._move_item_to_collection(
                            k, tk
                        ),
                        description=f"Move duplicate item {dup_key} to {trash_collection}",
                    )
                    logger.info(
                        f"  ✓ Moved duplicate {dup_key} to '{trash_collection}' "
                        f"(matched by {group.match_reason})"
                    )
                    moved_count += 1
                except Exception as e:
                    logger.error(f"  ✗ Failed to move {dup_key}: {e}")

        return moved_count

    async def _get_or_create_trash_collection(
        self, collection_name: str
    ) -> dict[str, Any] | None:
        """
        Find or create a trash collection.

        Args:
            collection_name: Name of the trash collection

        Returns:
            Collection dict with key, or None if failed
        """
        # Try to find existing collection
        collections = await self.item_service.find_collection_by_name(
            collection_name, exact_match=True
        )

        if collections:
            logger.info(f"Using existing trash collection: {collection_name}")
            return collections[0]

        # Create new collection
        logger.info(f"Creating new trash collection: {collection_name}")
        try:
            result = await self.item_service.create_collection(collection_name)
            # Extract collection key from result
            if isinstance(result, dict) and "success" in result:
                # Create collection returns success dict, need to find the collection
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
        """
        Move an item to a target collection.

        This method:
        1. Gets the item's current collections
        2. Removes it from all current collections
        3. Adds it to the target collection

        Args:
            item_key: Key of the item to move
            target_collection_key: Key of the target collection

        Returns:
            Result of the add operation
        """
        # Get item data to find current collections
        item = await self.item_service.api_client.get_item(item_key)

        # Get collections from item data (may not exist for notes/attachments)
        collections = item.get("data", {}).get("collections", [])

        # Ensure collections is a list and handle None
        if collections is None:
            collections = []
        elif not isinstance(collections, list):
            logger.warning(
                f"Item {item_key}: collections is {type(collections)}, expected list"
            )
            collections = []

        # Remove from all current collections
        for collection_key in collections:
            try:
                await self.item_service.remove_item_from_collection(
                    collection_key, item_key
                )
            except Exception as e:
                logger.warning(
                    f"Failed to remove {item_key} from collection {collection_key}: {e}"
                )

        # Add to target collection
        result = await self.item_service.add_item_to_collection(
            target_collection_key, item_key
        )

        return result

    async def _get_items_to_scan(
        self,
        collection_key: str | None = None,
        scan_limit: int = 500,
        treated_limit: int = 1000,
    ) -> list[dict[str, Any]]:
        """
        Get items to scan for duplicates with batch scanning.

        Args:
            collection_key: Optional collection key to limit scan
            scan_limit: Number of items to fetch per batch from API
            treated_limit: Maximum total number of items to retrieve

        Returns:
            List of item dicts
        """
        all_items = []
        seen_keys = set()

        if collection_key:
            # Get items from specific collection in batches
            offset = 0
            while len(all_items) < treated_limit:
                # Fetch batch from API
                items = await self.item_service.get_collection_items(
                    collection_key, limit=scan_limit, start=offset
                )

                if not items:
                    break  # No more items

                # Convert and filter duplicates
                for item in items:
                    if item.key not in seen_keys:
                        seen_keys.add(item.key)
                        all_items.append(
                            {
                                "key": item.key,
                                "data": {
                                    "DOI": item.doi,
                                    "title": item.title,
                                    "url": item.url,
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
                        )

                        if len(all_items) >= treated_limit:
                            break

                # If we got fewer items than scan_limit, we've exhausted the collection
                if len(items) < scan_limit:
                    break

                offset += scan_limit

            logger.info(
                f"Retrieved {len(all_items)} items from collection in batches of {scan_limit}"
            )
        else:
            # Scan all collections in order (00_INBOXS, 01_*, 02_*, etc.)
            logger.info("Scanning all collections in name order...")

            # Get collections sorted by name
            collections = await self.item_service.get_sorted_collections()

            for coll in collections:
                # Check if we've reached the limit
                if len(all_items) >= treated_limit:
                    break

                coll_key = coll["key"]
                coll_name = coll.get("data", {}).get("name", "")
                logger.info(f"Scanning collection: {coll_name}")

                # Get items from this collection
                offset = 0
                while len(all_items) < treated_limit:
                    items = await self.item_service.get_collection_items(
                        coll_key, limit=scan_limit, start=offset
                    )

                    if not items:
                        break

                    # Convert and filter duplicates
                    for item in items:
                        if item.key not in seen_keys:
                            seen_keys.add(item.key)
                            all_items.append(
                                {
                                    "key": item.key,
                                    "data": {
                                        "DOI": item.doi,
                                        "title": item.title,
                                        "url": item.url,
                                        "creators": [],
                                        "abstractNote": item.abstract,
                                        "publicationTitle": None,
                                        "date": item.date,
                                        "volume": None,
                                        "issue": None,
                                        "pages": None,
                                        "tags": [
                                            {"tag": tag} for tag in (item.tags or [])
                                        ],
                                    },
                                    "children": [],
                                }
                            )

                            if len(all_items) >= treated_limit:
                                break

                    # If we got fewer items than scan_limit, we've exhausted this collection
                    if len(items) < scan_limit:
                        break

                    offset += scan_limit

                logger.info(
                    f"  Collection '{coll_name}': {len([i for i in all_items if True])} items"
                )

            logger.info(f"Retrieved {len(all_items)} items from all collections")

        return all_items

    async def _get_all_items(
        self, scan_limit: int = 500, treated_limit: int = 1000
    ) -> list[dict[str, Any]]:
        """Get all items from the library with batch scanning."""
        logger.info(
            f"Fetching items from entire library (batch size: {scan_limit}, max: {treated_limit})"
        )

        all_items = []
        start = 0

        try:
            import asyncio

            loop = asyncio.get_event_loop()

            while len(all_items) < treated_limit:
                # Fetch batch from API
                items = await loop.run_in_executor(
                    None,
                    lambda s=start,
                    limit=scan_limit: self.item_service.api_client.client.top(
                        start=s, limit=limit
                    ),
                )

                if not items:
                    break  # No more items

                all_items.extend(items)

                # If we got fewer items than scan_limit, we've exhausted the library
                if len(items) < scan_limit:
                    break

                start += scan_limit

            logger.info(f"Retrieved {len(all_items)} items from library")
            return all_items

        except Exception as e:
            logger.error(f"Error getting all items: {e}")
            return []
