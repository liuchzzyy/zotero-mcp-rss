"""
Tests for BatchLoader.
"""

from unittest.mock import AsyncMock

import pytest

from zotero_mcp.services.item import ItemService
from zotero_mcp.utils.batch_loader import BatchLoader


@pytest.fixture
def mock_item_service():
    service = AsyncMock(spec=ItemService)
    # Setup mock returns
    service.get_item.return_value = {"key": "KEY", "data": {"title": "Title"}}
    service.get_item_children.return_value = []
    service.get_fulltext.return_value = "Full text"
    service.get_annotations.return_value = []
    service.get_bibtex.return_value = "@article{...}"
    return service


@pytest.mark.asyncio
async def test_fetch_bundle_parallel(mock_item_service):
    loader = BatchLoader(item_service=mock_item_service)

    bundle = await loader.get_item_bundle_parallel("KEY1")

    assert bundle["metadata"]["key"] == "KEY"
    assert bundle["fulltext"] == "Full text"

    # Verify methods were called
    mock_item_service.get_item.assert_awaited_once_with("KEY1")
    mock_item_service.get_fulltext.assert_awaited_once_with("KEY1")


@pytest.mark.asyncio
async def test_fetch_many_bundles(mock_item_service):
    loader = BatchLoader(item_service=mock_item_service, concurrency=2)
    keys = ["KEY1", "KEY2", "KEY3"]

    bundles = await loader.fetch_many_bundles(keys)

    assert len(bundles) == 3
    assert mock_item_service.get_item.call_count == 3
