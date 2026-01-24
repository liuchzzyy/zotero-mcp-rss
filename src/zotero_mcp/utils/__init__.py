"""
Utility functions and helpers for Zotero MCP.
"""

from .config import (
    find_opencode_config,
    get_config_path,
    load_config,
)
from .errors import (
    AuthenticationError,
    ConnectionError,
    NotFoundError,
    ValidationError,
    ZoteroMCPError,
    handle_error,
)
from .helpers import clean_html, format_creators, is_local_mode

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
    "find_opencode_config",
    "get_config_path",
]
