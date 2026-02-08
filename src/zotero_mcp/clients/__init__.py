"""External service clients organized by domain."""

from .database import ChromaClient, create_chroma_client
from .llm import CLILLMClient, get_llm_client
from .metadata import CrossrefClient, OpenAlexClient
from .zotero import (
    LocalDatabaseClient,
    ZoteroAPIClient,
    get_local_database_client,
    get_zotero_client,
)

__all__ = [
    # Zotero
    "ZoteroAPIClient",
    "get_zotero_client",
    "LocalDatabaseClient",
    "get_local_database_client",
    # Database
    "ChromaClient",
    "create_chroma_client",
    # Metadata
    "CrossrefClient",
    "OpenAlexClient",
    # LLM
    "get_llm_client",
    "CLILLMClient",
]
