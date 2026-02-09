"""Pydantic models for Zotero MCP tool inputs and outputs."""

from .ai import AIAnalysisInput, AIAnalysisResult, AIModelConfig, AIProvider
from .common import DatabaseStatusResponse, ResponseFormat, SearchResultItem
from .database import DatabaseStatusInput, UpdateDatabaseInput
from .search import (
    AdvancedSearchInput,
    SearchItemsInput,
)
from .workflow import (
    AnalysisItem,
    BatchAnalyzeResponse,
    ItemAnalysisResult,
    PrepareAnalysisResponse,
)
from .zotero import (
    CreateNoteInput,
    GetAnnotationsInput,
    GetBundleInput,
    GetChildrenInput,
    GetCollectionsInput,
    GetFulltextInput,
    GetMetadataInput,
    GetNotesInput,
    SearchNotesInput,
)

__all__ = [
    # AI
    "AIProvider",
    "AIModelConfig",
    "AIAnalysisInput",
    "AIAnalysisResult",
    # Common
    "ResponseFormat",
    "SearchResultItem",
    "DatabaseStatusResponse",
    # Search
    "SearchItemsInput",
    "AdvancedSearchInput",
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
    # Workflow
    "AnalysisItem",
    "ItemAnalysisResult",
    "PrepareAnalysisResponse",
    "BatchAnalyzeResponse",
]
