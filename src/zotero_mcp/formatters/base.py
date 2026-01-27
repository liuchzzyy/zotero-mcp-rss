"""
Base formatter for Zotero MCP responses.
"""

from abc import ABC, abstractmethod
import json
from typing import Any

from zotero_mcp.models.common import ResponseFormat


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


def format_response(
    data: Any,
    response_format: ResponseFormat = ResponseFormat.MARKDOWN,
    **kwargs: Any,
) -> str:
    """
    Format a response according to the specified format.

    Args:
        data: Data to format (dict, list, or string)
        response_format: Output format (markdown or json)
        **kwargs: Additional formatting options

    Returns:
        Formatted string
    """
    if response_format == ResponseFormat.JSON:
        if isinstance(data, str):
            return data
        return json.dumps(data, indent=2, ensure_ascii=False)

    # For markdown, return as-is if already string
    if isinstance(data, str):
        return data

    # Default: convert to JSON for complex types
    return json.dumps(data, indent=2, ensure_ascii=False)
