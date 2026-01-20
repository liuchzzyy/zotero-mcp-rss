"""
Pydantic models for item-related tools.
"""

from typing import Literal

from pydantic import Field

from .common import BaseInput, PaginatedInput, OutputFormat


class GetMetadataInput(BaseInput):
    """Input for zotero_get_metadata tool."""

    item_key: str = Field(
        ...,
        min_length=1,
        max_length=20,
        description="Zotero item key/ID (8-character alphanumeric string)"
    )
    include_abstract: bool = Field(
        default=True,
        description="Whether to include the abstract in the output"
    )
    format: OutputFormat = Field(
        default=OutputFormat.MARKDOWN,
        description="Output format: 'markdown', 'bibtex', or 'json'"
    )


class GetFulltextInput(BaseInput):
    """Input for zotero_get_fulltext tool."""

    item_key: str = Field(
        ...,
        min_length=1,
        max_length=20,
        description="Zotero item key/ID"
    )
    include_metadata: bool = Field(
        default=True,
        description="Whether to include item metadata before the full text"
    )
    max_length: int | None = Field(
        default=None,
        ge=100,
        le=100000,
        description="Maximum characters to return. None for unlimited."
    )


class GetChildrenInput(BaseInput):
    """Input for zotero_get_children tool."""

    item_key: str = Field(
        ...,
        min_length=1,
        max_length=20,
        description="Zotero item key/ID"
    )
    child_type: Literal["all", "attachment", "note"] = Field(
        default="all",
        description="Filter children by type: 'all', 'attachment', or 'note'"
    )


class GetCollectionsInput(PaginatedInput):
    """Input for zotero_get_collections tool."""

    parent_key: str | None = Field(
        default=None,
        description="Parent collection key to list sub-collections. None for top-level."
    )
    include_item_count: bool = Field(
        default=True,
        description="Whether to include item count for each collection"
    )


class GetCollectionItemsInput(PaginatedInput):
    """Input for getting items in a collection."""

    collection_key: str = Field(
        ...,
        min_length=1,
        max_length=20,
        description="Collection key/ID"
    )
    item_type: str = Field(
        default="-attachment",
        description="Item type filter. Use '-' prefix to exclude."
    )
    recursive: bool = Field(
        default=False,
        description="Whether to include items from sub-collections"
    )


class GetBundleInput(BaseInput):
    """Input for zotero_get_bundle tool - fetches metadata, fulltext, and children at once."""

    item_key: str = Field(
        ...,
        min_length=1,
        max_length=20,
        description="Zotero item key/ID"
    )
    include_fulltext: bool = Field(
        default=True,
        description="Whether to include full text content"
    )
    include_children: bool = Field(
        default=True,
        description="Whether to include attachments and notes"
    )
    include_annotations: bool = Field(
        default=False,
        description="Whether to include annotations from PDF attachments"
    )
    fulltext_max_length: int | None = Field(
        default=10000,
        ge=100,
        le=100000,
        description="Maximum characters for full text. None for unlimited."
    )
