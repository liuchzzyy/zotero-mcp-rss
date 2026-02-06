"""
Collection models for Zotero library organization.

Represents Zotero collections (folders) for organizing items hierarchically.
"""

from pydantic import BaseModel, ConfigDict, Field


class Collection(BaseModel):
    """A Zotero collection (folder) for organizing items.

    Collections can be nested hierarchically and provide a way to group
    related items together.
    """

    model_config = ConfigDict(extra="allow", populate_by_name=True)

    # Core identifiers
    key: str = Field(..., description="Unique collection key")
    name: str = Field(..., description="Collection name")
    version: int | None = Field(
        default=None, description="Collection version for optimistic locking"
    )

    # Hierarchy
    parent_key: str | None = Field(
        default=None,
        alias="parentCollection",
        description="Parent collection key (None for root)",
    )

    # Metadata
    item_count: int | None = Field(
        default=None, description="Number of items in this collection"
    )

    # Raw API response
    raw_data: dict | None = Field(
        default=None, exclude=True, description="Raw API response data"
    )


class CollectionCreate(BaseModel):
    """Input model for creating a new collection."""

    name: str = Field(..., min_length=1, max_length=255, description="Collection name")
    parent_key: str | None = Field(
        default=None, description="Parent collection key (None for root collection)"
    )


class CollectionUpdate(BaseModel):
    """Input model for updating an existing collection."""

    name: str | None = Field(
        default=None, min_length=1, max_length=255, description="New collection name"
    )
    parent_key: str | None = Field(
        default=None, description="New parent collection key (None for root)"
    )
    version: int | None = Field(
        default=None, description="Collection version for optimistic locking"
    )
