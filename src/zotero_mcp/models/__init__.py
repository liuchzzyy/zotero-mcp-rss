"""
Pydantic models for Zotero MCP tool inputs and outputs.
"""

from .annotations import (
    CreateNoteInput,
    GetAnnotationsInput,
    GetNotesInput,
    SearchNotesInput,
)
from .common import PaginationParams, ResponseFormat
from .database import (
    DatabaseStatusInput,
    UpdateDatabaseInput,
)
from .items import (
    GetBundleInput,
    GetChildrenInput,
    GetCollectionsInput,
    GetFulltextInput,
    GetMetadataInput,
)
from .search import (
    AdvancedSearchInput,
    GetRecentInput,
    SearchByTagInput,
    SearchItemsInput,
    SemanticSearchInput,
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
