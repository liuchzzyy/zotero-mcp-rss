"""MCP error mapping utilities."""

from mcp.shared.exceptions import McpError
from mcp.types import INTERNAL_ERROR, INVALID_PARAMS, ErrorData

from zotero_mcp.utils.system.errors import (
    AuthenticationError,
    ConfigurationError,
    ConnectionError,
    DatabaseError,
    NotFoundError,
    ValidationError,
    ZoteroMCPError,
)


def format_error(exc: Exception) -> McpError:
    """Convert exceptions to MCP errors."""
    if isinstance(exc, (ValidationError, NotFoundError)):
        return McpError(ErrorData(code=INVALID_PARAMS, message=str(exc)))
    if isinstance(exc, (AuthenticationError, ConfigurationError, ConnectionError)):
        return McpError(ErrorData(code=INTERNAL_ERROR, message=str(exc)))
    if isinstance(exc, DatabaseError):
        return McpError(ErrorData(code=INTERNAL_ERROR, message=str(exc)))
    if isinstance(exc, ZoteroMCPError):
        return McpError(ErrorData(code=INTERNAL_ERROR, message=str(exc)))
    return McpError(
        ErrorData(code=INTERNAL_ERROR, message=f"Unexpected error: {exc!s}")
    )
