"""Tests for MetadataUpdateService."""

from unittest.mock import AsyncMock

import pytest

from zotero_mcp.services.zotero.metadata_update_service import MetadataUpdateService


@pytest.mark.asyncio
async def test_update_item_metadata_skips_attachment_item_type():
    """Should skip unsupported item types instead of attempting update."""
    item_service = AsyncMock()
    metadata_service = AsyncMock()
    service = MetadataUpdateService(item_service, metadata_service)

    item_service.get_item.return_value = {
        "data": {
            "itemType": "attachment",
            "title": "Attachment",
            "tags": [],
        }
    }

    result = await service.update_item_metadata("ATTACH1", dry_run=False)

    assert result["success"] is True
    assert result["updated"] is False
    assert "unsupported item type" in result["message"]
    item_service.update_item.assert_not_awaited()


@pytest.mark.asyncio
async def test_update_all_items_skips_unsupported_item_types_before_processing():
    """Batch update should count unsupported types as skipped without processing."""
    item_service = AsyncMock()
    metadata_service = AsyncMock()
    service = MetadataUpdateService(item_service, metadata_service)

    item_service.get_sorted_collections.return_value = [{"key": "COLL1"}]
    item_service.get_collection_items.side_effect = [
        [
            type("Item", (), {"key": "N1", "item_type": "note", "tags": []})(),
            type(
                "Item",
                (),
                {"key": "A1", "item_type": "journalArticle", "tags": []},
            )(),
        ],
        [],
    ]

    service.update_item_metadata = AsyncMock(
        return_value={"success": True, "updated": False}
    )

    result = await service.update_all_items(scan_limit=10, treated_limit=10, dry_run=True)

    assert result["skipped"] == 2
    service.update_item_metadata.assert_awaited_once_with("A1", dry_run=True)

