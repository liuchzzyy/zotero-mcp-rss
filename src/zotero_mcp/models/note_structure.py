"""
Structured note content models.

Defines Pydantic models for parsing and rendering structured AI-generated notes.
This allows complete control over note formatting independent of LLM output.
"""

from typing import Any, Literal
from pydantic import BaseModel, Field


class ContentBlock(BaseModel):
    """Base class for all content blocks."""

    type: Literal["heading", "paragraph", "bullet_list", "numbered_list", "quote", "code", "table", "hr"]


class HeadingBlock(ContentBlock):
    """Heading/title block."""

    type: Literal["heading"] = "heading"
    level: int = Field(..., ge=1, le=4, description="Heading level (1-4)")
    content: str = Field(..., description="Heading text")


class ParagraphBlock(ContentBlock):
    """Paragraph block."""

    type: Literal["paragraph"] = "paragraph"
    content: str = Field(..., description="Paragraph text")


class BulletListBlock(ContentBlock):
    """Bullet list block."""

    type: Literal["bullet_list"] = "bullet_list"
    items: list[str] = Field(..., description="List items")


class NumberedListBlock(ContentBlock):
    """Numbered list block."""

    type: Literal["numbered_list"] = "numbered_list"
    items: list[str] = Field(..., description="List items")


class QuoteBlock(ContentBlock):
    """Blockquote block."""

    type: Literal["quote"] = "quote"
    content: str = Field(..., description="Quote text")


class CodeBlock(ContentBlock):
    """Code block."""

    type: Literal["code"] = "code"
    language: str | None = Field(None, description="Programming language")
    content: str = Field(..., description="Code content")


class TableBlock(ContentBlock):
    """Table block."""

    type: Literal["table"] = "table"
    headers: list[str] = Field(..., description="Table headers")
    rows: list[list[str]] = Field(..., description="Table rows")


class HorizontalRuleBlock(ContentBlock):
    """Horizontal rule block."""

    type: Literal["hr"] = "hr"


# Type alias for any content block
AnyBlock = (
    HeadingBlock
    | ParagraphBlock
    | BulletListBlock
    | NumberedListBlock
    | QuoteBlock
    | CodeBlock
    | TableBlock
    | HorizontalRuleBlock
)


class StructuredNote(BaseModel):
    """Complete structured note."""

    title: str = Field(..., description="Note title")
    blocks: list[AnyBlock] = Field(..., description="Content blocks in order")


class StructuredAnalysisResponse(BaseModel):
    """Structured analysis response from LLM."""

    sections: list[AnyBlock] = Field(
        ..., description="Analysis sections in order"
    )
