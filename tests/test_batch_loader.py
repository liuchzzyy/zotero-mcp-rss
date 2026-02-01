"""
Tests for BatchLoader.
"""

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from zotero_mcp.services.zotero.item_service import ItemService
from zotero_mcp.utils.async_helpers.batch_loader import BatchLoader


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


@pytest.fixture
def mock_item_service_with_pdf():
    """Mock service with PDF attachment."""
    service = AsyncMock(spec=ItemService)
    # Setup mock returns
    service.get_item.return_value = {"key": "KEY", "data": {"title": "Title"}}
    service.get_item_children.return_value = [
        {
            "key": "ATTACH1",
            "data": {
                "itemType": "attachment",
                "contentType": "application/pdf",
                "path": "/fake/path/test.pdf",  # Direct path (not storage:)
            },
        }
    ]
    service.get_fulltext.return_value = "Full text"
    service.get_annotations.return_value = []
    service.get_bibtex.return_value = "@article{...}"
    return service


@pytest.mark.asyncio
async def test_get_item_bundle_with_multimodal_no_pdf(mock_item_service):
    """Test bundle fetching with multi-modal content when no PDF exists."""
    loader = BatchLoader(item_service=mock_item_service)

    # Test with include_multimodal=True but no PDF attachment
    bundle = await loader.get_item_bundle_parallel(
        "TEST_KEY",
        include_fulltext=True,
        include_multimodal=True,
    )

    assert "metadata" in bundle
    assert "fulltext" in bundle
    # Multimodal should be empty dict when no PDF
    assert bundle.get("multimodal") == {}


@pytest.mark.asyncio
async def test_get_item_bundle_with_multimodal_with_pdf(mock_item_service_with_pdf):
    """Test bundle fetching with multi-modal content when PDF exists."""
    loader = BatchLoader(item_service=mock_item_service_with_pdf)

    # Mock the MultiModalPDFExtractor
    mock_extractor_result = {
        "text_blocks": [{"type": "text", "content": "Sample text", "page": 0}],
        "images": [
            {
                "type": "image",
                "content": "base64encodeddata",
                "format": "base64.png",
                "page": 0,
            }
        ],
        "tables": [],
    }

    with patch(
        "zotero_mcp.utils.async_helpers.batch_loader.MultiModalPDFExtractor"
    ) as MockExtractor:
        mock_extractor_instance = MagicMock()
        mock_extractor_instance.extract_elements.return_value = mock_extractor_result
        MockExtractor.return_value = mock_extractor_instance

        # Need to also mock the path resolution
        with patch(
            "zotero_mcp.utils.async_helpers.batch_loader.Path.exists", return_value=True
        ):
            bundle = await loader.get_item_bundle_parallel(
                "TEST_KEY",
                include_fulltext=True,
                include_multimodal=True,
            )

            assert "metadata" in bundle
            assert "multimodal" in bundle
            assert "images" in bundle["multimodal"]
            assert "tables" in bundle["multimodal"]
            assert len(bundle["multimodal"]["images"]) == 1


@pytest.mark.asyncio
async def test_get_item_bundle_multimodal_disabled(mock_item_service):
    """Test that multimodal is not included when flag is False."""
    loader = BatchLoader(item_service=mock_item_service)

    bundle = await loader.get_item_bundle_parallel(
        "TEST_KEY",
        include_fulltext=True,
        include_multimodal=False,  # Disabled
    )

    assert "metadata" in bundle
    assert "fulltext" in bundle
    # Multimodal should not be in bundle when disabled
    assert "multimodal" not in bundle


@pytest.fixture
def mock_item_service_with_storage_pdf():
    """Mock service with PDF attachment using storage: path."""
    service = AsyncMock(spec=ItemService)
    # Setup mock returns
    service.get_item.return_value = {"key": "KEY", "data": {"title": "Title"}}
    service.get_item_children.return_value = [
        {
            "key": "ATTACH1",
            "data": {
                "itemType": "attachment",
                "contentType": "application/pdf",
                "path": "storage:test.pdf",  # Storage path (requires LocalDatabaseClient)
            },
        }
    ]
    service.get_fulltext.return_value = "Full text"
    service.get_annotations.return_value = []
    service.get_bibtex.return_value = "@article{...}"
    return service


@pytest.mark.asyncio
async def test_get_item_bundle_multimodal_storage_path(mock_item_service_with_storage_pdf):
    """Test that storage: paths return empty multimodal (requires LocalDatabaseClient)."""
    loader = BatchLoader(item_service=mock_item_service_with_storage_pdf)

    bundle = await loader.get_item_bundle_parallel(
        "TEST_KEY",
        include_fulltext=True,
        include_multimodal=True,
    )

    assert "metadata" in bundle
    assert "multimodal" in bundle
    # Storage paths can't be resolved without LocalDatabaseClient
    assert bundle["multimodal"] == {}
