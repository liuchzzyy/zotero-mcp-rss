"""
Pydantic models for Zotero MCP tool inputs and outputs.
"""

from .common import ResponseFormat, PaginationParams
from .search import (
    SearchItemsInput,
    SearchByTagInput,
    AdvancedSearchInput,
    SemanticSearchInput,
    GetRecentInput,
)
from .items import (
    GetMetadataInput,
    GetFulltextInput,
    GetChildrenInput,
    GetCollectionsInput,
    GetBundleInput,
)
from .annotations import (
    GetAnnotationsInput,
    GetNotesInput,
    SearchNotesInput,
    CreateNoteInput,
)
from .database import (
    UpdateDatabaseInput,
    DatabaseStatusInput,
)

__all__ = [
    # Common
    "ResponseFormat",
    "PaginationParams",
    # Search
    "SearchItemsInput",
    "SearchByTagInput",
    "AdvancedSearchInput",
    "SemanticSearchInput",
    "GetRecentInput",
    # Items
    "GetMetadataInput",
    "GetFulltextInput",
    "GetChildrenInput",
    "GetCollectionsInput",
    "GetBundleInput",
    # Annotations
    "GetAnnotationsInput",
    "GetNotesInput",
    "SearchNotesInput",
    "CreateNoteInput",
    # Database
    "UpdateDatabaseInput",
    "DatabaseStatusInput",
]
