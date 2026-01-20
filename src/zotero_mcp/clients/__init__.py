"""
Clients for Zotero MCP.

Provides unified access to Zotero data through multiple backends:
- ZoteroAPIClient: Web/Local API via pyzotero
- BetterBibTeXClient: Better BibTeX JSON-RPC API
- LocalDatabaseClient: Direct SQLite access
"""

from .zotero_client import ZoteroAPIClient, get_zotero_client
from .better_bibtex import BetterBibTeXClient
from .local_db import LocalDatabaseClient, ZoteroItem

__all__ = [
    "ZoteroAPIClient",
    "get_zotero_client",
    "BetterBibTeXClient",
    "LocalDatabaseClient",
    "ZoteroItem",
]
