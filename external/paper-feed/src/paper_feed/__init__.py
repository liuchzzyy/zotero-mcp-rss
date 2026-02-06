"""paper-feed: Academic paper collection framework."""

__version__ = "1.0.0"

# Core exports
from paper_feed.core.models import PaperItem, FilterCriteria, FilterResult
from paper_feed.core.base import PaperSource, ExportAdapter

# Source implementations
from paper_feed.sources import RSSSource

# Future exports
# from paper_feed.sources import GmailSource
# from paper_feed.filters import FilterPipeline
# from paper_feed.adapters import JSONAdapter, ZoteroAdapter

__all__ = [
    "PaperItem",
    "FilterCriteria",
    "FilterResult",
    "PaperSource",
    "ExportAdapter",
    "RSSSource",
]
