"""Tests for ZoteroAPIClient tag operations."""

from typing import Any, cast
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from zotero_mcp.clients.zotero.api_client import ZoteroAPIClient


@pytest.mark.asyncio
async def test_add_tags_normalizes_and_avoids_duplicate_append():
    client = ZoteroAPIClient(library_id="1", local=True)
    client._client = MagicMock()
    client._client.update_item.return_value = {"ok": True}

    get_item_mock = AsyncMock(
        return_value={
            "key": "ITEM1",
            "data": {
                "tags": [{"tag": "AI/条目分析"}, "保留"],
            },
        }
    )
    with patch.object(client, "get_item", get_item_mock):
        await client.add_tags("ITEM1", [" 保留 ", "新增", "", "新增"])

    get_item_mock.assert_awaited_once_with("ITEM1")
    update_item_mock = cast(Any, client.client.update_item)
    update_item_mock.assert_called_once()
    updated = update_item_mock.call_args.args[0]
    assert updated["data"]["tags"] == [
        {"tag": "AI/条目分析"},
        {"tag": "保留"},
        {"tag": "新增"},
    ]

