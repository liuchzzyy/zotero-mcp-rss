"""
Base formatter for Zotero MCP responses.
"""

from abc import ABC, abstractmethod
from typing import Any


class BaseFormatter(ABC):
    """Abstract base class for all formatters."""

    @abstractmethod
    def format_items(self, items: list[dict[str, Any]], **kwargs: Any) -> str:
        """Format a list of Zotero items."""
        ...

    @abstractmethod
    def format_item(self, item: dict[str, Any], **kwargs: Any) -> str:
        """Format a single Zotero item."""
        ...

    @abstractmethod
    def format_error(self, message: str, **kwargs: Any) -> str:
        """Format an error message."""
        ...

    @abstractmethod
    def format_search_results(
        self,
        items: list[dict[str, Any]],
        query: str,
        total: int,
        **kwargs: Any,
    ) -> str:
        """Format search results."""
        ...
