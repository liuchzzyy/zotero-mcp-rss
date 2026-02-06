"""Tests for the integration layer modules."""

from __future__ import annotations

import pytest

from zotero_mcp.integration.analyzer_integration import AnalyzerIntegration
from zotero_mcp.integration.zotero_integration import ZoteroIntegration


class TestZoteroIntegrationFormatting:
    """Test formatting methods (no real API calls)."""

    def test_format_items_empty(self):
        result = ZoteroIntegration.format_items([])
        assert "Found 0 items" in result

    def test_format_items(self):
        items = [
            {
                "key": "ABC123",
                "title": "Test Paper",
                "creators": [{"name": "John Doe"}],
                "date": "2024",
                "DOI": "10.1234/test",
            }
        ]
        result = ZoteroIntegration.format_items(items)
        assert "Test Paper" in result
        assert "ABC123" in result
        assert "John Doe" in result
        assert "10.1234/test" in result

    def test_format_items_no_creators(self):
        items = [
            {
                "key": "XYZ",
                "title": "No Authors",
                "creators": [],
                "date": "N/A",
                "DOI": "N/A",
            }
        ]
        result = ZoteroIntegration.format_items(items)
        assert "No Authors" in result

    def test_format_item(self):
        item = {
            "key": "ABC123",
            "title": "Test Paper",
            "itemType": "journalArticle",
            "creators": [{"name": "Jane Smith"}],
            "date": "2024-01-15",
            "DOI": "10.5678/test",
            "url": "https://example.com",
            "abstractNote": "This is a test abstract.",
            "tags": [{"tag": "ML"}, {"tag": "AI"}],
        }
        result = ZoteroIntegration.format_item(item)
        assert "Test Paper" in result
        assert "Jane Smith" in result
        assert "This is a test abstract" in result
        assert "ML" in result
        assert "AI" in result

    def test_format_item_minimal(self):
        item = {"key": "K", "title": "Minimal"}
        result = ZoteroIntegration.format_item(item)
        assert "Minimal" in result
        assert "No abstract available" in result
        assert "No tags" in result


class TestAnalyzerIntegrationFormatting:
    """Test analyzer formatting (no real LLM calls)."""

    def test_format_result(self):
        result = {
            "summary": "A great paper about AI",
            "key_points": ["Point 1", "Point 2"],
            "methodology": "Deep learning",
            "conclusions": "AI is powerful",
            "llm_provider": "deepseek",
            "model": "deepseek-chat",
            "processing_time": 2.5,
        }
        output = AnalyzerIntegration.format_result(result)
        assert "A great paper about AI" in output
        assert "Point 1" in output
        assert "Point 2" in output
        assert "Deep learning" in output
        assert "AI is powerful" in output
        assert "deepseek" in output
        assert "2.5s" in output

    def test_format_result_empty(self):
        result = {
            "summary": "",
            "key_points": [],
            "methodology": "",
            "conclusions": "",
            "llm_provider": "mock",
            "model": "mock",
            "processing_time": 0.0,
        }
        output = AnalyzerIntegration.format_result(result)
        assert "Analysis Result" in output

    def test_format_batch_results(self):
        results = [
            {"summary": "Paper 1 summary"},
            {"summary": "Paper 2 summary"},
        ]
        output = AnalyzerIntegration.format_batch_results(results)
        assert "2 papers" in output
        assert "Paper 1" in output
        assert "Paper 2" in output
