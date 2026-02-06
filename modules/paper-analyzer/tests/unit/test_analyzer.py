"""Tests for PDF analyzer."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

import pytest

from paper_analyzer.analyzers.pdf_analyzer import PDFAnalyzer
from paper_analyzer.clients.base import BaseLLMClient
from paper_analyzer.models.template import AnalysisTemplate


class MockLLMClient(BaseLLMClient):
    """Mock LLM client for testing."""

    def __init__(
        self,
        response: str = "Mock analysis output",
        vision: bool = False,
    ):
        super().__init__(api_key="mock-key", model="mock-model")
        self._response = response
        self._vision = vision
        self.last_prompt: Optional[str] = None
        self.last_system_prompt: Optional[str] = None
        self.last_images: Optional[List[str]] = None

    async def analyze(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        images: Optional[List[str]] = None,
        **kwargs: Any,
    ) -> str:
        self.last_prompt = prompt
        self.last_system_prompt = system_prompt
        self.last_images = images
        return self._response

    def supports_vision(self) -> bool:
        return self._vision

    def get_model_info(self) -> Dict[str, Any]:
        return {
            "provider": "mock",
            "model": self._response[:10],
            "supports_vision": self._vision,
            "max_tokens": 4000,
        }


class TestPDFAnalyzerTextMode:
    @pytest.mark.asyncio
    async def test_analyze_text(self):
        mock_llm = MockLLMClient(response="## Summary\nGreat paper.")
        analyzer = PDFAnalyzer(llm_client=mock_llm)

        result = await analyzer.analyze_text(
            text="This paper studies AI.",
            title="AI Paper",
        )

        assert result.raw_output == "## Summary\nGreat paper."
        assert result.llm_provider == "mock"
        assert result.processing_time >= 0
        assert "AI Paper" in mock_llm.last_prompt

    @pytest.mark.asyncio
    async def test_analyze_text_json_template(self):
        json_response = (
            '{"summary": "AI study", "key_points": ["Point 1"], '
            '"methodology": "Deep learning", "conclusions": "Works well"}'
        )
        mock_llm = MockLLMClient(response=json_response)
        analyzer = PDFAnalyzer(llm_client=mock_llm)

        result = await analyzer.analyze_text(
            text="Content",
            title="Title",
            template_name="structured",
        )

        assert result.summary == "AI study"
        assert result.key_points == ["Point 1"]
        assert result.methodology == "Deep learning"
        assert result.conclusions == "Works well"

    @pytest.mark.asyncio
    async def test_analyze_text_json_parse_failure(self):
        mock_llm = MockLLMClient(response="Not valid JSON")
        analyzer = PDFAnalyzer(llm_client=mock_llm)

        result = await analyzer.analyze_text(
            text="Content",
            title="Title",
            template_name="structured",
        )

        # Should not crash, raw output preserved
        assert result.formatted_output == "Not valid JSON"

    @pytest.mark.asyncio
    async def test_analyze_text_custom_template(self):
        mock_llm = MockLLMClient(response="Custom result")
        analyzer = PDFAnalyzer(llm_client=mock_llm)

        custom = AnalysisTemplate(
            name="custom",
            system_prompt="Custom system",
            user_prompt_template="Custom analysis of {title}: {text}",
            required_variables=["title", "text"],
        )

        result = await analyzer.analyze_text(
            text="Paper content",
            title="My Paper",
            template=custom,
        )

        assert result.template_name == "custom"
        assert "Custom analysis" in mock_llm.last_prompt
        assert "My Paper" in mock_llm.last_prompt

    @pytest.mark.asyncio
    async def test_analyze_text_markdown_parsing(self):
        md_response = (
            "## Summary\n"
            "This paper studies transformers.\n\n"
            "## Key Points\n"
            "- Attention is all you need\n"
            "- Transformers scale well\n\n"
            "## Methodology\n"
            "Self-attention mechanism\n\n"
            "## Conclusions\n"
            "Transformers are great\n"
        )
        mock_llm = MockLLMClient(response=md_response)
        analyzer = PDFAnalyzer(llm_client=mock_llm)

        result = await analyzer.analyze_text(
            text="Content", title="Title"
        )

        assert "transformers" in result.summary.lower()
        assert len(result.key_points) == 2
        assert "Self-attention" in result.methodology
        assert "great" in result.conclusions
