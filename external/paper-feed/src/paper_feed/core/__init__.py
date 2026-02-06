"""Core data models and base classes."""

from paper_feed.core.models import PaperItem, FilterCriteria, FilterResult
from paper_feed.core.base import PaperSource, ExportAdapter

__all__ = [
    "PaperItem",
    "FilterCriteria",
    "FilterResult",
    "PaperSource",
    "ExportAdapter",
]
