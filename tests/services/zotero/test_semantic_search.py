from pathlib import Path
from unittest.mock import MagicMock

import pytest

from zotero_mcp.services.zotero.semantic_search import ZoteroSemanticSearch


@pytest.fixture
def semantic_search(monkeypatch, tmp_path):
    mock_chroma = MagicMock()
    mock_zotero_wrapper = MagicMock()
    mock_zotero_wrapper.client = MagicMock()

    monkeypatch.setattr(
        "zotero_mcp.services.zotero.semantic_search.create_chroma_client",
        lambda config_path=None: mock_chroma,
    )
    monkeypatch.setattr(
        "zotero_mcp.services.zotero.semantic_search.get_zotero_client",
        lambda: mock_zotero_wrapper,
    )

    return ZoteroSemanticSearch(config_path=str(tmp_path / "config.json"))


def test_should_update_daily_with_invalid_last_update(semantic_search):
    semantic_search.update_config = {
        "auto_update": True,
        "update_frequency": "daily",
        "last_update": "not-a-date",
    }

    assert semantic_search.should_update_database() is True


def test_should_update_every_n_with_invalid_last_update(semantic_search):
    semantic_search.update_config = {
        "auto_update": True,
        "update_frequency": "every_3",
        "last_update": {"bad": "type"},
    }

    assert semantic_search.should_update_database() is True


def test_should_not_update_every_with_non_positive_days(semantic_search):
    semantic_search.update_config = {
        "auto_update": True,
        "update_frequency": "every_0",
        "last_update": None,
    }

    assert semantic_search.should_update_database() is False


def test_local_db_fallback_preserves_treated_limit(semantic_search, monkeypatch):
    class BrokenLocalDatabaseClient:
        def __init__(self, *args, **kwargs):
            msg = "db init failed"
            raise RuntimeError(msg)

    monkeypatch.setattr(
        "zotero_mcp.services.zotero.semantic_search.LocalDatabaseClient",
        BrokenLocalDatabaseClient,
    )

    captured = {}

    def fake_get_items_from_api(scan_limit=100, treated_limit=None):
        captured["scan_limit"] = scan_limit
        captured["treated_limit"] = treated_limit
        return []

    semantic_search._get_items_from_api = fake_get_items_from_api

    result = semantic_search._get_items_from_local_db(
        scan_limit=77,
        treated_limit=12,
        extract_fulltext=True,
    )

    assert result == []
    assert captured["scan_limit"] == 77
    assert captured["treated_limit"] == 12


def test_search_returns_empty_for_non_positive_limit(semantic_search):
    result = semantic_search.search(query="battery", limit=0)

    assert result["query"] == "battery"
    assert result["results"] == []
    assert result["total_found"] == 0


def test_enrich_search_results_handles_empty_nested_lists(semantic_search):
    chroma_results = {
        "ids": [],
        "distances": [],
        "documents": [],
        "metadatas": [],
    }

    enriched = semantic_search._enrich_search_results(chroma_results, query="q")

    assert enriched == []


def test_get_items_from_api_raises_runtime_error_on_connection_refused(
    semantic_search,
):
    semantic_search.zotero_client.items = MagicMock(
        side_effect=Exception("Connection refused by local Zotero API")
    )

    with pytest.raises(RuntimeError, match="Cannot connect to Zotero local API"):
        semantic_search._get_items_from_api(scan_limit=10, treated_limit=5)


def test_get_items_from_api_excludes_attachment_note_and_annotation(semantic_search):
    semantic_search.zotero_client.items = MagicMock(
        side_effect=[
            [
                {"key": "A1", "data": {"itemType": "journalArticle", "title": "A"}},
                {"key": "B1", "data": {"itemType": "attachment"}},
                {"key": "C1", "data": {"itemType": "note"}},
                {"key": "D1", "data": {"itemType": "annotation"}},
                {"key": "E1", "data": {"itemType": "book", "title": "E"}},
            ],
            [],
        ]
    )

    result = semantic_search._get_items_from_api(scan_limit=10, treated_limit=None)

    assert [item["key"] for item in result] == ["A1", "E1"]


def test_get_items_from_local_db_builds_note_and_pdf_fragments(
    semantic_search, monkeypatch
):
    class FakeItem:
        item_id = 1
        key = "ITEM1"
        item_type = "journalArticle"
        title = "Parent"
        abstract = "Abstract"
        extra = ""
        date_added = "2026-02-23T00:00:00"
        date_modified = "2026-02-23T00:00:00"
        creators = "Smith, Alice"
        notes = "legacy note field"
        tags = ["t1"]
        annotations = []

    class FakeLocalDatabaseClient:
        def __init__(self, *args, **kwargs):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return None

        def get_items(self, limit=None, include_fulltext=False):
            return [FakeItem()]

        def get_item_notes(self, parent_item_id):
            return [{"key": "NOTE1", "note": "<p>Note content</p>"}]

        def iter_pdf_attachments(self, parent_item_id):
            return [("PDF1", Path("paper.pdf"))]

        def _extract_pdf_text(self, file_path):
            return "PDF content for fragment indexing."

    monkeypatch.setattr(
        "zotero_mcp.services.zotero.semantic_search.LocalDatabaseClient",
        FakeLocalDatabaseClient,
    )

    rows = semantic_search._get_items_from_local_db(
        treated_limit=10,
        extract_fulltext=True,
    )

    assert any(
        not row.get("__semantic_fragment__") and row["key"] == "ITEM1"
        for row in rows
    )
    fragment_types = {
        row["metadata"]["fragment_type"]
        for row in rows
        if row.get("__semantic_fragment__")
    }
    assert fragment_types == {"note", "pdf"}


def test_process_item_batch_supports_item_and_fragment_records(semantic_search):
    semantic_search.chroma_client.upsert_documents = MagicMock()

    batch = [
        {"key": "ITEM1", "data": {"title": "Parent item title", "itemType": "book"}},
        {
            "key": "ITEM1::note::NOTE1::1",
            "__semantic_fragment__": True,
            "document": "Note fragment text",
            "metadata": {"item_key": "ITEM1", "fragment_type": "note"},
        },
    ]

    stats = semantic_search._process_item_batch(batch)

    assert stats == {
        "processed": 2,
        "added": 2,
        "updated": 0,
        "skipped": 0,
        "errors": 0,
    }
    documents, metadatas, ids = (
        semantic_search.chroma_client.upsert_documents.call_args.args
    )
    assert ids == ["ITEM1", "ITEM1::note::NOTE1::1"]
    assert documents[1] == "Note fragment text"
    assert metadatas[0]["fragment_type"] == "item"
    assert metadatas[1]["fragment_type"] == "note"


def test_enrich_search_results_uses_parent_item_key_for_fragment_result(
    semantic_search,
):
    semantic_search.zotero_client.item = MagicMock(
        return_value={"data": {"title": "Parent item"}}
    )
    chroma_results = {
        "ids": [["ITEM1::pdf::PDF1::1"]],
        "distances": [[0.2]],
        "documents": [["PDF chunk"]],
        "metadatas": [[{"item_key": "ITEM1", "fragment_type": "pdf"}]],
    }

    enriched = semantic_search._enrich_search_results(chroma_results, query="q")

    assert len(enriched) == 1
    assert enriched[0]["item_key"] == "ITEM1"
    assert enriched[0]["result_id"] == "ITEM1::pdf::PDF1::1"
    semantic_search.zotero_client.item.assert_called_once_with("ITEM1")


def test_chunk_text_truncates_large_source(semantic_search):
    semantic_search.extraction_config["chunk_size"] = 8
    semantic_search.extraction_config["chunk_overlap"] = 2
    semantic_search.extraction_config["max_source_chars"] = 20

    chunks = semantic_search._chunk_text("x" * 100)

    assert chunks == ["xxxxxxxx", "xxxxxxxx", "xxxxxxxx"]


def test_collect_local_fragments_skips_pdf_on_memory_error(
    semantic_search, monkeypatch
):
    class FakeReader:
        def get_item_notes(self, parent_item_id):
            return [{"key": "NOTE1", "note": "normal note"}]

        def iter_pdf_attachments(self, parent_item_id):
            return [("PDF1", Path("paper.pdf"))]

        def _extract_pdf_text(self, file_path):
            return "PDF BIG CONTENT"

    class FakeItem:
        item_id = 1
        key = "ITEM1"

    def fake_chunk(text: str):
        if "PDF" in text:
            raise MemoryError("simulated oom")
        return ["note chunk"]

    monkeypatch.setattr(semantic_search, "_chunk_text", fake_chunk)

    records = semantic_search._collect_local_fragment_records(
        reader=FakeReader(),
        item=FakeItem(),
        parent_item={
            "key": "ITEM1",
            "data": {"itemType": "journalArticle", "title": "Parent"},
        },
        extract_fulltext=True,
    )

    assert len(records) == 1
    assert records[0]["metadata"]["fragment_type"] == "note"
