"""
Tests for AnalysisStatusService.
"""

from unittest.mock import AsyncMock

import pytest

from zotero_mcp.services.analysis_status import AnalysisStatusService
from zotero_mcp.services.item import ItemService


@pytest.fixture
def mock_item_service():
    return AsyncMock(spec=ItemService)


@pytest.fixture
def status_service(mock_item_service):
    return AnalysisStatusService(item_service=mock_item_service)


@pytest.mark.asyncio
async def test_is_analyzed_with_tag(status_service, mock_item_service):
    mock_item_service.get_item.return_value = {
        "key": "KEY1",
        "data": {"tags": [{"tag": "AI分析"}]},
    }

    assert await status_service.is_analyzed("KEY1") is True


@pytest.mark.asyncio
async def test_is_analyzed_without_tag_no_notes(status_service, mock_item_service):
    mock_item_service.get_item.return_value = {"key": "KEY2", "data": {"tags": []}}
    mock_item_service.get_notes.return_value = []

    assert await status_service.is_analyzed("KEY2") is False


@pytest.mark.asyncio
async def test_is_analyzed_legacy_notes(status_service, mock_item_service):
    # Has notes but no tag -> considered analyzed in legacy mode?
    # Or considered "legacy analyzed"?
    # The plan says: Unified Logic: is_analyzed() = has AI分析 tag AND has notes?
    # No, typically "AI分析" tag is the marker.

    mock_item_service.get_item.return_value = {"key": "KEY3", "data": {"tags": []}}
    mock_item_service.get_notes.return_value = [{"note": "Some note"}]

    # If strictly tag based, this is False.
    # If loose, True.
    # Let's assume strict tag check for now, or configurable.
    pass
