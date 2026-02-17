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
