"""
Clients for Zotero MCP.

Provides unified access to Zotero data through multiple backends:
- ZoteroAPIClient: Web/Local API via pyzotero
- BetterBibTeXClient: Better BibTeX JSON-RPC API
- LocalDatabaseClient: Direct SQLite access
- ChromaClient: Semantic search vector database
"""

from .zotero_client import ZoteroAPIClient, get_zotero_client
from .better_bibtex import BetterBibTeXClient, get_better_bibtex_client
from .local_db import LocalDatabaseClient, ZoteroItem, get_local_database_client
from .chroma import ChromaClient, create_chroma_client

__all__ = [
    "ZoteroAPIClient",
    "get_zotero_client",
    "BetterBibTeXClient",
    "get_better_bibtex_client",
    "LocalDatabaseClient",
    "ZoteroItem",
    "get_local_database_client",
    "ChromaClient",
    "create_chroma_client",
]
