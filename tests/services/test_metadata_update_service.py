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


def test_build_updated_item_data_skips_periodical_fields_for_book():
    """Book items should not be assigned journal-only fields."""
    item_service = AsyncMock()
    metadata_service = AsyncMock()
    service = MetadataUpdateService(item_service, metadata_service)

    current = {
        "itemType": "book",
        "title": "Handbook",
        "creators": [],
        "publisher": "",
        "date": "",
    }
    enhanced = {
        "journal": "Choice Reviews",
        "journal_abbrev": "Choice",
        "volume": "33",
        "issue": "5",
        "pages": "12-14",
        "issn": "1234-5678",
        "publisher": "Test Publisher",
        "year": 2024,
    }

    updated = service._build_updated_item_data(current, enhanced)

    assert "publicationTitle" not in updated
    assert "journalAbbreviation" not in updated
    assert "volume" not in updated
    assert "issue" not in updated
    assert "pages" not in updated
    assert "ISSN" not in updated
    assert updated["publisher"] == "Test Publisher"
    assert updated["date"] == "2024"


def test_build_updated_item_data_only_updates_existing_item_fields():
    """Should avoid writing fields that are invalid for the current item type."""
    item_service = AsyncMock()
    metadata_service = AsyncMock()
    service = MetadataUpdateService(item_service, metadata_service)

    current = {
        "itemType": "computerProgram",
        "title": "Tool",
        "creators": [],
        "date": "",
        "url": "",
        "tags": [],
    }
    enhanced = {
        "language": "en",  # invalid for computerProgram in Zotero API
        "publisher": "X",
        "journal": "J",
        "year": 2025,
        "url": "https://doi.org/10.1/xyz",
    }

    updated = service._build_updated_item_data(current, enhanced)

    assert "language" not in updated
    assert "publisher" not in updated
    assert "publicationTitle" not in updated
    assert updated["date"] == "2025"
    assert updated["url"] == "https://doi.org/10.1/xyz"
