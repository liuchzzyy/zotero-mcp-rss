"""
Tests for SearchService.
"""

from unittest.mock import AsyncMock, MagicMock

import pytest

from zotero_mcp.clients.zotero import (
    LocalDatabaseClient,
    ZoteroAPIClient,
)
from zotero_mcp.services.zotero.search_service import SearchService


@pytest.fixture
def mock_api_client():
    client = AsyncMock(spec=ZoteroAPIClient)
    return client


@pytest.fixture
def mock_local_client():
    client = MagicMock(spec=LocalDatabaseClient)
    return client


@pytest.fixture
def search_service(mock_api_client, mock_local_client):
    return SearchService(api_client=mock_api_client, local_client=mock_local_client)


@pytest.mark.asyncio
async def test_search_items_api(search_service, mock_api_client):
    mock_api_client.search_items.return_value = [
        {"key": "KEY1", "data": {"title": "Test Result"}}
    ]

    results = await search_service.search_items("query")

    assert len(results) == 1
    assert results[0].key == "KEY1"
    mock_api_client.search_items.assert_awaited_once()


@pytest.mark.asyncio
async def test_get_recent_items(search_service, mock_api_client):
    mock_api_client.get_recent_items.return_value = [
        {"key": "KEY2", "data": {"title": "Recent"}}
    ]

    results = await search_service.get_recent_items(limit=5)

    assert len(results) == 1
    assert results[0].key == "KEY2"
    mock_api_client.get_recent_items.assert_awaited_once()


@pytest.mark.asyncio
async def test_search_by_tag_filters_mixed_tag_payload(search_service, mock_api_client):
    mock_api_client.get_items_by_tag.return_value = [
        {
            "key": "K1",
            "data": {
                "key": "K1",
                "title": "Pass",
                "tags": [{"tag": "AI/条目分析"}, "保留"],
            },
        },
        {
            "key": "K2",
            "data": {
                "key": "K2",
                "title": "Excluded",
                "tags": [{"tag": "AI/条目分析"}, {"tag": "保留"}, {"tag": "跳过"}],
            },
        },
        {
            "key": "K3",
            "data": {
                "key": "K3",
                "title": "Missing include",
                "tags": [{"tag": "AI/条目分析"}],
            },
        },
    ]

    results = await search_service.search_by_tag(
        tags=[" AI/条目分析 ", "保留"],
        exclude_tags=[" 跳过 "],
        limit=10,
    )

    mock_api_client.get_items_by_tag.assert_awaited_once_with(
        "AI/条目分析",
        limit=100,
        start=0,
    )
    assert [item.key for item in results] == ["K1"]


@pytest.mark.asyncio
async def test_search_by_tag_normalizes_and_respects_limit(
    search_service, mock_api_client
):
    mock_api_client.get_items_by_tag.return_value = [
        {
            "key": "K1",
            "data": {"key": "K1", "title": "One", "tags": [{"tag": "AI/条目分析"}]},
        },
        {
            "key": "K2",
            "data": {"key": "K2", "title": "Two", "tags": [{"tag": "AI/条目分析"}]},
        },
        {
            "key": "K3",
            "data": {"key": "K3", "title": "Three", "tags": [{"tag": "AI/条目分析"}]},
        },
    ]

    results = await search_service.search_by_tag(
        tags=["AI/条目分析", "AI/条目分析", " "],
        exclude_tags=None,
        limit=2,
    )

    mock_api_client.get_items_by_tag.assert_awaited_once_with(
        "AI/条目分析",
        limit=100,
        start=0,
    )
    assert len(results) == 2
    assert [item.key for item in results] == ["K1", "K2"]


@pytest.mark.asyncio
async def test_search_by_tag_returns_empty_when_include_tags_invalid(
    search_service, mock_api_client
):
    results = await search_service.search_by_tag(
        tags=[" ", ""],
        exclude_tags=["x"],
        limit=5,
    )

    assert results == []
    mock_api_client.get_items_by_tag.assert_not_called()

