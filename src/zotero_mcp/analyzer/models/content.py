"""PDF content models."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class ImageBlock(BaseModel):
    """Image block extracted from PDF."""

    index: int = Field(..., description="Image index")
    page_number: int = Field(..., description="Page number (1-based)")
    bbox: tuple[float, float, float, float] = Field(
        ..., description="Bounding box (x0, y0, x1, y1)"
    )
    width: float = Field(..., description="Image width in pixels")
    height: float = Field(..., description="Image height in pixels")
    data_base64: str | None = Field(None, description="Base64-encoded image data")
    format: str = Field(default="png", description="Image format")


class TableBlock(BaseModel):
    """Table block extracted from PDF."""

    page_number: int = Field(..., description="Page number (1-based)")
    bbox: tuple[float, float, float, float] = Field(..., description="Bounding box")
    rows: int = Field(..., description="Number of rows")
    cols: int = Field(..., description="Number of columns")
    data: list[list[str]] = Field(default_factory=list, description="Table cell data")
    markdown: str | None = Field(None, description="Markdown representation")


class PDFContent(BaseModel):
    """Extracted PDF content."""

    file_path: str = Field(..., description="PDF file path")
    total_pages: int = Field(..., description="Total number of pages")
    extracted_at: datetime = Field(
        default_factory=datetime.now, description="Extraction timestamp"
    )

    # Text content
    text: str = Field(default="", description="Full text")
    text_by_page: list[str] = Field(default_factory=list, description="Text by page")

    # Multi-modal content
    images: list[ImageBlock] = Field(
        default_factory=list, description="Extracted images"
    )
    tables: list[TableBlock] = Field(
        default_factory=list, description="Extracted tables"
    )

    # Metadata
    metadata: dict[str, Any] = Field(default_factory=dict, description="PDF metadata")

    @property
    def has_images(self) -> bool:
        return len(self.images) > 0

    @property
    def has_tables(self) -> bool:
        return len(self.tables) > 0

    @property
    def is_multimodal(self) -> bool:
        return self.has_images or self.has_tables
