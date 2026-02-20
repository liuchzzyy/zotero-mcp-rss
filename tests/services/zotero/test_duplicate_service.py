from unittest.mock import AsyncMock

import pytest

from zotero_mcp.services.zotero.duplicate_service import DuplicateDetectionService


def _api_item(
    key: str,
    *,
    doi: str | None = None,
    title: str = "",
    url: str | None = None,
    item_type: str = "journalArticle",
    parent_item: str | None = None,
) -> dict:
    return {
        "key": key,
        "data": {
            "key": key,
            "itemType": item_type,
            "DOI": doi,
            "title": title or key,
            "url": url,
            "parentItem": parent_item,
            "creators": [],
            "tags": [],
        },
    }


@pytest.mark.asyncio
async def test_find_duplicate_groups_excludes_child_items():
    service = DuplicateDetectionService(item_service=AsyncMock())

    items = [
        {
            "key": "A1",
            "data": {
                "itemType": "journalArticle",
                "DOI": "10.1000/abc",
                "title": "Paper A",
                "url": "https://example.com/a",
            },
            "children": [],
        },
        {
            "key": "A2",
            "data": {
                "itemType": "journalArticle",
                "DOI": "10.1000/abc",
                "title": "Paper A copy",
                "url": "https://example.com/a?x=1",
            },
            "children": [],
        },
        {
            "key": "N1",
            "data": {
                "itemType": "note",
                "title": "Untitled",
            },
            "children": [],
        },
        {
            "key": "N2",
            "data": {
                "itemType": "note",
                "title": "Untitled",
            },
            "children": [],
        },
    ]

    result = await service._find_duplicate_groups(items)

    assert len(result["groups"]) == 1
    group = result["groups"][0]
    assert group.primary_key in {"A1", "A2"}
    assert set(group.duplicate_keys) == ({"A1", "A2"} - {group.primary_key})


@pytest.mark.asyncio
async def test_find_and_remove_duplicates_rejects_invalid_limits():
    service = DuplicateDetectionService(item_service=AsyncMock())

    result = await service.find_and_remove_duplicates(scan_limit=0, treated_limit=10)

    assert result["error"] == "invalid dedup parameters"
    assert result["operation"] == "deduplicate"
    assert result["status"] == "validation_error"
    assert result["success"] is False


@pytest.mark.asyncio
async def test_find_and_remove_duplicates_detects_cross_batch_library_duplicates():
    item_service = AsyncMock()
    item_service.api_client.get_all_items = AsyncMock(
        side_effect=[
            [_api_item("A1", doi="10.1000/abc", title="Paper A")],
            [_api_item("A2", doi="10.1000/abc", title="Paper A copy")],
            [],
        ]
    )
    item_service.api_client.get_collection_items = AsyncMock()

    service = DuplicateDetectionService(item_service=item_service)
    result = await service.find_and_remove_duplicates(
        scan_limit=1,
        treated_limit=10,
        dry_run=True,
    )

    assert result["success"] is True
    assert result["duplicates_found"] == 1
    assert result["duplicates_removed"] == 0
    assert len(result["groups"]) == 1
    item_service.api_client.get_all_items.assert_awaited()
    item_service.api_client.get_collection_items.assert_not_awaited()


@pytest.mark.asyncio
async def test_find_and_remove_duplicates_clamps_scan_limit_to_avoid_early_stop():
    item_service = AsyncMock()
    first_page = [_api_item(f"K{i}", title=f"Paper {i}") for i in range(100)]
    second_page = [_api_item("K100", title="Paper 100")]
    item_service.api_client.get_all_items = AsyncMock(side_effect=[first_page, second_page])
    item_service.api_client.get_collection_items = AsyncMock()

    service = DuplicateDetectionService(item_service=item_service)
    result = await service.find_and_remove_duplicates(
        scan_limit=200,
        treated_limit=10,
        dry_run=True,
    )

    assert result["success"] is True
    assert result["total_scanned"] == 101
    assert item_service.api_client.get_all_items.await_count == 2


@pytest.mark.asyncio
async def test_find_and_remove_duplicates_detects_cross_batch_collection_duplicates():
    item_service = AsyncMock()
    item_service.api_client.get_collection_items = AsyncMock(
        side_effect=[
            [_api_item("B1", doi="10.1000/xyz", title="Paper B")],
            [_api_item("B2", doi="10.1000/xyz", title="Paper B copy")],
            [],
        ]
    )

    service = DuplicateDetectionService(item_service=item_service)
    result = await service.find_and_remove_duplicates(
        collection_key="COLL123",
        scan_limit=1,
        treated_limit=10,
        dry_run=True,
    )

    assert result["success"] is True
    assert result["duplicates_found"] == 1
    assert result["duplicates_removed"] == 0
    assert len(result["groups"]) == 1
    item_service.api_client.get_collection_items.assert_awaited()


@pytest.mark.asyncio
async def test_find_duplicate_groups_skips_items_with_parent_item():
    service = DuplicateDetectionService(item_service=AsyncMock())
    items = [
        _api_item("P1", doi="10.1000/parent"),
        _api_item("P2", doi="10.1000/parent"),
        _api_item(
            "C1",
            doi="10.1000/parent",
            item_type="note",
            parent_item="P1",
        ),
    ]

    result = await service._find_duplicate_groups(items)
    assert len(result["groups"]) == 1
    group = result["groups"][0]
    assert set(group.duplicate_keys) == ({"P1", "P2"} - {group.primary_key})
