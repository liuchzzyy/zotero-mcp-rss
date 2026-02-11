"""
Pydantic models for collection management tools.
"""

from pydantic import Field

from zotero_mcp.models.common import BaseInput


class CreateCollectionInput(BaseInput):
    """Input for creating a new collection."""

    name: str = Field(
        ..., min_length=1, max_length=100, description="Name of the new collection"
    )
    parent_key: str | None = Field(
        default=None,
        description="Parent collection key. If None, creates a root collection.",
    )


class DeleteCollectionInput(BaseInput):
    """Input for deleting a collection."""

    collection_key: str = Field(..., description="Key of the collection to delete")


class MoveCollectionInput(BaseInput):
    """Input for moving a collection."""

    collection_key: str = Field(..., description="Key of the collection to move")
    parent_key: str | None = Field(
        default=None,
        description="New parent collection key. Use specific string 'root' or empty string to move to root.",
    )


class RenameCollectionInput(BaseInput):
    """Input for renaming a collection."""

    collection_key: str = Field(..., description="Key of the collection to rename")
    new_name: str = Field(..., min_length=1, max_length=100, description="New name")
