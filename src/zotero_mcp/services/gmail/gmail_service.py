"""
Gmail Service - Email processing and Zotero integration.

This module provides the main workflow for processing Gmail emails:
1. Search for emails by sender/subject
2. Extract items from HTML tables
3. Filter using AI (reusing RSS_PROMPT)
4. Import to Zotero 00_INBOXS collection
5. Delete processed emails
"""

import asyncio
from datetime import datetime
import logging
import re

from bs4 import BeautifulSoup, Tag

from zotero_mcp.clients.gmail import GmailClient
from zotero_mcp.models.gmail import EmailItem, EmailMessage, GmailProcessResult
from zotero_mcp.models.rss import RSSItem
from zotero_mcp.services.rss.rss_filter import RSSFilter

logger = logging.getLogger(__name__)

# DOI regex pattern
DOI_PATTERN = re.compile(r"10\.\d{4,9}/[-._;()/:A-Z0-9]+", re.IGNORECASE)


class GmailService:
    """
    Service for processing Gmail emails and importing items to Zotero.

    Workflow:
    1. Search emails by sender/subject filter
    2. Parse HTML tables to extract article items
    3. Apply AI keyword filtering (reuses RSS_PROMPT)
    4. Import matching items to Zotero
    5. Delete/trash processed emails
    """

    def __init__(
        self,
        gmail_client: GmailClient | None = None,
        rss_filter: RSSFilter | None = None,
    ):
        """
        Initialize Gmail service.

        Args:
            gmail_client: GmailClient instance (created if not provided)
            rss_filter: RSSFilter instance for AI filtering (created if not provided)
        """
        self._gmail_client = gmail_client
        self._rss_filter = rss_filter

    @property
    def gmail_client(self) -> GmailClient:
        """Lazy-initialize Gmail client."""
        if self._gmail_client is None:
            self._gmail_client = GmailClient()
        return self._gmail_client

    @property
    def rss_filter(self) -> RSSFilter:
        """Lazy-initialize RSS filter (uses RSS_PROMPT env var)."""
        if self._rss_filter is None:
            self._rss_filter = RSSFilter()
        return self._rss_filter

    def parse_html_table(
        self,
        html_content: str,
        email_id: str = "",
        email_subject: str = "",
    ) -> list[EmailItem]:
        """
        Parse HTML content to extract items from tables.

        Supports common email newsletter formats with tables containing:
        - Article titles (often as links)
        - Authors
        - Journal names
        - DOIs or article URLs

        Args:
            html_content: HTML body content
            email_id: Gmail message ID for tracking
            email_subject: Email subject for tracking

        Returns:
            List of extracted EmailItem objects
        """
        if not html_content:
            return []

        items: list[EmailItem] = []
        soup = BeautifulSoup(html_content, "lxml")

        # Strategy 1: Look for table rows with links
        for table in soup.find_all("table"):
            rows = table.find_all("tr")
            for row in rows:
                item = self._extract_item_from_row(row, email_id, email_subject)
                if item:
                    items.append(item)

        # Strategy 2: If no tables, look for article-like divs/sections
        if not items:
            items = self._extract_items_from_divs(soup, email_id, email_subject)

        # Strategy 3: Extract from plain links with surrounding text
        if not items:
            items = self._extract_items_from_links(soup, email_id, email_subject)

        # Deduplicate by title
        seen_titles: set[str] = set()
        unique_items: list[EmailItem] = []
        for item in items:
            title_lower = item.title.lower().strip()
            if title_lower and title_lower not in seen_titles:
                seen_titles.add(title_lower)
                unique_items.append(item)

        logger.info(f"Extracted {len(unique_items)} items from email {email_id[:8]}...")
        return unique_items

    def _extract_item_from_row(
        self,
        row: Tag,
        email_id: str,
        email_subject: str,
    ) -> EmailItem | None:
        """Extract an item from a table row."""
        # Find title - usually in a link or strong/bold text
        title = ""
        link = ""

        # Look for the main link (title link)
        links = row.find_all("a", href=True)
        for a in links:
            href_value = a.get("href", "")
            # Normalize href to string
            href = href_value if isinstance(href_value, str) else ""
            text = a.get_text(strip=True)

            # Skip navigation/utility links
            if len(text) < 10 or text.lower() in ("read more", "view", "click here"):
                continue

            # This looks like a title link
            if not title or len(text) > len(title):
                title = text
                link = href

        if not title:
            # Try to get title from text content
            cells = row.find_all(["td", "th"])
            for cell in cells:
                text = cell.get_text(strip=True)
                if len(text) > 20 and len(text) < 500:
                    title = text
                    break

        if not title or len(title) < 10:
            return None

        # Extract DOI from link or text
        doi = None
        row_text = row.get_text()
        doi_match = DOI_PATTERN.search(link) or DOI_PATTERN.search(row_text)
        if doi_match:
            doi = doi_match.group(0)

        # Try to extract author/journal from other cells
        authors = None
        journal = None
        cells = row.find_all(["td", "th"])
        for cell in cells:
            text = cell.get_text(strip=True)
            if text == title:
                continue
            # Heuristic: shorter text might be journal, text with commas might be authors
            if "," in text and len(text) < 200:
                if not authors:
                    authors = text
            elif len(text) < 100 and not journal:
                journal = text

        return EmailItem(
            title=self._clean_title(title),
            link=link,
            authors=authors,
            journal=journal,
            doi=doi,
            source_email_id=email_id,
            source_subject=email_subject,
        )

    def _extract_items_from_divs(
        self,
        soup: BeautifulSoup,
        email_id: str,
        email_subject: str,
    ) -> list[EmailItem]:
        """Extract items from div-based layouts."""
        items: list[EmailItem] = []

        # Look for article-like containers
        for container in soup.find_all(["div", "article", "section"]):
            # Must have a link
            link_elem = container.find("a", href=True)
            if not link_elem:
                continue

            title = link_elem.get_text(strip=True)
            link_value = link_elem.get("href", "")
            # Normalize to string
            link = link_value if isinstance(link_value, str) else ""

            if len(title) < 15:
                # Try to find a heading
                heading = container.find(["h1", "h2", "h3", "h4"])
                if heading:
                    title = heading.get_text(strip=True)

            if len(title) < 15 or len(title) > 500:
                continue

            # Extract DOI
            doi = None
            container_text = container.get_text()
            doi_match = DOI_PATTERN.search(link) or DOI_PATTERN.search(container_text)
            if doi_match:
                doi = doi_match.group(0)

            items.append(
                EmailItem(
                    title=self._clean_title(title),
                    link=link,
                    doi=doi,
                    source_email_id=email_id,
                    source_subject=email_subject,
                )
            )

        return items

    def _extract_items_from_links(
        self,
        soup: BeautifulSoup,
        email_id: str,
        email_subject: str,
    ) -> list[EmailItem]:
        """Extract items from standalone links."""
        items: list[EmailItem] = []

        for a in soup.find_all("a", href=True):
            text = a.get_text(strip=True)
            href_value = a.get("href", "")
            # Normalize to string
            href = href_value if isinstance(href_value, str) else ""

            # Filter out non-article links
            if len(text) < 20 or len(text) > 500:
                continue
            if text.lower() in ("unsubscribe", "view in browser", "read more"):
                continue

            # Check if link looks like an article (DOI, journal site, etc.)
            is_article_link = any(
                domain in href.lower()
                for domain in [
                    "doi.org",
                    "nature.com",
                    "science.org",
                    "wiley.com",
                    "springer.com",
                    "acs.org",
                    "rsc.org",
                    "elsevier.com",
                    "cell.com",
                    "pnas.org",
                    "sciencedirect.com",
                ]
            )

            doi = None
            doi_match = DOI_PATTERN.search(href)
            if doi_match:
                doi = doi_match.group(0)
                is_article_link = True

            if is_article_link:
                items.append(
                    EmailItem(
                        title=self._clean_title(text),
                        link=href,
                        doi=doi,
                        source_email_id=email_id,
                        source_subject=email_subject,
                    )
                )

        return items

    def _clean_title(self, title: str) -> str:
        """Clean article title."""
        if not title:
            return ""
        # Remove common prefixes
        cleaned = re.sub(r"^\[.*?\]\s*", "", title)
        # Remove extra whitespace
        cleaned = " ".join(cleaned.split())
        return cleaned.strip()

    def _email_item_to_rss_item(self, email_item: EmailItem) -> RSSItem:
        """Convert EmailItem to RSSItem for filtering compatibility."""
        return RSSItem(
            title=email_item.title,
            link=email_item.link,
            description=email_item.abstract,
            pub_date=email_item.pub_date,
            author=email_item.authors,
            guid=email_item.link or email_item.title,
            source_url=f"gmail:{email_item.source_email_id}",
            source_title=email_item.source_subject,
            doi=email_item.doi,
        )

    async def fetch_and_parse_emails(
        self,
        sender: str | None = None,
        subject: str | None = None,
        query: str | None = None,
        max_emails: int = 50,
    ) -> list[EmailMessage]:
        """
        Fetch emails and parse their content.

        Args:
            sender: Filter by sender email
            subject: Filter by subject
            query: Raw Gmail query (overrides sender/subject)
            max_emails: Maximum emails to process

        Returns:
            List of parsed EmailMessage objects
        """
        # Search for emails
        messages = await self.gmail_client.search_messages(
            sender=sender,
            subject=subject,
            query=query,
            max_results=max_emails,
        )

        if not messages:
            logger.info("No matching emails found")
            return []

        # Parse each email
        parsed_emails: list[EmailMessage] = []
        for msg_info in messages:
            msg_id = msg_info["id"]
            thread_id = msg_info.get("threadId", "")

            try:
                # Get headers
                headers = await self.gmail_client.get_message_headers(msg_id)
                subject_val = headers.get("Subject", "")
                sender_val = headers.get("From", "")
                date_str = headers.get("Date", "")

                # Parse date
                date_val = None
                if date_str:
                    try:
                        # Try common email date formats
                        for fmt in [
                            "%a, %d %b %Y %H:%M:%S %z",
                            "%d %b %Y %H:%M:%S %z",
                            "%a, %d %b %Y %H:%M:%S",
                        ]:
                            try:
                                date_val = datetime.strptime(date_str[:31], fmt)
                                break
                            except ValueError:
                                continue
                    except Exception:
                        pass

                # Get body
                html_body, text_body = await self.gmail_client.get_message_body(msg_id)

                # Parse items from HTML
                items = self.parse_html_table(html_body, msg_id, subject_val)

                parsed_emails.append(
                    EmailMessage(
                        id=msg_id,
                        thread_id=thread_id,
                        subject=subject_val,
                        sender=sender_val,
                        date=date_val,
                        html_body=html_body,
                        text_body=text_body,
                        items=items,
                    )
                )

            except Exception as e:
                logger.error(f"Failed to parse email {msg_id}: {e}")
                continue

        logger.info(f"Parsed {len(parsed_emails)} emails")
        return parsed_emails

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
    ) -> GmailProcessResult:
        """
        Full Gmail processing workflow.

        1. Search and fetch emails
        2. Extract items from HTML tables
        3. Apply AI keyword filtering (uses RSS_PROMPT)
        4. Import to Zotero
        5. Delete/trash processed emails

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
        from zotero_mcp.services.data_access import get_data_service
        from zotero_mcp.services.metadata import MetadataService
        from zotero_mcp.services.rss.rss_service import RSSService

        result = GmailProcessResult()

        # Fetch and parse emails
        emails = await self.fetch_and_parse_emails(
            sender=sender,
            subject=subject,
            query=query,
            max_emails=max_emails,
        )
        result.emails_found = len(emails)

        if not emails:
            logger.info("No emails to process")
            return result

        # Collect all items from all emails
        all_items: list[EmailItem] = []
        processed_email_ids: list[str] = []

        for email in emails:
            if email.items:
                all_items.extend(email.items)
                processed_email_ids.append(email.id)
                result.emails_processed += 1

        result.items_extracted = len(all_items)

        if not all_items:
            logger.info("No items extracted from emails")
            return result

        # Convert to RSSItem for filtering compatibility
        rss_items = [self._email_item_to_rss_item(item) for item in all_items]

        # Apply AI filter using RSS_PROMPT
        try:
            relevant, irrelevant, keywords = await self.rss_filter.filter_with_keywords(
                rss_items
            )
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
            return result

        if dry_run:
            logger.info(f"[DRY RUN] Would import {len(relevant)} items")
            return result

        # Get services for Zotero import
        data_service = get_data_service()
        metadata_service = MetadataService()
        rss_service = RSSService()

        # Find collection
        matches = await data_service.find_collection_by_name(collection_name)
        if not matches:
            error_msg = f"Collection '{collection_name}' not found"
            logger.error(error_msg)
            result.errors.append(error_msg)
            return result

        collection_key = matches[0].get("data", {}).get("key")

        # Import items to Zotero (reuse RSS service logic)
        for rss_item in relevant:
            try:
                item_key = await rss_service.create_zotero_item(
                    data_service,
                    metadata_service,
                    rss_item,
                    collection_key,
                )
                if item_key:
                    result.items_imported += 1
                else:
                    result.items_duplicate += 1

                await asyncio.sleep(0.5)  # Rate limiting

            except Exception as e:
                logger.error(f"Failed to import item '{rss_item.title[:50]}': {e}")
                result.errors.append(f"Import failed: {rss_item.title[:50]}")

        # Mark processed emails as read
        if processed_email_ids:
            for email_id in processed_email_ids:
                try:
                    await self.gmail_client.mark_as_read(email_id)
                    await asyncio.sleep(0.1)  # Rate limiting
                except Exception as e:
                    logger.error(f"Failed to mark email {email_id} as read: {e}")

        # Delete/trash processed emails
        if delete_after and processed_email_ids:
            for email_id in processed_email_ids:
                try:
                    if trash_only:
                        success = await self.gmail_client.trash_message(email_id)
                    else:
                        success = await self.gmail_client.delete_message(email_id)

                    if success:
                        result.emails_deleted += 1

                    await asyncio.sleep(0.1)  # Rate limiting

                except Exception as e:
                    logger.error(f"Failed to delete email {email_id}: {e}")
                    result.errors.append(f"Delete failed: {email_id}")

        logger.info(
            f"Gmail workflow complete: "
            f"{result.emails_processed} emails, "
            f"{result.items_imported} imported, "
            f"{result.emails_deleted} deleted"
        )

        return result
