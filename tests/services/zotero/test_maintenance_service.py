from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from zotero_mcp.services.zotero.maintenance_service import LibraryMaintenanceService


@pytest.mark.asyncio
async def test_clean_empty_items_dry_run_filters_expected_candidates():
    data_service = MagicMock()
    data_service.get_collections = AsyncMock(
        return_value=[{"key": "C1", "data": {"name": "Inbox"}}]
    )
    data_service.get_collection_items = AsyncMock(
        return_value=[
            SimpleNamespace(key="I_EMPTY", title="", item_type="journalArticle"),
            SimpleNamespace(
                key="I_TITLE",
                title="Real Title",
                item_type="journalArticle",
            ),
            SimpleNamespace(key="I_ATT", title="", item_type="attachment"),
        ]
    )
    data_service.get_item_children = AsyncMock(return_value=[])

    service = LibraryMaintenanceService(data_service=data_service)
    result = await service.clean_empty_items(
        collection_name=None,
        scan_limit=10,
        treated_limit=10,
        dry_run=True,
    )

    assert result["dry_run"] is True
    assert result["empty_items_found"] == 1
    assert result["candidates"][0]["key"] == "I_EMPTY"


@pytest.mark.asyncio
async def test_clean_empty_items_delete_counts_failures():
    data_service = MagicMock()
    data_service.get_collections = AsyncMock(
        return_value=[{"key": "C1", "data": {"name": "Inbox"}}]
    )
    data_service.get_collection_items = AsyncMock(
        return_value=[
            SimpleNamespace(key="I1", title="", item_type="journalArticle"),
            SimpleNamespace(key="I2", title="", item_type="journalArticle"),
        ]
    )
    data_service.get_item_children = AsyncMock(return_value=[])
    data_service.delete_item = AsyncMock(
        side_effect=[None, RuntimeError("delete failed")]
    )

    service = LibraryMaintenanceService(data_service=data_service)
    result = await service.clean_empty_items(
        collection_name=None,
        scan_limit=10,
        treated_limit=10,
        dry_run=False,
    )

    assert result["empty_items_found"] == 2
    assert result["deleted"] == 1
    assert result["failed"] == 1
    assert result["failures"][0]["key"] == "I2"


@pytest.mark.asyncio
async def test_purge_tags_updates_items_and_reports_summary():
    data_service = MagicMock()
    data_service.get_collections = AsyncMock(
        return_value=[{"key": "C1", "data": {"name": "Inbox"}}]
    )
    data_service.get_collection_items = AsyncMock(
        return_value=[
            SimpleNamespace(key="I1", title="Item 1", item_type="journalArticle"),
            SimpleNamespace(key="I2", title="Item 2", item_type="journalArticle"),
        ]
    )
    data_service.get_item = AsyncMock(
        side_effect=[
            {"data": {"tags": [{"tag": "AI/条目分析"}, {"tag": "keep"}]}},
            {"data": {"tags": [{"tag": "keep"}]}},
        ]
    )
    data_service.update_item = AsyncMock(return_value={})

    service = LibraryMaintenanceService(data_service=data_service)
    result = await service.purge_tags(
        tags=[" AI/条目分析 ", "AI/条目分析"],
        collection_name=None,
        batch_size=10,
        scan_limit=None,
        update_limit=None,
        dry_run=False,
    )

    assert result["tags"] == ["AI/条目分析"]
    assert result["total_items_scanned"] == 2
    assert result["items_updated"] == 1
    assert result["total_tags_removed"] == 1
    data_service.update_item.assert_awaited_once()
    updated_item = data_service.update_item.await_args.args[0]
    assert updated_item["data"]["tags"] == [{"tag": "keep"}]
    assert result["details"][0]["item_key"] == "I1"
    assert result["details"][0]["removed_tags"] == ["AI/条目分析"]


@pytest.mark.asyncio
async def test_purge_tags_respects_scan_limit_and_collection_name():
    data_service = MagicMock()
    data_service.find_collection_by_name = AsyncMock(
        return_value=[{"key": "C1", "data": {"name": "Inbox"}}]
    )
    data_service.get_collection_items = AsyncMock(
        return_value=[
            SimpleNamespace(key="I1", title="Item 1", item_type="journalArticle"),
            SimpleNamespace(key="I2", title="Item 2", item_type="journalArticle"),
        ]
    )
    data_service.get_item = AsyncMock(
        side_effect=[
            {"data": {"tags": [{"tag": "AI/条目分析"}, {"tag": "keep"}]}},
            {"data": {"tags": [{"tag": "AI/条目分析"}]}},
        ]
    )
    data_service.update_item = AsyncMock(return_value={})

    service = LibraryMaintenanceService(data_service=data_service)
    result = await service.purge_tags(
        tags=["AI/条目分析"],
        collection_name="Inbox",
        batch_size=10,
        scan_limit=1,
        update_limit=None,
        dry_run=True,
    )

    data_service.find_collection_by_name.assert_awaited_once_with(
        "Inbox", exact_match=True
    )
    assert result["collection"] == "Inbox"
    assert result["total_items_scanned"] == 1
    assert result["items_updated"] == 1
    data_service.get_item.assert_awaited_once()
    data_service.update_item.assert_not_awaited()

