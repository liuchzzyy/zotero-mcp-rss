"""
Workflow models for Zotero MCP.

Provides Pydantic models for batch PDF analysis workflows.
"""

from typing import Any, Literal

from pydantic import BaseModel, Field

from zotero_mcp.models.common import BaseInput, BaseResponse

# -------------------- Input Models --------------------


class PrepareAnalysisInput(BaseInput):
    """
    Input for zotero_prepare_analysis tool (Mode A).

    Prepares PDF content and metadata for external AI analysis.
    """

    source: Literal["collection", "recent"] = Field(
        default="collection",
        description="Source of items: 'collection' or 'recent'",
    )
    collection_name: str | None = Field(
        default=None,
        description="Collection name (supports fuzzy matching)",
    )
    collection_key: str | None = Field(
        default=None,
        description="Collection key (takes precedence over collection_name)",
    )
    days: int = Field(
        default=7,
        ge=1,
        le=365,
        description="Number of days to look back (for source='recent')",
    )
    limit: int = Field(
        default=20,
        ge=1,
        le=100,
        description="Maximum number of items to process",
    )
    include_annotations: bool = Field(
        default=True,
        description="Whether to include PDF annotations",
    )
    skip_existing_notes: bool = Field(
        default=True,
        description="Skip items that already have analysis notes",
    )


class BatchAnalyzeInput(BaseInput):
    """
    Input for zotero_batch_analyze_pdfs tool (Mode B).

    Automatically analyzes PDFs using LLM and creates notes.
    """

    source: Literal["collection", "recent"] = Field(
        default="collection",
        description="Source of items: 'collection' or 'recent'",
    )
    collection_name: str | None = Field(
        default=None,
        description="Collection name (supports fuzzy matching)",
    )
    collection_key: str | None = Field(
        default=None,
        description="Collection key (takes precedence over collection_name)",
    )
    days: int = Field(
        default=7,
        ge=1,
        le=365,
        description="Number of days to look back (for source='recent')",
    )
    limit: int = Field(
        default=20,
        ge=1,
        le=100,
        description="Maximum number of items to process",
    )
    resume_workflow_id: str | None = Field(
        default=None,
        description="Workflow ID to resume (for checkpoint recovery)",
    )
    skip_existing_notes: bool = Field(
        default=True,
        description="Skip items that already have analysis notes",
    )
    include_annotations: bool = Field(
        default=True,
        description="Whether to include PDF annotations in analysis",
    )
    llm_provider: Literal["deepseek", "claude-cli", "auto"] = Field(
        default="auto",
        description="LLM provider to use for analysis",
    )
    llm_model: str | None = Field(
        default=None,
        description="Specific model to use (overrides default)",
    )
    template: str | None = Field(
        default=None,
        description="Custom analysis template/instruction (Markdown)",
    )
    dry_run: bool = Field(
        default=False,
        description="If true, only preview analysis without creating notes",
    )


class ResumeWorkflowInput(BaseInput):
    """Input for zotero_resume_workflow tool."""

    workflow_id: str = Field(
        ...,
        description="Workflow ID to resume",
    )


class FindCollectionInput(BaseInput):
    """Input for zotero_find_collection tool."""

    name: str = Field(
        ...,
        description="Collection name to search for (supports partial matching)",
    )
    exact_match: bool = Field(
        default=False,
        description="Whether to require exact name match",
    )


# -------------------- Output Models --------------------


class AnalysisItem(BaseModel):
    """Single item prepared for analysis (Mode A)."""

    item_key: str = Field(..., description="Zotero item key")
    title: str = Field(..., description="Item title")
    authors: str | None = Field(default=None, description="Authors")
    date: str | None = Field(default=None, description="Publication date")
    journal: str | None = Field(default=None, description="Journal/Publication")
    doi: str | None = Field(default=None, description="DOI")
    pdf_content: str | None = Field(default=None, description="Extracted PDF full text")
    annotations: list[dict[str, Any]] = Field(
        default_factory=list, description="PDF annotations"
    )
    metadata: dict[str, Any] = Field(
        default_factory=dict, description="Additional metadata"
    )
    template_questions: list[str] = Field(
        default_factory=list, description="Template questions for analysis"
    )


class PrepareAnalysisResponse(BaseResponse):
    """Response for zotero_prepare_analysis tool."""

    total_items: int = Field(..., description="Total items found")
    prepared_items: int = Field(..., description="Items prepared for analysis")
    skipped: int = Field(default=0, description="Items skipped (already have notes)")
    items: list[AnalysisItem] = Field(
        default_factory=list, description="Prepared analysis items"
    )
    template_structure: dict[str, Any] = Field(
        default_factory=dict, description="Analysis template structure"
    )


class ItemAnalysisResult(BaseModel):
    """Result for a single analyzed item."""

    item_key: str = Field(..., description="Zotero item key")
    title: str = Field(..., description="Item title")
    success: bool = Field(..., description="Whether analysis succeeded")
    note_key: str | None = Field(default=None, description="Created note key")
    error: str | None = Field(default=None, description="Error message if failed")
    skipped: bool = Field(default=False, description="Whether item was skipped")
    skip_reason: str | None = Field(
        default=None, description="Reason for skipping (e.g., 'already has note')"
    )
    processing_time: float | None = Field(
        default=None, description="Processing time in seconds"
    )


class BatchAnalyzeResponse(BaseResponse):
    """Response for zotero_batch_analyze_pdfs tool."""

    workflow_id: str = Field(..., description="Workflow ID (for resuming)")
    total_items: int = Field(..., description="Total items to process")
    processed: int = Field(..., description="Successfully processed items")
    skipped: int = Field(default=0, description="Skipped items")
    failed: int = Field(default=0, description="Failed items")
    results: list[ItemAnalysisResult] = Field(
        default_factory=list, description="Detailed results for each item"
    )
    status: Literal["completed", "partial", "failed"] = Field(
        default="completed", description="Overall workflow status"
    )
    can_resume: bool = Field(
        default=False, description="Whether workflow can be resumed"
    )


class WorkflowInfo(BaseModel):
    """Information about a saved workflow."""

    workflow_id: str = Field(..., description="Workflow ID")
    source_type: str = Field(..., description="Source type (collection/recent)")
    source_identifier: str = Field(..., description="Collection key or 'recent'")
    total_items: int = Field(..., description="Total items in workflow")
    processed: int = Field(..., description="Items processed so far")
    failed: int = Field(..., description="Items that failed")
    status: Literal["running", "paused", "completed", "failed"] = Field(
        ..., description="Workflow status"
    )
    created_at: str = Field(..., description="Creation timestamp (ISO format)")
    updated_at: str = Field(..., description="Last update timestamp (ISO format)")


class WorkflowListResponse(BaseResponse):
    """Response for zotero_list_workflows tool."""

    count: int = Field(..., description="Number of workflows")
    workflows: list[WorkflowInfo] = Field(
        default_factory=list, description="List of workflows"
    )


class CollectionMatch(BaseModel):
    """A matched collection."""

    key: str = Field(..., description="Collection key")
    name: str = Field(..., description="Collection name")
    item_count: int | None = Field(default=None, description="Number of items")
    parent_key: str | None = Field(default=None, description="Parent collection key")
    match_score: float = Field(
        default=1.0, description="Matching score (1.0 = exact match)"
    )


class FindCollectionResponse(BaseResponse):
    """Response for zotero_find_collection tool."""

    query: str = Field(..., description="Search query")
    count: int = Field(..., description="Number of matches found")
    matches: list[CollectionMatch] = Field(
        default_factory=list, description="Matched collections"
    )
