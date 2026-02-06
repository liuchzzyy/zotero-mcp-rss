"""Tests for template manager."""

import pytest

from paper_analyzer.models.template import AnalysisTemplate
from paper_analyzer.templates.template_manager import TemplateManager


class TestTemplateManager:
    def test_list_builtin_templates(self):
        mgr = TemplateManager()
        templates = mgr.list_templates()
        assert "default" in templates
        assert "multimodal" in templates
        assert "structured" in templates

    def test_get_default_template(self):
        mgr = TemplateManager()
        t = mgr.get_template("default")
        assert t.name == "default"
        assert "title" in t.required_variables
        assert "text" in t.required_variables

    def test_get_multimodal_template(self):
        mgr = TemplateManager()
        t = mgr.get_template("multimodal")
        assert t.supports_multimodal is True

    def test_get_structured_template(self):
        mgr = TemplateManager()
        t = mgr.get_template("structured")
        assert t.output_format == "json"
        assert t.output_schema is not None

    def test_get_nonexistent_template(self):
        mgr = TemplateManager()
        with pytest.raises(KeyError, match="not found"):
            mgr.get_template("nonexistent")

    def test_register_custom_template(self):
        mgr = TemplateManager()
        custom = AnalysisTemplate(
            name="custom",
            system_prompt="Custom system",
            user_prompt_template="Custom: {title}",
            required_variables=["title"],
        )
        mgr.register_template(custom)

        t = mgr.get_template("custom")
        assert t.name == "custom"
        assert "custom" in mgr.list_templates()

    def test_custom_overrides_builtin(self):
        mgr = TemplateManager()
        custom = AnalysisTemplate(
            name="default",
            system_prompt="Overridden",
            user_prompt_template="Overridden: {title}",
            required_variables=["title"],
        )
        mgr.register_template(custom)

        t = mgr.get_template("default")
        assert t.system_prompt == "Overridden"
