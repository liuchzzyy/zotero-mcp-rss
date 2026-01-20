"""
Unified error handling for Zotero MCP.
"""

from typing import TYPE_CHECKING
import logging

if TYPE_CHECKING:
    from fastmcp import Context

logger = logging.getLogger(__name__)


class ZoteroMCPError(Exception):
    """Base exception for Zotero MCP errors."""

    def __init__(self, message: str, suggestion: str | None = None):
        super().__init__(message)
        self.message = message
        self.suggestion = suggestion

    def __str__(self) -> str:
        if self.suggestion:
            return f"{self.message}. {self.suggestion}"
        return self.message


class ConnectionError(ZoteroMCPError):
    """Error connecting to Zotero or external services."""
    pass


class AuthenticationError(ZoteroMCPError):
    """Authentication or authorization error."""
    pass


class NotFoundError(ZoteroMCPError):
    """Resource not found error."""
    pass


class ValidationError(ZoteroMCPError):
    """Input validation error."""
    pass


class DatabaseError(ZoteroMCPError):
    """Database operation error."""
    pass


class ConfigurationError(ZoteroMCPError):
    """Configuration error."""
    pass


def handle_error(
    error: Exception,
    ctx: "Context | None" = None,
    operation: str = "operation"
) -> str:
    """
    Handle errors consistently across all tools.

    Args:
        error: The exception that occurred
        ctx: Optional MCP context for logging
        operation: Name of the operation that failed

    Returns:
        User-friendly error message with suggestions
    """
    # Log the error
    if ctx:
        ctx.error(f"Error in {operation}: {str(error)}")
    else:
        logger.error(f"Error in {operation}: {str(error)}")

    # Handle specific error types
    if isinstance(error, ZoteroMCPError):
        return f"Error: {error}"

    # Handle pyzotero errors
    error_str = str(error).lower()
    error_type = type(error).__name__

    if "connection" in error_str or "timeout" in error_str:
        return (
            f"Error: Could not connect to Zotero. "
            "Please ensure Zotero is running and 'Allow other applications' is enabled in preferences."
        )

    if "401" in error_str or "unauthorized" in error_str:
        return (
            f"Error: Authentication failed. "
            "Please check your ZOTERO_API_KEY is correct and has proper permissions."
        )

    if "403" in error_str or "forbidden" in error_str:
        return (
            f"Error: Access denied. "
            "You don't have permission to access this resource."
        )

    if "404" in error_str or "not found" in error_str:
        return (
            f"Error: Resource not found. "
            "Please check the item key or collection key is correct."
        )

    if "429" in error_str or "rate limit" in error_str:
        return (
            f"Error: Rate limit exceeded. "
            "Please wait a moment before making more requests."
        )

    if "chromadb" in error_str or "embedding" in error_str:
        return (
            f"Error: Semantic search database error. "
            "Try running 'zotero-mcp update-db --force-rebuild' to rebuild the database."
        )

    # Generic error
    return f"Error in {operation}: {error_type} - {str(error)}"


def format_api_error(status_code: int, message: str = "") -> str:
    """Format an API error with appropriate message."""
    error_messages = {
        400: "Bad request. Please check your input parameters.",
        401: "Authentication required. Please set ZOTERO_API_KEY.",
        403: "Access denied. You don't have permission to perform this action.",
        404: "Resource not found. Please check the item or collection key.",
        429: "Rate limit exceeded. Please wait before making more requests.",
        500: "Zotero server error. Please try again later.",
        503: "Zotero service unavailable. Please try again later.",
    }

    default_message = f"API error (status {status_code})"
    base_message = error_messages.get(status_code, default_message)

    if message:
        return f"Error: {base_message} Details: {message}"
    return f"Error: {base_message}"
