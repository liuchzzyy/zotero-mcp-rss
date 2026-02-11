"""
Unified error handling for Zotero MCP.
"""


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
