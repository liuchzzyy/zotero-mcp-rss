"""
Response format converter for backward compatibility.

Allows converting structured Pydantic models to legacy string formats (markdown/JSON)
for clients that haven't migrated to the new schema.
"""

import json

from zotero_mcp.models.common import (
    AnnotationsResponse,
    BaseResponse,
    ItemDetailResponse,
    SearchResponse,
)


class ResponseConverter:
    """Convert structured Pydantic responses to legacy string formats."""

    @staticmethod
    def to_legacy_format(response: BaseResponse, format_type: str = "json") -> str:
        """
        Convert structured response to legacy string format.

        Args:
            response: Structured Pydantic response
            format_type: Output format ("json" or "markdown")

        Returns:
            Formatted string in legacy format
        """
        if not response.success:
            return f"❌ Error: {response.error}"

        if format_type == "json":
            return ResponseConverter._to_json_string(response)
        else:
            return ResponseConverter._to_markdown_string(response)

    @staticmethod
    def _to_json_string(response: BaseResponse) -> str:
        """Convert to JSON string (legacy format)."""
        if isinstance(response, SearchResponse):
            # Convert to legacy format: {"items": [...], "count": N}
            legacy_format = {
                "items": [item.model_dump() for item in response.items],
                "count": response.count,
                "total": response.total,
            }
            return json.dumps(legacy_format, indent=2, default=str)

        elif isinstance(response, ItemDetailResponse):
            # Convert creators list to authors if needed (already handled in model)
            data = response.model_dump()
            # Legacy clients might expect 'authors' which is already present
            return json.dumps(data, indent=2, default=str)

        # Default: return full model as JSON
        return response.model_dump_json(indent=2)

    @staticmethod
    def _to_markdown_string(response: BaseResponse) -> str:
        """Convert to Markdown string (legacy format)."""
        if isinstance(response, SearchResponse):
            lines = [
                f"# Search Results: '{response.query}'",
                "",
                f"Found {response.total} results (showing {response.count})",
                "",
            ]

            for i, item in enumerate(response.items, 1):
                lines.extend(
                    [
                        f"## {i}. {item.title}",
                        f"**Authors:** {item.authors or 'Unknown'}",
                        f"**Year:** {item.date or 'N/A'}",
                        f"**Type:** {item.item_type}",
                        f"**Key:** `{item.key}`",
                        "",
                    ]
                )

            if response.has_more:
                lines.append(
                    f"*More results available (offset: {response.next_offset})*"
                )

            return "\n".join(lines)

        elif isinstance(response, AnnotationsResponse):
            lines = [
                f"# Annotations for {response.item_key}",
                "",
                f"Found {response.count} annotation(s)",
                "",
            ]

            for ann in response.annotations:
                lines.extend(
                    [
                        f"### {ann.type.title()}"
                        + (f" (Page {ann.page})" if ann.page else ""),
                        f"*Color: {ann.color}*" if ann.color else "",
                        f"> {ann.text}" if ann.text else "",
                        f"\n**Comment:** {ann.comment}" if ann.comment else "",
                        "",
                    ]
                )

            return "\n".join(filter(None, lines))

        # Default: return message field if exists (not standard in BaseResponse) or JSON
        # BaseResponse doesn't have 'message', but subclasses might
        if hasattr(response, "message") and response.message:
            return response.message

        return response.model_dump_json(indent=2)


# Usage Example
def convert_response_for_legacy_client(response: BaseResponse) -> str:
    """Helper function for legacy clients."""
    converter = ResponseConverter()
    return converter.to_legacy_format(response, format_type="markdown")
