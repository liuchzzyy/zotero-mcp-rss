"""Pydantic models for tool input validation (Logseq-style)."""

from zotero_mcp.models.common import BaseInput
from zotero_mcp.models.database.semantic import DatabaseStatusInput, UpdateDatabaseInput
from zotero_mcp.models.search.queries import (
    AdvancedSearchInput,
    GetRecentInput,
    SearchByTagInput,
    SearchItemsInput,
    SemanticSearchInput,
)
from zotero_mcp.models.workflow.analysis import (
    BatchAnalyzeInput,
    FindCollectionInput,
    PrepareAnalysisInput,
    ResumeWorkflowInput,
)
from zotero_mcp.models.workflow.batch import BatchGetMetadataInput
from zotero_mcp.models.zotero.annotations import (
    CreateNoteInput,
    GetAnnotationsInput,
    GetNotesInput,
    SearchNotesInput,
)
from zotero_mcp.models.zotero.collections import (
    CreateCollectionInput,
    DeleteCollectionInput,
    MoveCollectionInput,
    RenameCollectionInput,
)
from zotero_mcp.models.zotero.items import (
    GetBundleInput,
    GetChildrenInput,
    GetCollectionsInput,
    GetFulltextInput,
    GetMetadataInput,
)


class EmptyInput(BaseInput):
    """Empty input for no-argument tools."""

    pass


__all__ = [
    "AdvancedSearchInput",
    "BatchAnalyzeInput",
    "BatchGetMetadataInput",
    "CreateCollectionInput",
    "CreateNoteInput",
    "DatabaseStatusInput",
    "DeleteCollectionInput",
    "EmptyInput",
    "FindCollectionInput",
    "GetAnnotationsInput",
    "GetBundleInput",
    "GetChildrenInput",
    "GetCollectionsInput",
    "GetFulltextInput",
    "GetMetadataInput",
    "GetNotesInput",
    "GetRecentInput",
    "MoveCollectionInput",
    "PrepareAnalysisInput",
    "RenameCollectionInput",
    "ResumeWorkflowInput",
    "SearchByTagInput",
    "SearchItemsInput",
    "SearchNotesInput",
    "SemanticSearchInput",
    "UpdateDatabaseInput",
]
