"""
Pydantic models for search-related tools.
"""

from typing import Literal

from pydantic import Field, field_validator

from .common import BaseInput, PaginatedInput, SearchMode


class SearchItemsInput(PaginatedInput):
    """Input for zotero_search tool."""

    query: str = Field(
        ...,
        min_length=1,
        max_length=500,
        description="Search query string (e.g., 'machine learning', 'Smith 2023')",
    )
    qmode: SearchMode = Field(
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
    """Input for zotero_search_by_tag tool."""

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
    """Input for zotero_advanced_search tool."""

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
    """Input for zotero_semantic_search tool."""

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


class GetRecentInput(PaginatedInput):
    """Input for zotero_get_recent tool."""

    days: int | None = Field(
        default=None,
        ge=1,
        le=365,
        description="Only show items added within the last N days (1-365)",
    )
    item_type: str = Field(
        default="-attachment",
        description="Item type filter. Use '-' prefix to exclude.",
    )
