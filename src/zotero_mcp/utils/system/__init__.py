"""System-level utilities."""

from .errors import (
    AuthenticationError,
    ConfigurationError,
    ConnectionError,
    DatabaseError,
    NotFoundError,
    ValidationError,
    ZoteroMCPError,
    format_api_error,
    handle_error,
)
from .setup import setup_zotero_mcp
from .updater import check_for_updates

__all__ = [
    # Errors
    "ZoteroMCPError",
    "ConnectionError",
    "AuthenticationError",
    "NotFoundError",
    "ValidationError",
    "DatabaseError",
    "ConfigurationError",
    "handle_error",
    "format_api_error",
    # Setup
    "setup_zotero_mcp",
    # Updater
    "check_for_updates",
]
