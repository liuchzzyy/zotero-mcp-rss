"""
Common Pydantic models and enums used across all tools.
"""

from enum import Enum

from pydantic import BaseModel, ConfigDict, Field


class ResponseFormat(str, Enum):
    """Output format for tool responses."""

    MARKDOWN = "markdown"
    JSON = "json"


class OutputFormat(str, Enum):
    """Output format for metadata export."""

    MARKDOWN = "markdown"
    JSON = "json"


class SearchMode(str, Enum):
    """Search mode for keyword search."""

    TITLE_CREATOR_YEAR = "titleCreatorYear"
    EVERYTHING = "everything"


class PaginationParams(BaseModel):
    """Common pagination parameters."""

    model_config = ConfigDict(
        str_strip_whitespace=True,
        validate_assignment=True,
    )

    limit: int = Field(
        default=20,
        ge=1,
        le=100,
        description="Maximum number of results to return (1-100)",
    )
    offset: int = Field(
        default=0, ge=0, description="Number of results to skip for pagination"
    )


class BaseInput(BaseModel):
    """Base class for all tool input models."""

    model_config = ConfigDict(
        str_strip_whitespace=True,
        validate_assignment=True,
        extra="forbid",
    )

    response_format: ResponseFormat = Field(
        default=ResponseFormat.MARKDOWN,
        description="Output format: 'markdown' for human-readable or 'json' for machine-readable",
    )


class PaginatedInput(BaseInput):
    """Base class for paginated tool inputs."""

    limit: int = Field(
        default=20,
        ge=1,
        le=100,
        description="Maximum number of results to return (1-100)",
    )
    offset: int = Field(
        default=0, ge=0, description="Number of results to skip for pagination"
    )


class ZoteroItemResult(BaseModel):
    """Structured result for a Zotero item."""

    model_config = ConfigDict(extra="allow")

    key: str = Field(..., description="Zotero item key")
    title: str = Field(default="Untitled", description="Item title")
    item_type: str = Field(default="unknown", description="Item type")
    date: str | None = Field(default=None, description="Publication date")
    authors: str | None = Field(default=None, description="Formatted author names")
    abstract: str | None = Field(default=None, description="Abstract text")
    tags: list[str] = Field(default_factory=list, description="List of tags")
    doi: str | None = Field(default=None, description="DOI if available")
    url: str | None = Field(default=None, description="URL if available")


class SearchResultItem(ZoteroItemResult):
    """Search result with optional similarity score."""

    similarity_score: float | None = Field(
        default=None, description="Similarity score for semantic search (0-1)"
    )
    matched_text: str | None = Field(
        default=None, description="Text snippet that matched the query"
    )
    # Extended fields for note search
    creators: list[str] = Field(
        default_factory=list, description="List of creator names"
    )
    year: int | None = Field(default=None, description="Publication year")
    date_added: str | None = Field(default=None, description="Date item was added")
    snippet: str | None = Field(
        default=None, description="Context snippet for search result"
    )
    raw_data: dict | None = Field(default=None, description="Raw match data")


# ===== Response Models =====


class BaseResponse(BaseModel):
    """Base class for all tool responses."""

    model_config = ConfigDict(extra="allow")

    success: bool = Field(default=True, description="Whether the operation succeeded")
    error: str | None = Field(
        default=None, description="Error message if operation failed"
    )


class PaginatedResponse(BaseResponse):
    """Standard paginated response structure."""

    total: int = Field(..., description="Total number of matching items")
    count: int = Field(..., description="Number of items in this response")
    offset: int = Field(default=0, description="Current offset")
    limit: int = Field(..., description="Requested limit")
    has_more: bool = Field(..., description="Whether more results are available")
    next_offset: int | None = Field(default=None, description="Offset for next page")


# ===== Search Result Models =====


class SearchResponse(PaginatedResponse):
    """Response for search operations."""

    query: str = Field(..., description="Search query that was executed")
    items: list[SearchResultItem] = Field(
        default_factory=list, description="Search results"
    )
    # Alias for 'items' used in note search
    results: list[SearchResultItem] = Field(
        default_factory=list, description="Search results (alias for items)"
    )
    total_count: int | None = Field(
        default=None, description="Total matching items before pagination"
    )


# ===== Item Detail Models =====


class ItemDetailResponse(BaseResponse):
    """Response for single item details."""

    key: str = Field(..., description="Zotero item key")
    title: str = Field(default="Untitled", description="Item title")
    item_type: str = Field(default="unknown", description="Item type")
    authors: str | None = Field(default=None, description="Formatted author names")
    date: str | None = Field(default=None, description="Publication date")
    publication: str | None = Field(default=None, description="Publication title")
    doi: str | None = Field(default=None, description="DOI")
    url: str | None = Field(default=None, description="URL")
    abstract: str | None = Field(default=None, description="Abstract text")
    tags: list[str] = Field(default_factory=list, description="List of tags")
    raw_data: dict | None = Field(default=None, description="Raw Zotero item data")


class FulltextResponse(BaseResponse):
    """Response for fulltext retrieval."""

    item_key: str = Field(..., description="Item key")
    fulltext: str | None = Field(default=None, description="Full text content")
    length: int = Field(default=0, description="Character count")
    truncated: bool = Field(default=False, description="Whether content was truncated")


# ===== Annotation Models =====


class AnnotationItem(BaseModel):
    """Single annotation."""

    type: str = Field(..., description="Annotation type: highlight, note, underline")
    text: str | None = Field(default=None, description="Highlighted text")
    comment: str | None = Field(default=None, description="User comment")
    page: str | None = Field(default=None, description="Page number or label")
    color: str | None = Field(default=None, description="Highlight color")


class AnnotationsResponse(BaseResponse):
    """Response for annotations."""

    item_key: str = Field(..., description="Parent item key")
    count: int = Field(..., description="Number of annotations")
    total_count: int | None = Field(
        default=None, description="Total number of annotations before pagination"
    )
    annotations: list[AnnotationItem] = Field(
        default_factory=list, description="List of annotations"
    )
    has_more: bool = Field(
        default=False, description="Whether more results are available"
    )
    next_offset: int | None = Field(default=None, description="Offset for next page")


class NotesResponse(BaseResponse):
    """Response for notes."""

    item_key: str = Field(..., description="Parent item key")
    count: int = Field(..., description="Number of notes")
    total_count: int | None = Field(
        default=None, description="Total number of notes before pagination"
    )
    notes: list[dict] = Field(default_factory=list, description="List of notes")
    has_more: bool = Field(
        default=False, description="Whether more results are available"
    )
    next_offset: int | None = Field(default=None, description="Offset for next page")


# ===== File Link Models =====


class FileLink(BaseModel):
    """Structured link to a file or attachment."""

    url: str | None = Field(default=None, description="URL to the file")
    title: str | None = Field(default=None, description="Human-readable title")
    filename: str | None = Field(default=None, description="Filename if available")
    content_type: str | None = Field(default=None, description="MIME content type")
    source: str = Field(..., description="Source of this link")
    item_key: str | None = Field(
        default=None, description="Parent Zotero item key (if applicable)"
    )
    attachment_key: str | None = Field(
        default=None, description="Attachment key (if applicable)"
    )
    link_mode: str | None = Field(
        default=None, description="Zotero link mode (if applicable)"
    )
    path: str | None = Field(
        default=None, description="Local file path (if applicable)"
    )


class FindPdfSiResponse(BaseResponse):
    """Response for PDF & supporting information lookup."""

    item_key: str | None = Field(default=None, description="Zotero item key")
    doi: str | None = Field(default=None, description="Resolved DOI")
    title: str | None = Field(default=None, description="Resolved title")
    url: str | None = Field(default=None, description="Landing or source URL")
    pdfs: list[FileLink] = Field(default_factory=list, description="PDF links")
    supplementary: list[FileLink] = Field(
        default_factory=list, description="Supporting information links"
    )
    downloaded: list[FileLink] = Field(
        default_factory=list, description="Downloaded files"
    )
    attached: list[FileLink] = Field(
        default_factory=list, description="Files attached to Zotero"
    )
    download_errors: list[str] = Field(
        default_factory=list, description="Download errors"
    )
    attach_errors: list[str] = Field(
        default_factory=list, description="Attachment errors"
    )
    sources: list[str] = Field(
        default_factory=list, description="Sources used for lookup"
    )
    warnings: list[str] = Field(
        default_factory=list, description="Non-fatal warnings"
    )


class FindPdfSiBatchItem(BaseModel):
    """Per-item result for batch PDF/SI lookup."""

    item_key: str = Field(..., description="Zotero item key")
    title: str | None = Field(default=None, description="Item title")
    pdf_count: int = Field(default=0, description="Number of PDF links found")
    supplementary_count: int = Field(
        default=0, description="Number of supporting links found"
    )
    attached_count: int = Field(
        default=0, description="Number of files attached"
    )
    skipped: bool = Field(default=False, description="Whether item was skipped")
    success: bool = Field(default=True, description="Whether processing succeeded")
    error: str | None = Field(default=None, description="Error message")


class FindPdfSiBatchResponse(BaseResponse):
    """Response for batch PDF/SI lookup."""

    collection_key: str | None = Field(
        default=None, description="Collection key scanned"
    )
    collection_name: str | None = Field(
        default=None, description="Collection name scanned"
    )
    scan_limit: int = Field(default=0, description="Scan batch size")
    treated_limit: int = Field(default=0, description="Max items processed")
    scanned: int = Field(default=0, description="Total items scanned")
    processed: int = Field(default=0, description="Items processed (no PDF)")
    skipped: int = Field(default=0, description="Items skipped (had PDF)")
    succeeded: int = Field(default=0, description="Items succeeded")
    failed: int = Field(default=0, description="Items failed")
    results: list[FindPdfSiBatchItem] = Field(
        default_factory=list, description="Per-item results"
    )

# ===== Collection Models =====


class CollectionItem(BaseModel):
    """Single collection."""

    key: str = Field(..., description="Collection key")
    name: str = Field(..., description="Collection name")
    item_count: int | None = Field(
        default=None, description="Number of items in collection"
    )
    parent_key: str | None = Field(default=None, description="Parent collection key")


class CollectionsResponse(BaseResponse):
    """Response for collections list."""

    count: int = Field(..., description="Number of collections")
    collections: list[CollectionItem] = Field(
        default_factory=list, description="List of collections"
    )


# ===== Bundle Models =====


class BundleResponse(BaseResponse):
    """Comprehensive item bundle."""

    metadata: ItemDetailResponse = Field(..., description="Item metadata")
    attachments: list[dict] = Field(default_factory=list, description="Attachments")
    notes: list[dict] = Field(default_factory=list, description="Notes")
    annotations: list[AnnotationItem] = Field(
        default_factory=list, description="PDF annotations"
    )
    fulltext: str | None = Field(default=None, description="Full text content")


# ===== Database Models =====


class DatabaseStatusResponse(BaseResponse):
    """Semantic search database status."""

    exists: bool = Field(..., description="Whether database exists")
    item_count: int = Field(default=0, description="Number of indexed items")
    last_updated: str | None = Field(default=None, description="Last update timestamp")
    embedding_model: str = Field(default="default", description="Embedding model used")
    model_name: str | None = Field(default=None, description="Specific model name")
    fulltext_enabled: bool = Field(
        default=False, description="Whether full-text indexing is enabled"
    )
    auto_update: bool = Field(
        default=False, description="Whether auto-update is enabled"
    )
    update_frequency: str = Field(
        default="manual", description="Update frequency setting"
    )
    message: str | None = Field(default=None, description="Status message")


class DatabaseUpdateResponse(BaseResponse):
    """Response for database update operation."""

    items_processed: int = Field(default=0, description="Number of items processed")
    items_added: int = Field(default=0, description="Number of items added")
    items_updated: int = Field(default=0, description="Number of items updated")
    duration_seconds: float = Field(
        default=0, description="Operation duration in seconds"
    )
    force_rebuild: bool = Field(
        default=False, description="Whether database was rebuilt"
    )
    fulltext_included: bool = Field(
        default=False, description="Whether full-text was indexed"
    )
    message: str | None = Field(default=None, description="Status message")


# ===== Note Creation Models =====


class NoteCreationResponse(BaseResponse):
    """Response for note creation."""

    note_key: str | None = Field(default=None, description="Created note key")
    parent_key: str = Field(..., description="Parent item key")
    message: str = Field(..., description="Status message")
