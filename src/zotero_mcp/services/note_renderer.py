"""
Renderer for structured notes.

Converts ContentBlock objects into formatted HTML with controlled styling.
"""

import re

from zotero_mcp.models.zotero import (
    AnyBlock,
    BulletListBlock,
    CodeBlock,
    HeadingBlock,
    HorizontalRuleBlock,
    NumberedListBlock,
    ParagraphBlock,
    QuoteBlock,
    TableBlock,
)
from zotero_mcp.utils.logging_config import get_logger
from zotero_mcp.utils.templates import get_note_theme_config

logger = get_logger(__name__)


class StructuredNoteRenderer:
    """Render structured note blocks into HTML."""

    def __init__(self):
        self.theme = get_note_theme_config()

    def render(self, blocks: list[AnyBlock], title: str = "") -> str:
        """
        Render blocks into HTML.

        Args:
            blocks: List of ContentBlock objects
            title: Optional note title

        Returns:
            Formatted HTML string
        """
        html_parts = []

        # Add container
        container_style = (
            f"max-width: {self.theme['max_width']}; "
            "font-size: 1rem; "
            "color: black; "
            "line-height: 1.6; "
            "word-spacing: 0; "
            "letter-spacing: 0; "
            'font-family: Optima-Regular, Optima, PingFangSC-light, PingFangTC-light, "PingFang SC", Cambria, Cochin, Georgia, Times, "Times New Roman", serif; '
            "padding: 10px;"
        )
        html_parts.append(f'<div style="{container_style}">')

        # Add title if provided
        if title:
            h1_style = (
                f"font-size: 1.5rem; "
                f"margin: {self.theme.get('h1_margin', '0.8em')} 0 0.6em; "
                "padding: 0; "
                "font-weight: bold; "
                "color: black;"
            )
            html_parts.append(f'<h1 style="{h1_style}">AI分析 - {title}</h1>')

        # Render each block
        for block in blocks:
            block_html = self._render_block(block)
            if block_html:
                html_parts.append(block_html)

        html_parts.append("</div>")

        return "".join(html_parts)

    def _render_block(self, block: AnyBlock) -> str:
        """Render a single block."""
        if isinstance(block, HeadingBlock):
            return self._render_heading(block)
        elif isinstance(block, ParagraphBlock):
            return self._render_paragraph(block)
        elif isinstance(block, BulletListBlock):
            return self._render_bullet_list(block)
        elif isinstance(block, NumberedListBlock):
            return self._render_numbered_list(block)
        elif isinstance(block, QuoteBlock):
            return self._render_quote(block)
        elif isinstance(block, CodeBlock):
            return self._render_code(block)
        elif isinstance(block, TableBlock):
            return self._render_table(block)
        elif isinstance(block, HorizontalRuleBlock):
            return self._render_hr(block)
        else:
            logger.warning(f"Unknown block type: {type(block)}")
            return ""

    def _render_heading(self, block: HeadingBlock) -> str:
        """Render heading block."""
        if block.level == 1:
            margin_key = "h1_margin"
            font_size = "1.5rem"
        elif block.level == 2:
            margin_key = "h2_margin"
            font_size = "1.3rem"
        elif block.level == 3:
            margin_key = "h3_margin"
            font_size = "1.3rem"
        else:  # level 4
            margin_key = "h4_margin"
            font_size = "1.2rem"

        margin = self.theme.get(margin_key, "0.8em")

        # H2 gets special styling (orange background)
        if block.level == 2:
            style = (
                f"font-size: {font_size}; "
                f"margin: {margin} 0 0.6em; "
                "padding: 8px 15px; "
                "font-weight: bold; "
                f"background: {self.theme['h2_background']}; "
                f"color: {self.theme['h2_color']}; "
                f"border-bottom: 2px solid {self.theme['primary_color']}; "
                "border-radius: 3px; "
                "display: block;"
            )
        else:
            style = (
                f"font-size: {font_size}; "
                f"margin: {margin} 0 0.5em; "
                "padding: 0; "
                "font-weight: bold; "
                f"color: {self.theme['primary_color']};"
            )

        tag = f"h{block.level}"
        return f'<{tag} style="{style}">{block.content}</{tag}>'

    def _render_paragraph(self, block: ParagraphBlock) -> str:
        """Render paragraph block with optional citations."""
        margin = self.theme.get("paragraph_margin", "0.2em")
        style = f"margin: {margin} 0; line-height: 1.6; color: black;"

        # Render paragraph content
        content = block.content

        # Add citations if present
        if block.citations:
            citation_html = self._render_citations(block.citations)
            content = f"{content}\n{citation_html}"

        return f'<p style="{style}">{content}</p>'

    def _render_bullet_list(self, block: BulletListBlock) -> str:
        """Render bullet list block with optional citations per item."""
        margin = self.theme.get("list_margin", "0.2em")
        item_margin = self.theme.get("list_item_margin", "0.2em")

        style = (
            f"margin: {margin} 0; "
            "padding-left: 25px; "
            "color: black; "
            "list-style-type: disc;"
        )
        item_style = f"margin: {item_margin} 0; line-height: 1.6; color: rgb(1,1,1);"

        items_html = "\n".join(
            f'<li style="{item_style}">{self._format_list_item(item)}</li>'
            for item in block.items
        )

        return f'<ul style="{style}">\n{items_html}\n</ul>'

    def _render_numbered_list(self, block: NumberedListBlock) -> str:
        """Render numbered list block."""
        margin = self.theme.get("list_margin", "0.2em")
        item_margin = self.theme.get("list_item_margin", "0.2em")

        style = (
            f"margin: {margin} 0; "
            "padding-left: 25px; "
            "color: black; "
            "list-style-type: decimal;"
        )
        item_style = f"margin: {item_margin} 0; line-height: 1.6; color: rgb(1,1,1);"

        items_html = "\n".join(
            f'<li style="{item_style}">{self._format_list_item(item)}</li>'
            for item in block.items
        )

        return f'<ol style="{style}">\n{items_html}\n</ol>'

    def _render_quote(self, block: QuoteBlock) -> str:
        """Render blockquote block."""
        margin = self.theme.get("list_margin", "0.2em")

        style = (
            "display: block; "
            "font-size: 0.9em; "
            f"margin: {margin} 0; "
            "padding: 10px 10px 10px 20px; "
            f"border-left: 4px solid {self.theme['blockquote_border']}; "
            f"background: {self.theme['blockquote_background']}; "
            "color: #6a737d; "
            "overflow: auto;"
        )

        return f'<blockquote style="{style}">{block.content}</blockquote>'

    def _render_code(self, block: CodeBlock) -> str:
        """Render code block."""
        margin = self.theme.get("list_margin", "0.2em")

        style = (
            "display: block; "
            "font-size: 0.9rem; "
            f"margin: {margin} 0; "
            "padding: 1em; "
            f"background: {self.theme['code_background']}; "
            f"color: {self.theme['code_color']}; "
            "border-radius: 4px; "
            "overflow-x: auto; "
            "font-family: Operator Mono, Consolas, Monaco, Menlo, monospace; "
            "white-space: pre-wrap;"
        )

        return f'<pre style="{style}"><code>{block.content}</code></pre>'

    def _render_table(self, block: TableBlock) -> str:
        """Render table block."""
        margin = self.theme.get("list_margin", "0.2em")

        table_style = f"margin: {margin} 0; border-collapse: collapse; width: 100%;"

        # Header
        headers_html = "\n".join(
            f'<th style="border: 1px solid #ccc; padding: 8px; text-align: left; font-weight: bold; background-color: #f0f0f0;">{header}</th>'
            for header in block.headers
        )

        # Rows
        rows_html = []
        for row in block.rows:
            cells_html = "\n".join(
                f'<td style="border: 1px solid #ccc; padding: 8px; text-align: left;">{cell}</td>'
                for cell in row
            )
            rows_html.append(f"<tr>{cells_html}</tr>")

        return f'<table style="{table_style}">\n<tr>{headers_html}</tr>\n{"".join(rows_html)}\n</table>'

    def _render_hr(self, block: HorizontalRuleBlock) -> str:
        """Render horizontal rule."""
        style = "margin: 1em 0; border: 0; border-top: 1px solid #e0e0e0;"
        return f'<hr style="{style}"/>'

    def _format_list_item(self, item) -> str:
        """Format list item text, preserving bold markers and adding citations."""

        # Handle both string and ListItemWithCitation
        if isinstance(item, str):
            text = item
            citations = []
        else:
            text = item.text
            citations = item.citations

        # Convert **bold** to HTML
        text = re.sub(
            r"\*\*(.*?)\*\*",
            r'<b style="font-weight: bold; color: rgb(239, 112, 96);">\1</b>',
            text,
        )

        # Add citations if present
        if citations:
            citation_html = self._render_citations(citations)
            return f"{text}\n{citation_html}"
        return text

    def _render_citations(self, citations) -> str:
        """Render citations with source locations."""
        if not citations:
            return ""

        citation_style = (
            "display: block; "
            "margin: 0.5em 0; "
            "padding: 8px 12px; "
            "background: #f8f9fa; "
            "border-left: 3px solid rgb(239, 112, 96); "
            "font-size: 0.85em; "
            "color: #495057; "
            "line-height: 1.4;"
        )

        location_style = (
            "display: block; "
            "font-weight: bold; "
            "color: rgb(239, 112, 96); "
            "margin-bottom: 4px;"
        )

        citations_html = []
        for citation in citations:
            location = citation.location
            content = citation.content
            citations_html.append(
                f'<div style="{citation_style}">'
                f'<span style="{location_style}">📍 {location}</span>'
                f"<span>{content}</span>"
                f"</div>"
            )

        return "\n".join(citations_html)


# Singleton instance
_renderer: StructuredNoteRenderer | None = None


def get_structured_note_renderer() -> StructuredNoteRenderer:
    """Get singleton renderer instance."""
    global _renderer
    if _renderer is None:
        _renderer = StructuredNoteRenderer()
    return _renderer
