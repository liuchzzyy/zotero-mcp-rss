"""
JSON formatter for Zotero MCP responses.
"""

import json
from typing import Any

from .base import BaseFormatter


class JSONFormatter(BaseFormatter):
    """Formatter for JSON output."""

    def __init__(self, indent: int = 2, ensure_ascii: bool = False):
        """
        Initialize JSON formatter.

        Args:
            indent: JSON indentation level
            ensure_ascii: Whether to escape non-ASCII characters
        """
        self.indent = indent
        self.ensure_ascii = ensure_ascii

    def format_items(
        self,
        items: list[dict[str, Any]],
        include_meta: bool = True,
        **kwargs: Any,
    ) -> str:
        """
        Format a list of Zotero items as JSON.

        Args:
            items: List of Zotero item data
            include_meta: Whether to include metadata wrapper
            **kwargs: Additional options

        Returns:
            JSON-formatted string
        """
        if include_meta:
            result = {
                "count": len(items),
                "items": items,
            }
        else:
            result = items

        return json.dumps(result, indent=self.indent, ensure_ascii=self.ensure_ascii)

    def format_item(self, item: dict[str, Any], **kwargs: Any) -> str:
        """
        Format a single Zotero item as JSON.

        Args:
            item: Zotero item data
            **kwargs: Additional options

        Returns:
            JSON-formatted string
        """
        return json.dumps(item, indent=self.indent, ensure_ascii=self.ensure_ascii)

    def format_error(
        self,
        message: str,
        code: str = "error",
        suggestion: str = "",
        **kwargs: Any,
    ) -> str:
        """
        Format an error message as JSON.

        Args:
            message: Error message
            code: Error code
            suggestion: Optional suggestion for fixing the error
            **kwargs: Additional options

        Returns:
            JSON-formatted error string
        """
        error_obj: dict[str, Any] = {
            "error": True,
            "code": code,
            "message": message,
        }
        if suggestion:
            error_obj["suggestion"] = suggestion

        return json.dumps(error_obj, indent=self.indent, ensure_ascii=self.ensure_ascii)

    def format_search_results(
        self,
        items: list[dict[str, Any]],
        query: str,
        total: int,
        offset: int = 0,
        limit: int = 20,
        **kwargs: Any,
    ) -> str:
        """
        Format search results as JSON.

        Args:
            items: List of matching items
            query: Search query
            total: Total number of matches
            offset: Current offset
            limit: Results per page
            **kwargs: Additional options

        Returns:
            JSON-formatted search results
        """
        result = {
            "query": query,
            "total": total,
            "offset": offset,
            "limit": limit,
            "count": len(items),
            "has_more": offset + len(items) < total,
            "items": items,
        }

        return json.dumps(result, indent=self.indent, ensure_ascii=self.ensure_ascii)

    def format_semantic_results(
        self,
        items: list[dict[str, Any]],
        query: str,
        **kwargs: Any,
    ) -> str:
        """
        Format semantic search results as JSON.

        Args:
            items: List of items with similarity scores
            query: Search query
            **kwargs: Additional options

        Returns:
            JSON-formatted semantic search results
        """
        result = {
            "query": query,
            "search_type": "semantic",
            "count": len(items),
            "items": items,
        }

        return json.dumps(result, indent=self.indent, ensure_ascii=self.ensure_ascii)

    def format_annotations(
        self,
        annotations: list[dict[str, Any]],
        item_key: str = "",
        **kwargs: Any,
    ) -> str:
        """
        Format annotations as JSON.

        Args:
            annotations: List of annotation data
            item_key: Key of the parent item
            **kwargs: Additional options

        Returns:
            JSON-formatted annotations
        """
        result = {
            "item_key": item_key,
            "count": len(annotations),
            "annotations": annotations,
        }

        return json.dumps(result, indent=self.indent, ensure_ascii=self.ensure_ascii)

    def format_collections(
        self,
        collections: list[dict[str, Any]],
        **kwargs: Any,
    ) -> str:
        """
        Format collections as JSON.

        Args:
            collections: List of collection data
            **kwargs: Additional options

        Returns:
            JSON-formatted collections
        """
        result = {
            "count": len(collections),
            "collections": collections,
        }

        return json.dumps(result, indent=self.indent, ensure_ascii=self.ensure_ascii)
