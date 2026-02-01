"""Tests for template utilities."""

import pytest

from zotero_mcp.utils.data.templates import (
    DEFAULT_ANALYSIS_TEMPLATE_MULTIMODAL,
    format_multimodal_section,
    get_multimodal_analysis_template,
)


class TestMultimodalTemplate:
    """Tests for multi-modal analysis template."""

    def test_get_multimodal_template_returns_string(self):
        """Test that get_multimodal_analysis_template returns a string."""
        template = get_multimodal_analysis_template()
        assert isinstance(template, str)
        assert len(template) > 0

    def test_multimodal_template_contains_required_placeholders(self):
        """Test that multi-modal template contains required placeholders."""
        template = get_multimodal_analysis_template()

        # Check for basic placeholders
        assert "{title}" in template
        assert "{authors}" in template
        assert "{journal}" in template
        assert "{date}" in template
        assert "{doi}" in template
        assert "{fulltext}" in template
        assert "{annotations_section}" in template

        # Check for multi-modal specific placeholders
        assert "{multimodal_section}" in template
        assert "{figure_analysis_section}" in template
        assert "{table_analysis_section}" in template

    def test_multimodal_template_contains_figure_analysis_section(self):
        """Test that template has figure analysis section."""
        template = get_multimodal_analysis_template()
        # Template should have figure analysis placeholder
        assert "{figure_analysis_section}" in template

    def test_multimodal_template_contains_table_analysis_section(self):
        """Test that template has table analysis section."""
        template = get_multimodal_analysis_template()
        # Template should have table analysis placeholder
        assert "{table_analysis_section}" in template

    def test_default_template_constant_is_defined(self):
        """Test that DEFAULT_ANALYSIS_TEMPLATE_MULTIMODAL constant exists."""
        assert isinstance(DEFAULT_ANALYSIS_TEMPLATE_MULTIMODAL, str)
        assert len(DEFAULT_ANALYSIS_TEMPLATE_MULTIMODAL) > 1000  # Non-empty template


class TestFormatMultimodalSection:
    """Tests for format_multimodal_section function."""

    def test_format_images_with_single_image(self):
        """Test formatting a single image."""
        images = [{"page": 1, "type": "figure"}]
        tables = []

        result = format_multimodal_section(images, tables)

        assert "图片内容" in result
        assert "1 个图片" in result or "1 images" in result.lower()
        assert "图片 1" in result or "Image 1" in result
        assert "第 1 页" in result or "page 1" in result.lower()

    def test_format_images_with_multiple_images(self):
        """Test formatting multiple images."""
        images = [
            {"page": 1, "type": "figure"},
            {"page": 3, "type": "figure"},
            {"page": 5, "type": "figure"},
        ]
        tables = []

        result = format_multimodal_section(images, tables)

        assert "3 个图片" in result or "3 images" in result.lower()
        assert "图片 1" in result or "Image 1" in result
        assert "图片 2" in result or "Image 2" in result
        assert "图片 3" in result or "Image 3" in result

    def test_format_tables_with_single_table(self):
        """Test formatting a single table."""
        images = []
        tables = [{"page": 2, "content": [["A", "B"], ["1", "2"]]}]

        result = format_multimodal_section(images, tables)

        assert "表格内容" in result
        assert "1 个表格" in result or "1 tables" in result.lower()
        assert "表格 1" in result or "Table 1" in result
        assert "第 2 页" in result or "page 2" in result.lower()

    def test_format_tables_with_table_content(self):
        """Test that table content is formatted correctly."""
        images = []
        tables = [
            {
                "page": 2,
                "content": [
                    ["Header1", "Header2", "Header3"],
                    ["Row1Col1", "Row1Col2", "Row1Col3"],
                    ["Row2Col1", "Row2Col2", "Row2Col3"],
                ],
            }
        ]

        result = format_multimodal_section(images, tables)

        # Check that content rows are present
        assert "Header1" in result
        assert "Row1Col1" in result

    def test_format_tables_with_large_table_truncates_preview(self):
        """Test that large tables are truncated to 5 rows."""
        images = []
        # Create a table with 10 rows
        tables = [
            {
                "page": 1,
                "content": [[f"Row{i}Col{j}" for j in range(3)] for i in range(10)],
            }
        ]

        result = format_multimodal_section(images, tables)

        # Should only have first 5 rows
        assert "Row0Col0" in result
        assert "Row4Col0" in result
        # Row 5+ should not be in preview
        assert "Row5Col0" not in result

    def test_format_empty_images_and_tables(self):
        """Test formatting with no images or tables."""
        images = []
        tables = []

        result = format_multimodal_section(images, tables)

        # Should return empty string when no content
        assert result == ""

    def test_format_images_with_missing_page_number(self):
        """Test formatting images without page numbers."""
        images = [{"type": "figure"}]  # No 'page' key
        tables = []

        result = format_multimodal_section(images, tables)

        # Should still format, with placeholder for page number
        assert "图片" in result or "Image" in result.lower()

    def test_format_tables_with_missing_page_number(self):
        """Test formatting tables without page numbers."""
        images = []
        tables = [{"content": [["A", "B"]]}]  # No 'page' key

        result = format_multimodal_section(images, tables)

        # Should still format, with placeholder for page number
        assert "表格" in result or "Table" in result.lower()

    def test_format_tables_with_empty_content(self):
        """Test formatting tables with empty content."""
        images = []
        tables = [{"page": 1, "content": []}]  # Empty content

        result = format_multimodal_section(images, tables)

        # Should still format the table header
        assert "表格" in result or "Table" in result.lower()

    def test_format_mixed_images_and_tables(self):
        """Test formatting both images and tables together."""
        images = [{"page": 1, "type": "figure"}, {"page": 3, "type": "figure"}]
        tables = [{"page": 2, "content": [["A", "B"], ["1", "2"]]}]

        result = format_multimodal_section(images, tables)

        # Should have both sections
        assert "图片内容" in result
        assert "表格内容" in result
        assert "2 个图片" in result or "2 images" in result.lower()
        assert "1 个表格" in result or "1 tables" in result.lower()

    def test_format_images_with_non_standard_types(self):
        """Test that non-image types are handled."""
        # In the real implementation, tables are filtered by type != "table"
        images = [
            {"page": 1, "type": "figure"},
            {"page": 2, "type": "chart"},
            {"page": 3, "type": "diagram"},
        ]
        tables = []

        result = format_multimodal_section(images, tables)

        # Should format all non-table types as images
        assert "图片 1" in result or "Image 1" in result
        assert "图片 2" in result or "Image 2" in result
        assert "图片 3" in result or "Image 3" in result
