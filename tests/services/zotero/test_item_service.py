from unittest.mock import AsyncMock, MagicMock

import pytest

from zotero_mcp.services.zotero.item_service import ItemService


@pytest.mark.asyncio
async def test_get_all_items_uses_api_for_child_item_types_when_local_db_enabled():
    api_client = MagicMock()
    api_client.get_all_items = AsyncMock(
        return_value=[
            {
                "data": {
                    "key": "N1",
                    "itemType": "note",
                    "parentItem": "I1",
                    "note": "matched",
                    "title": "My Note",
                }
            }
        ]
    )
    local_client = MagicMock()
    local_client.get_items = MagicMock(return_value=[])
    service = ItemService(api_client=api_client, local_client=local_client)

    result = await service.get_all_items(limit=20, start=40, item_type="note")

    local_client.get_items.assert_not_called()
    api_client.get_all_items.assert_awaited_once_with(
        limit=20,
        start=40,
        item_type="note",
    )
    assert len(result) == 1
    assert result[0].key == "N1"
    assert result[0].item_type == "note"
