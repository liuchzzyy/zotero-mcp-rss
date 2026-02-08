"""Test WorkflowService multi-modal integration."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from zotero_mcp.models.workflow import AnalysisItem
from zotero_mcp.services.workflow import WorkflowService


@pytest.fixture
def mock_data_service():
    """Mock data service."""
    service = AsyncMock()
    service.item_service = AsyncMock()
    return service


@pytest.fixture
def mock_batch_loader(mock_data_service):
    """Mock batch loader."""
    with patch("zotero_mcp.services.workflow.BatchLoader") as mock:
        loader = MagicMock()
        loader.fetch_many_bundles = AsyncMock()
        mock.return_value = loader
        yield loader


@pytest.fixture
def mock_checkpoint_manager():
    """Mock checkpoint manager."""
    with patch("zotero_mcp.services.workflow.get_checkpoint_manager") as mock:
        manager = MagicMock()
        mock.return_value = manager
        yield manager


@pytest.fixture
def workflow_service(mock_data_service, mock_checkpoint_manager, mock_batch_loader):
    """Create workflow service with mocked dependencies."""
    with patch(
        "zotero_mcp.services.workflow.get_data_service", return_value=mock_data_service
    ):
        service = WorkflowService()
        service.data_service = mock_data_service
        service.batch_loader = mock_batch_loader
        yield service


@pytest.fixture
def sample_bundle_with_multimodal():
    """Sample item bundle with multi-modal content."""
    return {
        "metadata": {
            "key": "TEST123",
            "data": {
                "title": "Test Paper with Images",
                "creators": [
                    {"firstName": "John", "lastName": "Doe", "creatorType": "author"}
                ],
                "date": "2024",
                "publicationTitle": "Test Journal",
                "DOI": "10.1234/test",
                "itemType": "journalArticle",
                "abstractNote": "Test abstract",
                "tags": [],
            },
        },
        "fulltext": "This is the full text content of the paper.",
        "annotations": [],
        "notes": [],
        "multimodal": {
            "images": [
                {
                    "index": 0,
                    "page": 1,
                    "bbox": [100, 200, 300, 400],
                    "base64": "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg==",  # 1x1 pixel PNG
                    "format": "png",
                }
            ],
            "tables": [
                {
                    "page": 2,
                    "bbox": [50, 100, 500, 300],
                    "markdown": "| Col1 | Col2 |\n|------|------|\n| Val1 | Val2 |",
                }
            ],
        },
    }


@pytest.fixture
def sample_bundle_text_only():
    """Sample item bundle without multi-modal content."""
    return {
        "metadata": {
            "key": "TEST456",
            "data": {
                "title": "Text Only Paper",
                "creators": [
                    {"firstName": "Jane", "lastName": "Smith", "creatorType": "author"}
                ],
                "date": "2024",
                "publicationTitle": "Another Journal",
                "DOI": "10.5678/test2",
                "itemType": "journalArticle",
                "abstractNote": "Another abstract",
                "tags": [],
            },
        },
        "fulltext": "This paper has only text content.",
        "annotations": [],
        "notes": [],
        "multimodal": {
            "images": [],
            "tables": [],
        },
    }


# -------------------- Test _extract_bundle_context --------------------


def test_extract_bundle_context_with_multimodal(
    workflow_service, sample_bundle_with_multimodal
):
    """Test extracting bundle context with multi-modal content."""
    context = workflow_service._extract_bundle_context(
        sample_bundle_with_multimodal, include_multimodal=True
    )

    assert context["fulltext"] == "This is the full text content of the paper."
    assert context["annotations"] == []
    assert len(context["images"]) == 1
    assert context["images"][0]["page"] == 1
    assert len(context["tables"]) == 1
    assert context["tables"][0]["page"] == 2


def test_extract_bundle_context_without_multimodal(
    workflow_service, sample_bundle_with_multimodal
):
    """Test extracting bundle context without multi-modal content."""
    context = workflow_service._extract_bundle_context(
        sample_bundle_with_multimodal, include_multimodal=False
    )

    assert context["fulltext"] == "This is the full text content of the paper."
    assert context["annotations"] == []
    assert context["images"] == []
    assert context["tables"] == []


def test_extract_bundle_context_text_only(workflow_service, sample_bundle_text_only):
    """Test extracting bundle context from text-only paper."""
    context = workflow_service._extract_bundle_context(
        sample_bundle_text_only, include_multimodal=True
    )

    assert context["fulltext"] == "This paper has only text content."
    assert context["images"] == []
    assert context["tables"] == []


# -------------------- Test _validate_context --------------------


def test_validate_context_valid(workflow_service):
    """Test context validation with valid data."""
    item = MagicMock()
    item.key = "TEST123"

    context = {"fulltext": "Some content", "annotations": []}
    result = workflow_service._validate_context(item, context, 0.0)

    assert result is None  # No error result


def test_validate_context_missing_fulltext(workflow_service):
    """Test context validation with missing fulltext."""
    item = MagicMock()
    item.key = "TEST123"
    item.title = "Test Title"  # Provide actual string for Pydantic

    context = {"fulltext": None, "annotations": []}
    result = workflow_service._validate_context(item, context, 0.0)

    assert result is not None
    assert result.success is False
    assert "无法获取 PDF 全文内容" in result.error


# -------------------- Test prepare_analysis multi-modal --------------------


@pytest.mark.asyncio
async def test_prepare_analysis_includes_multimodal(
    workflow_service, mock_batch_loader
):
    """Test that prepare_analysis includes multi-modal content."""
    # Mock get_items
    items = [MagicMock(key="ITEM1", title="Paper 1")]
    workflow_service._get_items = AsyncMock(return_value=items)

    # Mock get_notes (no existing notes)
    workflow_service.data_service.get_notes = AsyncMock(return_value=[])

    # Mock bundle fetch with multi-modal content
    bundle = {
        "metadata": {
            "key": "ITEM1",
            "data": {
                "title": "Paper 1",
                "creators": [],
                "date": "2024",
                "publicationTitle": "Journal",
                "DOI": "10.1234/paper1",
                "itemType": "journalArticle",
                "abstractNote": "Abstract",
                "tags": [],
            },
        },
        "fulltext": "Full text",
        "annotations": [],
        "multimodal": {
            "images": [{"index": 0, "page": 1, "base64": "ABC123", "format": "png"}],
            "tables": [],
        },
    }
    mock_batch_loader.fetch_many_bundles = AsyncMock(return_value=[bundle])

    # Call prepare_analysis with include_multimodal=True
    response = await workflow_service.prepare_analysis(
        source="collection",
        collection_key="COLL1",
        include_multimodal=True,
    )

    assert response.total_items == 1
    assert response.prepared_items == 1
    assert len(response.items) == 1

    item = response.items[0]
    assert isinstance(item, AnalysisItem)
    assert len(item.images) == 1
    assert item.images[0]["page"] == 1
    assert item.tables == []


@pytest.mark.asyncio
async def test_prepare_analysis_excludes_multimodal(
    workflow_service, mock_batch_loader
):
    """Test that prepare_analysis excludes multi-modal content when requested."""
    # Mock get_items
    items = [MagicMock(key="ITEM1", title="Paper 1")]
    workflow_service._get_items = AsyncMock(return_value=items)

    # Mock get_notes (no existing notes)
    workflow_service.data_service.get_notes = AsyncMock(return_value=[])

    # Mock bundle fetch
    bundle = {
        "metadata": {
            "key": "ITEM1",
            "data": {
                "title": "Paper 1",
                "creators": [],
                "date": "2024",
                "publicationTitle": "Journal",
                "DOI": "10.1234/paper1",
                "itemType": "journalArticle",
                "abstractNote": "Abstract",
                "tags": [],
            },
        },
        "fulltext": "Full text",
        "annotations": [],
        "multimodal": {
            "images": [{"index": 0, "page": 1, "base64": "ABC123", "format": "png"}],
            "tables": [],
        },
    }
    mock_batch_loader.fetch_many_bundles = AsyncMock(return_value=[bundle])

    # Call with include_multimodal=False - should still fetch but not include in response
    response = await workflow_service.prepare_analysis(
        source="collection",
        collection_key="COLL1",
        include_multimodal=False,
    )

    assert response.prepared_items == 1
    item = response.items[0]
    assert len(item.images) == 0
    assert len(item.tables) == 0


# -------------------- Test LLM auto-selection --------------------


@pytest.mark.asyncio
async def test_batch_analyze_auto_selects_multimodal_llm(
    workflow_service, mock_batch_loader
):
    """Test that batch_analyze auto-selects multi-modal LLM when images present."""
    # Mock items
    items = [MagicMock(key="ITEM1", title="Paper with Images")]
    items[0].authors = "John Doe"
    items[0].date = "2024"
    items[0].doi = "10.1234/test"
    workflow_service._get_items = AsyncMock(return_value=items)

    # Mock checkpoint workflow
    workflow = MagicMock()
    workflow.workflow_id = "WF123"
    workflow.total_items = 1
    processed_list = []

    # Make mark_processed actually add to processed_keys
    def mock_mark_processed(key):
        processed_list.append(key)

    workflow.processed_keys = processed_list
    workflow.skipped_keys = []
    workflow.failed_keys = []
    workflow.mark_processed = MagicMock(side_effect=mock_mark_processed)
    workflow.mark_failed = MagicMock()
    workflow.get_remaining_items = MagicMock(return_value=["ITEM1"])
    workflow_state = workflow

    workflow_service.checkpoint_manager.create_workflow = MagicMock(
        return_value=workflow_state
    )
    workflow_service.checkpoint_manager.save_state = MagicMock()

    # Mock bundle with images - called twice (auto-select + actual)
    bundle_with_images = {
        "metadata": {
            "key": "ITEM1",
            "data": {"title": "Paper with Images", "creators": [], "date": "2024"},
        },
        "fulltext": "Full text",
        "annotations": [],
        "notes": [],
        "multimodal": {
            "images": [{"index": 0, "page": 1, "base64": "ABC123", "format": "png"}],
            "tables": [],
        },
    }

    # Mock fetch_many_bundles to return appropriate bundle based on call
    async def mock_fetch(
        keys,
        include_fulltext=False,
        include_annotations=False,
        include_multimodal=False,
    ):
        return [bundle_with_images]

    mock_batch_loader.fetch_many_bundles = AsyncMock(side_effect=mock_fetch)

    # Mock LLM client
    mock_llm_client = AsyncMock()
    mock_llm_client.provider = "claude-cli"
    mock_llm_client.analyze_paper = AsyncMock(return_value="Analysis result")

    # Mock data service operations
    workflow_service.data_service.get_notes = AsyncMock(return_value=[])
    workflow_service.data_service.create_note = AsyncMock(
        return_value={"successful": {"NOTE1": {"key": "NOTE1"}}}
    )

    with patch(
        "zotero_mcp.services.workflow.get_llm_client", return_value=mock_llm_client
    ):
        response = await workflow_service.batch_analyze(
            source="collection",
            collection_key="COLL1",
            llm_provider="auto",  # Auto-select
            include_multimodal=True,
        )

    # Should have processed successfully
    assert response.total_items == 1
    assert response.processed == 1
    assert len(response.results) == 1
    assert response.results[0].success is True


@pytest.mark.asyncio
async def test_batch_analyze_auto_selects_text_llm(workflow_service, mock_batch_loader):
    """Test that batch_analyze auto-selects text-only LLM when no images."""
    # Mock items
    items = [MagicMock(key="ITEM1", title="Text Only Paper")]
    items[0].authors = "Jane Smith"
    items[0].date = "2024"
    items[0].doi = "10.5678/test2"
    workflow_service._get_items = AsyncMock(return_value=items)

    # Mock checkpoint workflow
    workflow = MagicMock()
    workflow.workflow_id = "WF123"
    workflow.total_items = 1
    processed_list = []

    # Make mark_processed actually add to processed_keys
    def mock_mark_processed(key):
        processed_list.append(key)

    workflow.processed_keys = processed_list
    workflow.skipped_keys = []
    workflow.failed_keys = []
    workflow.mark_processed = MagicMock(side_effect=mock_mark_processed)
    workflow.mark_failed = MagicMock()
    workflow.get_remaining_items = MagicMock(return_value=["ITEM1"])
    workflow_state = workflow

    workflow_service.checkpoint_manager.create_workflow = MagicMock(
        return_value=workflow_state
    )
    workflow_service.checkpoint_manager.save_state = MagicMock()

    # Mock bundle without images - called twice (auto-select + actual)
    bundle_no_images = {
        "metadata": {
            "key": "ITEM1",
            "data": {"title": "Text Only Paper", "creators": [], "date": "2024"},
        },
        "fulltext": "Full text",
        "annotations": [],
        "notes": [],
        "multimodal": {"images": [], "tables": []},
    }

    # Mock fetch_many_bundles
    async def mock_fetch(
        keys,
        include_fulltext=False,
        include_annotations=False,
        include_multimodal=False,
    ):
        return [bundle_no_images]

    mock_batch_loader.fetch_many_bundles = AsyncMock(side_effect=mock_fetch)

    # Mock LLM client
    mock_llm_client = AsyncMock()
    mock_llm_client.provider = "deepseek"
    mock_llm_client.analyze_paper = AsyncMock(return_value="Analysis result")

    # Mock data service operations
    workflow_service.data_service.get_notes = AsyncMock(return_value=[])
    workflow_service.data_service.create_note = AsyncMock(
        return_value={"successful": {"NOTE1": {"key": "NOTE1"}}}
    )

    with patch(
        "zotero_mcp.services.workflow.get_llm_client", return_value=mock_llm_client
    ):
        response = await workflow_service.batch_analyze(
            source="collection",
            collection_key="COLL1",
            llm_provider="auto",  # Auto-select
            include_multimodal=True,
        )

    # Should have processed successfully
    assert response.total_items == 1
    assert response.processed == 1


# -------------------- Test _call_llm_analysis with images --------------------


@pytest.mark.asyncio
async def test_call_llm_analysis_sends_images_to_vision_llm(workflow_service):
    """Test that images are sent to vision-capable LLM."""
    item = MagicMock()
    item.title = "Test Paper"
    item.authors = "John Doe"
    item.date = "2024"
    item.doi = "10.1234/test"

    llm_client = AsyncMock()
    llm_client.provider = "claude-cli"
    llm_client.analyze_paper = AsyncMock(return_value="Analysis with images")

    metadata = {"data": {"publicationTitle": "Test Journal"}}

    # Call with images
    images = [{"index": 0, "page": 1, "base64": "ABC123", "format": "png"}]
    result = await workflow_service._call_llm_analysis(
        item=item,
        llm_client=llm_client,
        metadata=metadata,
        fulltext="Full text",
        annotations=[],
        template="",
        images=images,
    )

    assert result == "Analysis with images"
    llm_client.analyze_paper.assert_called_once()
    call_args = llm_client.analyze_paper.call_args
    assert call_args.kwargs["images"] == images


@pytest.mark.asyncio
async def test_call_llm_analysis_no_images_for_text_llm(workflow_service):
    """Test that images are NOT sent to text-only LLM."""
    item = MagicMock()
    item.title = "Test Paper"
    item.authors = "John Doe"
    item.date = "2024"
    item.doi = "10.1234/test"

    llm_client = AsyncMock()
    llm_client.provider = "deepseek"
    llm_client.analyze_paper = AsyncMock(return_value="Text analysis")

    metadata = {"data": {"publicationTitle": "Test Journal"}}

    # Call without images (None)
    result = await workflow_service._call_llm_analysis(
        item=item,
        llm_client=llm_client,
        metadata=metadata,
        fulltext="Full text",
        annotations=[],
        template="",
        images=None,
    )

    assert result == "Text analysis"
    llm_client.analyze_paper.assert_called_once()
    call_args = llm_client.analyze_paper.call_args
    assert call_args.kwargs["images"] is None
