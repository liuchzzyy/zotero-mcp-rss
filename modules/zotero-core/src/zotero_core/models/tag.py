"""
Tag models for Zotero item labeling.

Represents tags used to categorize and filter items in a Zotero library.
"""

from pydantic import BaseModel, Field


class Tag(BaseModel):
    """A Zotero tag for categorizing items.

    Tags provide a flexible way to label and filter items across collections.
    """

    tag: str = Field(..., description="Tag name")
    count: int | None = Field(default=None, description="Number of items with this tag")
    type: int | None = Field(
        default=None, description="Tag type (0=user, 1=automatic import)"
    )


class TagCreate(BaseModel):
    """Input model for creating/adding a tag."""

    tag: str = Field(..., min_length=1, max_length=255, description="Tag name")
    type: int = Field(default=0, description="Tag type (0=user, 1=automatic)")


class TagUpdate(BaseModel):
    """Input model for updating a tag."""

    tag: str | None = Field(
        default=None, min_length=1, max_length=255, description="New tag name"
    )
