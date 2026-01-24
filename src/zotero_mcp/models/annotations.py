"""
Pydantic models for annotation and note-related tools.
"""

from typing import Literal

from pydantic import Field, field_validator

from .common import BaseInput, PaginatedInput


class GetAnnotationsInput(PaginatedInput):
    """Input for zotero_get_annotations tool."""

    item_key: str | None = Field(
        default=None,
        description="Zotero item key to filter annotations by parent item. None for all annotations.",
    )
    use_pdf_extraction: bool = Field(
        default=False,
        description="Whether to attempt direct PDF annotation extraction as fallback",
    )
    annotation_type: Literal["all", "highlight", "note", "underline", "image"] = Field(
        default="all", description="Filter by annotation type"
    )


class GetNotesInput(PaginatedInput):
    """Input for zotero_get_notes tool."""

    item_key: str | None = Field(
        default=None,
        description="Zotero item key to filter notes by parent item. None for all notes.",
    )
    include_standalone: bool = Field(
        default=True,
        description="Whether to include standalone notes (not attached to items)",
    )


class SearchNotesInput(PaginatedInput):
    """Input for zotero_search_notes tool."""

    query: str = Field(
        ...,
        min_length=1,
        max_length=500,
        description="Search query to find in notes and annotations",
    )
    include_annotations: bool = Field(
        default=True, description="Whether to also search in PDF annotations"
    )
    case_sensitive: bool = Field(
        default=False, description="Whether the search should be case-sensitive"
    )

    @field_validator("query")
    @classmethod
    def validate_query(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("Query cannot be empty or whitespace only")
        return v.strip()


class CreateNoteInput(BaseInput):
    """Input for zotero_create_note tool."""

    item_key: str = Field(
        ...,
        min_length=1,
        max_length=20,
        description="Parent item key to attach the note to",
    )
    content: str = Field(
        ...,
        min_length=1,
        max_length=100000,
        description="Note content in HTML or plain text format",
    )
    tags: list[str] | None = Field(
        default=None, description="Optional tags to add to the note"
    )

    @field_validator("content")
    @classmethod
    def validate_content(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("Note content cannot be empty")
        return v
