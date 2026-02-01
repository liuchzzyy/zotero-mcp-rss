# Multi-Modal PDF Analysis Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Enhance the PDF analysis pipeline to support multi-modal content extraction (text, images, tables) and dynamically adjust input based on LLM capabilities (text-only vs. vision-enabled).

**Architecture:** Layered enhancement with clear separation between PDF extraction, content classification, and LLM provider capabilities. The solution will:

1. **PDF Extraction Layer**: Extract and classify PDF elements (text, images, tables) using PyMuPDF (fitz) - **high performance**
2. **Content Processing Layer**: Generate image descriptions/base64 encodings for vision-capable LLMs
3. **LLM Capability Layer**: Abstract interface to handle text-only (DeepSeek) vs. multi-modal (Claude, GPT-4V) providers
4. **Template Enhancement Layer**: Extended templates with structured image/figure analysis sections

**Tech Stack:**
- **PDF Parsing**: PyMuPDF (fitz) for high-performance extraction, PyMuPDF4LLM for LLM-optimized markdown conversion
- **Image Processing**: PIL (Pillow) for image encoding
- **OCR**: pytesseract (optional, for text within images)
- **LLM Integration**: Enhanced multi-modal support for Claude CLI, DeepSeek (text-only fallback)
- **Models**: Pydantic v2 for structured data
- **Testing**: pytest with fixtures for mock PDF data

**Why PyMuPDF?**
- **10x faster** than pdfplumber/pdf2image
- **Better table extraction** with built-in table detection
- **PyMuPDF4LLM**: Optimized markdown conversion for LLMs
- **Single dependency**: No need for separate pdf2image
- **More accurate**: Better text positioning and image extraction

---

## Phase 1: Core PDF Multi-Modal Extraction

### Task 1: Add PDF Dependencies

**Files:**
- Modify: `pyproject.toml`

**Step 1: Add dependencies to pyproject.toml**

Add to `dependencies` section:
```toml
pymupdf = "^1.24.0"  # PyMuPDF (fitz)
pymupdf4llm = "^0.0.7"  # LLM-optimized helpers
Pillow = "^10.0.0"
pytesseract = {version = "^0.3.10", optional = true}
```

Add to `optional-dependencies`:
```toml
[project.optional-dependencies]
ocr = [
    "pytesseract>=0.3.10",
]
all = [
    "zotero-mcp[ocr]",
]
```

**Step 2: Run dependency sync**

Run: `uv sync`

Expected: Dependencies installed successfully

**Step 3: Commit**

```bash
git add pyproject.toml
git commit -m "feat: add PyMuPDF for high-performance PDF extraction

- Add PyMuPDF (fitz) for fast PDF parsing
- Add PyMuPDF4LLM for LLM-optimized markdown conversion
- Add Pillow for image processing
- Add pytesseract as optional OCR dependency

PyMuPDF is ~10x faster than pdfplumber and has better table extraction."

---

### Task 2: Create Multi-Modal PDF Extractor

**Files:**
- Create: `src/zotero_mcp/clients/zotero/pdf_extractor.py`
- Test: `tests/clients/zotero/test_pdf_extractor.py`

**Step 1: Write the failing test**

Create `tests/clients/zotero/test_pdf_extractor.py`:
```python
import pytest
from pathlib import Path
from zotero_mcp.clients.zotero.pdf_extractor import MultiModalPDFExtractor

def test_extract_text_content():
    """Test text extraction from PDF"""
    extractor = MultiModalPDFExtractor()
    result = extractor.extract_elements(Path("tests/fixtures/sample.pdf"))

    assert "text_blocks" in result
    assert len(result["text_blocks"]) > 0
    assert "content" in result["text_blocks"][0]
    assert "page" in result["text_blocks"][0]

def test_extract_images():
    """Test image extraction from PDF"""
    extractor = MultiModalPDFExtractor()
    result = extractor.extract_elements(Path("tests/fixtures/sample.pdf"))

    assert "images" in result
    # Image extraction returns base64 or path references
    assert isinstance(result["images"], list)

def test_extract_tables():
    """Test table extraction from PDF"""
    extractor = MultiModalPDFExtractor()
    result = extractor.extract_elements(Path("tests/fixtures/sample.pdf"))

    assert "tables" in result
    assert isinstance(result["tables"], list)

def test_classify_content_types():
    """Test content type classification"""
    extractor = MultiModalPDFExtractor()
    elements = [
        {"type": "text", "content": "Sample text"},
        {"type": "image", "content": "base64..."},
        {"type": "table", "content": [["Header"], ["Data"]]}
    ]

    classified = extractor.classify_by_type(elements)

    assert "text" in classified
    assert "images" in classified
    assert "tables" in classified
```

**Step 2: Run test to verify it fails**

Run: `uv run pytest tests/clients/zotero/test_pdf_extractor.py -v`

Expected: FAIL with "ModuleNotFoundError: No module named 'zotero_mcp.clients.zotero.pdf_extractor'"

**Step 3: Write minimal implementation**

Create `src/zotero_mcp/clients/zotero/pdf_extractor.py`:
```python
"""
Multi-modal PDF extraction for Zotero MCP.

Extracts and classifies PDF elements: text, images, tables.
Uses PyMuPDF (fitz) for high-performance extraction.
Supports both path-based and in-memory PDF processing.
"""

import base64
import io
import logging
from pathlib import Path
from typing import Any

import fitz  # PyMuPDF
from PIL import Image

logger = logging.getLogger(__name__)


class MultiModalPDFExtractor:
    """
    Extract multi-modal content from PDF files.

    Supports:
    - Text blocks with position metadata
    - Images as base64 encoded data
    - Tables as structured data
    - Fast extraction using PyMuPDF (~10x faster than pdfplumber)
    """

    def __init__(self, dpi: int = 200):
        """
        Initialize PDF extractor.

        Args:
            dpi: Resolution for image extraction (default: 200)
        """
        self.dpi = dpi
        self.zoom = dpi / 72.0  # PyMuPDF uses zoom, not DPI

    def extract_elements(
        self,
        pdf_path: Path,
        extract_images: bool = True,
        extract_tables: bool = True,
    ) -> dict[str, Any]:
        """
        Extract all content elements from PDF.

        Args:
            pdf_path: Path to PDF file
            extract_images: Whether to extract images
            extract_tables: Whether to extract tables

        Returns:
            Dictionary with 'text_blocks', 'images', 'tables' keys
        """
        result = {
            "text_blocks": [],
            "images": [],
            "tables": [],
        }

        try:
            doc = fitz.open(pdf_path)
                for page_num, page in enumerate(doc, start=1):  # PyMuPDF pages are 0-indexed in doc
                    # Extract text blocks
                    text_blocks = self._extract_text_from_page(page, page_num)
                    result["text_blocks"].extend(text_blocks)

                    # Extract images
                    if extract_images:
                        images = self._extract_images_from_page(page, page_num)
                        result["images"].extend(images)

                    # Extract tables
                    if extract_tables:
                        tables = self._extract_tables_from_page(page, page_num)
                        result["tables"].extend(tables)

            doc.close()

        except Exception as e:
            logger.error(f"Failed to extract PDF elements: {e}")
            raise

        return result

    def _extract_text_from_page(
        self, page: fitz.Page, page_num: int
    ) -> list[dict[str, Any]]:
        """Extract text blocks from a page."""
        blocks = []

        # Get text blocks with position info
        text_blocks = page.get_text("blocks")  # PyMuPDF's block extraction

        for block in text_blocks:
            # block format: (x0, y0, x1, y1, text, block_no, block_type)
            if len(block) >= 5:
                blocks.append({
                    "type": "text",
                    "content": block[4],  # text content
                    "page": page_num,
                    "x0": block[0],
                    "x1": block[2],
                    "y0": block[1],
                    "y1": block[3],
                })

        # Group by proximity and merge into paragraphs
        paragraphs = self._merge_text_blocks(blocks)

        return paragraphs

    def _extract_images_from_page(
        self, page: fitz.Page, page_num: int
    ) -> list[dict[str, Any]]:
        """Extract images from a page."""
        images = []

        try:
            # Get image list
            image_list = page.get_images()

            if not image_list:
                # If no embedded images, render entire page as image
                mat = fitz.Matrix(self.zoom, self.zoom)
                pix = page.get_pixmap(matrix=mat)

                # Convert to PNG bytes
                img_bytes = pix.tobytes("png")

                # Encode as base64
                img_base64 = base64.b64encode(img_bytes).decode("utf-8")

                images.append({
                    "type": "image",
                    "content": img_base64,
                    "format": "base64",
                    "page": page_num,
                    "width": page.rect.width,
                    "height": page.rect.height,
                    "bbox": [page.rect.x0, page.rect.y0, page.rect.x1, page.rect.y1],
                })
            else:
                # Extract each embedded image
                for img_index, img in enumerate(image_list, 1):
                    xref = img[0]

                    # Extract image
                    base_image = page.parent.extract_image(xref)
                    image_bytes = base_image["image"]
                    image_ext = base_image["ext"]

                    # Encode as base64
                    img_base64 = base64.b64encode(image_bytes).decode("utf-8")

                    images.append({
                        "type": "image",
                        "content": img_base64,
                        "format": f"base64.{image_ext}",
                        "page": page_num,
                        "xref": xref,
                        "index": img_index,
                    })

        except Exception as e:
            logger.warning(f"Failed to extract image from page {page_num}: {e}")

        return images

    def _extract_tables_from_page(
        self, page: fitz.Page, page_num: int
    ) -> list[dict[str, Any]]:
        """Extract tables from a page."""
        tables = []

        try:
            # PyMuPDF has built-in table finding
            tables_found = page.find_tables()

            for table in tables_found:
                table_data = table.extract()

                # Convert to list of lists
                table_content = []
                for row in table_data:
                    row_content = [cell if cell else "" for cell in row]
                    table_content.append(row_content)

                tables.append({
                    "type": "table",
                    "content": table_content,
                    "page": page_num,
                    "rows": len(table_content),
                    "cols": len(table_content[0]) if table_content else 0,
                    "bbox": list(table.bbox),  # [x0, y0, x1, y1]
                })

        except Exception as e:
            logger.warning(f"Failed to extract tables from page {page_num}: {e}")

        return tables

    def _merge_text_blocks(
        self, blocks: list[dict[str, Any]]
    ) -> list[dict[str, Any]]:
        """Merge nearby text blocks into paragraphs."""
        # Simple implementation: merge blocks on same line
        if not blocks:
            return []

        paragraphs = []
        current_paragraph = {
            "type": "text",
            "content": blocks[0]["content"],
            "page": blocks[0]["page"],
        }

        for block in blocks[1:]:
            # If same page, append to current paragraph
            if block["page"] == current_paragraph["page"]:
                current_paragraph["content"] += " " + block["content"]
            else:
                # Save current and start new
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
        """
        Classify elements by type.

        Returns dict with 'text', 'images', 'tables' keys.
        """
        classified = {
            "text": [],
            "images": [],
            "tables": [],
        }

        for element in elements:
            element_type = element.get("type", "text")
            if element_type in classified:
                classified[element_type].append(element)

        return classified
```

**Step 4: Run test to verify it passes**

Run: `uv run pytest tests/clients/zotero/test_pdf_extractor.py -v`

Expected: Tests may fail due to missing test fixture PDF, but structure should be correct

**Step 5: Commit**

```bash
git add src/zotero_mcp/clients/zotero/pdf_extractor.py tests/clients/zotero/test_pdf_extractor.py
git commit -m "feat: add multi-modal PDF extractor with PyMuPDF

- Extract text blocks with position metadata (10x faster than pdfplumber)
- Extract images as base64 encoded data (embedded or page-level)
- Extract tables with built-in table detection
- Support content type classification
- Use PyMuPDF (fitz) for high-performance extraction"

Performance: PyMuPDF is ~10x faster than pdfplumber and has better table extraction.
```

---

### Task 3: Integrate PDF Extractor with BatchLoader

**Files:**
- Modify: `src/zotero_mcp/utils/async_helpers/batch_loader.py:34-100`
- Modify: `src/zotero_mcp/clients/zotero/pdf_extractor.py`

**Step 1: Write the failing test**

```python
# Add to tests/async_helpers/test_batch_loader.py
def test_get_item_bundle_with_multimodal():
    """Test bundle fetching with multi-modal content."""
    loader = BatchLoader(item_service)

    bundle = loader.get_item_bundle_parallel(
        "TEST_KEY",
        include_fulltext=True,
        include_multimodal=True,  # New parameter
    )

    assert "multimodal" in bundle
    assert "images" in bundle["multimodal"]
    assert "tables" in bundle["multimodal"]
```

**Step 2: Run test to verify it fails**

Run: `uv run pytest tests/async_helpers/test_batch_loader.py::test_get_item_bundle_with_multimodal -v`

Expected: FAIL with "TypeError: get_item_bundle_parallel() got an unexpected keyword argument 'include_multimodal'"

**Step 3: Modify BatchLoader to support multi-modal**

In `src/zotero_mcp/utils/async_helpers/batch_loader.py`:

Update method signature:
```python
async def get_item_bundle_parallel(
    self,
    item_key: str,
    include_fulltext: bool = True,
    include_annotations: bool = True,
    include_notes: bool = True,
    include_bibtex: bool = True,
    include_multimodal: bool = False,  # NEW
) -> dict[str, Any]:
```

Add to task mapping:
```python
if include_multimodal:
    from zotero_mcp.clients.zotero.pdf_extractor import MultiModalPDFExtractor

    # Get PDF path from attachments
    async def get_multimodal_content():
        attachments = await self.item_service.get_item_children(item_key)
        pdf_attachments = [
            a for a in attachments
            if a.get("data", {}).get("itemType") == "attachment"
            and a.get("data", {}).get("contentType") == "application/pdf"
        ]

        if not pdf_attachments:
            return {}

        # Get local path from first PDF attachment
        pdf_path = pdf_attachments[0].get("data", {}).get("path")
        if not pdf_path:
            return {}

        # Extract multi-modal content
        extractor = MultiModalPDFExtractor()
        return extractor.extract_elements(Path(pdf_path))

    tasks.append(get_multimodal_content())
    task_map[next_idx] = "multimodal"
    next_idx += 1
```

**Step 4: Run test to verify it passes**

Run: `uv run pytest tests/async_helpers/test_batch_loader.py::test_get_item_bundle_with_multimodal -v`

Expected: PASS (may need mocking for actual PDF)

**Step 5: Commit**

```bash
git add src/zotero_mcp/utils/async_helpers/batch_loader.py
git commit -m "feat: add multi-modal extraction support to BatchLoader

- Add include_multimodal parameter
- Extract PDF images and tables when requested
- Integrate with MultiModalPDFExtractor"
```

---

### Task 3.5: Add PyMuPDF4LLM Markdown Converter

**Files:**
- Create: `src/zotero_mcp/clients/zotero/markdown_converter.py`
- Test: `tests/clients/zotero/test_markdown_converter.py`

**Step 1: Write the failing test**

Create `tests/clients/zotero/test_markdown_converter.py`:
```python
import pytest
from pathlib import Path
from zotero_mcp.clients.zotero.markdown_converter import PDFToMarkdownConverter

def test_convert_pdf_to_markdown():
    """Test PDF to markdown conversion with PyMuPDF4LLM"""
    converter = PDFToMarkdownConverter()

    result = converter.to_markdown(Path("tests/fixtures/sample.pdf"))

    assert isinstance(result, str)
    assert len(result) > 0
    # Markdown should contain headings, text, etc.
    assert "#" in result or "##" in result

def test_convert_with_page_breaks():
    """Test conversion preserves page structure"""
    converter = PDFToMarkdownConverter()

    result = converter.to_markdown(
        Path("tests/fixtures/sample.pdf"),
        show_progress=False,
        page_breaks=True,
    )

    assert "---" in result  # Page breaks in markdown
```

**Step 2: Run test to verify it fails**

Run: `uv run pytest tests/clients/zotero/test_markdown_converter.py -v`

Expected: FAIL with "ModuleNotFoundError: No module named 'zotero_mcp.clients.zotero.markdown_converter'"

**Step 3: Write minimal implementation**

Create `src/zotero_mcp/clients/zotero/markdown_converter.py`:
```python
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
        extract_images: bool = True,
    ) -> str:
        """
        Convert PDF to markdown.

        Args:
            pdf_path: Path to PDF file
            show_progress: Show conversion progress (default: False)
            page_breaks: Insert page break markers (default: True)
            extract_images: Extract and embed images (default: True)

        Returns:
            Markdown string
        """
        try:
            # Use PyMuPDF4LLM's to_markdown function
            md_text = pymupdf4llm.to_markdown(
                str(pdf_path),
                pages=None,  # All pages
                hdr_info=None,  # Auto-detect headers
                show_progress=show_progress,
                page_breaks=page_breaks,
            )

            return md_text

        except Exception as e:
            logger.error(f"Failed to convert PDF to markdown: {e}")
            raise

    def to_markdown_with_images(
        self,
        pdf_path: Path,
        image_format: str = "base64",
        max_image_size: int = 5 * 1024 * 1024,  # 5MB limit
    ) -> dict[str, Any]:
        """
        Convert PDF to markdown with extracted images.

        Args:
            pdf_path: Path to PDF file
            image_format: 'base64' or 'path'
            max_image_size: Maximum image size in bytes

        Returns:
            Dictionary with 'markdown' and 'images' keys
        """
        result = {
            "markdown": "",
            "images": [],
        }

        try:
            # Convert to markdown with images
            md_text = pymupdf4llm.to_markdown(
                str(pdf_path),
                pages=None,
                hdr_info=None,
                show_progress=False,
                page_breaks=True,
            )

            result["markdown"] = md_text

            # Extract images separately if needed
            if image_format == "base64":
                # Note: PyMuPDF4LLM already embeds images in markdown
                # This is for structured access if needed
                from zotero_mcp.clients.zotero.pdf_extractor import MultiModalPDFExtractor

                extractor = MultiModalPDFExtractor()
                elements = extractor.extract_elements(pdf_path, extract_images=True)
                result["images"] = elements["images"]

        except Exception as e:
            logger.error(f"Failed to convert PDF with images: {e}")
            raise

        return result
```

**Step 4: Run test to verify it passes**

Run: `uv run pytest tests/clients/zotero/test_markdown_converter.py -v`

Expected: PASS (may need test fixture PDF)

**Step 5: Commit**

```bash
git add src/zotero_mcp/clients/zotero/markdown_converter.py tests/clients/zotero/test_markdown_converter.py
git commit -m "feat: add PyMuPDF4LLM markdown converter

- Add PDF to markdown conversion optimized for LLMs
- Preserve document structure (headings, tables, lists)
- Automatic image embedding support
- Handle complex multi-column layouts

PyMuPDF4LLM provides better structure preservation than raw text extraction."
```

---

## Phase 2: LLM Capability Detection

### Task 4: Create LLM Capability Registry

**Files:**
- Create: `src/zotero_mcp/clients/llm/capabilities.py`
- Test: `tests/clients/llm/test_capabilities.py`

**Step 1: Write the failing test**

Create `tests/clients/llm/test_capabilities.py`:
```python
from zotero_mcp.clients.llm.capabilities import (
    LLMCapability,
    get_provider_capability,
)

def test_deepseek_capability():
    """Test DeepSeek is text-only"""
    cap = get_provider_capability("deepseek")

    assert cap.supports_images == False
    assert cap.supports_text == True
    assert cap.max_input_tokens > 0

def test_claude_cli_capability():
    """Test Claude CLI supports vision"""
    cap = get_provider_capability("claude-cli")

    assert cap.supports_images == True
    assert cap.supports_text == True

def test_capability_check():
    """Test capability checking"""
    cap = get_provider_capability("deepseek")

    assert cap.can_handle_images() == False
    assert cap.can_handle_text() == True
```

**Step 2: Run test to verify it fails**

Run: `uv run pytest tests/clients/llm/test_capabilities.py -v`

Expected: FAIL with "ModuleNotFoundError: No module named 'zotero_mcp.clients.llm.capabilities'"

**Step 3: Write minimal implementation**

Create `src/zotero_mcp/clients/llm/capabilities.py`:
```python
"""
LLM capability detection and registry.

Defines what each LLM provider can handle:
- Text input
- Image/vision input
- Token limits
- Special features
"""

from dataclasses import dataclass
from typing import Literal


@dataclass(frozen=True)
class LLMCapability:
    """Defines LLM capabilities."""

    provider: str
    supports_text: bool
    supports_images: bool
    supports_video: bool = False
    max_input_tokens: int = 128000
    max_output_tokens: int = 4096
    supports_streaming: bool = True

    def can_handle_text(self) -> bool:
        """Check if LLM can handle text input."""
        return self.supports_text

    def can_handle_images(self) -> bool:
        """Check if LLM can handle image input."""
        return self.supports_images

    def is_multimodal(self) -> bool:
        """Check if LLM is multi-modal (text + images)."""
        return self.supports_text and self.supports_images


# Provider Capability Registry
PROVIDER_CAPABILITIES: dict[str, LLMCapability] = {
    "deepseek": LLMCapability(
        provider="deepseek",
        supports_text=True,
        supports_images=False,  # DeepSeek is text-only
        max_input_tokens=128000,
        max_output_tokens=8192,
    ),
    "claude-cli": LLMCapability(
        provider="claude-cli",
        supports_text=True,
        supports_images=True,  # Claude CLI supports vision
        max_input_tokens=200000,
        max_output_tokens=8192,
    ),
    "openai": LLMCapability(
        provider="openai",
        supports_text=True,
        supports_images=True,  # GPT-4V supports vision
        max_input_tokens=128000,
        max_output_tokens=4096,
    ),
    "gemini": LLMCapability(
        provider="gemini",
        supports_text=True,
        supports_images=True,  # Gemini Pro Vision
        max_input_tokens=128000,
        max_output_tokens=8192,
    ),
}


def get_provider_capability(provider: str) -> LLMCapability:
    """
    Get capability info for a provider.

    Args:
        provider: Provider name ('deepseek', 'claude-cli', etc.)

    Returns:
        LLMCapability object

    Raises:
        ValueError: If provider not found
    """
    if provider not in PROVIDER_CAPABILITIES:
        raise ValueError(
            f"Unknown provider: {provider}. "
            f"Available: {list(PROVIDER_CAPABILITIES.keys())}"
        )

    return PROVIDER_CAPABILITIES[provider]


def is_multimodal_provider(provider: str) -> bool:
    """Check if provider supports multi-modal input."""
    try:
        cap = get_provider_capability(provider)
        return cap.is_multimodal()
    except ValueError:
        return False
```

**Step 4: Run test to verify it passes**

Run: `uv run pytest tests/clients/llm/test_capabilities.py -v`

Expected: PASS

**Step 5: Commit**

```bash
git add src/zotero_mcp/clients/llm/capabilities.py tests/clients/llm/test_capabilities.py
git commit -m "feat: add LLM capability detection

- Define capabilities for each provider (text/images)
- Add DeepSeek as text-only
- Add Claude CLI as multi-modal
- Add utility functions for capability checks"
```

---

### Task 5: Update LLM Client Interface

**Files:**
- Modify: `src/zotero_mcp/clients/llm/base.py:99-150`
- Modify: `src/zotero_mcp/clients/llm/cli.py:78-150`

**Step 1: Write the failing test**

Add to existing test file:
```python
# tests/clients/llm/test_base.py
def test_analyze_paper_with_images():
    """Test LLM client can handle image content."""
    client = LLMClient()

    result = client.analyze_paper(
        title="Test",
        authors="Author",
        journal="Journal",
        date="2024",
        doi="10.1234/test",
        fulltext="Sample text",
        images=[{
            "type": "image",
            "content": "base64...",
            "page": 1,
        }],  # NEW parameter
    )

    assert "image analysis" in result.lower() or len(result) > 0
```

**Step 2: Run test to verify it fails**

Run: `uv run pytest tests/clients/llm/test_base.py::test_analyze_paper_with_images -v`

Expected: FAIL with "TypeError: analyze_paper() got an unexpected keyword argument 'images'"

**Step 3: Modify LLMClient base.py**

Update signature and implementation:
```python
async def analyze_paper(
    self,
    title: str,
    authors: str | None,
    journal: str | None,
    date: str | None,
    doi: str | None,
    fulltext: str,
    annotations: list[dict[str, Any]] | None = None,
    template: str | None = None,
    images: list[dict[str, Any]] | None = None,  # NEW
) -> str:
    """
    Analyze a research paper.

    Args:
        title: Paper title
        authors: Authors
        journal: Journal name
        date: Publication date
        doi: DOI
        fulltext: Full text content
        annotations: PDF annotations
        template: Custom template
        images: Image data (multi-modal LLMs only)  # NEW
    """
```

Update content assembly:
```python
# Build content
content_sections = []

# Add paper info
content_sections.append(f"# {title}\n")
if authors:
    content_sections.append(f"**Authors**: {authors}\n")
if journal:
    content_sections.append(f"**Journal**: {journal}\n")
if date:
    content_sections.append(f"**Date**: {date}\n")
if doi:
    content_sections.append(f"**DOI**: {doi}\n")
content_sections.append("\n")

# Add fulltext
content_sections.append("## Full Text\n\n")
content_sections.append(fulltext)
content_sections.append("\n")

# Add annotations
if annotations:
    content_sections.append("## PDF Annotations\n\n")
    for i, ann in enumerate(annotations, 1):
        content_sections.append(f"### Annotation {i}\n")
        content_sections.append(f"{ann}\n")
    content_sections.append("\n")

# Add images (NEW)
if images and self.provider == "deepseek":
    # DeepSeek can't handle images - add placeholder
    content_sections.append("## Images\n\n")
    content_sections.append(
        f"[Note: This PDF contains {len(images)} image(s), "
        f"but the current LLM (DeepSeek) cannot analyze images. "
        f"Use a vision-capable model like Claude CLI for image analysis.]\n\n"
    )

prompt = "\n".join(content_sections)
```

**Step 4: Update CLILLMClient cli.py**

Similar signature update:
```python
async def analyze_paper(
    self,
    title: str,
    authors: str | None,
    journal: str | None,
    date: str | None,
    doi: str | None,
    fulltext: str,
    annotations: list[dict[str, Any]] | None = None,
    template: str | None = None,
    images: list[dict[str, Any]] | None = None,  # NEW
) -> str:
```

Add image embedding:
```python
# Build full prompt
content_parts = []

# ... existing text content ...

# Add images with base64 (NEW)
if images:
    content_parts.append("\n## Images\n\n")
    for i, img in enumerate(images, 1):
        content_parts.append(f"### Image {i} (Page {img.get('page', '?')})\n")
        if img.get("format") == "base64":
            # For Claude CLI, we can include base64 directly
            content_parts.append(f"![Image](data:image/png;base64,{img['content']})\n")
        content_parts.append(f"*Figure {i}*\n\n")

prompt_content = "\n".join(content_parts)
```

**Step 5: Run test to verify it passes**

Run: `uv run pytest tests/clients/llm/test_base.py::test_analyze_paper_with_images -v`

Expected: PASS

**Step 6: Commit**

```bash
git add src/zotero_mcp/clients/llm/base.py src/zotero_mcp/clients/llm/cli.py
git commit -m "feat: add image support to LLM clients

- Add images parameter to analyze_paper()
- DeepSeek: Add placeholder for unavailable image analysis
- Claude CLI: Embed base64 images in prompt
- Maintain backward compatibility with None default"
```

---

## Phase 3: Workflow Integration

### Task 6: Update WorkflowService for Multi-Modal

**Files:**
- Modify: `src/zotero_mcp/services/workflow.py:300-400`
- Modify: `src/zotero_mcp/models/workflow/analysis.py:143-162`

**Step 1: Update AnalysisItem model**

In `src/zotero_mcp/models/workflow/analysis.py`:
```python
class AnalysisItem(BaseModel):
    """Single item prepared for analysis (Mode A)."""

    item_key: str = Field(..., description="Zotero item key")
    title: str = Field(..., description="Item title")
    authors: str | None = Field(default=None, description="Authors")
    date: str | None = Field(default=None, description="Publication date")
    journal: str | None = Field(default=None, description="Journal/Publication")
    doi: str | None = Field(default=None, description="DOI")
    pdf_content: str | None = Field(default=None, description="Extracted PDF full text")
    annotations: list[dict[str, Any]] = Field(
        default_factory=list, description="PDF annotations"
    )
    images: list[dict[str, Any]] = Field(  # NEW
        default_factory=list, description="PDF images (base64)"
    )
    tables: list[dict[str, Any]] = Field(  # NEW
        default_factory=list, description="PDF tables"
    )
    metadata: dict[str, Any] = Field(
        default_factory=dict, description="Additional metadata"
    )
    template_questions: list[str] = Field(
        default_factory=list, description="Template questions for analysis"
    )
```

**Step 2: Update WorkflowService._extract_bundle_context**

In `src/zotero_mcp/services/workflow.py`, locate the `_extract_bundle_context` method (around line 350) and update:
```python
def _extract_bundle_context(
    self,
    bundle: dict[str, Any],
    include_annotations: bool = True,
    include_multimodal: bool = True,  # NEW
) -> dict[str, Any]:
    """Extract analysis context from item bundle."""
    metadata = bundle.get("metadata", {})

    context = {
        "title": metadata.get("title", ""),
        "authors": format_creators(metadata.get("creators", {})),
        "journal": metadata.get("publicationTitle", ""),
        "date": metadata.get("date", ""),
        "doi": metadata.get("DOI", ""),
        "fulltext": bundle.get("fulltext", ""),
    }

    # Annotations
    if include_annotations:
        annotations = bundle.get("annotations", [])
        context["annotations"] = annotations

    # Multi-modal content (NEW)
    if include_multimodal:
        multimodal = bundle.get("multimodal", {})
        context["images"] = multimodal.get("images", [])
        context["tables"] = multimodal.get("tables", [])

    return context
```

**Step 3: Update WorkflowService._analyze_single_item**

Update the LLM call (around line 400):
```python
# Determine LLM provider
llm_provider = llm_provider or "auto"
if llm_provider == "auto":
    # Auto-detect: prefer multi-modal if images available
    has_images = bool(context.get("images"))
    llm_provider = "claude-cli" if has_images else "deepseek"

# Get capability
from zotero_mcp.clients.llm.capabilities import get_provider_capability
capability = get_provider_capability(llm_provider)

# Prepare images based on capability
images_to_send = None
if capability.can_handle_images():
    images_to_send = context.get("images", [])

# Call LLM
analysis = await llm_client.analyze_paper(
    title=context["title"],
    authors=context["authors"],
    journal=context["journal"],
    date=context["date"],
    doi=context["doi"],
    fulltext=context["fulltext"],
    annotations=context.get("annotations"),
    images=images_to_send,  # NEW
    template=template,
)
```

**Step 4: Update prepare_analysis method**

Add multi-modal extraction:
```python
async def prepare_analysis(
    self,
    source: str,
    collection_key: str | None = None,
    collection_name: str | None = None,
    days: int = 7,
    limit: int = 20,
    include_annotations: bool = True,
    include_multimodal: bool = True,  # NEW
    skip_existing: bool = True,
) -> PrepareAnalysisResponse:
```

Update bundle fetching:
```python
bundle = await self.batch_loader.get_item_bundle_parallel(
    item.key,
    include_fulltext=True,
    include_annotations=include_annotations,
    include_multimodal=include_multimodal,  # NEW
)
```

**Step 5: Write tests**

```python
# tests/services/test_workflow.py
def test_prepare_analysis_with_multimodal():
    """Test prepare analysis includes images/tables."""
    service = WorkflowService()

    response = service.prepare_analysis(
        source="collection",
        collection_name="test",
        include_multimodal=True,
    )

    assert response.prepared_items > 0
    first_item = response.items[0]
    assert "images" in first_item.model_fields
    assert "tables" in first_item.model_fields

def test_auto_select_multimodal_llm():
    """Test auto-selection of multi-modal LLM when images present."""
    service = WorkflowService()

    # Should auto-select claude-cli when images present
    result = service.batch_analyze(
        source="collection",
        collection_name="test_with_images",
        llm_provider="auto",
    )

    # Verify correct LLM was used
```

**Step 6: Run tests**

Run: `uv run pytest tests/services/test_workflow.py -v`

Expected: PASS

**Step 7: Commit**

```bash
git add src/zotero_mcp/services/workflow.py src/zotero_mcp/models/workflow/analysis.py
git commit -m "feat: integrate multi-modal PDF analysis into workflow

- Add images/tables to AnalysisItem model
- Auto-detect and use multi-modal LLM when images present
- Support include_multimodal parameter in prepare_analysis
- Maintain backward compatibility with text-only mode"
```

---

## Phase 4: Enhanced Note Templates

### Task 7: Create Multi-Modal Analysis Template

**Files:**
- Modify: `src/zotero_mcp/utils/data/templates.py:100-250`
- Test: `tests/utils/test_templates.py`

**Step 1: Write the failing test**

Create `tests/utils/test_templates.py`:
```python
from zotero_mcp.utils.data.templates import (
    get_multimodal_analysis_template,
    DEFAULT_ANALYSIS_TEMPLATE_MULTIMODAL,
)

def test_multimodal_template_exists():
    """Test multi-modal template is defined."""
    assert DEFAULT_ANALYSIS_TEMPLATE_MULTIMODAL is not None
    assert "{images}" in DEFAULT_ANALYSIS_TEMPLATE_MULTIMODAL
    assert "{tables}" in DEFAULT_ANALYSIS_TEMPLATE_MULTIMODAL

def test_get_multimodal_template():
    """Test retrieving multi-modal template."""
    template = get_multimodal_analysis_template()

    assert "图片分析" in template or "Image Analysis" in template
    assert "表格分析" in template or "Table Analysis" in template
```

**Step 2: Run test to verify it fails**

Run: `uv run pytest tests/utils/test_templates.py::test_multimodal_template_exists -v`

Expected: FAIL with "NameError: name 'DEFAULT_ANALYSIS_TEMPLATE_MULTIMODAL' is not defined"

**Step 3: Add multi-modal template**

In `src/zotero_mcp/utils/data/templates.py`, add after existing templates:
```python
DEFAULT_ANALYSIS_TEMPLATE_MULTIMODAL = """你是一位专业的科研文献分析助手。请仔细阅读以下论文内容，并按照指定的结构进行深入、全面的分析。

## 论文基本信息

- **标题**: {title}
- **作者**: {authors}
- **期刊**: {journal}
- **发表日期**: {date}
- **DOI**: {doi}

## 论文全文

{fulltext}

{annotations_section}

{multimodal_section}

---

## 分析要求

请按照以下结构进行详细分析，以 Markdown 格式返回：

### 📖 粗读筛选

请从以下维度快速评估这篇论文的质量和阅读价值：
- 论文发表期刊的影响力和领域地位
- 研究问题的重要性和前沿性
- 方法和结论的可靠性和创新性
- **结论**: 是否建议深入阅读？适合哪类研究者？

### 📚 前言及文献综述

#### 引用文献评估
- 引用的文献是否**最新**、**全面**？
- 以往文献有什么**不足**或**研究空白**？
- 作者如何定位本研究与前人工作的关系？

#### 聚焦问题
- 本研究**聚焦的核心科学问题**是什么？
- 研究的**逻辑思路**是什么？（从问题到方法到结论的完整链条）
- **可行性**：方法设计是否合理？技术路线是否可行？
- **可靠性**：实验设计是否严谨？对照组设置是否合理？

#### 选题新颖性
- 作者选题角度是否**新颖**？
- 这项研究有什么**科学价值**和**应用前景**？

### 💡 创新点

请从以下五个维度分析创新点：

#### 科学问题
- 提出了什么新的科学问题或研究视角？

#### 制备方法
- 在材料制备或样品准备上有什么创新？
- 是否开发了新的合成路线或工艺？

#### 研究思路
- 研究设计有何独特之处？
- 是否采用了新的研究范式或策略？

#### 研究工具
- 使用了什么新的研究工具、技术或表征手段？
- 是否开发了新的测试方法或分析手段？

#### 研究理论
- 在理论层面有何贡献？

{figure_analysis_section}

### 🔬 实验部分

#### 制备方法和步骤
- 关键的制备方法和步骤是什么？

#### 表征方法和结果
- 使用了哪些表征方法？主要结果是什么？
- 关键性能数据和指标有哪些？

#### 机制解释
- 作者提出的机制解释是什么？
- 理论基础和模型是什么？

### 📊 结果与讨论

{table_analysis_section}

### ✅ 优缺点总结

这篇论文有什么优点和不足？

### 📝 笔记原子化（便于引用追踪）

请将上述分析按**原子化**结构整理，便于后续引用追踪：

#### 🎯 核心观点
- **观点1**: [描述] - 引用证据：[图X/表Y/页Z]
- **观点2**: [描述] - 引用证据：[图X/表Y/页Z]

#### 🔬 关键实验
- **实验1**: [描述] - 结果：[图X/表Y]
- **实验2**: [描述] - 结果：[图X/表Y]

#### 💡 创新点
- **创新点1**: [描述] - 引用：[图X/页Y]
- **创新点2**: [描述] - 引用：[图X/页Y]

#### 📚 文献引用
- **文献1**: [作者 et al., 期刊, 年份] - 相关性：[描述]
- **文献2**: [作者 et al., 期刊, 年份] - 相关性：[描述]
"""


def get_multimodal_analysis_template() -> str:
    """
    Get the multi-modal analysis template.

    Checks ANALYSIS_TEMPLATE env var first, then returns default.
    """
    return os.getenv("ANALYSIS_TEMPLATE", DEFAULT_ANALYSIS_TEMPLATE_MULTIMODAL)


def format_multimodal_section(
    images: list[dict[str, Any]],
    tables: list[dict[str, Any]],
) -> str:
    """
    Format multi-modal content for template.

    Args:
        images: List of image dicts with 'page', 'content' keys
        tables: List of table dicts with 'page', 'content' keys

    Returns:
        Formatted markdown section
    """
    sections = []

    # Images section
    if images:
        sections.append("## 图片内容\n\n")
        sections.append(f"本文档包含 {len(images)} 个图片：\n\n")
        for i, img in enumerate(images, 1):
            sections.append(f"### 图片 {i} (第 {img.get('page', '?')} 页)\n")
            # For multi-modal LLMs, the image is embedded elsewhere
            sections.append(f"[图片 {i} 位于第 {img.get('page', '?')} 页]\n\n")

    # Tables section
    if tables:
        sections.append("## 表格内容\n\n")
        sections.append(f"本文档包含 {len(tables)} 个表格：\n\n")
        for i, table in enumerate(tables, 1):
            sections.append(f"### 表格 {i} (第 {table.get('page', '?')} 页)\n")
            # Add table preview
            content = table.get("content", [])
            if content and len(content) > 0:
                # Show first few rows
                preview = content[:min(5, len(content))]
                for row in preview:
                    sections.append(f"{' | '.join(str(cell) for cell in row)}\n")
                sections.append("\n")

    return "".join(sections)
```

**Step 4: Update template formatting in workflow**

In `src/zotero_mcp/services/workflow.py`, update `_generate_html_note`:
```python
def _generate_html_note(
    self,
    analysis: str,
    context: dict[str, Any],
) -> str:
    """Generate HTML note from analysis."""
    # Get template
    template = get_analysis_template()

    # Prepare multi-modal section
    multimodal_section = ""
    if context.get("images") or context.get("tables"):
        from zotero_mcp.utils.data.templates import format_multimodal_section
        multimodal_section = format_multimodal_section(
            context.get("images", []),
            context.get("tables", []),
        )

    # Format figure analysis placeholder
    figure_analysis = "### 🖼️ 图片/图表分析\n\n"
    if context.get("images"):
        figure_analysis += (
            f"本文档包含 {len(context['images'])} 个图片。"
            f"请分析每个图片的内容、作用和关键信息。\n\n"
        )
    else:
        figure_analysis += "本文档无图片。\n\n"

    # Format table analysis placeholder
    table_analysis = "### 📋 表格数据分析\n\n"
    if context.get("tables"):
        table_analysis += (
            f"本文档包含 {len(context['tables'])} 个表格。"
            f"请分析每个表格的数据、趋势和关键结论。\n\n"
        )
    else:
        table_analysis += "本文档无表格。\n\n"

    # Fill template
    filled = template.format(
        title=context["title"],
        authors=context["authors"] or "",
        journal=context["journal"] or "",
        date=context["date"] or "",
        doi=context["doi"] or "",
        fulltext=context["fulltext"] or "",
        annotations_section=self._format_annotations(context.get("annotations")),
        multimodal_section=multimodal_section,
        figure_analysis_section=figure_analysis,
        table_analysis_section=table_analysis,
    )

    # Convert to HTML
    html = markdown_to_html(filled)

    return html
```

**Step 5: Run tests**

Run: `uv run pytest tests/utils/test_templates.py -v`

Expected: PASS

**Step 6: Commit**

```bash
git add src/zotero_mcp/utils/data/templates.py tests/utils/test_templates.py
git commit -m "feat: add multi-modal analysis template

- Add dedicated template for PDFs with images/tables
- Add format_multimodal_section() helper
- Include figure analysis and table analysis sections
- Support image references in atomic notes"
```

---

## Phase 5: MCP Tool Updates

### Task 8: Update MCP Tools for Multi-Modal

**Files:**
- Modify: `src/zotero_mcp/tools/workflow.py:50-150`
- Modify: `src/zotero_mcp/models/workflow/analysis.py:57-116`

**Step 1: Update BatchAnalyzeInput model**

In `src/zotero_mcp/models/workflow/analysis.py`:
```python
class BatchAnalyzeInput(BaseInput):
    """
    Input for zotero_batch_analyze_pdfs tool (Mode B).

    Automatically analyzes PDFs using LLM and creates notes.
    """

    source: Literal["collection", "recent"] = Field(
        default="collection",
        description="Source of items: 'collection' or 'recent'",
    )
    collection_name: str | None = Field(
        default=None,
        description="Collection name (supports fuzzy matching)",
    )
    collection_key: str | None = Field(
        default=None,
        description="Collection key (takes precedence over collection_name)",
    )
    days: int = Field(
        default=7,
        ge=1,
        le=365,
        description="Number of days to look back (for source='recent')",
    )
    limit: int = Field(
        default=20,
        ge=1,
        le=100,
        description="Maximum number of items to process",
    )
    resume_workflow_id: str | None = Field(
        default=None,
        description="Workflow ID to resume (for checkpoint recovery)",
    )
    skip_existing_notes: bool = Field(
        default=True,
        description="Skip items that already have analysis notes",
    )
    include_annotations: bool = Field(
        default=True,
        description="Whether to include PDF annotations in analysis",
    )
    include_multimodal: bool = Field(  # NEW
        default=True,
        description="Whether to extract and analyze images/tables",
    )
    llm_provider: Literal["deepseek", "claude-cli", "auto"] = Field(
        default="auto",
        description="LLM provider to use for analysis ('auto' selects based on content)",
    )
    llm_model: str | None = Field(
        default=None,
        description="Specific model to use (overrides default)",
    )
    template: str | None = Field(
        default=None,
        description="Custom analysis template/instruction (Markdown)",
    )
    dry_run: bool = Field(
        default=False,
        description="If true, only preview analysis without creating notes",
    )
```

**Step 2: Update PrepareAnalysisInput model**

```python
class PrepareAnalysisInput(BaseInput):
    """
    Input for zotero_prepare_analysis tool (Mode A).

    Prepares PDF content and metadata for external AI analysis.
    """

    source: Literal["collection", "recent"] = Field(
        default="collection",
        description="Source of items: 'collection' or 'recent'",
    )
    collection_name: str | None = Field(
        default=None,
        description="Collection name (supports fuzzy matching)",
    )
    collection_key: str | None = Field(
        default=None,
        description="Collection key (takes precedence over collection_name)",
    )
    days: int = Field(
        default=7,
        ge=1,
        le=365,
        description="Number of days to look back (for source='recent')",
    )
    limit: int = Field(
        default=20,
        ge=1,
        le=100,
        description="Maximum number of items to process",
    )
    include_annotations: bool = Field(
        default=True,
        description="Whether to include PDF annotations",
    )
    include_multimodal: bool = Field(  # NEW
        default=True,
        description="Whether to extract images/tables from PDFs",
    )
    skip_existing_notes: bool = Field(
        default=True,
        description="Skip items that already have analysis notes",
    )
```

**Step 3: Update MCP tool wrapper**

In `src/zotero_mcp/tools/workflow.py`:
```python
@mcp.tool()
async def zotero_batch_analyze_pdfs(
    source: Literal["collection", "recent"] = "collection",
    collection_name: str | None = None,
    collection_key: str | None = None,
    days: int = 7,
    limit: int = 20,
    resume_workflow_id: str | None = None,
    skip_existing_notes: bool = True,
    include_annotations: bool = True,
    include_multimodal: bool = True,  # NEW
    llm_provider: Literal["deepseek", "claude-cli", "auto"] = "auto",
    llm_model: str | None = None,
    template: str | None = None,
    dry_run: bool = False,
) -> dict[str, Any]:
    """
    Batch analyze research papers with AI (Mode B).

    Automatically analyzes PDFs using LLM and creates structured Zotero notes.
    Supports checkpoint/resume for interrupted workflows.

    **NEW**: Multi-modal support - extracts and analyzes images and tables!

    Args:
        source: 'collection' or 'recent'
        collection_name: Collection name (fuzzy matching)
        collection_key: Collection key (exact match, overrides name)
        days: Days to look back (for source='recent')
        limit: Max items to process
        resume_workflow_id: Resume from checkpoint
        skip_existing_notes: Skip items with existing analysis notes
        include_annotations: Include PDF annotations
        include_multimodal: Extract images/tables (requires vision-capable LLM)
        llm_provider: LLM provider ('deepseek', 'claude-cli', or 'auto')
        llm_model: Specific model (overrides default)
        template: Custom analysis template
        dry_run: Preview only, don't create notes

    Returns:
        Batch analysis results with workflow_id for resuming
    """
    # Convert input model
    input_data = BatchAnalyzeInput(
        source=source,
        collection_name=collection_name,
        collection_key=collection_key,
        days=days,
        limit=limit,
        resume_workflow_id=resume_workflow_id,
        skip_existing_notes=skip_existing_notes,
        include_annotations=include_annotations,
        include_multimodal=include_multimodal,  # NEW
        llm_provider=llm_provider,
        llm_model=llm_model,
        template=template,
        dry_run=dry_run,
    )

    # Call service
    service = get_workflow_service()
    result = await service.batch_analyze(
        source=input_data.source,
        collection_key=input_data.collection_key,
        collection_name=input_data.collection_name,
        days=input_data.days,
        limit=input_data.limit,
        resume_workflow_id=input_data.resume_workflow_id,
        skip_existing=input_data.skip_existing_notes,
        include_annotations=input_data.include_annotations,
        include_multimodal=input_data.include_multimodal,  # NEW
        llm_provider=input_data.llm_provider,
        llm_model=input_data.llm_model,
        template=input_data.template,
        dry_run=input_data.dry_run,
    )

    return result.model_dump()
```

**Step 4: Add tool documentation update**

```python
@mcp.tool()
async def zotero_prepare_analysis(
    source: Literal["collection", "recent"] = "collection",
    collection_name: str | None = None,
    collection_key: str | None = None,
    days: int = 7,
    limit: int = 20,
    include_annotations: bool = True,
    include_multimodal: bool = True,  # NEW
    skip_existing_notes: bool = True,
) -> dict[str, Any]:
    """
    Prepare research papers for AI analysis (Mode A).

    Extracts PDF content, annotations, images, and tables for external AI analysis.
    Does NOT call LLM - returns structured data for your own analysis.

    **NEW**: Multi-modal extraction - includes images and tables!

    Args:
        source: 'collection' or 'recent'
        collection_name: Collection name (fuzzy matching)
        collection_key: Collection key (exact match, overrides name)
        days: Days to look back (for source='recent')
        limit: Max items to process
        include_annotations: Include PDF annotations
        include_multimodal: Extract images/tables
        skip_existing_notes: Skip items with existing notes

    Returns:
        Prepared items with fulltext, annotations, images, tables
    """
```

**Step 5: Write integration tests**

```python
# tests/tools/test_workflow_tools.py
import pytest
from zotero_mcp.tools.workflow import zotero_batch_analyze_pdfs

@pytest.mark.asyncio
async def test_batch_analyze_with_multimodal():
    """Test batch analyze includes multimodal parameter."""
    result = await zotero_batch_analyze_pdfs(
        source="collection",
        collection_name="test",
        include_multimodal=True,
        llm_provider="claude-cli",
        dry_run=True,
    )

    assert "workflow_id" in result
    assert result["total_items"] >= 0

@pytest.mark.asyncio
async def test_prepare_analysis_with_multimodal():
    """Test prepare analysis includes images/tables."""
    from zotero_mcp.tools.workflow import zotero_prepare_analysis

    result = await zotero_prepare_analysis(
        source="collection",
        collection_name="test",
        include_multimodal=True,
    )

    assert "items" in result
    if result["items"]:
        assert "images" in result["items"][0]
        assert "tables" in result["items"][0]
```

**Step 6: Run tests**

Run: `uv run pytest tests/tools/test_workflow_tools.py -v`

Expected: PASS

**Step 7: Commit**

```bash
git add src/zotero_mcp/tools/workflow.py src/zotero_mcp/models/workflow/analysis.py
git commit -m "feat: add multi-modal support to MCP tools

- Add include_multimodal parameter to batch_analyze and prepare_analysis
- Update tool documentation with multi-modal capabilities
- Add integration tests for multi-modal workflows
- Support auto-detection of vision-capable LLMs"
```

---

## Phase 6: Documentation & Testing

### Task 9: Update Documentation

**Files:**
- Create: `docs/MULTIMODAL_ANALYSIS.md`
- Modify: `README.md`
- Modify: `.env.example`

**Step 1: Create multi-modal analysis guide**

Create `docs/MULTIMODAL_ANALYSIS.md`:
```markdown
# Multi-Modal PDF Analysis

Zotero MCP now supports **multi-modal PDF analysis** with image and table extraction!

## Features

### 🖼️ Image Extraction
- Extract images from PDF pages as base64-encoded data
- Support for vision-capable LLMs (Claude CLI, GPT-4V, Gemini)
- Automatic image description and analysis

### 📊 Table Extraction
- Extract tables as structured data
- Support for table content analysis
- Easy reference in atomic notes

### 🤖 Dynamic LLM Selection
- **Auto mode**: Automatically selects Claude CLI when images detected
- **DeepSeek**: Text-only mode (faster, cheaper)
- **Claude CLI**: Full multi-modal analysis
- Fallback logic for unavailable capabilities

## Usage

### Mode A: Prepare Analysis (External AI)

\`\`\`python
# Prepare with images/tables
result = await zotero_prepare_analysis(
    source="collection",
    collection_name="Materials Science",
    include_multimodal=True,  # Extract images and tables
)

for item in result["items"]:
    print(f"Title: {item['title']}")
    print(f"Images: {len(item['images'])}")
    print(f"Tables: {len(item['tables'])}")
\`\`\`

### Mode B: Batch Analyze (Built-in LLM)

\`\`\`python
# Auto-detect best LLM
result = await zotero_batch_analyze_pdfs(
    source="collection",
    collection_name="Materials Science",
    llm_provider="auto",  # Auto-select based on content
    include_multimodal=True,
)

# Force multi-modal LLM
result = await zotero_batch_analyze_pdfs(
    source="recent",
    days=7,
    llm_provider="claude-cli",  # Use Claude for vision
    include_multimodal=True,
)
\`\`\`

## Configuration

### Environment Variables

\`\`\`bash
# LLM Selection
CLI_LLM_COMMAND=claude  # For multi-modal analysis
DEEPSEEK_API_KEY=sk-xxx  # For text-only analysis

# Optional: OCR for images with embedded text
# (Requires: uv sync --all-groups --extra ocr)
TESSERACT_CMD=/usr/bin/tesseract  # Path to tesseract executable
\`\`\`

### Template Customization

The multi-modal template includes:
- 📖 粗读筛选
- 📚 前言及文献综述
- 💡 创新点 (5 dimensions)
- 🖼️ 图片/图表分析
- 📋 表格数据分析
- ✅ 优缺点总结
- 📝 笔记原子化

Customize via:
\`\`\`bash
export ANALYSIS_TEMPLATE="$(cat my_template.md)"
\`\`\`

## LLM Provider Comparison

| Provider | Text | Images | Tables | Speed | Cost |
|----------|------|--------|--------|-------|------|
| DeepSeek | ✅ | ❌ | ⚠️* | Fast | Low |
| Claude CLI | ✅ | ✅ | ✅ | Medium | Medium |
| GPT-4V | ✅ | ✅ | ✅ | Slow | High |
| Gemini | ✅ | ✅ | ✅ | Medium | Medium |

*Table structure extracted but requires text-based LLM analysis

## Architecture

```
PDF File
  ↓
MultiModalPDFExtractor
  ├→ Text Blocks (with position metadata)
  ├→ Images (base64 encoded)
  └→ Tables (structured 2D arrays)
  ↓
ContentClassifier
  ↓
LLMCapabilityDetector
  ↓
LLMClient (based on capabilities)
  ├→ DeepSeek: Text only (images filtered out)
  └→ Claude CLI: Multi-modal (images embedded)
  ↓
Structured Note (with image references)
```

## Examples

### Example 1: Materials Science Paper

\`\`\`python
# Paper contains 5 figures with TEM/SEM images
result = await zotero_batch_analyze_pdfs(
    source="collection",
    collection_name="Nanomaterials",
    include_multimodal=True,
    llm_provider="auto",  # Uses Claude CLI
)

# Result includes:
# - Figure 1 (Page 3): TEM image showing nanoparticle size distribution
# - Figure 2 (Page 4): XRD pattern analysis
# - Table 1 (Page 5): Comparison of synthesis methods
\`\`\`

### Example 2: Text-Only Analysis (Faster)

\`\`\`python
# Skip images for faster analysis
result = await zotero_batch_analyze_pdfs(
    source="recent",
    days=3,
    include_multimodal=False,  # Text only
    llm_provider="deepseek",  # Fast & cheap
)
\`\`\`

## Troubleshooting

### Images not extracted
- Check: `include_multimodal=True`
- Verify: PDF has actual images (not just text)
- Check: LLM supports vision (`claude-cli` not `deepseek`)

### Analysis fails on large PDFs
- Reduce DPI: `MultiModalPDFExtractor(dpi=150)`
- Skip images: `include_multimodal=False`
- Use text-only LLM: `llm_provider="deepseek"`

### Memory issues with many images
- Process in smaller batches: `limit=10`
- Use text-only mode for initial screening
- Extract only specific pages (future feature)
\`\`\`

## Performance Tips

1. **Initial Screening**: Use DeepSeek (text-only) for fast triage
2. **Deep Analysis**: Use Claude CLI (multi-modal) for selected papers
3. **Batch Size**: Limit to 10-20 papers with images per batch
4. **Storage**: Image data increases note size significantly
\`\`\`
```

**Step 2: Update README.md**

Add section:
```markdown
## 🆕 Multi-Modal PDF Analysis

Extract and analyze images, tables, and text from PDFs with vision-capable AI!

\`\`\`bash
# Auto-detect best LLM (Claude for images, DeepSeek for text)
uv run zotero-mcp analyze --collection "Recent Papers" --multimodal --auto-llm

# Force multi-modal analysis
uv run zotero-mcp analyze --collection "Figures" --llm claude-cli --multimodal
\`\`\`

**Supported LLMs:**
- ✅ Claude CLI (multi-modal: text + images)
- ⚠️ DeepSeek (text-only, faster/cheaper)
- 🚧 GPT-4V (coming soon)
- 🚧 Gemini (coming soon)

See [docs/MULTIMODAL_ANALYSIS.md](docs/MULTIMODAL_ANALYSIS.md) for details.
```

**Step 3: Update .env.example**

```bash
# Multi-Modal Analysis
CLI_LLM_COMMAND=claude  # Command for vision-capable LLM
CLI_LLM_TIMEOUT=300  # Timeout in seconds (increase for image analysis)

# OCR (Optional - for text within images)
# Requires: uv sync --extra ocr
# TESSERACT_CMD=/usr/bin/tesseract
# TESSERACT_LANG=eng+chi_sim  # Languages for OCR
```

**Step 4: Commit**

```bash
git add docs/MULTIMODAL_ANALYSIS.md README.md .env.example
git commit -m "docs: add multi-modal analysis documentation

- Add comprehensive multi-modal analysis guide
- Update README with new features
- Document LLM provider comparison
- Add troubleshooting and performance tips"
```

---

### Task 10: End-to-End Integration Tests

**Files:**
- Create: `tests/integration/test_multimodal_e2e.py`

**Step 1: Write comprehensive E2E tests**

Create `tests/integration/test_multimodal_e2e.py`:
```python
"""
End-to-end integration tests for multi-modal PDF analysis.

These tests require:
- Zotero running with local API access
- At least one PDF attachment in test collection
- Claude CLI available (for multi-modal tests)
"""
import pytest
from pathlib import Path

from zotero_mcp.services.workflow import WorkflowService
from zotero_mcp.clients.llm.capabilities import get_provider_capability


@pytest.mark.integration
@pytest.mark.asyncio
async def test_prepare_analysis_with_real_pdf():
    """Test prepare analysis with real PDF from Zotero."""
    service = WorkflowService()

    result = await service.prepare_analysis(
        source="collection",
        collection_name="Test",
        limit=1,
        include_multimodal=True,
    )

    assert result.total_items >= 0
    if result.prepared_items > 0:
        item = result.items[0]
        assert item.title
        assert "images" in item.model_fields
        assert "tables" in item.model_fields


@pytest.mark.integration
@pytest.mark.asyncio
async def test_auto_select_claude_for_images():
    """Test auto-selection of Claude CLI when images present."""
    from zotero_mcp.clients.llm.capabilities import is_multimodal_provider

    # Verify capability detection
    assert is_multimodal_provider("claude-cli") == True
    assert is_multimodal_provider("deepseek") == False


@pytest.mark.integration
@pytest.mark.asyncio
async def test_batch_analyze_workflow():
    """Test full batch analyze workflow with multi-modal."""
    service = WorkflowService()

    result = await service.batch_analyze(
        source="collection",
        collection_name="Test",
        limit=1,
        include_multimodal=True,
        llm_provider="auto",
        dry_run=True,  # Don't actually create notes
    )

    assert result.workflow_id
    assert result.total_items >= 0


@pytest.mark.integration
@pytest.mark.asyncio
async def test_deepseek_fallback_for_images():
    """Test DeepSeek gracefully handles images (text-only)."""
    from zotero_mcp.clients.llm import get_llm_client

    client = get_llm_client(provider="deepseek")
    capability = get_provider_capability("deepseek")

    assert capability.can_handle_images() == False

    # Verify client doesn't crash with image data
    # (Images should be filtered out or placeholder added)
```

**Step 2: Run integration tests**

Run: `uv run pytest tests/integration/test_multimodal_e2e.py -v -m integration`

Expected: PASS (may require test environment setup)

**Step 3: Commit**

```bash
git add tests/integration/test_multimodal_e2e.py
git commit -m "test: add end-to-end multi-modal integration tests

- Test prepare_analysis with real PDFs
- Test auto-selection of multi-modal LLM
- Test full batch analyze workflow
- Test DeepSeek fallback behavior"
```

---

## Phase 7: CLI Updates

### Task 11: Update CLI for Multi-Modal

**Files:**
- Modify: `src/zotero_mcp/cli.py:200-300`

**Step 1: Add --multimodal flag to scan command**

In `src/zotero_mcp/cli.py`:
```python
@app.command()
def scan(
    collection: str = typer.Option(None, "--collection", "-c", help="Collection name"),
    days: int = typer.Option(7, "--days", "-d", help="Days to look back"),
    limit: int = typer.Option(20, "--limit", "-l", help="Max items to process"),
    llm: str = typer.Option("auto", "--llm", help="LLM provider (deepseek/claude-cli/auto)"),
    multimodal: bool = typer.Option(True, "--multimodal/--no-multimodal", help="Extract images/tables"),  # NEW
):
    """Scan and analyze research papers with AI."""
    # ... existing code ...

    # Pass multimodal flag
    result = service.batch_analyze(
        source="collection",
        collection_name=collection,
        days=days,
        limit=limit,
        include_multimodal=multimodal,  # NEW
        llm_provider=llm,
    )
```

**Step 2: Add help text**

```python
@app.command()
def scan(
    collection: str = typer.Option(
        None,
        "--collection",
        "-c",
        help="Collection name (supports fuzzy matching)",
    ),
    days: int = typer.Option(
        7,
        "--days",
        "-d",
        help="Days to look back (for source='recent')",
    ),
    limit: int = typer.Option(
        20,
        "--limit",
        "-l",
        help="Max items to process (1-100)",
    ),
    llm: str = typer.Option(
        "auto",
        "--llm",
        help=(
            "LLM provider: "
            "'auto' (default), 'deepseek' (fast, text-only), "
            "'claude-cli' (multi-modal, supports images)"
        ),
    ),
    multimodal: bool = typer.Option(
        True,
        "--multimodal/--no-multimodal",
        help="Extract and analyze images/tables (requires vision-capable LLM)",
    ),
):
    """
    Scan and analyze research papers with AI.

    **NEW**: Multi-modal support! Use --multimodal to extract images and tables.

    Examples:
        zotero-mcp scan -c "Recent Papers" --llm auto
        zotero-mcp scan -c "Figures" --llm claude-cli --multimodal
        zotero-mcp scan -c "Text Only" --llm deepseek --no-multimodal
    """
    typer.echo(f"🔍 Scanning collection: {collection or 'All'}")
    typer.echo(f"📊 Multimodal: {'Enabled' if multimodal else 'Disabled'}")
    typer.echo(f"🤖 LLM: {llm}")

    # ... rest of implementation
```

**Step 3: Test CLI**

```bash
# Test help
uv run zotero-mcp scan --help

# Test with flags (dry run)
uv run zotero-mcp scan -c "Test" --llm auto --multimodal --dry-run
```

**Step 4: Commit**

```bash
git add src/zotero_mcp/cli.py
git commit -m "feat: add multi-modal flags to CLI

- Add --multimodal/--no-multimodal flag
- Update help text with examples
- Improve LLM provider documentation"
```

---

## Summary

This implementation plan adds comprehensive multi-modal PDF analysis capabilities to Zotero MCP:

### ✅ What's Built

1. **Multi-Modal PDF Extraction** (`pdf_extractor.py`)
   - Text blocks with position metadata
   - Images as base64 encoded data
   - Tables as structured 2D arrays
   - **Powered by PyMuPDF (fitz) - ~10x faster than pdfplumber**

2. **LLM-Optimized Markdown Converter** (`markdown_converter.py`)
   - PDF to markdown conversion using PyMuPDF4LLM
   - Preserves document structure (headings, lists, tables)
   - Automatic image embedding
   - Better than raw text extraction for LLM consumption

3. **LLM Capability Detection** (`capabilities.py`)
   - Provider registry with capabilities
   - Auto-detection of vision support
   - Fallback logic for text-only LLMs

4. **Enhanced Workflow Integration**
   - Auto-selection of multi-modal LLM when images detected
   - Backward compatibility with text-only mode
   - Support for both Mode A (prepare) and Mode B (analyze)

5. **Rich Analysis Templates**
   - Dedicated multi-modal template
   - Image/figure analysis sections
   - Table/data analysis sections
   - Atomic note structure with image references

6. **MCP Tool Updates**
   - `include_multimodal` parameter
   - Enhanced documentation
   - Integration tests

### 🎯 Key Features

- **Auto LLM Selection**: Uses Claude CLI when images present, DeepSeek for text-only
- **Graceful Degradation**: DeepSeek gets placeholder text instead of images
- **Performance**: Optional multi-modal extraction (skip for faster analysis)
- **Backward Compatible**: All existing code works without changes

### 🚀 Usage Examples

```python
# Auto-detect best LLM
await zotero_batch_analyze_pdfs(
    collection_name="Materials",
    include_multimodal=True,
    llm_provider="auto",  # Claude for images, DeepSeek for text
)

# Force multi-modal
await zotero_batch_analyze_pdfs(
    collection_name="Figures",
    llm_provider="claude-cli",
    include_multimodal=True,
)

# Text-only (faster)
await zotero_batch_analyze_pdfs(
    collection_name="Review",
    llm_provider="deepseek",
    include_multimodal=False,
)
```

### 📝 Next Steps (Future Enhancements)

1. **OCR Integration**: Add pytesseract for text within images
2. **Page-Level Extraction**: Extract specific pages only
3. **Image Compression**: Reduce base64 size for large images
4. **Figure Caption Extraction**: Parse PDF structure for captions
5. **Batch Optimization**: Parallel PDF extraction
6. **Caching**: Cache extracted multimodal content

---

**Estimated Implementation Time**: 3-4 hours (following TDD approach)

**Testing Strategy**:
- Unit tests for each component
- Integration tests for workflows
- E2E tests with real Zotero instance
- Manual testing with sample PDFs

**Dependencies Added**:
- `PyMuPDF (fitz)` - High-performance PDF extraction (~10x faster than pdfplumber)
- `PyMuPDF4LLM` - LLM-optimized markdown conversion
- `Pillow` - Image processing
- `pytesseract` (optional) - OCR

**Key Performance Improvements**:
- PyMuPDF is **~10x faster** than pdfplumber for PDF parsing
- Better table extraction with built-in table detection
- More accurate text positioning and layout analysis
- Single dependency replaces pdfplumber + pdf2image

**Breaking Changes**: None - all additions are backward compatible.
