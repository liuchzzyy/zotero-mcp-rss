"""Analysis template model."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class AnalysisTemplate(BaseModel):
    """Analysis template configuration."""

    name: str = Field(..., description="Template name")
    description: str = Field(default="", description="Template description")
    version: str = Field(default="1.0", description="Template version")

    # Prompt configuration
    system_prompt: str = Field(..., description="System prompt")
    user_prompt_template: str = Field(
        ..., description="User prompt template (supports {variables})"
    )

    # Output configuration
    output_format: str = Field(
        default="markdown",
        description="Output format: markdown, json, html",
    )
    output_schema: dict[str, Any] | None = Field(None, description="Output JSON Schema")

    # Feature configuration
    supports_multimodal: bool = Field(
        default=False, description="Whether template supports multi-modal input"
    )
    max_tokens: int = Field(default=4000, description="Max output tokens")
    temperature: float = Field(default=0.7, ge=0.0, le=2.0, description="Temperature")

    # Variable definitions
    required_variables: list[str] = Field(
        default_factory=list, description="Required variables"
    )
    optional_variables: list[str] = Field(
        default_factory=list, description="Optional variables"
    )

    def render(self, **kwargs: Any) -> str:
        """Render the prompt template with variables."""
        missing = [v for v in self.required_variables if v not in kwargs]
        if missing:
            raise ValueError(f"Missing required variables: {missing}")
        return self.user_prompt_template.format(**kwargs)

    def validate_output(self, output: str) -> bool:
        """Validate output format."""
        if self.output_format == "json" and self.output_schema:
            import json

            try:
                data = json.loads(output)
                return all(
                    key in data for key in self.output_schema.get("required", [])
                )
            except json.JSONDecodeError:
                return False
        return True
