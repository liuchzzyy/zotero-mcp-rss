"""Multi-modal PDF extraction using PyMuPDF."""

import base64
import logging
from pathlib import Path
from typing import Any

import fitz  # PyMuPDF

logger = logging.getLogger(__name__)


class MultiModalPDFExtractor:
    """Extract multi-modal content from PDF files using PyMuPDF.

    This class provides high-performance extraction of text, images, and tables
    from PDF documents. PyMuPDF is approximately 10x faster than pdfplumber
    and includes built-in table detection capabilities.
    """

    def __init__(self, dpi: int = 200):
        """Initialize the PDF extractor.

        Args:
            dpi: Resolution for image extraction (default: 200)
        """
        self.dpi = dpi
        self.zoom = dpi / 72.0  # PyMuPDF uses zoom factor, not DPI

    def extract_elements(
        self,
        pdf_path: Path,
        extract_images: bool = True,
        extract_tables: bool = True,
    ) -> dict[str, Any]:
        """Extract all content elements from PDF.

        Args:
            pdf_path: Path to PDF file
            extract_images: Whether to extract images
            extract_tables: Whether to extract tables

        Returns:
            Dictionary with keys:
                - text_blocks: List of text blocks with metadata
                - images: List of extracted images (base64 encoded)
                - tables: List of extracted tables

        Raises:
            Exception: If PDF cannot be opened or parsed
        """
        result = {"text_blocks": [], "images": [], "tables": []}

        try:
            doc = fitz.open(pdf_path)
            for page_num in range(len(doc)):
                page = doc[page_num]
                # Extract text blocks
                text_blocks = self._extract_text_from_page(page, page_num)
                result["text_blocks"].extend(text_blocks)

                # Extract images if requested
                if extract_images:
                    images = self._extract_images_from_page(page, page_num)
                    result["images"].extend(images)

                # Extract tables if requested
                if extract_tables:
                    tables = self._extract_tables_from_page(page, page_num)
                    result["tables"].extend(tables)

            doc.close()

        except Exception as e:
            logger.error(f"Failed to extract PDF elements from {pdf_path}: {e}")
            raise

        return result

    def _extract_text_from_page(
        self, page: fitz.Page, page_num: int
    ) -> list[dict[str, Any]]:
        """Extract text blocks from a page.

        Args:
            page: PyMuPDF Page object
            page_num: Page number (1-indexed)

        Returns:
            List of text block dictionaries with content and position metadata
        """
        blocks = []
        text_blocks = page.get_text("blocks")

        for block in text_blocks:
            # Each block is a tuple: (x0, y0, x1, y1, text, block_type, ...)
            if len(block) >= 5:
                blocks.append(
                    {
                        "type": "text",
                        "content": block[4],  # text content
                        "page": page_num,
                        "x0": block[0],
                        "x1": block[2],
                        "y0": block[1],
                        "y1": block[3],
                    }
                )

        return self._merge_text_blocks(blocks)

    def _extract_images_from_page(
        self, page: fitz.Page, page_num: int
    ) -> list[dict[str, Any]]:
        """Extract images from a page.

        Args:
            page: PyMuPDF Page object
            page_num: Page number (1-indexed)

        Returns:
            List of image dictionaries with base64-encoded content
        """
        images = []
        try:
            image_list = page.get_images()

            if not image_list:
                # No embedded images found - render entire page as image
                mat = fitz.Matrix(self.zoom, self.zoom)
                pix = page.get_pixmap(matrix=mat)
                img_bytes = pix.tobytes("png")
                img_base64 = base64.b64encode(img_bytes).decode("utf-8")

                images.append(
                    {
                        "type": "image",
                        "content": img_base64,
                        "format": "base64.png",
                        "page": page_num,
                        "width": page.rect.width,
                        "height": page.rect.height,
                        "bbox": [
                            page.rect.x0,
                            page.rect.y0,
                            page.rect.x1,
                            page.rect.y1,
                        ],
                    }
                )
            else:
                # Extract each embedded image
                for img_index, img in enumerate(image_list, 1):
                    xref = img[0]
                    if page.parent is None:
                        continue
                    base_image = page.parent.extract_image(xref)
                    if not base_image:
                        continue
                    image_bytes = base_image["image"]
                    image_ext = base_image["ext"]
                    img_base64 = base64.b64encode(image_bytes).decode("utf-8")

                    images.append(
                        {
                            "type": "image",
                            "content": img_base64,
                            "format": f"base64.{image_ext}",
                            "page": page_num,
                            "xref": xref,
                            "index": img_index,
                        }
                    )

        except Exception as e:
            logger.warning(f"Failed to extract image from page {page_num}: {e}")

        return images

    def _extract_tables_from_page(
        self, page: fitz.Page, page_num: int
    ) -> list[dict[str, Any]]:
        """Extract tables from a page.

        Args:
            page: PyMuPDF Page object
            page_num: Page number (1-indexed)

        Returns:
            List of table dictionaries with row/column data
        """
        tables = []
        try:
            # PyMuPDF's find_tables is available in recent versions
            tables_found = page.find_tables()  # type: ignore[attr-defined]

            for table in tables_found:
                table_data = table.extract()
                table_content = []
                for row in table_data:
                    # Replace None cells with empty strings
                    row_content = [cell if cell else "" for cell in row]
                    table_content.append(row_content)

                tables.append(
                    {
                        "type": "table",
                        "content": table_content,
                        "page": page_num,
                        "rows": len(table_content),
                        "cols": len(table_content[0]) if table_content else 0,
                        "bbox": list(table.bbox),
                    }
                )

        except Exception as e:
            logger.warning(f"Failed to extract tables from page {page_num}: {e}")

        return tables

    def _merge_text_blocks(self, blocks: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Merge nearby text blocks into paragraphs.

        This combines consecutive text blocks from the same page into
        a single paragraph for better readability.

        Args:
            blocks: List of text block dictionaries

        Returns:
            List of merged paragraph dictionaries
        """
        if not blocks:
            return []

        paragraphs = []
        current_paragraph = {
            "type": "text",
            "content": blocks[0]["content"],
            "page": blocks[0]["page"],
        }

        for block in blocks[1:]:
            if block["page"] == current_paragraph["page"]:
                # Same page - merge with space
                current_paragraph["content"] += " " + block["content"]
            else:
                # Different page - start new paragraph
                paragraphs.append(current_paragraph)
                current_paragraph = {
                    "type": "text",
                    "content": block["content"],
                    "page": block["page"],
                }

        paragraphs.append(current_paragraph)
        return paragraphs

    def classify_by_type(
        self, elements: list[dict[str, Any]]
    ) -> dict[str, list[dict[str, Any]]]:
        """Classify elements by type.

        Args:
            elements: List of element dictionaries with 'type' field

        Returns:
            Dictionary with keys 'text', 'images', 'tables'
        """
        classified = {"text": [], "images": [], "tables": []}

        # Map element types to classification keys
        type_mapping = {
            "text": "text",
            "image": "images",
            "table": "tables",
        }

        for element in elements:
            element_type = element.get("type", "text")
            mapped_type = type_mapping.get(element_type, "text")
            classified[mapped_type].append(element)

        return classified
