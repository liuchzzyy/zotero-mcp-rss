"""PDF analyzer orchestrating extraction, template rendering, and LLM analysis."""

from __future__ import annotations

import json
from pathlib import Path
import time

from zotero_mcp.analyzer.clients.base import BaseLLMClient
from zotero_mcp.analyzer.extractors.pdf_extractor import PDFExtractor
from zotero_mcp.analyzer.models.content import PDFContent
from zotero_mcp.analyzer.models.result import AnalysisResult
from zotero_mcp.analyzer.models.template import AnalysisTemplate
from zotero_mcp.analyzer.templates.template_manager import TemplateManager


class PDFAnalyzer:
    """
    PDF analysis orchestrator.

    Pipeline: extract PDF -> select template -> call LLM -> parse result
    """

    def __init__(
        self,
        llm_client: BaseLLMClient,
        template_manager: TemplateManager | None = None,
        extractor: PDFExtractor | None = None,
    ):
        self.llm_client = llm_client
        self.template_manager = template_manager or TemplateManager()
        self.extractor = extractor or PDFExtractor()

    async def analyze(
        self,
        file_path: str,
        template_name: str = "default",
        template: AnalysisTemplate | None = None,
        extract_images: bool = True,
        extract_tables: bool = False,
    ) -> AnalysisResult:
        """
        Analyze a PDF file.

        Args:
            file_path: Path to PDF
            template_name: Built-in template name (if template is None)
            template: Custom template (overrides template_name)
            extract_images: Whether to extract images
            extract_tables: Whether to extract tables

        Returns:
            AnalysisResult
        """
        start_time = time.time()

        # 1. Select template
        if template is None:
            template = self.template_manager.get_template(template_name)

        # 2. Extract content
        self.extractor.extract_images = extract_images
        self.extractor.extract_tables = extract_tables
        content = await self.extractor.extract(file_path)

        # 3. Build prompt
        user_prompt = self._build_prompt(template, content)

        # 4. Prepare multi-modal input
        images = None
        if (
            template.supports_multimodal
            and content.has_images
            and self.llm_client.supports_vision()
        ):
            images = [img.data_base64 for img in content.images[:10] if img.data_base64]

        # 5. Call LLM
        raw_output = await self.llm_client.analyze(
            prompt=user_prompt,
            system_prompt=template.system_prompt,
            images=images,
            max_tokens=template.max_tokens,
            temperature=template.temperature,
        )

        # 6. Parse output
        result = self._parse_result(
            file_path=file_path,
            template_name=template.name,
            raw_output=raw_output,
            template=template,
        )

        # 7. Record performance
        result.processing_time = time.time() - start_time
        info = self.llm_client.get_model_info()
        result.llm_provider = info["provider"]
        result.model = self.llm_client.model

        return result

    async def analyze_text(
        self,
        text: str,
        title: str = "Untitled",
        template_name: str = "default",
        template: AnalysisTemplate | None = None,
    ) -> AnalysisResult:
        """
        Analyze pre-extracted text (no PDF extraction step).

        Args:
            text: Paper text content
            title: Paper title
            template_name: Template to use
            template: Custom template override

        Returns:
            AnalysisResult
        """
        start_time = time.time()

        if template is None:
            template = self.template_manager.get_template(template_name)

        variables = {
            "title": title,
            "text": text[:10000],
            "page_count": 0,
            "has_images": False,
            "has_tables": False,
            "image_count": 0,
            "table_count": 0,
        }
        user_prompt = template.render(**variables)

        raw_output = await self.llm_client.analyze(
            prompt=user_prompt,
            system_prompt=template.system_prompt,
            max_tokens=template.max_tokens,
            temperature=template.temperature,
        )

        result = self._parse_result(
            file_path="<text-input>",
            template_name=template.name,
            raw_output=raw_output,
            template=template,
        )
        result.processing_time = time.time() - start_time
        info = self.llm_client.get_model_info()
        result.llm_provider = info["provider"]
        result.model = self.llm_client.model

        return result

    def _build_prompt(
        self,
        template: AnalysisTemplate,
        content: PDFContent,
    ) -> str:
        """Build prompt from template and content."""
        variables = {
            "title": content.metadata.get("title", Path(content.file_path).stem),
            "text": content.text[:10000],
            "page_count": content.total_pages,
            "has_images": content.has_images,
            "has_tables": content.has_tables,
            "image_count": len(content.images),
            "table_count": len(content.tables),
        }
        return template.render(**variables)

    def _parse_result(
        self,
        file_path: str,
        template_name: str,
        raw_output: str,
        template: AnalysisTemplate,
    ) -> AnalysisResult:
        """Parse LLM output into AnalysisResult."""
        result = AnalysisResult(
            file_path=file_path,
            template_name=template_name,
            raw_output=raw_output,
        )

        if template.output_format == "json":
            self._parse_json_output(result, raw_output)
        elif template.output_format == "markdown":
            self._parse_markdown_output(result, raw_output)
        else:
            result.formatted_output = raw_output
            result.summary = raw_output[:500]

        return result

    def _parse_json_output(self, result: AnalysisResult, raw_output: str) -> None:
        """Parse JSON-formatted LLM output."""
        try:
            data = json.loads(raw_output)
            result.summary = data.get("summary", "")
            result.key_points = data.get("key_points", [])
            result.methodology = data.get("methodology", "")
            result.conclusions = data.get("conclusions", "")
            result.formatted_output = json.dumps(data, indent=2, ensure_ascii=False)
        except json.JSONDecodeError:
            result.formatted_output = raw_output

    def _parse_markdown_output(self, result: AnalysisResult, raw_output: str) -> None:
        """Parse Markdown-formatted LLM output."""
        section_map = {
            "summary": "summary",
            "key points": "key_points",
            "key innovations": "key_points",
            "methodology": "methodology",
            "research method": "methodology",
            "conclusions": "conclusions",
            "main conclusions": "conclusions",
        }

        current_field: str | None = None
        current_lines: list[str] = []

        for line in raw_output.split("\n"):
            if line.startswith("## "):
                # Save previous section
                self._save_section(result, current_field, current_lines)
                # Detect new section
                heading = line[3:].strip().lower()
                current_field = section_map.get(heading)
                current_lines = []
            else:
                current_lines.append(line)

        # Save last section
        self._save_section(result, current_field, current_lines)
        result.formatted_output = raw_output

    @staticmethod
    def _save_section(
        result: AnalysisResult,
        field: str | None,
        lines: list[str],
    ) -> None:
        """Save parsed section content to result."""
        if not field:
            return
        text = "\n".join(lines).strip()
        if field == "summary":
            result.summary = text
        elif field == "key_points":
            result.key_points = [
                line.strip().lstrip("-*").strip() for line in lines if line.strip()
            ]
        elif field == "methodology":
            result.methodology = text
        elif field == "conclusions":
            result.conclusions = text
