from unittest.mock import AsyncMock, MagicMock

import pytest


@pytest.fixture
def mock_data_service():
    """Fixture for DataAccessService mock."""
    mock = MagicMock()
    mock.get_item = AsyncMock(
        return_value={
            "data": {"publicationTitle": "Mock Journal", "title": "Mock Title"}
        }
    )
    mock.get_fulltext = AsyncMock(return_value="Mock Fulltext")
    mock.get_notes = AsyncMock(return_value=[])
    mock.get_annotations = AsyncMock(return_value=[])
    mock.create_note = AsyncMock(return_value={"successful": {"0": {"key": "NOTE123"}}})
    mock.find_collection_by_name = AsyncMock(
        return_value=[{"data": {"key": "COLL123", "name": "Mock Collection"}}]
    )
    mock.get_collection_items = AsyncMock(return_value=[])
    mock.get_recent_items = AsyncMock(return_value=[])
    return mock


@pytest.fixture
def mock_llm_client():
    """Fixture for LLMClient mock."""
    mock = MagicMock()
    mock.analyze_paper = AsyncMock(return_value="# Mock Analysis Result")
    return mock


@pytest.fixture
def mock_metadata_service():
    """Fixture for MetadataService mock."""
    mock = MagicMock()
    mock.lookup_doi = AsyncMock(return_value=None)
    return mock
