"""Gmail Service - Email processing workflow and Zotero integration.

This module provides the main workflow for processing Gmail emails:
1. Search for emails by sender/subject
2. Extract items from HTML tables
3. Mark emails as read
4. Filter using AI (reusing RSS_PROMPT)
5. Import to Zotero 00_INBOXS collection
6. Trash/delete processed emails
"""

import asyncio
import logging

from zotero_mcp.models.gmail import EmailItem, GmailProcessResult
from zotero_mcp.models.rss import RSSItem
from zotero_mcp.services.common import PaperFilter, ZoteroItemCreator
from zotero_mcp.services.data_access import get_data_service
from zotero_mcp.services.gmail.gmail_fetcher import GmailFetcher

logger = logging.getLogger(__name__)


class GmailService:
    """
    Service for Gmail paper workflow orchestration.

    This service coordinates email fetching, AI filtering, and Zotero import.
    """

    def __init__(
        self,
        fetcher: GmailFetcher | None = None,
        paper_filter: PaperFilter | None = None,
    ):
        """
        Initialize Gmail service.

        Args:
            fetcher: GmailFetcher instance for email operations
            paper_filter: PaperFilter instance for AI filtering
        """
        self._fetcher = fetcher
        self._paper_filter = paper_filter

    @property
    def fetcher(self) -> GmailFetcher:
        """Lazy-initialize Gmail fetcher."""
        if self._fetcher is None:
            self._fetcher = GmailFetcher()
        return self._fetcher

    @property
    def paper_filter(self) -> PaperFilter:
        """Lazy-initialize paper filter (uses RSS_PROMPT env var)."""
        if self._paper_filter is None:
            self._paper_filter = PaperFilter()
        return self._paper_filter

    async def _trash_emails(
        self,
        email_ids: list[str],
        delete_after: bool,
        trash_only: bool,
        dry_run: bool,
        result: GmailProcessResult,
    ) -> None:
        """Trash or delete emails, updating result stats."""
        if not delete_after or dry_run or not email_ids:
            return

        for email_id in email_ids:
            try:
                if trash_only:
                    success = await self.fetcher.gmail_client.trash_message(email_id)
                else:
                    success = await self.fetcher.gmail_client.delete_message(email_id)

                if success:
                    result.emails_deleted += 1

                await asyncio.sleep(0.1)  # Rate limiting

            except Exception as e:
                logger.error(f"Failed to delete email {email_id}: {e}")
                result.errors.append(f"Delete failed: {email_id}")

        logger.info(f"Trashed {result.emails_deleted}/{len(email_ids)} emails")

    async def process_gmail_workflow(
        self,
        sender: str | None = None,
        subject: str | None = None,
        query: str | None = None,
        collection_name: str = "00_INBOXS",
        max_emails: int = 50,
        delete_after: bool = True,
        trash_only: bool = True,
        dry_run: bool = False,
        llm_provider: str = "deepseek",
    ) -> GmailProcessResult:
        """
        Full Gmail processing workflow.

        1. Search all emails from specified sender in inbox
        2. Extract items from HTML tables
        3. Mark all matched emails as read
        4. AI keyword filtering (uses RSS_PROMPT)
        5. Trash/delete all matched emails
        6. Import filtered items to Zotero

        Args:
            sender: Filter emails by sender
            subject: Filter emails by subject
            query: Raw Gmail query (overrides sender/subject)
            collection_name: Zotero collection to import to
            max_emails: Maximum emails to process
            delete_after: Whether to delete emails after processing
            trash_only: If True, move to trash; if False, permanently delete
            dry_run: If True, don't actually import or delete

        Returns:
            GmailProcessResult with statistics
        """
        from zotero_mcp.services.metadata import MetadataService

        result = GmailProcessResult()

        # Fetch and parse emails
        emails = await self.fetcher.fetch_and_parse_emails(
            sender=sender,
            subject=subject,
            query=query,
            max_emails=max_emails,
        )
        result.emails_found = len(emails)

        if not emails:
            logger.info("No emails to process")
            return result

        # Collect all items and track all email IDs for cleanup
        all_items: list[EmailItem] = []
        all_email_ids: list[str] = [email.id for email in emails]

        for email in emails:
            if email.items:
                all_items.extend(email.items)
                result.emails_processed += 1

        result.items_extracted = len(all_items)

        # Mark all matched emails as read
        for email_id in all_email_ids:
            try:
                await self.fetcher.gmail_client.mark_as_read(email_id)
                await asyncio.sleep(0.1)  # Rate limiting
            except Exception as e:
                logger.error(f"Failed to mark email {email_id} as read: {e}")

        if not all_items:
            logger.info("No items extracted from emails")
            # Still trash emails even if no items extracted
            await self._trash_emails(
                all_email_ids, delete_after, trash_only, dry_run, result
            )
            return result

        # Convert to RSSItem for filtering compatibility
        rss_items = [self.fetcher.email_item_to_rss_item(item) for item in all_items]

        # Apply AI filter using RSS_PROMPT
        try:
            if llm_provider == "claude-cli":
                logger.info("Using Claude CLI for Gmail filtering")
                relevant, irrelevant, keywords = await self.paper_filter.filter_with_cli(
                    rss_items
                )
            else:
                (
                    relevant,
                    irrelevant,
                    keywords,
                ) = await self.paper_filter.filter_with_keywords(rss_items)
            result.keywords_used = keywords
            result.items_filtered = len(relevant)
            logger.info(
                f"AI filter: {len(relevant)} relevant, {len(irrelevant)} filtered out"
            )
        except Exception as e:
            logger.error(f"AI filtering failed: {e}")
            result.errors.append(f"AI filtering failed: {e}")
            # Fall back to all items if filtering fails
            relevant = rss_items
            result.items_filtered = len(relevant)

        if not relevant:
            logger.info("No items passed AI filter")
            # Still trash emails even if no items passed filter
            await self._trash_emails(
                all_email_ids, delete_after, trash_only, dry_run, result
            )
            return result

        if dry_run:
            logger.info(f"[DRY RUN] Would import {len(relevant)} items")
            # Don't trash emails in dry-run mode
            return result

        # Import filtered items to Zotero FIRST
        data_service = get_data_service()
        metadata_service = MetadataService()
        item_creator = ZoteroItemCreator(data_service, metadata_service)

        # Find collection
        matches = await data_service.find_collection_by_name(collection_name)
        if not matches:
            error_msg = f"Collection '{collection_name}' not found"
            logger.error(error_msg)
            result.errors.append(error_msg)
            # Still trash emails even if import fails
            await self._trash_emails(
                all_email_ids, delete_after, trash_only, dry_run, result
            )
            return result

        collection_key = matches[0].get("data", {}).get("key")

        # Import items to Zotero
        for rss_item in relevant:
            try:
                item_key = await item_creator.create_item(rss_item, collection_key)
                if item_key:
                    result.items_imported += 1
                else:
                    result.items_duplicate += 1

                await asyncio.sleep(0.5)  # Rate limiting

            except Exception as e:
                logger.error(f"Failed to import item '{rss_item.title[:50]}': {e}")
                result.errors.append(f"Import failed: {rss_item.title[:50]}")

        # Trash all matched emails AFTER importing to Zotero
        # Emails are trashed regardless of filter results — they have been processed
        await self._trash_emails(
            all_email_ids, delete_after, trash_only, dry_run, result
        )

        logger.info(
            f"Gmail workflow complete: "
            f"{result.emails_processed} emails, "
            f"{result.items_imported} imported, "
            f"{result.emails_deleted} trashed"
        )

        return result
