"""
Unit tests for ItemService.

Tests the ItemService business logic with mocked ZoteroClient.
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from zotero_core.clients.zotero_client import ZoteroClient, ZoteroClientError
from zotero_core.models import ItemCreate, ItemUpdate
from zotero_core.services.item_service import ItemService, ItemServiceError


@pytest.fixture
def mock_client():
    """Create a mock ZoteroClient."""
    client = MagicMock(spec=ZoteroClient)
    return client


@pytest.fixture
def service(mock_client):
    """Create an ItemService with mocked client."""
    with patch(
        "zotero_core.services.item_service.ZoteroClient", return_value=mock_client
    ):
        service = ItemService(
            library_id="test_library",
            api_key="test_key",
            library_type="user",
        )
        service.client = mock_client
        return service


@pytest.fixture
def sample_item_data():
    """Sample item data from pyzotero."""
    return {
        "key": "ABCD1234",
        "version": 123,
        "data": {
            "key": "ABCD1234",
            "version": 123,
            "itemType": "journalArticle",
            "title": "Test Paper",
            "creators": [
                {"firstName": "John", "lastName": "Doe", "creatorType": "author"}
            ],
            "abstractNote": "This is a test abstract.",
            "date": "2024",
            "DOI": "10.1234/test",
            "url": "https://example.com",
            "tags": [{"tag": "test"}, {"tag": "sample"}],
            "collections": ["COLL1"],
        },
    }


@pytest.fixture
def sample_item_data_flat():
    """Sample item data in flat format (no nested data)."""
    return {
        "key": "ABCD1234",
        "version": 123,
        "type": "journalArticle",
        "title": "Test Paper",
        "creators": [{"firstName": "John", "lastName": "Doe", "creatorType": "author"}],
        "abstractNote": "This is a test abstract.",
        "date": "2024",
        "DOI": "10.1234/test",
        "url": "https://example.com",
        "tags": ["test", "sample"],
        "collections": ["COLL1"],
    }


class TestItemServiceGetItem:
    """Tests for get_item method."""

    @pytest.mark.asyncio
    async def test_get_item_success(self, service, mock_client, sample_item_data):
        """Test successfully getting an item."""
        mock_client.get_item = AsyncMock(return_value=sample_item_data)

        result = await service.get_item("ABCD1234")

        assert result is not None
        assert result.key == "ABCD1234"
        assert result.title == "Test Paper"
        assert result.type == "journalArticle"
        assert len(result.tags) == 2
        mock_client.get_item.assert_called_once_with("ABCD1234")

    @pytest.mark.asyncio
    async def test_get_item_flat_format(
        self, service, mock_client, sample_item_data_flat
    ):
        """Test getting item with flat data format."""
        mock_client.get_item = AsyncMock(return_value=sample_item_data_flat)

        result = await service.get_item("ABCD1234")

        assert result is not None
        assert result.key == "ABCD1234"
        assert result.title == "Test Paper"

    @pytest.mark.asyncio
    async def test_get_item_not_found(self, service, mock_client):
        """Test getting a non-existent item."""
        mock_client.get_item = AsyncMock(return_value=None)

        result = await service.get_item("NOTFOUND")

        assert result is None
        mock_client.get_item.assert_called_once_with("NOTFOUND")

    @pytest.mark.asyncio
    async def test_get_item_client_error(self, service, mock_client):
        """Test handling of client error."""
        mock_client.get_item = AsyncMock(side_effect=ZoteroClientError("API error"))

        with pytest.raises(ItemServiceError, match="Failed to get item"):
            await service.get_item("ERROR")

    @pytest.mark.asyncio
    async def test_get_item_invalid_data(self, service, mock_client):
        """Test handling of invalid item data."""
        mock_client.get_item = AsyncMock(return_value={"invalid": "data"})

        with pytest.raises(ItemServiceError):
            await service.get_item("INVALID")


class TestItemServiceGetAllItems:
    """Tests for get_all_items method."""

    @pytest.mark.asyncio
    async def test_get_all_items_success(self, service, mock_client, sample_item_data):
        """Test successfully getting all items."""
        item_data_1 = sample_item_data
        item_data_2 = {
            **sample_item_data,
            "key": "EFGH5678",
            "data": {**sample_item_data["data"], "key": "EFGH5678"},
        }
        mock_client.get_items = AsyncMock(return_value=[item_data_1, item_data_2])

        results = await service.get_all_items(limit=100)

        assert len(results) == 2
        assert results[0].key == "ABCD1234"
        assert results[1].key == "EFGH5678"
        mock_client.get_items.assert_called_once_with(
            limit=100, start=0, item_type=None
        )

    @pytest.mark.asyncio
    async def test_get_all_items_with_filter(self, service, mock_client):
        """Test getting items with type filter."""
        mock_client.get_items = AsyncMock(return_value=[])

        results = await service.get_all_items(limit=50, item_type="journalArticle")

        assert results == []
        mock_client.get_items.assert_called_once_with(
            limit=50, start=0, item_type="journalArticle"
        )

    @pytest.mark.asyncio
    async def test_get_all_items_skip_invalid(
        self, service, mock_client, sample_item_data
    ):
        """Test that invalid items are skipped."""
        valid_item = sample_item_data
        invalid_item = {"invalid": "data"}
        mock_client.get_items = AsyncMock(return_value=[valid_item, invalid_item])

        results = await service.get_all_items()

        assert len(results) == 1
        assert results[0].key == "ABCD1234"


class TestItemServiceCreateItem:
    """Tests for create_item method."""

    @pytest.mark.asyncio
    async def test_create_item_success(self, service, mock_client, sample_item_data):
        """Test successfully creating an item."""
        mock_client.create_item = AsyncMock(return_value=sample_item_data)

        item_create = ItemCreate(
            type="journalArticle", title="Test Paper", abstract="Test abstract"
        )

        result = await service.create_item(item_create)

        assert result.key == "ABCD1234"
        assert result.title == "Test Paper"
        mock_client.create_item.assert_called_once()

        # Check the dict passed to create_item
        call_args = mock_client.create_item.call_args[0][0]
        assert call_args["itemType"] == "journalArticle"
        assert call_args["title"] == "Test Paper"

    @pytest.mark.asyncio
    async def test_create_item_with_creators(
        self, service, mock_client, sample_item_data
    ):
        """Test creating an item with creators."""
        mock_client.create_item = AsyncMock(return_value=sample_item_data)

        item_create = ItemCreate(
            type="journalArticle",
            title="Test Paper",
            creators=[
                {"firstName": "John", "lastName": "Doe", "creatorType": "author"}
            ],
        )

        await service.create_item(item_create)

        call_args = mock_client.create_item.call_args[0][0]
        assert "creators" in call_args
        assert len(call_args["creators"]) == 1

    @pytest.mark.asyncio
    async def test_create_item_with_tags(self, service, mock_client, sample_item_data):
        """Test creating an item with tags."""
        mock_client.create_item = AsyncMock(return_value=sample_item_data)

        item_create = ItemCreate(
            type="journalArticle", title="Test Paper", tags=["test", "sample"]
        )

        await service.create_item(item_create)

        call_args = mock_client.create_item.call_args[0][0]
        assert "tags" in call_args
        assert call_args["tags"] == [{"tag": "test"}, {"tag": "sample"}]


class TestItemServiceUpdateItem:
    """Tests for update_item method."""

    @pytest.mark.asyncio
    async def test_update_item_success(self, service, mock_client, sample_item_data):
        """Test successfully updating an item."""
        updated_data = {
            **sample_item_data,
            "data": {
                **sample_item_data["data"],
                "title": "Updated Title",
                "version": 124,
            },
        }
        mock_client.update_item = AsyncMock(return_value=updated_data)

        item_update = ItemUpdate(title="Updated Title")

        result = await service.update_item("ABCD1234", item_update)

        assert result.title == "Updated Title"
        mock_client.update_item.assert_called_once()

        # Check the dict passed to update_item
        call_args = mock_client.update_item.call_args[0]
        assert call_args[0] == "ABCD1234"
        assert call_args[1]["title"] == "Updated Title"

    @pytest.mark.asyncio
    async def test_update_item_with_version(
        self, service, mock_client, sample_item_data
    ):
        """Test updating item with version for optimistic locking."""
        mock_client.update_item = AsyncMock(return_value=sample_item_data)

        item_update = ItemUpdate(title="Updated Title", version=123)

        await service.update_item("ABCD1234", item_update)

        call_args = mock_client.update_item.call_args[0][1]
        assert call_args["version"] == 123

    @pytest.mark.asyncio
    async def test_update_item_partial(self, service, mock_client, sample_item_data):
        """Test partial update (only some fields)."""
        mock_client.update_item = AsyncMock(return_value=sample_item_data)

        item_update = ItemUpdate(abstract="New abstract")

        await service.update_item("ABCD1234", item_update)

        call_args = mock_client.update_item.call_args[0][1]
        assert "abstractNote" in call_args
        assert call_args["abstractNote"] == "New abstract"
        # Other fields should not be present
        assert "title" not in call_args


class TestItemServiceDeleteItem:
    """Tests for delete_item method."""

    @pytest.mark.asyncio
    async def test_delete_item_success(self, service, mock_client):
        """Test successfully deleting an item."""
        mock_client.delete_item = AsyncMock(return_value=True)

        result = await service.delete_item("ABCD1234")

        assert result is True
        mock_client.delete_item.assert_called_once_with("ABCD1234")

    @pytest.mark.asyncio
    async def test_delete_item_not_found(self, service, mock_client):
        """Test deleting a non-existent item."""
        mock_client.delete_item = AsyncMock(
            side_effect=ZoteroClientError("Item not found")
        )

        with pytest.raises(ItemServiceError, match="Failed to delete item"):
            await service.delete_item("NOTFOUND")


class TestItemServiceAddTags:
    """Tests for add_tags method."""

    @pytest.mark.asyncio
    async def test_add_tags_success(self, service, mock_client, sample_item_data):
        """Test successfully adding tags to an item."""
        updated_data = {
            **sample_item_data,
            "data": {
                **sample_item_data["data"],
                "tags": [
                    {"tag": "test"},
                    {"tag": "sample"},
                    {"tag": "new_tag"},
                ],
            },
        }
        mock_client.add_tags = AsyncMock(return_value=updated_data)

        result = await service.add_tags("ABCD1234", ["new_tag"])

        assert len(result.tags) == 3
        assert "new_tag" in result.tags
        mock_client.add_tags.assert_called_once_with("ABCD1234", ["new_tag"])

    @pytest.mark.asyncio
    async def test_add_tags_not_found(self, service, mock_client):
        """Test adding tags to non-existent item."""
        mock_client.add_tags = AsyncMock(return_value=None)

        with pytest.raises(ItemServiceError, match="Item .* not found"):
            await service.add_tags("NOTFOUND", ["tag"])


class TestItemServiceRemoveTags:
    """Tests for remove_tags method."""

    @pytest.mark.asyncio
    async def test_remove_tags_success(self, service, mock_client, sample_item_data):
        """Test successfully removing tags from an item."""
        updated_data = {
            **sample_item_data,
            "data": {
                **sample_item_data["data"],
                "tags": [{"tag": "test"}],  # "sample" removed
            },
        }
        mock_client.remove_tags = AsyncMock(return_value=updated_data)

        result = await service.remove_tags("ABCD1234", ["sample"])

        assert len(result.tags) == 1
        assert "test" in result.tags
        assert "sample" not in result.tags
        mock_client.remove_tags.assert_called_once_with("ABCD1234", ["sample"])

    @pytest.mark.asyncio
    async def test_remove_tags_case_insensitive(
        self, service, mock_client, sample_item_data
    ):
        """Test that tag removal is case-insensitive."""
        updated_data = {
            **sample_item_data,
            "data": {**sample_item_data["data"], "tags": []},
        }
        mock_client.remove_tags = AsyncMock(return_value=updated_data)

        await service.remove_tags("ABCD1234", ["TEST", "SAMPLE"])

        assert len(mock_client.remove_tags.call_args[0][1]) == 2


class TestItemServiceHelpers:
    """Tests for helper methods."""

    def test_normalize_item_data_nested(self, service, sample_item_data):
        """Test normalizing item data with nested structure."""
        result = service._normalize_item_data(sample_item_data)

        assert result["key"] == "ABCD1234"
        assert result["type"] == "journalArticle"
        assert result["title"] == "Test Paper"
        assert result["tags"] == ["test", "sample"]
        assert "raw_data" in result

    def test_normalize_item_data_flat(self, service, sample_item_data_flat):
        """Test normalizing flat item data."""
        result = service._normalize_item_data(sample_item_data_flat)

        assert result["key"] == "ABCD1234"
        assert result["type"] == "journalArticle"
        assert result["title"] == "Test Paper"

    def test_normalize_item_data_missing_key(self, service):
        """Test normalizing data with missing key raises error."""
        invalid_data = {"title": "Test"}

        with pytest.raises(ValueError, match="missing required 'key' field"):
            service._normalize_item_data(invalid_data)

    def test_item_create_to_dict(self, service):
        """Test converting ItemCreate to dict."""
        item_create = ItemCreate(
            type="journalArticle",
            title="Test Paper",
            abstract="Test abstract",
            doi="10.1234/test",
            tags=["test"],
            collections=["COLL1"],
        )

        result = service._item_create_to_dict(item_create)

        assert result["itemType"] == "journalArticle"
        assert result["title"] == "Test Paper"
        assert result["abstractNote"] == "Test abstract"
        assert result["DOI"] == "10.1234/test"
        assert result["tags"] == [{"tag": "test"}]
        assert result["collections"] == ["COLL1"]

    def test_item_update_to_dict(self, service):
        """Test converting ItemUpdate to dict."""
        item_update = ItemUpdate(
            title="Updated Title", abstract="New abstract", version=123
        )

        result = service._item_update_to_dict(item_update)

        assert result["title"] == "Updated Title"
        assert result["abstractNote"] == "New abstract"
        assert result["version"] == 123
        # Fields not set should not be present
        assert "creators" not in result
