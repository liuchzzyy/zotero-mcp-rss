"""
Services for Zotero MCP.

Provides high-level business logic and data access abstraction.
"""

from .data_access import DataAccessService, get_data_service

__all__ = [
    "DataAccessService",
    "get_data_service",
]
