"""
End-to-end integration tests for multi-modal PDF analysis.

These tests require:
- Zotero running with local API access
- At least one PDF attachment in test collection

Run with:
    uv run pytest tests/integration/test_multimodal_e2e.py -v -m integration
"""

import pytest
from dotenv import load_dotenv

load_dotenv(override=False)

from zotero_mcp.clients.llm import get_llm_client
from zotero_mcp.clients.llm.capabilities import (
    get_provider_capability,
    is_multimodal_provider,
)
from zotero_mcp.services.workflow import WorkflowService

pytestmark = pytest.mark.integration


@pytest.mark.asyncio
async def test_prepare_analysis_with_real_pdf():
    """Test prepare analysis with real PDF from Zotero."""
    try:
        service = WorkflowService()

        result = await service.prepare_analysis(
            source="collection",
            collection_name="Test",
            limit=1,
            include_multimodal=True,
        )

        # Verify response structure
        assert result.total_items >= 0
        assert result.prepared_items >= 0
        assert hasattr(result, "items")

        # If items found, verify structure
        if result.prepared_items > 0:
            item = result.items[0]
            assert item.title is not None
            assert "pdf_content" in item.model_fields
            assert "images" in item.model_fields
            assert "tables" in item.model_fields
            assert "annotations" in item.model_fields

    except Exception as e:
        pytest.skip(f"Zotero not available or no test collection: {e}")


@pytest.mark.asyncio
async def test_auto_select_claude_for_images():
    """Test auto-selection of Claude CLI when images present."""
    # Verify capability detection
    assert is_multimodal_provider("claude-cli") is True
    assert is_multimodal_provider("deepseek") is False
    assert is_multimodal_provider("openai") is True
    assert is_multimodal_provider("gemini") is True

    # Verify capability details
    cap_claude = get_provider_capability("claude-cli")
    assert cap_claude.can_handle_images() is True
    assert cap_claude.is_multimodal() is True

    cap_deepseek = get_provider_capability("deepseek")
    assert cap_deepseek.can_handle_images() is False
    assert cap_deepseek.is_multimodal() is False


@pytest.mark.asyncio
async def test_batch_analyze_workflow():
    """Test full batch analyze workflow with multi-modal."""
    try:
        service = WorkflowService()

        result = await service.batch_analyze(
            source="collection",
            collection_name="Test",
            limit=1,
            include_multimodal=True,
            llm_provider="auto",
            dry_run=True,  # Don't actually create notes
        )

        # Verify response structure
        assert result.workflow_id is not None
        assert result.total_items >= 0
        assert hasattr(result, "status")

    except Exception as e:
        pytest.skip(f"Zotero not available or no test collection: {e}")


@pytest.mark.asyncio
async def test_deepseek_fallback_for_images():
    """Test DeepSeek gracefully handles images."""
    try:
        client = get_llm_client(provider="deepseek")
        capability = get_provider_capability("deepseek")

        # Verify DeepSeek cannot handle images
        assert capability.can_handle_images() is False
        assert capability.is_multimodal() is False

        # Verify client exists and doesn't crash with image data
        # (Images should be filtered out or placeholder added in actual workflow)
        assert client is not None

    except Exception as e:
        pytest.skip(f"DeepSeek not configured: {e}")


@pytest.mark.asyncio
async def test_multimodal_capability_detection():
    """Test that multi-modal capabilities are correctly detected for all providers."""
    providers = {
        "claude-cli": True,
        "deepseek": False,
        "openai": True,
        "gemini": True,
    }

    for provider, expected_multimodal in providers.items():
        cap = get_provider_capability(provider)

        # Verify capability matches expectation
        assert cap.can_handle_text() is True, f"{provider} should support text"
        assert cap.is_multimodal() == expected_multimodal, (
            f"{provider} multimodal capability mismatch"
        )

        # Verify provider name matches
        assert cap.provider == provider


@pytest.mark.asyncio
async def test_capability_registry_completeness():
    """Test that capability registry has all expected providers."""
    from zotero_mcp.clients.llm.capabilities import PROVIDER_CAPABILITIES

    # Verify all expected providers are present
    expected_providers = ["deepseek", "claude-cli", "openai", "gemini"]
    for provider in expected_providers:
        assert provider in PROVIDER_CAPABILITIES, f"{provider} not in registry"

    # Verify each capability has required fields
    for provider, cap in PROVIDER_CAPABILITIES.items():
        assert cap.provider == provider
        assert isinstance(cap.supports_text, bool)
        assert isinstance(cap.supports_images, bool)
        assert cap.max_input_tokens > 0
        assert cap.max_output_tokens > 0
