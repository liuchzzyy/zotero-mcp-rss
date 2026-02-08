"""
Tests for ItemService.
"""

from unittest.mock import AsyncMock

import pytest

from zotero_mcp.clients.zotero import ZoteroAPIClient
from zotero_mcp.services.zotero.item_service import ItemService


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
