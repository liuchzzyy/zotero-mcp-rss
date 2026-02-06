"""Paper data sources (RSS, Gmail, etc.)."""

from paper_feed.sources.rss import RSSSource
from paper_feed.sources.rss_parser import RSSParser

__all__ = ["RSSSource", "RSSParser"]
