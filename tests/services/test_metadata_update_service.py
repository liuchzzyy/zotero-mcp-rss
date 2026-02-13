"""Tests for MetadataUpdateService."""

from unittest.mock import AsyncMock

import pytest

from zotero_mcp.services.zotero.metadata_update_service import (
    AI_METADATA_TAG,
    MetadataUpdateService,
)


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

    assert result["processed_candidates"] == 1
    assert result["skipped"] == 1
    assert result["ai_metadata_tagged"] == 0
    service.update_item_metadata.assert_awaited_once_with("A1", dry_run=True)


@pytest.mark.asyncio
async def test_update_all_items_counts_ai_metadata_tagged_items():
    """Batch update should expose count of items skipped due to AI metadata tag."""
    item_service = AsyncMock()
    metadata_service = AsyncMock()
    service = MetadataUpdateService(item_service, metadata_service)

    item_service.get_sorted_collections.return_value = [{"key": "COLL1"}]
    item_service.get_collection_items.side_effect = [
        [
            type("Item", (), {"key": "T1", "item_type": "journalArticle", "tags": [AI_METADATA_TAG]})(),
            type("Item", (), {"key": "A1", "item_type": "journalArticle", "tags": []})(),
        ],
        [],
    ]
    service.update_item_metadata = AsyncMock(
        return_value={"success": True, "updated": False}
    )

    result = await service.update_all_items(scan_limit=10, treated_limit=10, dry_run=True)

    assert result["processed_candidates"] == 1
    assert result["ai_metadata_tagged"] == 1
    assert result["skipped"] == 2
    service.update_item_metadata.assert_awaited_once_with("A1", dry_run=True)


@pytest.mark.asyncio
async def test_fetch_enhanced_metadata_with_doi_does_not_fallback_when_not_found():
    """If DOI lookup fails, title/url fallback should be skipped for efficiency."""
    item_service = AsyncMock()
    metadata_service = AsyncMock()
    metadata_service.get_metadata_by_doi = AsyncMock(return_value=None)
    metadata_service.lookup_metadata = AsyncMock(return_value=None)
    service = MetadataUpdateService(item_service, metadata_service)

    result = await service._fetch_enhanced_metadata(
        doi="10.1234/missing",
        title="Some Title",
        url="https://example.com",
    )

    assert result is None
    metadata_service.get_metadata_by_doi.assert_awaited_once_with("10.1234/missing")
    metadata_service.lookup_metadata.assert_not_called()


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


def test_build_updated_item_data_crossref_overwrites_existing_fields():
    """Crossref metadata should overwrite existing Zotero values."""
    item_service = AsyncMock()
    metadata_service = AsyncMock()
    service = MetadataUpdateService(item_service, metadata_service)

    current = {
        "itemType": "journalArticle",
        "title": "Old Title",
        "creators": [{"creatorType": "author", "name": "Old Author"}],
        "publisher": "Old Publisher",
        "date": "2019",
        "url": "https://old.example.com",
        "tags": [],
    }
    enhanced = {
        "source": "crossref",
        "title": "New Title",
        "authors": ["Smith, John"],
        "publisher": "New Publisher",
        "year": 2024,
        "url": "https://doi.org/10.1000/new",
    }

    updated = service._build_updated_item_data(current, enhanced)

    assert updated["title"] == "New Title"
    assert updated["publisher"] == "New Publisher"
    assert updated["date"] == "2024"
    assert updated["url"] == "https://doi.org/10.1000/new"
    assert updated["creators"][0]["lastName"] == "Smith"


def test_build_updated_item_data_openalex_only_fills_missing_fields():
    """OpenAlex metadata should only fill missing values."""
    item_service = AsyncMock()
    metadata_service = AsyncMock()
    service = MetadataUpdateService(item_service, metadata_service)

    current = {
        "itemType": "journalArticle",
        "title": "Existing Title",
        "creators": [{"creatorType": "author", "name": "Existing Author"}],
        "publisher": "Existing Publisher",
        "date": "2020",
        "url": "https://existing.example.com",
        "tags": [],
    }
    enhanced = {
        "source": "openalex",
        "title": "OpenAlex Title",
        "authors": ["New, Author"],
        "publisher": "OpenAlex Publisher",
        "year": 2025,
        "url": "https://doi.org/10.1000/openalex",
    }

    updated = service._build_updated_item_data(current, enhanced)

    assert updated["title"] == "Existing Title"
    assert updated["publisher"] == "Existing Publisher"
    assert updated["date"] == "2020"
    assert updated["url"] == "https://existing.example.com"
    assert updated["creators"][0]["name"] == "Existing Author"


def test_build_updated_item_data_unmatched_fields_go_to_extra():
    """Unmapped metadata should be persisted to Zotero extra field."""
    item_service = AsyncMock()
    metadata_service = AsyncMock()
    service = MetadataUpdateService(item_service, metadata_service)

    current = {
        "itemType": "book",
        "title": "Book Title",
        "creators": [],
        "extra": "Existing line",
        "tags": [],
    }
    enhanced = {
        "source": "openalex",
        "journal": "Journal Name",  # mapped but not valid for book itemType
        "unknown_field": "mystery",
        "subjects": ["ML", "AI"],
        "funders": ["NSF"],
        "pdf_url": "https://example.com/full.pdf",
    }

    updated = service._build_updated_item_data(current, enhanced)

    assert "publicationTitle" not in updated
    assert "Existing line" in updated["extra"]
    assert "Subject: ML" in updated["extra"]
    assert "Funder: NSF" in updated["extra"]
    assert "Full-text PDF: https://example.com/full.pdf" in updated["extra"]
    assert "Journal: Journal Name" in updated["extra"]
    assert "Unknown Field: mystery" in updated["extra"]
