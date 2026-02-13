"""Tests for GlobalScanner behavior."""

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
        patch("zotero_mcp.services.scanner.get_data_service", return_value=data_service),
        patch(
            "zotero_mcp.services.scanner.get_workflow_service",
            return_value=workflow_service,
        ),
        patch("zotero_mcp.clients.llm.get_llm_client", return_value=MagicMock()),
    ):
        scanner = GlobalScanner()
        scanner.batch_loader.fetch_many_bundles = AsyncMock(
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
