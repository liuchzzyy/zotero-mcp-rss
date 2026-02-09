"""
Pydantic models for item-related tools.
"""

from typing import Literal

from pydantic import Field, model_validator

from zotero_mcp.models.common import BaseInput, OutputFormat, PaginatedInput


class GetMetadataInput(BaseInput):
    """Input for zotero_get_metadata tool."""

    item_key: str = Field(
        ...,
        min_length=1,
        max_length=20,
        description="Zotero item key/ID (8-character alphanumeric string)",
    )
    include_abstract: bool = Field(
        default=True, description="Whether to include the abstract in the output"
    )
    output_format: OutputFormat = Field(
        default=OutputFormat.MARKDOWN,
        description="Output format: 'markdown' or 'json'",
    )


class GetFulltextInput(BaseInput):
    """Input for zotero_get_fulltext tool."""

    item_key: str = Field(
        ..., min_length=1, max_length=20, description="Zotero item key/ID"
    )
    include_metadata: bool = Field(
        default=True,
        description="Whether to include item metadata before the full text",
    )
    max_length: int | None = Field(
        default=None,
        ge=100,
        le=100000,
        description="Maximum characters to return. None for unlimited.",
    )


class GetChildrenInput(BaseInput):
    """Input for zotero_get_children tool."""

    item_key: str = Field(
        ..., min_length=1, max_length=20, description="Zotero item key/ID"
    )
    child_type: Literal["all", "attachment", "note"] = Field(
        default="all",
        description="Filter children by type: 'all', 'attachment', or 'note'",
    )


class GetCollectionsInput(PaginatedInput):
    """Input for zotero_get_collections tool."""

    collection_key: str | None = Field(
        default=None,
        description="If provided, get items in this collection. If None, list collections.",
    )
    parent_key: str | None = Field(
        default=None,
        description="Parent collection key to list sub-collections. None for top-level.",
    )
    include_item_count: bool = Field(
        default=True, description="Whether to include item count for each collection"
    )


class GetCollectionItemsInput(PaginatedInput):
    """Input for getting items in a collection."""

    collection_key: str = Field(
        ..., min_length=1, max_length=20, description="Collection key/ID"
    )
    item_type: str = Field(
        default="-attachment",
        description="Item type filter. Use '-' prefix to exclude.",
    )
    recursive: bool = Field(
        default=False, description="Whether to include items from sub-collections"
    )


class GetBundleInput(BaseInput):
    """Input for zotero_get_bundle tool - fetches metadata, fulltext, and children at once."""

    item_key: str = Field(
        ..., min_length=1, max_length=20, description="Zotero item key/ID"
    )
    include_fulltext: bool = Field(
        default=True, description="Whether to include full text content"
    )
    include_children: bool = Field(
        default=True, description="Whether to include attachments and notes"
    )
    include_notes: bool = Field(default=True, description="Whether to include notes")
    include_annotations: bool = Field(
        default=False, description="Whether to include annotations from PDF attachments"
    )
    fulltext_max_length: int | None = Field(
        default=10000,
        ge=100,
        le=100000,
        description="Maximum characters for full text. None for unlimited.",
    )


class FindPdfSiInput(BaseInput):
    """Input for zotero_find_pdf_si tool."""

    item_key: str | None = Field(
        default=None, description="Zotero item key (optional)"
    )
    doi: str | None = Field(default=None, description="DOI (optional)")
    title: str | None = Field(default=None, description="Title (optional)")
    url: str | None = Field(default=None, description="Landing URL (optional)")
    include_supplementary: bool = Field(
        default=True, description="Whether to include supporting information"
    )
    include_scihub: bool = Field(
        default=True, description="Whether to include Sci-Hub link when DOI exists"
    )
    scihub_base_url: str | None = Field(
        default=None,
        description="Optional Sci-Hub base URL (overrides env SCIHUB_BASE_URL)",
    )
    max_supplementary: int = Field(
        default=10, ge=0, le=50, description="Max supplementary links to return"
    )
    download_pdfs: bool = Field(
        default=True, description="Download discovered PDFs"
    )
    download_supplementary: bool = Field(
        default=True, description="Download supporting information files"
    )
    attach_to_zotero: bool = Field(
        default=True, description="Attach downloaded files to Zotero item"
    )
    max_pdf_downloads: int = Field(
        default=1, ge=0, le=5, description="Maximum PDFs to download"
    )
    max_supplementary_downloads: int = Field(
        default=3, ge=0, le=20, description="Maximum supplementary files to download"
    )
    dry_run: bool = Field(
        default=False, description="Preview without downloading or uploading"
    )

    @model_validator(mode="after")
    def _require_identifier(self) -> "FindPdfSiInput":
        if not (self.item_key or self.doi or self.title or self.url):
            raise ValueError(
                "Provide at least one of item_key, doi, title, or url."
            )
        return self


class FindPdfSiBatchInput(BaseInput):
    """Input for zotero_find_pdf_si_batch tool."""

    collection_name: str = Field(
        default="00_INBOXS",
        description="Collection name to scan for missing PDFs",
    )
    scan_limit: int = Field(
        default=50, ge=1, le=200, description="Batch size for scanning items"
    )
    treated_limit: int = Field(
        default=50,
        ge=1,
        le=1000,
        description="Maximum items to process (excluding skipped items)",
    )
    process_items_with_pdf: bool = Field(
        default=False,
        description="Also scan items that already have PDF (for SI only)",
    )
    include_supplementary: bool = Field(
        default=True, description="Include supporting information links"
    )
    include_scihub: bool = Field(
        default=True, description="Include Sci-Hub links when DOI exists"
    )
    scihub_base_url: str | None = Field(
        default=None,
        description="Optional Sci-Hub base URL (overrides env)",
    )
    max_supplementary: int = Field(
        default=10, ge=0, le=50, description="Max supplementary links to return"
    )
    download_pdfs: bool = Field(
        default=True, description="Download discovered PDFs"
    )
    download_supplementary: bool = Field(
        default=True, description="Download supporting information files"
    )
    attach_to_zotero: bool = Field(
        default=True, description="Attach downloaded files to Zotero item"
    )
    max_pdf_downloads: int = Field(
        default=1, ge=0, le=5, description="Maximum PDFs to download"
    )
    max_supplementary_downloads: int = Field(
        default=3, ge=0, le=20, description="Maximum supplementary files to download"
    )
    dry_run: bool = Field(
        default=False, description="Preview without downloading or uploading"
    )
