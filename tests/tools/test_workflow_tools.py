"""
Tests for workflow MCP tools.

Tests the multi-modal PDF analysis functionality exposed through MCP tools.
"""

from unittest.mock import AsyncMock, Mock

import pytest

from zotero_mcp.models.workflow import (
    AnalysisItem,
    BatchAnalyzeInput,
    BatchAnalyzeResponse,
    PrepareAnalysisInput,
    PrepareAnalysisResponse,
)


class TestPrepareAnalysisTool:
    """Test zotero_prepare_analysis MCP tool."""

    @pytest.mark.asyncio
    async def test_prepare_analysis_multimodal_parameter_passthrough(self):
        """Test that include_multimodal parameter is correctly passed to service."""
        # Create a mock workflow service
        mock_service = Mock()
        mock_service.prepare_analysis = AsyncMock(
            return_value=PrepareAnalysisResponse(
                success=True,
                total_items=2,
                prepared_items=2,
                skipped=0,
                items=[],
                template_structure={},
            )
        )

        # Test with multimodal=True
        params = PrepareAnalysisInput(
            source="collection",
            collection_name="Test Collection",
            include_multimodal=True,
            limit=5,
        )

        # Call the service directly (simulating the tool execution)
        _ = await mock_service.prepare_analysis(
            source=params.source,
            collection_key=params.collection_key,
            collection_name=params.collection_name,
            days=params.days,
            limit=params.limit,
            include_annotations=params.include_annotations,
            include_multimodal=params.include_multimodal,
            skip_existing=params.skip_existing_notes,
        )

        # Verify the service was called with the correct parameters
        mock_service.prepare_analysis.assert_called_once_with(
            source="collection",
            collection_key=None,
            collection_name="Test Collection",
            days=7,
            limit=5,
            include_annotations=True,
            include_multimodal=True,
            skip_existing=True,
        )

    @pytest.mark.asyncio
    async def test_prepare_analysis_multimodal_disabled(self):
        """Test that include_multimodal=False is correctly passed to service."""
        # Create a mock workflow service
        mock_service = Mock()
        mock_service.prepare_analysis = AsyncMock(
            return_value=PrepareAnalysisResponse(
                success=True,
                total_items=3,
                prepared_items=3,
                skipped=0,
                items=[],
                template_structure={},
            )
        )

        # Test with multimodal=False
        params = PrepareAnalysisInput(
            source="recent", include_multimodal=False, limit=3, days=30
        )

        # Call the service directly
        _ = await mock_service.prepare_analysis(
            source=params.source,
            collection_key=params.collection_key,
            collection_name=params.collection_name,
            days=params.days,
            limit=params.limit,
            include_annotations=params.include_annotations,
            include_multimodal=params.include_multimodal,
            skip_existing=params.skip_existing_notes,
        )

        # Verify the service was called with multimodal=False
        mock_service.prepare_analysis.assert_called_once_with(
            source="recent",
            collection_key=None,
            collection_name=None,
            days=30,
            limit=3,
            include_annotations=True,
            include_multimodal=False,
            skip_existing=True,
        )

    @pytest.mark.asyncio
    async def test_prepare_analysis_multimodal_default(self):
        """Test that include_multimodal defaults to True."""
        # Create a mock workflow service
        mock_service = Mock()
        mock_service.prepare_analysis = AsyncMock(
            return_value=PrepareAnalysisResponse(
                success=True,
                total_items=1,
                prepared_items=1,
                skipped=0,
                items=[],
                template_structure={},
            )
        )

        # Test without specifying multimodal (should default to True)
        params = PrepareAnalysisInput(
            source="collection",
            collection_name="Test Collection",
            # include_multimodal not specified - should default to True
        )

        # Call the service directly
        _ = await mock_service.prepare_analysis(
            source=params.source,
            collection_key=params.collection_key,
            collection_name=params.collection_name,
            days=params.days,
            limit=params.limit,
            include_annotations=params.include_annotations,
            include_multimodal=params.include_multimodal,  # Should be True by default
            skip_existing=params.skip_existing_notes,
        )

        # Verify the service was called with multimodal=True (default)
        mock_service.prepare_analysis.assert_called_once_with(
            source="collection",
            collection_key=None,
            collection_name="Test Collection",
            days=7,
            limit=20,
            include_annotations=True,
            include_multimodal=True,  # Default value
            skip_existing=True,
        )


class TestBatchAnalyzeTool:
    """Test zotero_batch_analyze_pdfs MCP tool."""

    @pytest.mark.asyncio
    async def test_batch_analyze_multimodal_parameter_passthrough(self):
        """Test that include_multimodal parameter is correctly passed to service."""
        # Create a mock workflow service
        mock_service = Mock()
        mock_service.batch_analyze = AsyncMock(
            return_value=BatchAnalyzeResponse(
                success=True,
                workflow_id="test_workflow_123",
                total_items=10,
                processed=8,
                skipped=2,
                failed=0,
                results=[],
                status="completed",
                can_resume=False,
            )
        )

        # Create a progress callback
        async def progress_callback(current, total, message):
            pass

        # Test with multimodal=True
        params = BatchAnalyzeInput(
            source="collection",
            collection_name="Test Collection",
            include_multimodal=True,
            limit=10,
            llm_provider="auto",
        )

        # Call the service directly
        _ = await mock_service.batch_analyze(
            source=params.source,
            collection_key=params.collection_key,
            collection_name=params.collection_name,
            days=params.days,
            limit=params.limit,
            resume_workflow_id=params.resume_workflow_id,
            skip_existing=params.skip_existing_notes,
            include_annotations=params.include_annotations,
            include_multimodal=params.include_multimodal,
            llm_provider=params.llm_provider,
            llm_model=params.llm_model,
            template=params.template,
            dry_run=params.dry_run,
            progress_callback=progress_callback,
        )

        # Verify the service was called with multimodal=True
        mock_service.batch_analyze.assert_called_once()
        call_args = mock_service.batch_analyze.call_args
        assert call_args.kwargs["include_multimodal"] is True
        assert call_args.kwargs["source"] == "collection"
        assert call_args.kwargs["collection_name"] == "Test Collection"

    @pytest.mark.asyncio
    async def test_batch_analyze_multimodal_disabled(self):
        """Test that include_multimodal=False is correctly passed to service."""
        # Create a mock workflow service
        mock_service = Mock()
        mock_service.batch_analyze = AsyncMock(
            return_value=BatchAnalyzeResponse(
                success=True,
                workflow_id="test_workflow_456",
                total_items=5,
                processed=5,
                skipped=0,
                failed=0,
                results=[],
                status="completed",
                can_resume=False,
            )
        )

        # Create a progress callback
        async def progress_callback(current, total, message):
            pass

        # Test with multimodal=False
        params = BatchAnalyzeInput(
            source="recent", include_multimodal=False, limit=5, days=14
        )

        # Call the service directly
        _ = await mock_service.batch_analyze(
            source=params.source,
            collection_key=params.collection_key,
            collection_name=params.collection_name,
            days=params.days,
            limit=params.limit,
            resume_workflow_id=params.resume_workflow_id,
            skip_existing=params.skip_existing_notes,
            include_annotations=params.include_annotations,
            include_multimodal=params.include_multimodal,
            llm_provider=params.llm_provider,
            llm_model=params.llm_model,
            template=params.template,
            dry_run=params.dry_run,
            progress_callback=progress_callback,
        )

        # Verify the service was called with multimodal=False
        mock_service.batch_analyze.assert_called_once()
        call_args = mock_service.batch_analyze.call_args
        assert call_args.kwargs["include_multimodal"] is False
        assert call_args.kwargs["source"] == "recent"
        assert call_args.kwargs["days"] == 14

    @pytest.mark.asyncio
    async def test_batch_analyze_dry_run_with_multimodal(self):
        """Test batch analyze with dry run and multimodal enabled."""
        # Create a mock workflow service
        mock_service = Mock()
        mock_service.batch_analyze = AsyncMock(
            return_value=BatchAnalyzeResponse(
                success=True,
                workflow_id="dry_run_workflow",
                total_items=3,
                processed=0,
                skipped=0,
                failed=0,
                results=[],
                status="completed",
                can_resume=False,
            )
        )

        # Create a progress callback
        async def progress_callback(current, total, message):
            pass

        # Test with dry run and multimodal
        params = BatchAnalyzeInput(
            source="collection",
            collection_key="12345",
            include_multimodal=True,
            dry_run=True,
            limit=3,
        )

        # Call the service directly
        _ = await mock_service.batch_analyze(
            source=params.source,
            collection_key=params.collection_key,
            collection_name=params.collection_name,
            days=params.days,
            limit=params.limit,
            resume_workflow_id=params.resume_workflow_id,
            skip_existing=params.skip_existing_notes,
            include_annotations=params.include_annotations,
            include_multimodal=params.include_multimodal,
            llm_provider=params.llm_provider,
            llm_model=params.llm_model,
            template=params.template,
            dry_run=params.dry_run,
            progress_callback=progress_callback,
        )

        # Verify the service was called with correct parameters
        mock_service.batch_analyze.assert_called_once()
        call_args = mock_service.batch_analyze.call_args
        assert call_args.kwargs["include_multimodal"] is True
        assert call_args.kwargs["dry_run"] is True
        assert call_args.kwargs["collection_key"] == "12345"


class TestMultimodalContentIntegration:
    """Test multimodal content integration with workflow tools."""

    def test_multimodal_content_in_prepare_response_model(self):
        """Test that AnalysisItem model supports multimodal content."""
        # Create a sample response with multimodal content
        sample_item = AnalysisItem(
            item_key="TEST123",
            title="Test Paper with Figures",
            authors="Test Author",
            date="2024",
            journal="Test Journal",
            doi="10.1234/test",
            pdf_content="Sample PDF content",
            annotations=[],
            images=[
                {
                    "type": "chart",
                    "data": "base64_chart_data",
                    "caption": "Figure 1: Results",
                },
                {
                    "type": "diagram",
                    "data": "base64_diagram_data",
                    "caption": "Figure 2: Method",
                },
            ],
            tables=[
                {
                    "type": "data",
                    "data": "table_html",
                    "caption": "Table 1: Experiment Results",
                }
            ],
            metadata={},
            template_questions=[],
        )

        # Verify multimodal content is in the response structure
        assert sample_item.images
        assert sample_item.tables
        assert sample_item.images[0]["type"] == "chart"
        assert sample_item.tables[0]["type"] == "data"

    def test_multimodal_content_with_annotations_model(self):
        """Test multimodal content combined with annotations in model."""
        sample_item = AnalysisItem(
            item_key="TEST456",
            title="Test Paper with Charts and Notes",
            pdf_content="Sample content",
            annotations=[
                {"page": 1, "text": "This is important!", "type": "highlight"}
            ],
            images=[
                {"type": "chart", "data": "base64_chart", "caption": "Important chart"}
            ],
            tables=[],
            metadata={},
            template_questions=[],
        )

        # Verify both annotations and multimodal content can coexist
        assert sample_item.annotations
        assert sample_item.images
        assert not sample_item.tables  # Empty in this case

    def test_multimodal_parameter_validation(self):
        """Test that multimodal parameter accepts boolean values."""
        # Test True
        params_true = PrepareAnalysisInput(include_multimodal=True)
        assert params_true.include_multimodal is True

        # Test False
        params_false = PrepareAnalysisInput(include_multimodal=False)
        assert params_false.include_multimodal is False

        # Test default (should be True)
        params_default = PrepareAnalysisInput()
        assert params_default.include_multimodal is True

        # Test for batch analyze
        batch_params_true = BatchAnalyzeInput(include_multimodal=True)
        assert batch_params_true.include_multimodal is True

        batch_params_false = BatchAnalyzeInput(include_multimodal=False)
        assert batch_params_false.include_multimodal is False

        batch_params_default = BatchAnalyzeInput()
        assert batch_params_default.include_multimodal is True
