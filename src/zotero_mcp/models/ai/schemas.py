"""Schemas for AI-related inputs and outputs."""

from __future__ import annotations

from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class AIProvider(str, Enum):
    """Supported AI providers."""

    AUTO = "auto"
    DEEPSEEK = "deepseek"
    CLAUDE_CLI = "claude-cli"
    OPENAI = "openai"
    GEMINI = "gemini"


class AIModelConfig(BaseModel):
    """Configuration for AI model selection."""

    provider: AIProvider = Field(default=AIProvider.AUTO, description="AI provider")
    model: str | None = Field(default=None, description="Model name")
    supports_images: bool = Field(
        default=False, description="Whether the model supports images"
    )
    max_input_tokens: int | None = Field(
        default=None, description="Optional max input tokens"
    )


class AIAnalysisInput(BaseModel):
    """Normalized input for AI analysis."""

    title: str = Field(..., description="Paper title")
    authors: str | None = Field(default=None, description="Authors")
    abstract: str | None = Field(default=None, description="Abstract")
    fulltext: str | None = Field(default=None, description="Full text content")
    annotations: list[dict[str, Any]] = Field(
        default_factory=list, description="Annotations"
    )
    images: list[dict[str, Any]] = Field(default_factory=list, description="Images")
    tables: list[dict[str, Any]] = Field(default_factory=list, description="Tables")
    template: str | None = Field(default=None, description="Analysis template")


class AIAnalysisResult(BaseModel):
    """Result of AI analysis."""

    content: str = Field(..., description="Generated analysis content")
    provider: AIProvider = Field(..., description="AI provider used")
    model: str | None = Field(default=None, description="Model name")
