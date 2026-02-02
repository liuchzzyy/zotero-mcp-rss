"""Test MultiModalPDFExtractor class."""

from pathlib import Path

import pytest

from zotero_mcp.clients.zotero.pdf_extractor import MultiModalPDFExtractor


def test_extract_text_content(tmp_path):
    """Test text extraction from PDF."""
    # Create a simple test PDF
    import fitz

    doc = fitz.open()
    page = doc.new_page()
    page.insert_text((50, 50), "This is a test PDF for text extraction.")
    page.insert_text((50, 70), "Second line of text.")
    test_pdf = tmp_path / "test.pdf"
    doc.save(test_pdf)
    doc.close()

    extractor = MultiModalPDFExtractor()
    result = extractor.extract_elements(test_pdf)

    assert "text_blocks" in result
    assert len(result["text_blocks"]) > 0
    assert "content" in result["text_blocks"][0]
    assert "page" in result["text_blocks"][0]
    assert "test PDF" in result["text_blocks"][0]["content"]


def test_extract_images(tmp_path):
    """Test image extraction from PDF."""
    import fitz

    doc = fitz.open()
    page = doc.new_page()
    page.insert_text((50, 50), "Page with text")

    # Add an image to the page
    img_rect = fitz.Rect(100, 100, 200, 200)
    # Create a simple red rectangle as a placeholder for an image
    page.draw_rect(img_rect, color=(1, 0, 0))

    test_pdf = tmp_path / "test_with_image.pdf"
    doc.save(test_pdf)
    doc.close()

    extractor = MultiModalPDFExtractor()
    result = extractor.extract_elements(test_pdf, extract_images=True)

    assert "images" in result
    assert isinstance(result["images"], list)


def test_extract_tables(tmp_path):
    """Test table extraction from PDF."""
    import fitz

    doc = fitz.open()
    page = doc.new_page()

    # Insert text that might be detected as a table
    text = """
    Header1    Header2    Header3
    Data1      Data2      Data3
    Data4      Data5      Data6
    """
    page.insert_text((50, 50), text)

    test_pdf = tmp_path / "test_with_table.pdf"
    doc.save(test_pdf)
    doc.close()

    extractor = MultiModalPDFExtractor()
    result = extractor.extract_elements(test_pdf, extract_tables=True)

    assert "tables" in result
    assert isinstance(result["tables"], list)


def test_classify_content_types():
    """Test content type classification."""
    extractor = MultiModalPDFExtractor()
    elements = [
        {"type": "text", "content": "Sample text"},
        {"type": "image", "content": "base64..."},
        {"type": "table", "content": [["Header"], ["Data"]]},
    ]

    classified = extractor.classify_by_type(elements)

    assert "text" in classified
    assert "images" in classified
    assert "tables" in classified
    assert len(classified["text"]) == 1
    assert len(classified["images"]) == 1
    assert len(classified["tables"]) == 1


def test_extract_with_missing_file():
    """Test extraction with missing PDF file."""
    extractor = MultiModalPDFExtractor()

    with pytest.raises(FileNotFoundError):
        extractor.extract_elements(Path("nonexistent.pdf"))


def test_merge_text_blocks():
    """Test text block merging logic."""
    import fitz

    doc = fitz.open()
    page = doc.new_page()
    page.insert_text((50, 50), "First line")
    page.insert_text((50, 70), "Second line")

    test_pdf = Path("/tmp/test_merge.pdf")
    doc.save(test_pdf)
    doc.close()

    extractor = MultiModalPDFExtractor()
    result = extractor.extract_elements(test_pdf)

    assert "text_blocks" in result
    # Text blocks should be merged
    assert len(result["text_blocks"]) >= 1

    # Clean up
    test_pdf.unlink()


def test_extract_no_images_if_disabled(tmp_path):
    """Test that images are not extracted when disabled."""
    import fitz

    doc = fitz.open()
    page = doc.new_page()
    page.insert_text((50, 50), "Text only")

    test_pdf = tmp_path / "test_no_images.pdf"
    doc.save(test_pdf)
    doc.close()

    extractor = MultiModalPDFExtractor()
    result = extractor.extract_elements(test_pdf, extract_images=False)

    assert "images" in result
    assert len(result["images"]) == 0


def test_extract_no_tables_if_disabled(tmp_path):
    """Test that tables are not extracted when disabled."""
    import fitz

    doc = fitz.open()
    page = doc.new_page()
    page.insert_text((50, 50), "Text only")

    test_pdf = tmp_path / "test_no_tables.pdf"
    doc.save(test_pdf)
    doc.close()

    extractor = MultiModalPDFExtractor()
    result = extractor.extract_elements(test_pdf, extract_tables=False)

    assert "tables" in result
    assert len(result["tables"]) == 0
