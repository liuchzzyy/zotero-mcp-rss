"""
Utility functions and helpers for Zotero MCP.
"""

from .errors import (
    ZoteroMCPError,
    ConnectionError,
    AuthenticationError,
    NotFoundError,
    ValidationError,
    handle_error,
)
from .helpers import format_creators, clean_html, is_local_mode
from .config import (
    load_config,
    find_claude_config,
    find_opencode_config,
    get_config_path,
)

__all__ = [
    # Errors
    "ZoteroMCPError",
    "ConnectionError",
    "AuthenticationError",
    "NotFoundError",
    "ValidationError",
    "handle_error",
    # Helpers
    "format_creators",
    "clean_html",
    "is_local_mode",
    # Config
    "load_config",
    "find_claude_config",
    "find_opencode_config",
    "get_config_path",
]
