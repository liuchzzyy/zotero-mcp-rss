"""Test ZoteroItemCreator."""

import pytest
from zotero_mcp.models.rss import RSSItem
from zotero_mcp.services.common.zotero_item_creator import (
    ZoteroItemCreator,
    parse_creator_string,
)


@pytest.mark.asyncio
async def test_create_zotero_item_with_minimal_data(mock_data_service, mock_metadata_service):
    """Test creating item with minimal required fields."""
    creator = ZoteroItemCreator(mock_data_service, mock_metadata_service)

    item = RSSItem(
        title="Test Paper",
        link="https://example.com/paper",
        source_url="https://feed.com",
        source_title="Test Feed",
    )

    # Mock the services
    mock_data_service.search_items.return_value = []
    mock_data_service.create_items.return_value = {"successful": {"KEY": {}}}
    mock_metadata_service.lookup_doi.return_value = None

    result = await creator.create_item(item, collection_key="ABC123")

    assert result is not None
    assert isinstance(result, str)


def test_parse_creator_string_single_author():
    """Test parsing single author."""
    creators = parse_creator_string("John Doe")
    assert len(creators) == 1
    assert creators[0]["name"] == "John Doe"
    assert creators[0]["creatorType"] == "author"


def test_parse_creator_string_multiple_authors():
    """Test parsing multiple authors separated by commas."""
    creators = parse_creator_string("John Doe, Jane Smith, Bob Johnson")
    assert len(creators) == 3
    assert creators[0]["name"] == "John Doe"
    assert creators[1]["name"] == "Jane Smith"
    assert creators[2]["name"] == "Bob Johnson"


def test_parse_creator_string_truncation():
    """Test that long author lists are truncated."""
    many_authors = ", ".join([f"Author {i}" for i in range(15)])
    creators = parse_creator_string(many_authors)
    assert len(creators) == 10
    assert "et al." in creators[-1]["name"]
