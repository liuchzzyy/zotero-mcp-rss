"""
Service for detecting and removing duplicate Zotero items.

This service scans the Zotero library for duplicate items based on
DOI, title, and URL matching with configurable priority.
"""

import logging
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Any

from zotero_mcp.services.zotero.item_service import ItemService
from zotero_mcp.services.common.retry import async_retry_with_backoff
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
        dry_run: bool = False,
    ) -> dict[str, Any]:
        """
        Find and remove duplicate items.

        Args:
            collection_key: Optional collection key to limit scan
            dry_run: If True, don't actually delete items

        Returns:
            Dict with statistics:
                - total_scanned: int
                - duplicates_found: int
                - duplicates_removed: int
                - groups: list of DuplicateGroup
        """
        logger.info("Starting duplicate detection...")

        # Get all items
        items = await self._get_items_to_scan(collection_key)
        logger.info(f"Scanning {len(items)} items for duplicates...")

        # Find duplicate groups
        duplicate_groups = await self._find_duplicate_groups(items)

        duplicates_found = sum(len(g.duplicate_keys) for g in duplicate_groups)
        logger.info(f"Found {duplicates_found} duplicates in {len(duplicate_groups)} groups")

        if dry_run:
            logger.info("DRY RUN: No items will be deleted")
            for group in duplicate_groups:
                logger.info(
                    f"  → Would delete {len(group.duplicate_keys)} items "
                    f"(matched by {group.match_reason}: {group.match_value[:50]})"
                )
            return {
                "total_scanned": len(items),
                "duplicates_found": duplicates_found,
                "duplicates_removed": 0,
                "groups": duplicate_groups,
                "dry_run": True,
            }

        # Remove duplicates
        duplicates_removed = await self._remove_duplicates(duplicate_groups)

        logger.info(f"Removed {duplicates_removed} duplicate items")

        return {
            "total_scanned": len(items),
            "duplicates_found": duplicates_found,
            "duplicates_removed": duplicates_removed,
            "groups": duplicate_groups,
            "dry_run": False,
        }

    async def _find_duplicate_groups(
        self, items: list[dict[str, Any]]
    ) -> list[DuplicateGroup]:
        """
        Find groups of duplicate items.

        Priority: DOI > title > URL
        """
        # Group by DOI (highest priority)
        doi_groups = defaultdict(list)
        for item in items:
            item_key = item.get("key", "")
            item_data = item.get("data", {})
            doi = item_data.get("DOI", "").strip()
            if doi:
                doi_groups[doi.lower()].append(item)

        # Group by title (second priority) - only for items without DOI match
        title_groups = defaultdict(list)
        processed_keys = set()

        for doi, items_list in doi_groups.items():
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

        for title, items_list in title_groups.items():
            if len(items_list) > 1:
                for item in items_list:
                    processed_keys.add(item.get("key", ""))

        for item in items:
            item_key = item.get("key", "")
            if item_key in processed_keys:
                continue

            item_data = item.get("data", {})
            url = item_data.get("url", "").strip()
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
                duplicate_groups.append(group)

        # Title groups
        for title, items_list in title_groups.items():
            if len(items_list) > 1:
                group = self._create_duplicate_group(
                    items_list, match_reason="title", match_value=title
                )
                duplicate_groups.append(group)

        # URL groups
        for url, items_list in url_groups.items():
            if len(items_list) > 1:
                group = self._create_duplicate_group(
                    items_list, match_reason="url", match_value=url
                )
                duplicate_groups.append(group)

        return duplicate_groups

    def _create_duplicate_group(
        self, items: list[dict[str, Any]], match_reason: str, match_value: str
    ) -> DuplicateGroup:
        """
        Create a DuplicateGroup from a list of duplicate items.

        Selects the most complete item as primary (keeps the one with
        attachments, notes, or most metadata).
        """
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

    async def _remove_duplicates(
        self, duplicate_groups: list[DuplicateGroup]
    ) -> int:
        """
        Remove duplicate items from Zotero.

        Args:
            duplicate_groups: List of duplicate groups

        Returns:
            Number of items removed
        """
        removed_count = 0

        for group in duplicate_groups:
            for dup_key in group.duplicate_keys:
                try:
                    await async_retry_with_backoff(
                        lambda k=dup_key: self.item_service.delete_item(k),
                        description=f"Delete duplicate item {dup_key}",
                    )
                    logger.info(
                        f"  ✓ Deleted duplicate {dup_key} "
                        f"(matched by {group.match_reason})"
                    )
                    removed_count += 1
                except Exception as e:
                    logger.error(f"  ✗ Failed to delete {dup_key}: {e}")

        return removed_count

    async def _get_items_to_scan(
        self, collection_key: str | None = None
    ) -> list[dict[str, Any]]:
        """
        Get items to scan for duplicates.

        Args:
            collection_key: Optional collection key to limit scan

        Returns:
            List of item dicts
        """
        if collection_key:
            # Get items from specific collection
            return await self.item_service.get_collection_items(collection_key)
        else:
            # Get all items from library
            # This is a simplified version - should implement pagination
            return await self._get_all_items()

    async def _get_all_items(self) -> list[dict[str, Any]]:
        """Get all items from the library."""
        # TODO: Implement proper pagination
        # For now, use empty list - user should specify collection
        logger.warning(
            "_get_all_items: Getting all items not fully implemented. "
            "Please specify a collection_key for better results."
        )
        try:
            # Use API client to get top-level items
            import asyncio
            loop = asyncio.get_event_loop()
            items = await loop.run_in_executor(
                None,
                lambda: self.item_service.api_client.client.top(limit=1000)
            )
            return items if items else []
        except Exception as e:
            logger.error(f"Error getting all items: {e}")
            return []
