"""Gmail email fetching and parsing module."""

from datetime import datetime
import logging

from bs4 import BeautifulSoup, Tag

from zotero_mcp.clients.gmail import GmailClient
from zotero_mcp.models.ingestion import EmailItem, EmailMessage, RSSItem
from zotero_mcp.utils.helpers import DOI_PATTERN, clean_title

logger = logging.getLogger(__name__)


class GmailFetcher:
    """
    Handles Gmail email fetching and HTML parsing operations.

    This class is responsible for:
    - Searching and fetching emails from Gmail
    - Parsing HTML email content to extract article items
    - Converting EmailItem to RSSItem for filtering
    """

    def __init__(self, gmail_client: GmailClient | None = None):
        """
        Initialize Gmail fetcher.

        Args:
            gmail_client: GmailClient instance (created if not provided)
        """
        self._gmail_client = gmail_client

    @property
    def gmail_client(self) -> GmailClient:
        """Lazy-initialize Gmail client."""
        if self._gmail_client is None:
            self._gmail_client = GmailClient()
        return self._gmail_client

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

    @staticmethod
    def _clean_title(title: str) -> str:
        """Clean article title. Delegates to utils.helpers.clean_title."""
        return clean_title(title)

    def email_item_to_rss_item(self, email_item: EmailItem) -> RSSItem:
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
