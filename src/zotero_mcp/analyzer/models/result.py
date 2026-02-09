"""Analysis result model."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class AnalysisResult(BaseModel):
    """LLM analysis result."""

    file_path: str = Field(..., description="PDF file path")
    template_name: str = Field(..., description="Template used")
    analyzed_at: datetime = Field(
        default_factory=datetime.now, description="Analysis timestamp"
    )

    # LLM info
    llm_provider: str = Field(default="", description="LLM provider")
    model: str = Field(default="", description="Model name")

    # Parsed output
    summary: str = Field(default="", description="Paper summary")
    key_points: list[str] = Field(default_factory=list, description="Key points")
    methodology: str = Field(default="", description="Methodology")
    conclusions: str = Field(default="", description="Conclusions")

    # Raw output
    raw_output: str = Field(..., description="Raw LLM output")
    formatted_output: str = Field(default="", description="Formatted output")

    # Metadata
    metadata: dict[str, Any] = Field(default_factory=dict, description="Extra metadata")

    # Performance
    tokens_used: int = Field(default=0, description="Tokens consumed")
    processing_time: float = Field(
        default=0.0, description="Processing time in seconds"
    )
