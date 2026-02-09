"""
PDF to Markdown conversion using PyMuPDF4LLM.

Provides LLM-optimized markdown conversion that:
- Preserves document structure (headings, lists, tables)
- Extracts images with base64 encoding
- Maintains reading order
- Handles multi-column layouts
"""

import logging
from pathlib import Path
from typing import Any

import fitz  # PyMuPDF
import pymupdf4llm

logger = logging.getLogger(__name__)


class PDFToMarkdownConverter:
    """
    Convert PDF to markdown using PyMuPDF4LLM.

    PyMuPDF4LLM is optimized for LLM consumption:
    - Better structure preservation than raw text extraction
    - Automatic image embedding
    - Table formatting as markdown tables
    - Handles complex layouts
    """

    def to_markdown(
        self,
        pdf_path: Path,
        show_progress: bool = False,
        page_breaks: bool = True,
    ) -> str:
        """
        Convert PDF to markdown.

        Args:
            pdf_path: Path to PDF file
            show_progress: Show conversion progress (default: False)
            page_breaks: Insert page break markers (default: True)

        Returns:
            Markdown string
        """
        try:
            # PyMuPDF4LLM ignores page_breaks in legacy mode, so add markers manually.
            if page_breaks:
                with fitz.open(str(pdf_path)) as doc:
                    page_count = doc.page_count

                if page_count <= 1:
                    md_text = pymupdf4llm.to_markdown(
                        str(pdf_path),
                        pages=None,
                        hdr_info=None,
                        show_progress=show_progress,
                        page_breaks=False,
                    )
                else:
                    parts: list[str] = []
                    for page_index in range(page_count):
                        part = pymupdf4llm.to_markdown(
                            str(pdf_path),
                            pages=[page_index],
                            hdr_info=None,
                            show_progress=show_progress,
                            page_breaks=False,
                        )
                        parts.append(part.strip())

                    md_text = "\n\n---\n\n".join(parts).strip() + "\n"
            else:
                md_text = pymupdf4llm.to_markdown(
                    str(pdf_path),
                    pages=None,  # All pages
                    hdr_info=None,  # Auto-detect headers
                    show_progress=show_progress,
                    page_breaks=False,
                )

            return md_text

        except Exception as e:
            logger.error(f"Failed to convert PDF to markdown: {e}")
            raise

    def to_markdown_with_images(
        self,
        pdf_path: Path,
        image_format: str = "base64",
    ) -> dict[str, Any]:
        """
        Convert PDF to markdown with extracted images.

        Args:
            pdf_path: Path to PDF file
            image_format: 'base64' or 'path' (default: 'base64')

        Returns:
            Dictionary with 'markdown' and 'images' keys. Images are only
            extracted separately when image_format='base64' for structured access.
        """
        # Validate image_format parameter
        if image_format not in ("base64", "path"):
            raise ValueError(
                f"image_format must be 'base64' or 'path', got '{image_format}'"
            )

        # Check file exists
        if not pdf_path.exists():
            raise FileNotFoundError(f"PDF file not found: {pdf_path}")

        result = {
            "markdown": "",
            "images": [],
        }

        try:
            # PyMuPDF4LLM automatically embeds images in markdown
            md_text = self.to_markdown(
                pdf_path,
                show_progress=False,
                page_breaks=True,
            )
            result["markdown"] = md_text

            # For structured access, extract images separately when base64 is requested
            # Note: PyMuPDF4LLM already embeds images in the markdown text above.
            # This additional extraction provides structured access to images.
            if image_format == "base64":
                from zotero_mcp.clients.zotero.pdf_extractor import (
                    MultiModalPDFExtractor,
                )

                extractor = MultiModalPDFExtractor()
                elements = extractor.extract_elements(pdf_path, extract_images=True)
                result["images"] = elements["images"]

        except Exception as e:
            logger.error(f"Failed to convert PDF with images: {e}")
            raise

        return result
