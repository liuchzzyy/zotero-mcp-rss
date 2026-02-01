"""RSS workflow service for fetching, filtering, and importing papers."""

import asyncio
from datetime import datetime, timedelta
import logging
from typing import TYPE_CHECKING

from zotero_mcp.models.ingestion import RSSProcessResult
from zotero_mcp.services.common import PaperFilter, ZoteroItemCreator
from zotero_mcp.services.data_access import get_data_service
from zotero_mcp.services.rss.rss_fetcher import RSSFetcher
from zotero_mcp.services.zotero.metadata_service import MetadataService
from zotero_mcp.utils.formatting.helpers import clean_title as helper_clean_title

if TYPE_CHECKING:
    pass

logger = logging.getLogger(__name__)


class RSSService:
    """
    Service for RSS paper workflow orchestration.

    This service coordinates feed fetching, AI filtering, and Zotero import.
    """

    def __init__(self, fetcher: RSSFetcher | None = None):
        """
        Initialize RSS service.

        Args:
            fetcher: RSSFetcher instance (created if not provided)
        """
        self._fetcher = fetcher

    @property
    def fetcher(self) -> RSSFetcher:
        """Lazy-initialize RSS fetcher."""
        if self._fetcher is None:
            self._fetcher = RSSFetcher()
        return self._fetcher

    @staticmethod
    def clean_title(title: str) -> str:
        """
        Clean article title by removing common prefixes.

        Delegates to utils.helpers.clean_title for backward compatibility.
        """
        return helper_clean_title(title)

    async def process_rss_workflow(
        self,
        opml_path: str,
        prompt_path: str | None = None,
        collection_name: str = "00_INBOXS",
        days_back: int = 15,
        max_items: int | None = None,
        dry_run: bool = False,
        llm_provider: str = "deepseek",
    ) -> RSSProcessResult:
        """
        Full RSS fetching and importing workflow.

        Args:
            opml_path: Path to OPML file with feed list
            prompt_path: Path to research interests prompt file
            collection_name: Target Zotero collection name
            days_back: Only import items from last N days (0 for all)
            max_items: Maximum number of items to import
            dry_run: If True, don't actually import to Zotero
            llm_provider: LLM provider for filtering ("deepseek" or "claude-cli")

        Returns:
            RSSProcessResult with workflow statistics
        """
        result = RSSProcessResult()

        data_service = get_data_service()
        paper_filter = PaperFilter(prompt_file=prompt_path)
        metadata_service = MetadataService()
        item_creator = ZoteroItemCreator(data_service, metadata_service)

        # Find collection
        matches = await data_service.find_collection_by_name(collection_name)
        if not matches:
            raise ValueError(f"Collection '{collection_name}' not found")
        collection_key = matches[0].get("data", {}).get("key")

        # Fetch feeds
        feeds = await self.fetcher.fetch_feeds_from_opml(opml_path)
        result.feeds_fetched = len(feeds)

        # Count total items across all feeds
        total_items = sum(len(feed.items) for feed in feeds)
        result.items_found = total_items

        # Collect and filter by date
        cutoff = datetime.now() - timedelta(days=days_back) if days_back else None

        all_items = []
        for feed in feeds:
            all_items.extend(
                [
                    i
                    for i in feed.items
                    if not i.pub_date or (cutoff is None or i.pub_date >= cutoff)
                ]
            )
        result.items_after_date_filter = len(all_items)

        if not all_items:
            logger.info("No recent items found")
            return result

        # AI filter
        if llm_provider == "claude-cli":
            logger.info("Using Claude CLI for RSS filtering")
            relevant, _, _ = await paper_filter.filter_with_cli(all_items, prompt_path)
        else:
            relevant, _, _ = await paper_filter.filter_with_keywords(
                all_items, prompt_path
            )
        result.items_filtered = len(relevant)

        # Sort and limit
        relevant.sort(key=lambda x: x.pub_date or datetime.min, reverse=True)
        if max_items:
            relevant = relevant[:max_items]

        # Import
        for item in relevant:
            if dry_run:
                logger.info(f"[DRY RUN] Would import: {item.title}")
                continue
            item_key = await item_creator.create_item(item, collection_key)
            if item_key:
                result.items_imported += 1
            else:
                result.items_duplicate += 1
            await asyncio.sleep(0.5)

        return result
