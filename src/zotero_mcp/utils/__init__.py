"""
Utility functions and helpers for Zotero MCP.
"""

from .async_helpers import BatchLoader, cached_tool, tool_cache
from .config import get_config, get_logger, log_task_end, log_task_start
from .data import DEFAULT_ANALYSIS_TEMPLATE_JSON, get_analysis_questions, map_zotero_item
from .formatting import (
    DOI_PATTERN,
    beautify_note,
    clean_html,
    clean_title,
    format_creators,
    is_local_mode,
    markdown_to_html,
)
from .system import (
    AuthenticationError,
    ConfigurationError,
    ConnectionError,
    DatabaseError,
    NotFoundError,
    ValidationError,
    ZoteroMCPError,
    check_for_updates,
    format_api_error,
    handle_error,
    setup_zotero_mcp,
)

__all__ = [
    # System
    "ZoteroMCPError",
    "ConnectionError",
    "AuthenticationError",
    "NotFoundError",
    "ValidationError",
    "DatabaseError",
    "ConfigurationError",
    "handle_error",
    "format_api_error",
    "setup_zotero_mcp",
    "check_for_updates",
    # Config
    "get_config",
    "get_logger",
    "log_task_start",
    "log_task_end",
    # Data
    "map_zotero_item",
    "get_analysis_questions",
    "DEFAULT_ANALYSIS_TEMPLATE_JSON",
    # Formatting
    "beautify_note",
    "markdown_to_html",
    "format_creators",
    "clean_title",
    "clean_html",
    "is_local_mode",
    "DOI_PATTERN",
    # Async helpers
    "BatchLoader",
    "cached_tool",
    "tool_cache",
]
