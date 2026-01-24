"""
Pydantic models for database-related tools.
"""

from pydantic import Field

from .common import BaseInput


class UpdateDatabaseInput(BaseInput):
    """Input for zotero_update_database tool."""

    force_rebuild: bool = Field(
        default=False, description="Whether to rebuild the entire database from scratch"
    )
    limit: int | None = Field(
        default=None,
        ge=1,
        le=10000,
        description="Maximum number of items to process (useful for testing)",
    )
    extract_fulltext: bool = Field(
        default=False,
        description="Whether to extract and index full text content (slower but more comprehensive)",
    )


class DatabaseStatusInput(BaseInput):
    """Input for zotero_database_status tool."""

    # No additional parameters needed, just uses response_format from BaseInput
    pass
