"""RSS and Gmail ingestion models."""

from .gmail import EmailItem, EmailMessage, GmailProcessResult
from .rss import RSSFeed, RSSItem, RSSProcessResult

__all__ = [
    "EmailItem",
    "EmailMessage",
    "GmailProcessResult",
    "RSSFeed",
    "RSSItem",
    "RSSProcessResult",
]
