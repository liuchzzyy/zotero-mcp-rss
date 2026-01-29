"""
Tests for ItemService.
"""

from unittest.mock import AsyncMock, MagicMock

import pytest

from zotero_mcp.clients.better_bibtex import BetterBibTeXClient
from zotero_mcp.clients.zotero_client import ZoteroAPIClient
from zotero_mcp.services.item import ItemService


@pytest.fixture
def mock_api_client():
    client = AsyncMock(spec=ZoteroAPIClient)
    return client


@pytest.fixture
def mock_bibtex_client():
    client = MagicMock(spec=BetterBibTeXClient)
    return client


@pytest.fixture
def item_service(mock_api_client, mock_bibtex_client):
    return ItemService(api_client=mock_api_client, bibtex_client=mock_bibtex_client)


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
