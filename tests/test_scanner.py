"""Tests for GlobalScanner behavior."""

from types import SimpleNamespace
from typing import Any, cast
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from zotero_mcp.services.scanner import GlobalScanner


@pytest.mark.asyncio
async def test_scan_skips_items_without_fulltext_instead_of_failing():
    """Items without fulltext should be skipped and not counted as failures."""
    item = MagicMock()
    item.key = "ITEM1"
    item.title = "Paper 1"
    item.data = {"tags": []}

    data_service = AsyncMock()
    data_service.find_collection_by_name = AsyncMock(
        return_value=[{"key": "COLL1", "data": {"name": "00_INBOXS"}}]
    )
    data_service.get_collection_items = AsyncMock(side_effect=[[item], []])
    data_service.get_item_children = AsyncMock(
        return_value=[{"data": {"contentType": "application/pdf"}}]
    )
    data_service.get_sorted_collections = AsyncMock(return_value=[])

    workflow_service = MagicMock()
    workflow_service._analyze_single_item = AsyncMock()

    with (
        patch(
            "zotero_mcp.services.scanner.get_data_service",
            return_value=data_service,
        ),
        patch(
            "zotero_mcp.services.scanner.get_workflow_service",
            return_value=workflow_service,
        ),
        patch("zotero_mcp.clients.llm.get_llm_client", return_value=MagicMock()),
    ):
        scanner = GlobalScanner()
        loader = cast(Any, scanner.batch_loader)
        loader.fetch_many_bundles = AsyncMock(
            return_value=[{"metadata": {"key": "ITEM1"}, "fulltext": None}]
        )

        result = await scanner.scan_and_process(
            scan_limit=10,
            treated_limit=1,
            target_collection="01_SHORTTERMS",
            source_collection="00_INBOXS",
            dry_run=False,
        )

    assert result["candidates"] == 1
    assert result["processed"] == 0
    assert result["failed"] == 0
    assert result["skipped_no_fulltext"] == 1
    assert "skipped_no_fulltext 1" in result["message"]


@pytest.mark.asyncio
async def test_scan_rejects_invalid_limits():
    with (
        patch("zotero_mcp.services.scanner.get_data_service", return_value=AsyncMock()),
        patch(
            "zotero_mcp.services.scanner.get_workflow_service",
            return_value=MagicMock(),
        ),
    ):
        scanner = GlobalScanner()
        result = await scanner.scan_and_process(
            scan_limit=0,
            treated_limit=1,
            target_collection="01_SHORTTERMS",
        )

    assert result["error"] == "invalid scanner parameters"
    assert result["operation"] == "global_scan"
    assert result["status"] == "validation_error"
    assert result["success"] is False


@pytest.mark.asyncio
async def test_check_item_needs_analysis_skips_non_library_item_types():
    data_service = AsyncMock()
    data_service.get_item_children = AsyncMock()

    with (
        patch(
            "zotero_mcp.services.scanner.get_data_service",
            return_value=data_service,
        ),
        patch(
            "zotero_mcp.services.scanner.get_workflow_service",
            return_value=MagicMock(),
        ),
    ):
        scanner = GlobalScanner()
        note_item = MagicMock()
        note_item.key = "NOTE1"
        note_item.data = {"itemType": "note", "tags": []}

        needs_analysis = await scanner._check_item_needs_analysis(note_item)

    assert needs_analysis is False
    data_service.get_item_children.assert_not_awaited()


@pytest.mark.asyncio
async def test_check_item_needs_analysis_skips_items_with_parent_item():
    data_service = AsyncMock()
    data_service.get_item_children = AsyncMock()

    with (
        patch(
            "zotero_mcp.services.scanner.get_data_service",
            return_value=data_service,
        ),
        patch(
            "zotero_mcp.services.scanner.get_workflow_service",
            return_value=MagicMock(),
        ),
    ):
        scanner = GlobalScanner()
        child_item = SimpleNamespace(
            key="CHILD1",
            item_type="journalArticle",
            tags=[],
            raw_data={
                "itemType": "journalArticle",
                "parentItem": "PARENT1",
                "tags": [],
            },
        )

        needs_analysis = await scanner._check_item_needs_analysis(child_item)

    assert needs_analysis is False
    data_service.get_item_children.assert_not_awaited()


@pytest.mark.asyncio
async def test_scan_uses_text_only_initial_fetch_for_deepseek():
    item = MagicMock()
    item.key = "ITEM1"
    item.title = "Paper 1"
    item.data = {"tags": []}

    data_service = AsyncMock()
    data_service.find_collection_by_name = AsyncMock(
        return_value=[{"key": "COLL1", "data": {"name": "00_INBOXS"}}]
    )
    data_service.get_collection_items = AsyncMock(side_effect=[[item], []])
    data_service.get_item_children = AsyncMock(
        return_value=[{"data": {"contentType": "application/pdf"}}]
    )
    data_service.get_sorted_collections = AsyncMock(return_value=[])

    workflow_service = MagicMock()
    workflow_service._analyze_single_item = AsyncMock(
        return_value=SimpleNamespace(success=True, skipped=False, error=None)
    )

    deepseek_client = MagicMock()
    deepseek_client.provider = "deepseek"

    with (
        patch(
            "zotero_mcp.services.scanner.get_data_service",
            return_value=data_service,
        ),
        patch(
            "zotero_mcp.services.scanner.get_workflow_service",
            return_value=workflow_service,
        ),
        patch("zotero_mcp.clients.llm.get_llm_client", return_value=deepseek_client),
    ):
        scanner = GlobalScanner()
        loader = cast(Any, scanner.batch_loader)
        loader.fetch_many_bundles = AsyncMock(
            return_value=[{"metadata": {"key": "ITEM1"}, "fulltext": "text"}]
        )

        result = await scanner.scan_and_process(
            scan_limit=10,
            treated_limit=1,
            target_collection="01_SHORTTERMS",
            source_collection="00_INBOXS",
            dry_run=False,
            llm_provider="deepseek",
        )

    assert result["processed"] == 1
    first_call = loader.fetch_many_bundles.await_args_list[0]
    assert first_call.kwargs["include_multimodal"] is False
    analyze_call = workflow_service._analyze_single_item.await_args
    assert analyze_call.kwargs["template"] == "auto"


@pytest.mark.asyncio
async def test_scan_backfills_multimodal_only_for_missing_fulltext_items():
    item = MagicMock()
    item.key = "ITEM1"
    item.title = "Paper 1"
    item.data = {"tags": []}

    data_service = AsyncMock()
    data_service.find_collection_by_name = AsyncMock(
        return_value=[{"key": "COLL1", "data": {"name": "00_INBOXS"}}]
    )
    data_service.get_collection_items = AsyncMock(side_effect=[[item], []])
    data_service.get_item_children = AsyncMock(
        return_value=[{"data": {"contentType": "application/pdf"}}]
    )
    data_service.get_sorted_collections = AsyncMock(return_value=[])

    workflow_service = MagicMock()
    workflow_service._analyze_single_item = AsyncMock(
        return_value=SimpleNamespace(success=True, skipped=False, error=None)
    )

    deepseek_client = MagicMock()
    deepseek_client.provider = "deepseek"

    with (
        patch(
            "zotero_mcp.services.scanner.get_data_service",
            return_value=data_service,
        ),
        patch(
            "zotero_mcp.services.scanner.get_workflow_service",
            return_value=workflow_service,
        ),
        patch("zotero_mcp.clients.llm.get_llm_client", return_value=deepseek_client),
    ):
        scanner = GlobalScanner()
        loader = cast(Any, scanner.batch_loader)
        loader.fetch_many_bundles = AsyncMock(
            side_effect=[
                [{"metadata": {"key": "ITEM1"}, "fulltext": None}],
                [
                    {
                        "metadata": {"key": "ITEM1"},
                        "multimodal": {"text_blocks": [{"type": "text"}]},
                    }
                ],
            ]
        )

        result = await scanner.scan_and_process(
            scan_limit=10,
            treated_limit=1,
            target_collection="01_SHORTTERMS",
            source_collection="00_INBOXS",
            dry_run=False,
            llm_provider="deepseek",
        )

    assert result["processed"] == 1
    assert result["skipped_no_fulltext"] == 0
    assert loader.fetch_many_bundles.await_count == 2
    first_call = loader.fetch_many_bundles.await_args_list[0]
    second_call = loader.fetch_many_bundles.await_args_list[1]
    assert first_call.kwargs["include_fulltext"] is True
    assert first_call.kwargs["include_multimodal"] is False
    assert second_call.kwargs["include_fulltext"] is False
    assert second_call.kwargs["include_multimodal"] is True


@pytest.mark.asyncio
async def test_scan_auto_selects_claude_when_images_present():
    item = MagicMock()
    item.key = "ITEM1"
    item.title = "Paper 1"
    item.data = {"tags": []}

    data_service = AsyncMock()
    data_service.find_collection_by_name = AsyncMock(
        return_value=[{"key": "COLL1", "data": {"name": "00_INBOXS"}}]
    )
    data_service.get_collection_items = AsyncMock(side_effect=[[item], []])
    data_service.get_item_children = AsyncMock(
        return_value=[{"data": {"contentType": "application/pdf"}}]
    )
    data_service.get_sorted_collections = AsyncMock(return_value=[])

    workflow_service = MagicMock()
    workflow_service._analyze_single_item = AsyncMock(
        return_value=SimpleNamespace(success=True, skipped=False, error=None)
    )

    claude_client = MagicMock()
    claude_client.provider = "claude-cli"

    with (
        patch(
            "zotero_mcp.services.scanner.get_data_service",
            return_value=data_service,
        ),
        patch(
            "zotero_mcp.services.scanner.get_workflow_service",
            return_value=workflow_service,
        ),
        patch(
            "zotero_mcp.clients.llm.get_llm_client",
            return_value=claude_client,
        ) as mock_get_client,
    ):
        scanner = GlobalScanner()
        loader = cast(Any, scanner.batch_loader)
        loader.fetch_many_bundles = AsyncMock(
            side_effect=[
                [
                    {
                        "metadata": {"key": "ITEM1"},
                        "multimodal": {"images": [{"type": "figure"}]},
                    }
                ],
                [{"metadata": {"key": "ITEM1"}, "fulltext": "text"}],
            ]
        )

        result = await scanner.scan_and_process(
            scan_limit=10,
            treated_limit=1,
            target_collection="01_SHORTTERMS",
            source_collection="00_INBOXS",
            dry_run=False,
            llm_provider="auto",
        )

    assert result["processed"] == 1
    mock_get_client.assert_called_once_with(provider="claude-cli")
    first_call = loader.fetch_many_bundles.await_args_list[0]
    second_call = loader.fetch_many_bundles.await_args_list[1]
    assert first_call.kwargs["include_multimodal"] is True
    assert second_call.kwargs["include_multimodal"] is True


@pytest.mark.asyncio
async def test_scan_counts_skipped_existing_notes_in_metrics():
    item = MagicMock()
    item.key = "ITEM1"
    item.title = "Paper 1"
    item.data = {"tags": []}

    data_service = AsyncMock()
    data_service.find_collection_by_name = AsyncMock(
        return_value=[{"key": "COLL1", "data": {"name": "00_INBOXS"}}]
    )
    data_service.get_collection_items = AsyncMock(side_effect=[[item], []])
    data_service.get_item_children = AsyncMock(
        return_value=[{"data": {"contentType": "application/pdf"}}]
    )
    data_service.get_sorted_collections = AsyncMock(return_value=[])

    workflow_service = MagicMock()
    workflow_service._analyze_single_item = AsyncMock(
        return_value=SimpleNamespace(success=True, skipped=True, error=None)
    )

    deepseek_client = MagicMock()
    deepseek_client.provider = "deepseek"

    with (
        patch(
            "zotero_mcp.services.scanner.get_data_service",
            return_value=data_service,
        ),
        patch(
            "zotero_mcp.services.scanner.get_workflow_service",
            return_value=workflow_service,
        ),
        patch("zotero_mcp.clients.llm.get_llm_client", return_value=deepseek_client),
    ):
        scanner = GlobalScanner()
        loader = cast(Any, scanner.batch_loader)
        loader.fetch_many_bundles = AsyncMock(
            return_value=[{"metadata": {"key": "ITEM1"}, "fulltext": "text"}]
        )

        result = await scanner.scan_and_process(
            scan_limit=10,
            treated_limit=1,
            target_collection="01_SHORTTERMS",
            source_collection="00_INBOXS",
            dry_run=False,
            llm_provider="deepseek",
        )

    assert result["processed"] == 0
    assert result["failed"] == 0
    assert result["metrics"]["skipped"] == 1
    assert result["skipped_existing"] == 1
    assert result["skipped_no_fulltext"] == 0


@pytest.mark.asyncio
async def test_scan_retries_collection_page_on_transient_failure():
    """Collection page fetch should retry transient failures and continue."""
    item = MagicMock()
    item.key = "ITEM1"
    item.title = "Paper 1"
    item.data = {"tags": []}

    data_service = AsyncMock()
    data_service.find_collection_by_name = AsyncMock(
        return_value=[{"key": "COLL1", "data": {"name": "00_INBOXS"}}]
    )
    data_service.get_collection_items = AsyncMock(
        side_effect=[
            [item],
            RuntimeError("Code: 500"),
            [],
        ]
    )
    data_service.get_item_children = AsyncMock(
        return_value=[{"data": {"contentType": "application/pdf"}}]
    )
    data_service.get_sorted_collections = AsyncMock(return_value=[])

    workflow_service = MagicMock()
    workflow_service._analyze_single_item = AsyncMock()

    with (
        patch(
            "zotero_mcp.services.scanner.get_data_service",
            return_value=data_service,
        ),
        patch(
            "zotero_mcp.services.scanner.get_workflow_service",
            return_value=workflow_service,
        ),
    ):
        scanner = GlobalScanner()
        result = await scanner.scan_and_process(
            scan_limit=1,
            treated_limit=1,
            target_collection="01_SHORTTERMS",
            source_collection="00_INBOXS",
            dry_run=True,
        )

    assert result["success"] is True
    assert result["candidates"] == 1
    assert data_service.get_collection_items.await_count == 3


@pytest.mark.asyncio
async def test_scan_continues_to_stage2_when_source_collection_keeps_failing():
    """Persistent source collection failures should not abort entire scan."""
    item = MagicMock()
    item.key = "ITEM2"
    item.title = "Paper 2"
    item.data = {"tags": []}

    data_service = AsyncMock()
    data_service.find_collection_by_name = AsyncMock(
        return_value=[{"key": "COLL1", "data": {"name": "00_INBOXS"}}]
    )
    data_service.get_sorted_collections = AsyncMock(
        return_value=[
            {"key": "COLL1", "data": {"name": "00_INBOXS"}},
            {"key": "COLL2", "data": {"name": "01_SHORTTERMS"}},
        ]
    )
    data_service.get_item_children = AsyncMock(
        return_value=[{"data": {"contentType": "application/pdf"}}]
    )

    async def _get_collection_items_side_effect(collection_key, limit=100, start=0):
        if collection_key == "COLL1":
            raise RuntimeError("Code: 500")
        if start == 0:
            return [item]
        return []

    data_service.get_collection_items = AsyncMock(
        side_effect=_get_collection_items_side_effect
    )

    workflow_service = MagicMock()
    workflow_service._analyze_single_item = AsyncMock()

    with (
        patch(
            "zotero_mcp.services.scanner.get_data_service",
            return_value=data_service,
        ),
        patch(
            "zotero_mcp.services.scanner.get_workflow_service",
            return_value=workflow_service,
        ),
    ):
        scanner = GlobalScanner()
        result = await scanner.scan_and_process(
            scan_limit=1,
            treated_limit=1,
            target_collection="01_SHORTTERMS",
            source_collection="00_INBOXS",
            dry_run=True,
        )

    assert result["success"] is True
    assert result["candidates"] == 1
    assert result["processed"] == 0


@pytest.mark.asyncio
async def test_scan_stage2_skips_all_00_inboxs_collections():
    """Stage 2 should skip every 00_INBOXS_* collection."""
    item = MagicMock()
    item.key = "ITEM2"
    item.title = "Paper 2"
    item.data = {"tags": []}

    data_service = AsyncMock()
    data_service.find_collection_by_name = AsyncMock(
        return_value=[{"key": "COLL1", "data": {"name": "00_INBOXS_BB"}}]
    )
    data_service.get_sorted_collections = AsyncMock(
        return_value=[
            {"key": "COLL1", "data": {"name": "00_INBOXS_BB"}},
            {"key": "COLL2", "data": {"name": "00_INBOXS_AA"}},
            {"key": "COLL3", "data": {"name": "00_INBOXS_CC"}},
            {"key": "COLL4", "data": {"name": "01_SHORTTERMS"}},
        ]
    )
    data_service.get_item_children = AsyncMock(
        return_value=[{"data": {"contentType": "application/pdf"}}]
    )

    async def _get_collection_items_side_effect(collection_key, limit=100, start=0):
        if collection_key == "COLL1":
            return []
        if collection_key == "COLL4" and start == 0:
            return [item]
        if collection_key == "COLL4":
            return []
        raise AssertionError(f"Should not scan excluded collection: {collection_key}")

    data_service.get_collection_items = AsyncMock(
        side_effect=_get_collection_items_side_effect
    )

    workflow_service = MagicMock()
    workflow_service._analyze_single_item = AsyncMock()

    with (
        patch(
            "zotero_mcp.services.scanner.get_data_service",
            return_value=data_service,
        ),
        patch(
            "zotero_mcp.services.scanner.get_workflow_service",
            return_value=workflow_service,
        ),
    ):
        scanner = GlobalScanner()
        result = await scanner.scan_and_process(
            scan_limit=1,
            treated_limit=1,
            target_collection="01_SHORTTERMS",
            source_collection="00_INBOXS_BB",
            dry_run=True,
        )

    scanned_collection_keys = [
        call.args[0] for call in data_service.get_collection_items.await_args_list
    ]
    assert result["success"] is True
    assert result["candidates"] == 1
    assert "COLL2" not in scanned_collection_keys
    assert "COLL3" not in scanned_collection_keys
    assert "COLL4" in scanned_collection_keys


@pytest.mark.asyncio
async def test_scan_counts_only_parent_items_in_total_scanned():
    parent_item = SimpleNamespace(
        key="PARENT1",
        title="Parent Paper",
        item_type="journalArticle",
        tags=[],
        raw_data={"itemType": "journalArticle", "tags": []},
    )
    note_item = SimpleNamespace(
        key="NOTE1",
        title="Note",
        item_type="note",
        tags=[],
        raw_data={"itemType": "note", "parentItem": "PARENT1", "tags": []},
    )
    child_biblio_item = SimpleNamespace(
        key="CHILD2",
        title="Child Biblio",
        item_type="journalArticle",
        tags=[],
        raw_data={"itemType": "journalArticle", "parentItem": "PARENT1", "tags": []},
    )

    data_service = AsyncMock()
    data_service.find_collection_by_name = AsyncMock(
        return_value=[{"key": "COLL1", "data": {"name": "00_INBOXS"}}]
    )
    data_service.get_collection_items = AsyncMock(
        side_effect=[[parent_item, note_item, child_biblio_item], []]
    )
    data_service.get_item_children = AsyncMock(
        return_value=[{"data": {"contentType": "application/pdf"}}]
    )
    data_service.get_sorted_collections = AsyncMock(return_value=[])

    workflow_service = MagicMock()
    workflow_service._analyze_single_item = AsyncMock()

    with (
        patch(
            "zotero_mcp.services.scanner.get_data_service",
            return_value=data_service,
        ),
        patch(
            "zotero_mcp.services.scanner.get_workflow_service",
            return_value=workflow_service,
        ),
    ):
        scanner = GlobalScanner()
        result = await scanner.scan_and_process(
            scan_limit=10,
            treated_limit=1,
            target_collection="01_SHORTTERMS",
            source_collection="00_INBOXS",
            dry_run=True,
        )

    assert result["success"] is True
    assert result["total_scanned"] == 1
    assert result["metrics"]["scanned"] == 1
    assert result["candidates"] == 1
