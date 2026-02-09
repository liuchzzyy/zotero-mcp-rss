"""PDF content extractor using PyMuPDF."""

from __future__ import annotations

import asyncio
import base64
from pathlib import Path
from typing import Any

import fitz  # PyMuPDF

from zotero_mcp.analyzer.models.content import (
    ImageBlock,
    PDFContent,
    TableBlock,
)


class PDFExtractor:
    """
    PDF content extractor based on PyMuPDF.

    Features:
    - 10x faster than pdfplumber
    - Multi-modal: text, images, tables
    - Configurable extraction options
    """

    def __init__(
        self,
        extract_images: bool = True,
        extract_tables: bool = True,
        image_format: str = "png",
        image_dpi: int = 150,
    ):
        self.extract_images = extract_images
        self.extract_tables = extract_tables
        self.image_format = image_format
        self.image_dpi = image_dpi

    async def extract(
        self,
        file_path: str,
        pages: list[int] | None = None,
    ) -> PDFContent:
        """
        Extract PDF content.

        Args:
            file_path: Path to PDF file
            pages: Page numbers to extract (1-based). None extracts all.

        Returns:
            PDFContent with text, images, and tables
        """
        return await asyncio.to_thread(self._extract_sync, file_path, pages)

    def _extract_sync(
        self,
        file_path: str,
        pages: list[int] | None = None,
    ) -> PDFContent:
        """Synchronous extraction (runs in thread)."""
        doc = fitz.open(file_path)

        content = PDFContent(
            file_path=str(Path(file_path).resolve()),
            total_pages=doc.page_count,
            metadata=self._extract_metadata(doc),
        )

        for page_num in range(doc.page_count):
            if pages and (page_num + 1) not in pages:
                continue

            page = doc[page_num]

            # Extract text
            page_text = page.get_text()
            content.text_by_page.append(page_text)
            content.text += page_text + "\n\n"

            # Extract images
            if self.extract_images:
                images = self._extract_images(doc, page, page_num)
                content.images.extend(images)

            # Extract tables
            if self.extract_tables:
                tables = self._extract_tables(page, page_num)
                content.tables.extend(tables)

        doc.close()
        return content

    async def extract_text_only(self, file_path: str) -> str:
        """Fast text-only extraction."""
        return await asyncio.to_thread(self._extract_text_only_sync, file_path)

    def _extract_text_only_sync(self, file_path: str) -> str:
        """Synchronous text-only extraction."""
        doc = fitz.open(file_path)
        text = ""
        for page in doc:
            text += page.get_text() + "\n\n"
        doc.close()
        return text

    def _extract_metadata(self, doc: fitz.Document) -> dict[str, Any]:
        """Extract PDF metadata."""
        raw = doc.metadata or {}
        metadata = {
            "title": raw.get("title", ""),
            "author": raw.get("author", ""),
            "subject": raw.get("subject", ""),
            "keywords": raw.get("keywords", ""),
            "creator": raw.get("creator", ""),
            "producer": raw.get("producer", ""),
        }
        return {k: v for k, v in metadata.items() if v}

    def _extract_images(
        self,
        doc: fitz.Document,
        page: fitz.Page,
        page_num: int,
    ) -> list[ImageBlock]:
        """Extract images from a page."""
        images: list[ImageBlock] = []
        image_list = page.get_images()

        for _img_index, img in enumerate(image_list):
            xref = img[0]

            try:
                base_image = doc.extract_image(xref)
            except Exception:
                continue

            if not base_image or not base_image.get("image"):
                continue

            image_bytes = base_image["image"]
            image_ext = base_image.get("ext", "png")

            # Get bounding box
            bbox = (0.0, 0.0, 0.0, 0.0)
            try:
                img_rects = page.get_image_rects(xref)
                if img_rects:
                    rect = img_rects[0]
                    bbox = (rect.x0, rect.y0, rect.x1, rect.y1)
            except Exception:
                pass

            data_base64 = base64.b64encode(image_bytes).decode("utf-8")

            images.append(
                ImageBlock(
                    index=len(images),
                    page_number=page_num + 1,
                    bbox=bbox,
                    width=float(base_image.get("width", 0)),
                    height=float(base_image.get("height", 0)),
                    data_base64=data_base64,
                    format=image_ext,
                )
            )

        return images

    def _extract_tables(
        self,
        page: fitz.Page,
        page_num: int,
    ) -> list[TableBlock]:
        """Extract tables using line-based heuristics."""
        tables: list[TableBlock] = []

        horizontal_lines: list[float] = []
        vertical_lines: list[float] = []

        for drawing in page.get_drawings():
            for item in drawing.get("items", []):
                if len(item) < 3:
                    continue
                kind = item[0]
                if kind == "l":  # line
                    p1 = item[1]
                    p2 = item[2]
                    dx = abs(p2.x - p1.x)
                    dy = abs(p2.y - p1.y)
                    if dx > dy * 5 and dx > 20:
                        horizontal_lines.append(p1.y)
                    elif dy > dx * 5 and dy > 20:
                        vertical_lines.append(p1.x)

        if len(horizontal_lines) > 2 and len(vertical_lines) > 2:
            h_sorted = sorted(set(horizontal_lines))
            v_sorted = sorted(set(vertical_lines))

            rows = len(h_sorted) - 1
            cols = len(v_sorted) - 1

            if rows > 0 and cols > 0:
                table_bbox = (
                    min(v_sorted),
                    min(h_sorted),
                    max(v_sorted),
                    max(h_sorted),
                )
                tables.append(
                    TableBlock(
                        page_number=page_num + 1,
                        bbox=table_bbox,
                        rows=rows,
                        cols=cols,
                    )
                )

        return tables
