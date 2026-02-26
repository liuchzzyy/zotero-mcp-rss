"""Tests for structured note parser recovery behavior."""

from zotero_mcp.models.zotero import ParagraphBlock
from zotero_mcp.services.note_parser import StructuredNoteParser


def test_recover_json_from_single_paragraph_block():
    """Should recover structured sections from a single paragraph containing JSON."""
    parser = StructuredNoteParser()

    blocks = [
        ParagraphBlock(
            content=(
                'prefix {"sections":[{"type":"heading","level":3,"text":"A"},'
                '{"type":"paragraph","text":"B"}]} suffix'
            )
        )
    ]
    recovered = parser._recover_json_from_single_block(blocks)

    assert recovered is not None
    assert len(recovered) == 2


def test_json_heading_strips_markdown_prefix_and_uses_inferred_level():
    parser = StructuredNoteParser()
    content = (
        '```json\n{"sections":[{"type":"heading","level":2,"text":"### 标题A"}]}\n```'
    )

    blocks = parser.parse(content)

    assert len(blocks) == 1
    assert blocks[0].type == "heading"
    assert blocks[0].level == 3
    assert blocks[0].content == "标题A"
