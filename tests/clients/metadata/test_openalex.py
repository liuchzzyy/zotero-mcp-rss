"""Tests for OpenAlex metadata parsing robustness."""

from zotero_mcp.clients.metadata.openalex import OpenAlexWork


def test_openalex_from_api_response_handles_nullable_fields():
    """Should parse OpenAlex payloads even when optional fields are null."""
    payload = {
        "doi": None,
        "title": None,
        "display_name": "Fallback Title",
        "authorships": None,
        "primary_location": None,
        "publication_year": 2024,
        "abstract_inverted_index": None,
        "concepts": None,
        "grants": None,
        "locations": None,
        "type": "article",
    }

    work = OpenAlexWork.from_api_response(payload)

    assert work.title == "Fallback Title"
    assert work.doi == ""
    assert work.authors == []
    assert work.subjects == []
    assert work.funders == []
    assert work.item_type == "journalArticle"


def test_openalex_from_api_response_handles_mixed_invalid_types():
    """Should ignore malformed nested fields rather than crashing."""
    payload = {
        "doi": 123,
        "title": "Typed Payload",
        "authorships": [{"author": {"display_name": "A. Author"}}, "bad"],
        "primary_location": {"source": {"display_name": "J", "abbreviated_title": "J."}},
        "abstract_inverted_index": {"hello": [0], "bad": None},
        "concepts": [{"display_name": "AI", "score": 0.5}, None],
        "grants": [{"funder": {"display_name": "NSF"}, "award_id": "123"}],
        "locations": [{"source": {"type": "pdf"}, "pdf_url": "https://x/y.pdf"}],
        "type": "article",
    }

    work = OpenAlexWork.from_api_response(payload)

    assert work.title == "Typed Payload"
    assert work.authors == ["A. Author"]
    assert work.journal == "J"
    assert work.journal_abbrev == "J."
    assert work.abstract == "hello"
    assert work.subjects == ["AI"]
    assert work.funders == ["NSF (Award: 123)"]
    assert work.pdf_url == "https://x/y.pdf"

