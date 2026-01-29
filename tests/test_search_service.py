"""
Tests for SearchService.
"""

from unittest.mock import AsyncMock, MagicMock

import pytest

from zotero_mcp.clients.local_db import LocalDatabaseClient
from zotero_mcp.clients.zotero_client import ZoteroAPIClient
from zotero_mcp.services.search import SearchService


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
