from unittest.mock import AsyncMock

import pytest

from zotero_mcp.services.zotero.duplicate_service import DuplicateDetectionService


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
