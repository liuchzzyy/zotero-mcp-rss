"""
Search models for Zotero item queries.

Provides models for keyword, tag, advanced, and semantic search operations.
"""

from enum import Enum
from typing import Literal

from pydantic import BaseModel, Field, field_validator

from zotero_core.models.base import BaseInput, PaginatedInput


class SearchMode(str, Enum):
    """Search mode for keyword search."""

    TITLE_CREATOR_YEAR = "titleCreatorYear"
    EVERYTHING = "everything"


class SearchItemsInput(PaginatedInput):
    """Input for keyword search across Zotero items."""

    query: str = Field(
        ...,
        min_length=1,
        max_length=500,
        description="Search query string (e.g., 'machine learning', 'Smith 2023')",
    )
    mode: SearchMode = Field(
        default=SearchMode.TITLE_CREATOR_YEAR,
        description="Search mode: 'titleCreatorYear' searches title/author/year, 'everything' searches all fields",
    )
    item_type: str = Field(
        default="-attachment",
        description="Item type filter. Use '-' prefix to exclude (e.g., '-attachment', '-note')",
    )
    tags: list[str] | None = Field(
        default=None, description="Filter by tags. Items must have all specified tags."
    )

    @field_validator("query")
    @classmethod
    def validate_query(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("Query cannot be empty or whitespace only")
        return v.strip()


class SearchByTagInput(PaginatedInput):
    """Input for tag-based search."""

    tags: list[str] = Field(
        ...,
        min_length=1,
        description=(
            "Tag filter conditions. Conditions are ANDed. "
            "Use '||' for OR (e.g., 'research || important'), "
            "use '-' prefix to exclude (e.g., '-draft'). "
            "Example: ['research || important', '-draft'] matches items with "
            "(research OR important) AND NOT draft"
        ),
    )
    item_type: str = Field(
        default="-attachment",
        description="Item type filter. Use '-' prefix to exclude.",
    )

    @field_validator("tags")
    @classmethod
    def validate_tags(cls, v: list[str]) -> list[str]:
        if not v:
            raise ValueError("At least one tag condition is required")
        return [tag.strip() for tag in v if tag.strip()]


class AdvancedSearchCondition(BaseInput):
    """A single condition for advanced search."""

    field: str = Field(
        ...,
        description="Field to search (e.g., 'title', 'creator', 'date', 'abstractNote')",
    )
    operation: Literal[
        "contains", "is", "isNot", "beginsWith", "isLessThan", "isGreaterThan"
    ] = Field(default="contains", description="Search operation")
    value: str = Field(..., min_length=1, description="Value to search for")


class AdvancedSearchInput(PaginatedInput):
    """Input for advanced search with multiple conditions."""

    conditions: list[AdvancedSearchCondition] = Field(
        ..., min_length=1, max_length=10, description="List of search conditions"
    )
    join_mode: Literal["all", "any"] = Field(
        default="all",
        description="How to combine conditions: 'all' (AND) or 'any' (OR)",
    )

    @field_validator("conditions")
    @classmethod
    def validate_conditions(cls, v: list) -> list:
        if not v:
            raise ValueError("At least one search condition is required")
        return v


class SemanticSearchInput(PaginatedInput):
    """Input for semantic vector search."""

    query: str = Field(
        ...,
        min_length=2,
        max_length=1000,
        description=(
            "Natural language search query describing concepts or topics. "
            "Can be a phrase, question, or abstract snippet. "
            "Examples: 'papers about machine learning in healthcare', "
            "'research on climate change impacts on agriculture'"
        ),
    )
    filters: dict[str, str] | None = Field(
        default=None,
        description=(
            "Optional metadata filters as key-value pairs. "
            "Example: {'item_type': 'journalArticle'}"
        ),
    )

    @field_validator("query")
    @classmethod
    def validate_query(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("Query cannot be empty or whitespace only")
        return v.strip()


class HybridSearchInput(PaginatedInput):
    """Input for hybrid search combining keyword and semantic search."""

    query: str = Field(
        ...,
        min_length=2,
        max_length=1000,
        description="Search query for both keyword and semantic search",
    )
    keyword_weight: float = Field(
        default=0.5,
        ge=0.0,
        le=1.0,
        description="Weight for keyword search results (0-1)",
    )
    semantic_weight: float = Field(
        default=0.5,
        ge=0.0,
        le=1.0,
        description="Weight for semantic search results (0-1)",
    )
    keyword_mode: SearchMode = Field(
        default=SearchMode.TITLE_CREATOR_YEAR,
        description="Search mode for keyword component",
    )

    @field_validator("query")
    @classmethod
    def validate_query(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("Query cannot be empty or whitespace only")
        return v.strip()


class SearchResultItem(BaseModel):
    """A single search result with optional relevance scoring."""

    key: str = Field(..., description="Item key")
    title: str = Field(default="Untitled", description="Item title")
    item_type: str = Field(default="unknown", description="Item type")
    authors: str | None = Field(default=None, description="Formatted author names")
    date: str | None = Field(default=None, description="Publication date")
    year: int | None = Field(default=None, description="Publication year")
    abstract: str | None = Field(default=None, description="Abstract text")
    tags: list[str] = Field(default_factory=list, description="List of tags")
    doi: str | None = Field(default=None, description="DOI if available")
    url: str | None = Field(default=None, description="URL if available")

    # Scoring
    relevance_score: float | None = Field(
        default=None, description="Combined relevance score (0-1)"
    )
    keyword_score: float | None = Field(
        default=None, description="Keyword search score (0-1)"
    )
    semantic_score: float | None = Field(
        default=None, description="Semantic similarity score (0-1)"
    )
    rank: int | None = Field(default=None, description="Rank in results")

    # Context
    matched_text: str | None = Field(
        default=None, description="Text snippet that matched the query"
    )
    snippet: str | None = Field(
        default=None, description="Context snippet for search result"
    )

    # Metadata
    date_added: str | None = Field(default=None, description="Date item was added")
    collections: list[str] = Field(default_factory=list, description="Collection keys")

    # Raw data
    raw_data: dict | None = Field(
        default=None, exclude=True, description="Raw match data"
    )


class SearchResults(BaseModel):
    """Search results with metadata."""

    query: str = Field(..., description="Search query that was executed")
    total: int = Field(..., description="Total number of matching items")
    count: int = Field(..., description="Number of items in this response")
    items: list[SearchResultItem] = Field(
        default_factory=list, description="Search results"
    )
    has_more: bool = Field(
        default=False, description="Whether more results are available"
    )
