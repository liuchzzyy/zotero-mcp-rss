"""
Item models for Zotero resources.

Represents Zotero items (papers, books, notes, etc.) with full metadata support.
"""

from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class Creator(BaseModel):
    """A creator/author of a Zotero item."""

    model_config = ConfigDict(extra="allow")

    creator_type: str = Field(
        default="author", description="Role of the creator (author, editor, etc.)"
    )
    first_name: str | None = Field(default=None, description="First name")
    last_name: str | None = Field(default=None, description="Last name")
    name: str | None = Field(default=None, description="Full name (if no first/last)")


class Item(BaseModel):
    """A Zotero item (paper, book, note, etc.).

    Represents the core Zotero item structure with all metadata fields.
    Uses flexible data field to accommodate different item types.
    """

    model_config = ConfigDict(extra="allow")

    # Core identifiers
    key: str = Field(..., description="Unique item key (8-character alphanumeric)")
    type: str = Field(..., description="Item type (journalArticle, book, etc.)")
    version: int | None = Field(
        default=None, description="Item version for optimistic locking"
    )

    # Core metadata
    title: str = Field(default="Untitled", description="Item title")
    creators: list[Creator] = Field(
        default_factory=list, description="List of creators"
    )
    abstract: str | None = Field(default=None, description="Abstract or summary")
    date: str | None = Field(default=None, description="Publication date")
    year: int | None = Field(default=None, description="Publication year (integer)")

    # Identifiers
    doi: str | None = Field(default=None, description="Digital Object Identifier")
    url: str | None = Field(default=None, description="URL to the resource")
    isbn: str | None = Field(default=None, description="ISBN")
    issn: str | None = Field(default=None, description="ISSN")

    # Publication info
    publication_title: str | None = Field(
        default=None, alias="publicationTitle", description="Journal or publisher name"
    )
    volume: str | None = Field(default=None, description="Volume number")
    issue: str | None = Field(default=None, description="Issue number")
    pages: str | None = Field(default=None, description="Page range")
    publisher: str | None = Field(default=None, description="Publisher name")

    # Organization
    collections: list[str] = Field(
        default_factory=list, description="Collection keys this item belongs to"
    )
    tags: list[str] = Field(default_factory=list, description="Tag names")

    # Metadata
    date_added: str | None = Field(
        default=None, alias="dateAdded", description="Date item was added to library"
    )
    date_modified: str | None = Field(
        default=None, alias="dateModified", description="Date item was last modified"
    )

    # Access info
    access_date: str | None = Field(
        default=None, alias="accessDate", description="Date resource was accessed"
    )
    library_catalog: str | None = Field(
        default=None, alias="libraryCatalog", description="Source library/catalog"
    )

    # Notes/extra
    notes: list[str] = Field(
        default_factory=list, description="Note keys (child notes)"
    )
    extra: str | None = Field(default=None, description="Extra field for custom data")

    # Flexible data field for type-specific properties
    data: dict[str, Any] = Field(
        default_factory=dict, description="Additional type-specific fields"
    )

    # Raw API response (for debugging/advanced use)
    raw_data: dict[str, Any] | None = Field(
        default=None, exclude=True, description="Raw API response data"
    )

    def get_creator_names(self) -> list[str]:
        """Get formatted list of creator names."""
        names = []
        for creator in self.creators:
            if creator.name:
                names.append(creator.name)
            elif creator.last_name:
                if creator.first_name:
                    names.append(f"{creator.last_name}, {creator.first_name}")
                else:
                    names.append(creator.last_name)
        return names

    def get_authors(self) -> list[str]:
        """Get list of author-type creator names."""
        authors = []
        for creator in self.creators:
            if creator.creator_type == "author":
                if creator.name:
                    authors.append(creator.name)
                elif creator.last_name:
                    if creator.first_name:
                        authors.append(f"{creator.last_name}, {creator.first_name}")
                    else:
                        authors.append(creator.last_name)
        return authors

    def has_tag(self, tag: str) -> bool:
        """Check if item has a specific tag (case-insensitive)."""
        return any(t.lower() == tag.lower() for t in self.tags)

    def has_any_tag(self, tags: list[str]) -> bool:
        """Check if item has any of the specified tags (case-insensitive)."""
        return any(self.has_tag(tag) for tag in tags)

    def has_all_tags(self, tags: list[str]) -> bool:
        """Check if item has all of the specified tags (case-insensitive)."""
        return all(self.has_tag(tag) for tag in tags)


class ItemCreate(BaseModel):
    """Input model for creating a new item."""

    model_config = ConfigDict(extra="allow")

    type: str = Field(..., description="Item type (journalArticle, book, etc.)")
    title: str = Field(..., description="Item title")
    creators: list[dict] = Field(
        default_factory=list, description="List of creator dicts"
    )
    abstract: str | None = Field(default=None, description="Abstract or summary")
    date: str | None = Field(default=None, description="Publication date")
    doi: str | None = Field(default=None, description="Digital Object Identifier")
    url: str | None = Field(default=None, description="URL to the resource")
    tags: list[str] = Field(default_factory=list, description="Tag names")
    collections: list[str] = Field(
        default_factory=list, description="Collection keys to add item to"
    )
    data: dict[str, Any] = Field(
        default_factory=dict, description="Additional type-specific fields"
    )


class ItemUpdate(BaseModel):
    """Input model for updating an existing item."""

    model_config = ConfigDict(extra="allow", populate_by_name=True)

    title: str | None = Field(default=None, description="Item title")
    creators: list[dict] | None = Field(
        default=None, description="List of creator dicts"
    )
    abstract: str | None = Field(default=None, description="Abstract or summary")
    date: str | None = Field(default=None, description="Publication date")
    doi: str | None = Field(default=None, description="Digital Object Identifier")
    url: str | None = Field(default=None, description="URL to the resource")
    tags: list[str] | None = Field(default=None, description="Tag names")
    collections: list[str] | None = Field(
        default=None, description="Collection keys to add item to"
    )
    data: dict[str, Any] | None = Field(
        default=None, description="Additional type-specific fields"
    )
    version: int | None = Field(
        default=None, description="Item version for optimistic locking"
    )
