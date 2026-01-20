"""
Common Pydantic models and enums used across all tools.
"""

from enum import Enum
from typing import Literal

from pydantic import BaseModel, Field, ConfigDict


class ResponseFormat(str, Enum):
    """Output format for tool responses."""
    MARKDOWN = "markdown"
    JSON = "json"


class OutputFormat(str, Enum):
    """Output format for metadata export."""
    MARKDOWN = "markdown"
    BIBTEX = "bibtex"
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
        description="Maximum number of results to return (1-100)"
    )
    offset: int = Field(
        default=0,
        ge=0,
        description="Number of results to skip for pagination"
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
        description="Output format: 'markdown' for human-readable or 'json' for machine-readable"
    )


class PaginatedInput(BaseInput):
    """Base class for paginated tool inputs."""
    
    limit: int = Field(
        default=20,
        ge=1,
        le=100,
        description="Maximum number of results to return (1-100)"
    )
    offset: int = Field(
        default=0,
        ge=0,
        description="Number of results to skip for pagination"
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
        default=None,
        description="Similarity score for semantic search (0-1)"
    )
    matched_text: str | None = Field(
        default=None,
        description="Text snippet that matched the query"
    )


class PaginatedResponse(BaseModel):
    """Standard paginated response structure."""
    total: int = Field(..., description="Total number of matching items")
    count: int = Field(..., description="Number of items in this response")
    offset: int = Field(..., description="Current offset")
    has_more: bool = Field(..., description="Whether more results are available")
    next_offset: int | None = Field(default=None, description="Offset for next page")
    items: list[ZoteroItemResult] = Field(default_factory=list, description="Result items")
