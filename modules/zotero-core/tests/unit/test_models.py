"""
Unit tests for zotero-core models.
"""

import pytest
from pydantic import ValidationError


def test_item_model():
    """Test Item model creation and validation."""
    from zotero_core.models import Creator, Item

    # Test minimal item
    item = Item(
        key="ABCD1234",
        type="journalArticle",
        title="Test Paper",
    )
    assert item.key == "ABCD1234"
    assert item.type == "journalArticle"
    assert item.title == "Test Paper"
    assert item.creators == []
    assert item.tags == []

    # Test full item
    item = Item(
        key="ABCD1234",
        type="journalArticle",
        title="Test Paper",
        creators=[
            Creator(
                creator_type="author",
                first_name="John",
                last_name="Doe",
            )
        ],
        abstract="This is a test abstract.",
        date="2024",
        doi="10.1234/test.doi",
        tags=["research", "important"],
    )
    assert len(item.creators) == 1
    assert item.abstract == "This is a test abstract."
    assert item.doi == "10.1234/test.doi"
    assert item.has_tag("research")
    assert item.has_tag("IMPORTANT")  # Case insensitive


def test_item_creator_methods():
    """Test Item creator helper methods."""
    from zotero_core.models import Creator, Item

    item = Item(
        key="ABCD1234",
        type="journalArticle",
        title="Test Paper",
        creators=[
            Creator(
                creator_type="author",
                first_name="Jane",
                last_name="Smith",
            ),
            Creator(
                creator_type="editor",
                name="Bob Johnson",
            ),
        ],
    )

    names = item.get_creator_names()
    assert len(names) == 2
    assert "Smith, Jane" in names
    assert "Bob Johnson" in names

    authors = item.get_authors()
    assert len(authors) == 1
    assert "Smith, Jane" in authors


def test_collection_model():
    """Test Collection model creation and validation."""
    from zotero_core.models import Collection

    # Test root collection
    collection = Collection(
        key="ABC123",
        name="Research Papers",
        parent_key=None,
    )
    assert collection.key == "ABC123"
    assert collection.name == "Research Papers"
    assert collection.parent_key is None

    # Test nested collection
    collection = Collection(
        key="DEF456",
        name="Sub Collection",
        parent_key="ABC123",
        item_count=42,
    )
    assert collection.parent_key == "ABC123"
    assert collection.item_count == 42


def test_tag_model():
    """Test Tag model creation and validation."""
    from zotero_core.models import Tag

    tag = Tag(tag="important", count=10)
    assert tag.tag == "important"
    assert tag.count == 10


def test_search_models():
    """Test search input models."""
    from zotero_core.models import (
        AdvancedSearchCondition,
        AdvancedSearchInput,
        SearchByTagInput,
        SearchItemsInput,
        SearchMode,
        SemanticSearchInput,
    )

    # Test keyword search
    search_input = SearchItemsInput(
        query="machine learning",
        mode=SearchMode.TITLE_CREATOR_YEAR,
        limit=10,
    )
    assert search_input.query == "machine learning"
    assert search_input.mode == SearchMode.TITLE_CREATOR_YEAR

    # Test tag search
    tag_input = SearchByTagInput(
        tags=["research", "important"],
        limit=20,
    )
    assert len(tag_input.tags) == 2

    # Test advanced search
    condition = AdvancedSearchCondition(
        field="title",
        operation="contains",
        value="climate",
    )
    advanced_input = AdvancedSearchInput(
        conditions=[condition],
        join_mode="all",
    )
    assert len(advanced_input.conditions) == 1

    # Test semantic search
    semantic_input = SemanticSearchInput(
        query="papers about neural networks",
        limit=15,
    )
    assert semantic_input.query == "papers about neural networks"

    # Test validation error for empty query
    with pytest.raises(ValidationError):
        SearchItemsInput(query="   ")


def test_base_models():
    """Test base model functionality."""
    from zotero_core.models import BaseInput, BaseResponse, PaginatedInput

    # Test BaseInput
    class TestInput(BaseInput):
        name: str

    input_obj = TestInput(name="test")
    assert input_obj.name == "test"

    # Test BaseResponse
    response = BaseResponse(success=True)
    assert response.success is True
    assert response.error is None

    # Test PaginatedInput
    class TestPaginatedInput(PaginatedInput):
        query: str

    paginated = TestPaginatedInput(query="test", limit=10, offset=5)
    assert paginated.query == "test"
    assert paginated.limit == 10
    assert paginated.offset == 5
    assert paginated.limit == 10  # Default


def test_validation_errors():
    """Test model validation errors."""
    import pytest
    from pydantic import ValidationError

    from zotero_core.models import Item, SearchItemsInput

    # Test missing required fields
    with pytest.raises(ValidationError):
        Item(key="ABCD1234")  # Missing 'type' field

    # Test query validation - Pydantic validates min_length first
    with pytest.raises(ValidationError) as exc_info:
        SearchItemsInput(query="")
    assert "String should have at least 1 character" in str(exc_info.value)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
