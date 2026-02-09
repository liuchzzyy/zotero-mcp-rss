"""Template manager with built-in and custom templates."""

from __future__ import annotations

import json
from pathlib import Path

from zotero_mcp.analyzer.models.template import AnalysisTemplate

# Built-in templates
_DEFAULT_TEMPLATE = AnalysisTemplate(
    name="default",
    description="Default paper analysis template",
    version="1.0",
    system_prompt=(
        "You are a professional academic paper analysis assistant. "
        "Analyze the provided paper content and extract key information."
    ),
    user_prompt_template=(
        "Please analyze the following paper:\n\n"
        "Title: {title}\n"
        "Pages: {page_count}\n\n"
        "Paper content:\n{text}\n\n"
        "Please provide:\n"
        "1. Research summary\n"
        "2. Key innovations (3-5)\n"
        "3. Methodology\n"
        "4. Main conclusions\n\n"
        "Output in Markdown format."
    ),
    output_format="markdown",
    supports_multimodal=False,
    max_tokens=2000,
    temperature=0.7,
    required_variables=["title", "text"],
    optional_variables=["page_count", "has_images", "has_tables"],
)

_MULTIMODAL_TEMPLATE = AnalysisTemplate(
    name="multimodal",
    description="Multi-modal paper analysis template (with images)",
    version="1.0",
    system_prompt=(
        "You are a professional academic paper analysis assistant "
        "with the ability to understand images and charts."
    ),
    user_prompt_template=(
        "Please analyze the following paper (with images):\n\n"
        "Title: {title}\n"
        "Pages: {page_count}\n"
        "Images: {image_count}\n\n"
        "Paper content:\n{text}\n\n"
        "Please analyze the paper including any figures and charts."
    ),
    output_format="markdown",
    supports_multimodal=True,
    max_tokens=3000,
    temperature=0.7,
    required_variables=["title", "text"],
    optional_variables=["page_count", "image_count"],
)

_STRUCTURED_TEMPLATE = AnalysisTemplate(
    name="structured",
    description="Structured output template (JSON)",
    version="1.0",
    system_prompt=(
        "You are a professional academic paper analysis assistant. "
        "Output analysis results in structured JSON format."
    ),
    user_prompt_template=(
        "Please analyze the following paper and output JSON:\n\n"
        "Title: {title}\n"
        "Content: {text}\n\n"
        "Output format:\n"
        "{{\n"
        '  "summary": "Research summary",\n'
        '  "key_points": ["Point 1", "Point 2"],\n'
        '  "methodology": "Research method",\n'
        '  "conclusions": "Main conclusions"\n'
        "}}"
    ),
    output_format="json",
    output_schema={
        "type": "object",
        "required": ["summary", "key_points", "methodology", "conclusions"],
    },
    supports_multimodal=False,
    max_tokens=2000,
    temperature=0.5,
    required_variables=["title", "text"],
)


class TemplateManager:
    """Manages built-in and custom analysis templates."""

    BUILTIN_TEMPLATES: dict[str, AnalysisTemplate] = {
        "default": _DEFAULT_TEMPLATE,
        "multimodal": _MULTIMODAL_TEMPLATE,
        "structured": _STRUCTURED_TEMPLATE,
    }

    def __init__(self, custom_templates_dir: Path | None = None):
        self.custom_templates_dir = custom_templates_dir
        self._custom: dict[str, AnalysisTemplate] = {}

        if custom_templates_dir and custom_templates_dir.exists():
            self._load_custom_templates()

    def get_template(self, name: str) -> AnalysisTemplate:
        """Get a template by name (custom takes priority)."""
        if name in self._custom:
            return self._custom[name]
        if name in self.BUILTIN_TEMPLATES:
            return self.BUILTIN_TEMPLATES[name]
        raise KeyError(
            f"Template '{name}' not found. Available: {self.list_templates()}"
        )

    def list_templates(self) -> list[str]:
        """List all available template names."""
        names = set(self.BUILTIN_TEMPLATES.keys())
        names.update(self._custom.keys())
        return sorted(names)

    def register_template(self, template: AnalysisTemplate) -> None:
        """Register a custom template."""
        self._custom[template.name] = template

    def _load_custom_templates(self) -> None:
        """Load custom templates from JSON files in directory."""
        if not self.custom_templates_dir:
            return
        for path in self.custom_templates_dir.glob("*.json"):
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
                template = AnalysisTemplate(**data)
                self._custom[template.name] = template
            except Exception:
                continue
