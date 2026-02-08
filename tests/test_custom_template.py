from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from zotero_mcp.clients.llm import LLMClient
from zotero_mcp.services.workflow import WorkflowService


@pytest.mark.asyncio
async def test_llm_client_custom_template():
    """Test that LLMClient uses custom template when provided."""
    # Setup - LLMClient is DeepSeek-only, requires API key
    client = LLMClient(api_key="test_key")

    # Mock the internal _call_with_retry method to capture the prompt
    client._call_with_retry = AsyncMock(return_value="Mock Analysis")  # type: ignore

    custom_template = "My Custom Template with {title}"

    # Execute
    await client.analyze_paper(
        title="Test Paper",
        authors="Author A",
        journal="Journal B",
        date="2023",
        doi="10.1234/5678",
        fulltext="Full content",
        template=custom_template,
    )

    # Verify
    # _call_with_retry is called with (self._call_deepseek_api, prompt)
    call_args = client._call_with_retry.call_args  # type: ignore
    prompt = call_args[0][1]  # Second positional arg is the prompt

    # The implementation inserts the template string AS IS, without formatting it
    # This is to avoid format errors with user templates (e.g. ${...})
    assert custom_template in prompt
    assert "分析要求" in prompt  # Part of the wrapper prompt
    assert "请阅读上述内容，并严格按照以下模板格式生成分析报告" in prompt


@pytest.mark.asyncio
async def test_workflow_service_propagates_template():
    """Test that WorkflowService propagates template to LLM client."""

    # Mock dependencies
    mock_data_service = MagicMock()

    # Configure ItemService for BatchLoader
    mock_item_service = MagicMock()
    mock_item_service.get_item = AsyncMock(
        return_value={
            "key": "ABC",
            "data": {"publicationTitle": "Journal", "title": "Title", "creators": []},
        }
    )
    mock_item_service.get_item_children = AsyncMock(return_value=[])
    mock_item_service.get_fulltext = AsyncMock(return_value="Content")
    mock_item_service.get_annotations = AsyncMock(return_value=[])

    # Set item_service property
    # Since DataAccessService.item_service is a property, we need to mock it on the instance if possible,
    # or just set it as an attribute since MagicMock handles attributes.
    mock_data_service.item_service = mock_item_service

    # DataAccessService methods
    mock_data_service.get_notes = AsyncMock(return_value=[])
    mock_data_service.create_note = AsyncMock(
        return_value={"successful": {"0": {"key": "NOTE123"}}}
    )

    mock_llm_client = MagicMock()
    mock_llm_client.analyze_paper = AsyncMock(return_value="# Note")
    mock_llm_client.provider = "deepseek"  # Required for capability checks

    with (
        patch(
            "zotero_mcp.services.workflow.get_data_service",
            return_value=mock_data_service,
        ),
        patch("zotero_mcp.services.workflow.get_checkpoint_manager"),
        patch(
            "zotero_mcp.services.workflow.get_llm_client", return_value=mock_llm_client
        ),
    ):
        service = WorkflowService()
        service.data_service = mock_data_service  # Explicit set

        # Create a dummy item
        item = MagicMock()
        item.key = "ABC"
        item.title = "Title"

        # We need to bypass _get_items or mock it
        service._get_items = AsyncMock(return_value=[item])  # type: ignore

        # Mock Checkpoint Manager behaviors
        mock_cp = service.checkpoint_manager
        mock_cp.create_workflow.return_value = MagicMock(  # type: ignore
            workflow_id="wf_1",
            total_items=1,
            processed_keys=[],
            get_remaining_items=lambda k: ["ABC"],
        )
        mock_cp.load_state.return_value = None  # type: ignore

        # Execute
        await service.batch_analyze(
            source="recent", limit=1, template="CUSTOM_TEMPLATE_CONTENT", dry_run=False
        )

        # Verify
        mock_llm_client.analyze_paper.assert_called_once()
        call_kwargs = mock_llm_client.analyze_paper.call_args.kwargs
        assert call_kwargs["template"] == "CUSTOM_TEMPLATE_CONTENT"
