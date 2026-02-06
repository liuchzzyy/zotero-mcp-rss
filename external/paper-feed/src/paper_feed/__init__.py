"""paper-feed: Academic paper collection framework."""

__version__ = "1.0.0"

# Core exports
from paper_feed.core.models import PaperItem, FilterCriteria, FilterResult
from paper_feed.core.base import PaperSource, ExportAdapter

# Source implementations
from paper_feed.sources import RSSSource

# Filter implementations
from paper_feed.filters import FilterPipeline

# Adapter implementations
from paper_feed.adapters import JSONAdapter
try:
    from paper_feed.adapters import ZoteroAdapter
    _zotero_available = True
except ImportError:
    ZoteroAdapter = None
    _zotero_available = False

# Future exports
# from paper_feed.sources import GmailSource

__all__ = [
    "PaperItem",
    "FilterCriteria",
    "FilterResult",
    "PaperSource",
    "ExportAdapter",
    "RSSSource",
    "FilterPipeline",
    "JSONAdapter",
    "ZoteroAdapter",
]
