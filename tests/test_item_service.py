"""
Tests for ItemService.
"""

from unittest.mock import AsyncMock, MagicMock

import pytest

from zotero_mcp.clients.zotero import ZoteroAPIClient
from zotero_mcp.services.zotero.item_service import ItemService, _normalize_url


@pytest.fixture
def mock_api_client():
    client = AsyncMock(spec=ZoteroAPIClient)
    return client


@pytest.fixture
def item_service(mock_api_client):
    return ItemService(api_client=mock_api_client)


@pytest.mark.asyncio
async def test_get_item(item_service, mock_api_client):
    mock_api_client.get_item.return_value = {
        "key": "ABC12345",
        "data": {"title": "Test Item"},
    }

    item = await item_service.get_item("ABC12345")

    assert item["key"] == "ABC12345"
    mock_api_client.get_item.assert_awaited_once_with("ABC12345")


@pytest.mark.asyncio
async def test_create_note(item_service, mock_api_client):
    mock_api_client.create_note.return_value = {
        "key": "NOTE123",
        "data": {"note": "<p>Test</p>"},
    }

    note = await item_service.create_note("ABC12345", "<p>Test</p>", ["tag1"])

    assert note["key"] == "NOTE123"
    mock_api_client.create_note.assert_awaited_once_with(
        "ABC12345", "<p>Test</p>", ["tag1"]
    )


@pytest.mark.asyncio
async def test_get_collections(item_service, mock_api_client):
    mock_api_client.get_collections.return_value = [
        {"key": "COLL1", "data": {"name": "Collection 1"}}
    ]

    collections = await item_service.get_collections()

    assert len(collections) == 1
    assert collections[0]["key"] == "COLL1"
    mock_api_client.get_collections.assert_awaited_once()


@pytest.mark.asyncio
async def test_create_items_skips_library_duplicate_by_doi(
    item_service, mock_api_client, monkeypatch
):
    monkeypatch.delenv("ZOTERO_PRECREATE_DEDUP", raising=False)
    mock_api_client.search_items.return_value = [
        {"data": {"DOI": "10.1000/xyz", "title": "Existing", "date": "2024"}}
    ]

    result = await item_service.create_items(
        [{"itemType": "journalArticle", "title": "New", "DOI": "10.1000/xyz"}]
    )

    assert result["created"] == 0
    assert result["failed_count"] == 0
    assert result["skipped_duplicates"] == 1
    mock_api_client.create_items.assert_not_called()


@pytest.mark.asyncio
async def test_create_items_skips_intra_batch_duplicates(item_service, mock_api_client):
    mock_api_client.search_items.return_value = []
    mock_api_client.create_items.return_value = {
        "successful": {"0": "AAA"},
        "failed": {},
    }

    result = await item_service.create_items(
        [
            {"itemType": "journalArticle", "title": "Paper A", "DOI": "10.1000/abc"},
            {
                "itemType": "journalArticle",
                "title": "Paper A Copy",
                "DOI": "10.1000/abc",
            },
        ]
    )

    assert result["created"] == 1
    assert result["failed_count"] == 0
    assert result["skipped_duplicates"] == 1
    mock_api_client.create_items.assert_awaited_once_with(
        [{"itemType": "journalArticle", "title": "Paper A", "DOI": "10.1000/abc"}]
    )


@pytest.mark.asyncio
async def test_create_item_uses_precreate_dedup(item_service, mock_api_client):
    mock_api_client.search_items.return_value = [
        {"data": {"DOI": "10.2000/dup", "title": "Existing", "date": "2023"}}
    ]

    result = await item_service.create_item(
        {"itemType": "journalArticle", "title": "Single", "DOI": "10.2000/dup"}
    )

    assert result["created"] == 0
    assert result["failed_count"] == 0
    assert result["skipped_duplicates"] == 1
    mock_api_client.create_items.assert_not_called()


def test_normalize_url_handles_scheme_less_urls():
    assert _normalize_url("example.com/path?a=1#frag") == "https://example.com/path"
    assert _normalize_url("HTTP://Example.com/path/") == "http://example.com/path"


@pytest.mark.asyncio
async def test_create_items_reuses_library_search_cache_for_title(
    item_service, mock_api_client
):
    mock_api_client.search_items.return_value = [
        {"data": {"title": "Same Title", "date": "2025"}}
    ]
    mock_api_client.create_items.return_value = {
        "successful": {"0": "A", "1": "B"},
        "failed": {},
    }

    result = await item_service.create_items(
        [
            {"itemType": "journalArticle", "title": "Same Title", "date": "2023"},
            {"itemType": "journalArticle", "title": "Same Title", "date": "2024"},
        ]
    )

    assert result["created"] == 2
    assert result["failed_count"] == 0
    assert result["skipped_duplicates"] == 0
    mock_api_client.search_items.assert_awaited_once_with(
        "same title",
        qmode="titleCreatorYear",
        limit=25,
    )


@pytest.mark.asyncio
async def test_get_fulltext_prefers_local_when_local_is_richer(mock_api_client):
    local_client = MagicMock()
    service = ItemService(api_client=mock_api_client, local_client=local_client)

    api_text = "### 附件PDF 1: A\n\nOnly one attachment"
    local_text = (
        "### 附件 1: A.pdf\n\nText A\n\n---\n\n"
        "### 附件 2: B.pdf\n\nText B from second attachment"
    )

    mock_api_client.get_fulltext.return_value = api_text
    local_client.get_fulltext_by_key.return_value = (local_text, "pdf-multi")

    result = await service.get_fulltext("ITEM1")

    assert result == local_text
    mock_api_client.get_fulltext.assert_awaited_once_with("ITEM1")
    local_client.get_fulltext_by_key.assert_called_once_with("ITEM1")


@pytest.mark.asyncio
async def test_get_fulltext_keeps_api_when_local_is_not_richer(mock_api_client):
    local_client = MagicMock()
    service = ItemService(api_client=mock_api_client, local_client=local_client)

    api_text = (
        "### 附件PDF 1: A\n\nText A\n\n---\n\n"
        "### 附件PDF 2: B\n\nText B"
    )
    local_text = "### 附件 1: A.pdf\n\nText A"

    mock_api_client.get_fulltext.return_value = api_text
    local_client.get_fulltext_by_key.return_value = (local_text, "pdf")

    result = await service.get_fulltext("ITEM2")

    assert result == api_text
