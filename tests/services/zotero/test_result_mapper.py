from zotero_mcp.clients.zotero.local_db import ZoteroItem
from zotero_mcp.services.zotero.result_mapper import (
    api_item_to_search_result,
    zotero_item_to_search_result,
)


def test_api_item_to_search_result_maps_common_fields():
    item = {
        "key": "OUTER",
        "data": {
            "key": "INNER",
            "title": "Paper",
            "creators": [
                {"creatorType": "author", "firstName": "A", "lastName": "B"}
            ],
            "date": "2024",
            "itemType": "journalArticle",
            "abstractNote": "Abstract",
            "DOI": "10.1/abc",
            "tags": [{"tag": "t1"}],
        },
    }

    result = api_item_to_search_result(item)

    assert result.key == "INNER"
    assert result.title == "Paper"
    assert result.doi == "10.1/abc"
    assert result.tags == ["t1"]


def test_zotero_item_to_search_result_maps_local_item():
    item = ZoteroItem(
        key="K1",
        item_id=1,
        item_type="journalArticle",
        item_type_id=2,
        title="Local Paper",
        creators="Author A",
        date_added="2025-01-01",
        date_modified="2025-01-02",
        tags=["x", "y"],
    )

    result = zotero_item_to_search_result(item)

    assert result.key == "K1"
    assert result.title == "Local Paper"
    assert result.authors == "Author A"
    assert result.tags == ["x", "y"]
