"""
Base Pydantic models for zotero-core.

Provides common base classes and enums used across the library.
"""

from enum import Enum

from pydantic import BaseModel, ConfigDict, Field


class ResponseFormat(str, Enum):
    """Output format for API responses."""

    MARKDOWN = "markdown"
    JSON = "json"


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
    """Base class for all input models.

    Provides common configuration and validation behavior.
    """

    model_config = ConfigDict(
        str_strip_whitespace=True,
        validate_assignment=True,
        extra="forbid",
    )


class BaseResponse(BaseModel):
    """Base class for all response models.

    Provides common response structure with success/error tracking.
    """

    model_config = ConfigDict(extra="allow")

    success: bool = Field(default=True, description="Whether the operation succeeded")
    error: str | None = Field(
        default=None, description="Error message if operation failed"
    )


class PaginatedResponse(BaseResponse):
    """Standard paginated response structure.

    Provides pagination metadata along with results.
    """

    total: int = Field(..., description="Total number of matching items")
    count: int = Field(..., description="Number of items in this response")
    offset: int = Field(default=0, description="Current offset")
    limit: int = Field(..., description="Requested limit")
    has_more: bool = Field(..., description="Whether more results are available")
    next_offset: int | None = Field(default=None, description="Offset for next page")


class PaginatedInput(BaseInput):
    """Base class for paginated input models.

    Combines input validation with pagination parameters.
    """

    limit: int = Field(
        default=20,
        ge=1,
        le=100,
        description="Maximum number of results to return (1-100)",
    )
    offset: int = Field(
        default=0, ge=0, description="Number of results to skip for pagination"
    )
