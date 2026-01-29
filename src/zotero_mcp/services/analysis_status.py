"""
Analysis Status Service.

Centralizes logic for determining if a Zotero item has been analyzed by AI.
"""

import logging

from zotero_mcp.services.item import ItemService

logger = logging.getLogger(__name__)


class AnalysisStatusService:
    """Service for checking item analysis status."""

    def __init__(self, item_service: ItemService):
        """
        Initialize AnalysisStatusService.

        Args:
            item_service: ItemService instance
        """
        self.item_service = item_service
        self.analyzed_tags = {"AI分析"}

    async def get_analysis_status(self, item_key: str) -> dict[str, bool]:
        """
        Get detailed analysis status for an item.

        Returns:
            Dict with keys:
            - has_tag: True if 'AI分析' tag exists
            - has_notes: True if item has child notes
            - is_analyzed: True if fully analyzed (has tag)
        """
        # Check tags (fast, in metadata)
        item = await self.item_service.get_item(item_key)
        tags = {t.get("tag", "") for t in item.get("data", {}).get("tags", [])}
        has_tag = bool(tags & self.analyzed_tags)

        # Check notes (requires fetching children)
        # We assume if it has the tag, it likely has notes, but we check to be sure?
        # No, checking notes is an extra API call if we don't have children.
        # But ItemService.get_item_children is needed.

        children = await self.item_service.get_item_children(item_key, item_type="note")
        has_notes = len(children) > 0

        return {
            "has_tag": has_tag,
            "has_notes": has_notes,
            "is_analyzed": has_tag,  # Strict definition
        }

    async def is_analyzed(self, item_key: str) -> bool:
        """
        Check if item is considered analyzed (has 'AI分析' tag).
        """
        item = await self.item_service.get_item(item_key)
        tags = {t.get("tag", "") for t in item.get("data", {}).get("tags", [])}
        return bool(tags & self.analyzed_tags)

    async def has_notes(self, item_key: str) -> bool:
        """Check if item has notes."""
        notes = await self.item_service.get_notes(item_key)
        return len(notes) > 0
