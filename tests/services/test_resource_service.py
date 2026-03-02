from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from zotero_mcp.services.resource_service import ResourceService


@pytest.mark.asyncio
async def test_create_items_wraps_single_payload():
    data_service = MagicMock()
    data_service.create_items = AsyncMock(return_value={"successful": {"0": {}}})
    service = ResourceService(data_service=data_service)

    payload = {"data": {"title": "Example"}}
    await service.create_items(payload)

    data_service.create_items.assert_awaited_once_with([payload])


@pytest.mark.asyncio
async def test_search_notes_scans_whole_library_and_paginates_stably():
    data_service = MagicMock()
    data_service.get_all_items = AsyncMock(
        side_effect=[
            [
                SimpleNamespace(
                    key="N3",
                    item_type="note",
                    raw_data={"parentItem": "I2", "note": "Matched note B"},
                ),
                SimpleNamespace(
                    key="N2",
                    item_type="note",
                    raw_data={"parentItem": "I1", "note": "irrelevant"},
                ),
                SimpleNamespace(
                    key="N1",
                    item_type="note",
                    raw_data={"parentItem": "I1", "note": "matched note A"},
                ),
            ]
        ]
    )
    data_service.get_item = AsyncMock(return_value={"data": {"title": "Item Two"}})
    service = ResourceService(data_service=data_service)

    result = await service.search_notes(query="matched", limit=1, offset=1)

    assert data_service.get_all_items.await_count == 1
    assert data_service.get_all_items.await_args_list[0].kwargs == {
        "limit": 50,
        "start": 0,
        "item_type": "note",
    }
    data_service.get_notes.assert_not_called()
    data_service.search_items.assert_not_called()
    data_service.get_item.assert_awaited_once_with("I2")
    assert result["collection_key"] is None
    assert result["collection_name"] is None
    assert result["query"] == "matched"
    assert result["total"] == 2
    assert result["count"] == 1
    assert result["results"][0]["note_key"] == "N3"


@pytest.mark.asyncio
async def test_search_notes_supports_collection_name_scope():
    data_service = MagicMock()
    data_service.get_collections = AsyncMock(
        return_value=[{"key": "COLL001", "data": {"name": "My Collection"}}]
    )
    data_service.get_collection_items = AsyncMock(
        side_effect=[
            [SimpleNamespace(key="I1", title="Item One", item_type="journalArticle")],
        ]
    )
    data_service.get_all_items = AsyncMock(
        side_effect=[
            [
                SimpleNamespace(
                    key="N1",
                    item_type="note",
                    raw_data={"parentItem": "I1", "note": "matched note"},
                ),
                SimpleNamespace(
                    key="N2",
                    item_type="note",
                    raw_data={"parentItem": "I9", "note": "matched but out of scope"},
                ),
            ]
        ]
    )
    data_service.get_item = AsyncMock(return_value={"data": {"title": "Item One"}})
    service = ResourceService(data_service=data_service)

    result = await service.search_notes(
        query="matched",
        limit=50,
        offset=0,
        collection="My Collection",
    )

    data_service.get_collection_items.assert_any_await(
        collection_key="COLL001",
        limit=50,
        start=0,
    )
    data_service.get_all_items.assert_any_await(limit=50, start=0, item_type="note")
    assert result["collection_key"] == "COLL001"
    assert result["collection_name"] == "My Collection"
    assert result["total"] == 1
    assert result["count"] == 1
    assert result["results"][0]["note_key"] == "N1"


@pytest.mark.asyncio
async def test_list_annotations_filters_by_type():
    data_service = MagicMock()
    data_service.get_annotations = AsyncMock(
        return_value=[
            {"data": {"annotationType": "highlight"}},
            {"data": {"annotationType": "note"}},
        ]
    )
    service = ResourceService(data_service=data_service)

    result = await service.list_annotations(
        item_key="ITEM1",
        annotation_type="HIGHLIGHT",
        limit=10,
        offset=0,
    )

    assert result["total"] == 1
    assert result["count"] == 1
    assert result["annotations"][0]["data"]["annotationType"] == "highlight"


@pytest.mark.asyncio
async def test_delete_note_calls_delete_item():
    data_service = MagicMock()
    data_service.delete_item = AsyncMock(return_value={"ok": True})
    service = ResourceService(data_service=data_service)

    result = await service.delete_note("NOTE1")

    data_service.delete_item.assert_awaited_once_with("NOTE1")
    assert result["deleted"] is True
    assert result["note_key"] == "NOTE1"


@pytest.mark.asyncio
async def test_search_annotations_filters_and_paginates():
    data_service = MagicMock()
    data_service.search_items = AsyncMock(
        return_value=[SimpleNamespace(key="I1", title="Item One")]
    )
    data_service.get_annotations = AsyncMock(
        return_value=[
            {
                "data": {
                    "key": "A1",
                    "annotationType": "highlight",
                    "annotationText": "important phrase",
                }
            },
            {
                "data": {
                    "key": "A2",
                    "annotationType": "note",
                    "annotationComment": "not matched",
                }
            },
        ]
    )
    service = ResourceService(data_service=data_service)

    result = await service.search_annotations(
        query="important",
        limit=10,
        offset=0,
        annotation_type="highlight",
    )

    data_service.search_items.assert_awaited_once_with(
        "important",
        limit=50,
        offset=0,
        qmode="everything",
    )
    assert result["total"] == 1
    assert result["count"] == 1
    assert result["results"][0]["annotation_key"] == "A1"


@pytest.mark.asyncio
async def test_pdfs_list_and_search_work():
    data_service = MagicMock()
    data_service.get_item_children = AsyncMock(
        side_effect=[
            [
                {"data": {"key": "P1", "contentType": "application/pdf"}},
                {"data": {"key": "X1", "contentType": "text/plain"}},
            ],
            [
                {
                    "data": {
                        "key": "P2",
                        "contentType": "application/pdf",
                        "title": "Paper PDF",
                        "filename": "paper.pdf",
                    }
                }
            ],
        ]
    )
    data_service.search_items = AsyncMock(
        return_value=[SimpleNamespace(key="I1", title="Paper Item")]
    )
    service = ResourceService(data_service=data_service)

    listed = await service.list_pdfs(item_key="I1", limit=10, offset=0)
    searched = await service.search_pdfs(query="paper", limit=10, offset=0)

    assert listed["total"] == 1
    assert listed["count"] == 1
    assert listed["pdfs"][0]["data"]["key"] == "P1"
    assert searched["total"] == 1
    assert searched["results"][0]["attachment_key"] == "P2"


@pytest.mark.asyncio
async def test_upload_pdf_rejects_missing_file(tmp_path):
    data_service = MagicMock()
    data_service.item_service = MagicMock()
    data_service.item_service.upload_attachment = AsyncMock()
    service = ResourceService(data_service=data_service)

    with pytest.raises(FileNotFoundError):
        await service.upload_pdf(
            item_key="I1",
            file_path=str(tmp_path / "missing.pdf"),
        )

    data_service.item_service.upload_attachment.assert_not_awaited()


@pytest.mark.asyncio
async def test_upload_pdf_rejects_non_pdf_file(tmp_path):
    text_file = tmp_path / "note.txt"
    text_file.write_text("not a pdf", encoding="utf-8")

    data_service = MagicMock()
    data_service.item_service = MagicMock()
    data_service.item_service.upload_attachment = AsyncMock()
    service = ResourceService(data_service=data_service)

    with pytest.raises(ValueError, match="Only PDF files are supported"):
        await service.upload_pdf(item_key="I1", file_path=str(text_file))

    data_service.item_service.upload_attachment.assert_not_awaited()


@pytest.mark.asyncio
async def test_upload_pdf_returns_structured_result(tmp_path):
    pdf_file = tmp_path / "paper.pdf"
    pdf_file.write_bytes(b"%PDF-1.7\n%fake")

    data_service = MagicMock()
    data_service.item_service = MagicMock()
    data_service.item_service.upload_attachment = AsyncMock(
        return_value={"successful": {"0": "ATTACH001"}, "failed": {}}
    )
    service = ResourceService(data_service=data_service)

    result = await service.upload_pdf(item_key="I1", file_path=str(pdf_file))

    data_service.item_service.upload_attachment.assert_awaited_once_with(
        parent_key="I1",
        file_path=str(pdf_file.resolve()),
        title=None,
    )
    assert result["success"] is True
    assert result["attachment_keys"] == ["ATTACH001"]
    assert result["item_key"] == "I1"
    assert result["title"] == "paper.pdf"


@pytest.mark.asyncio
async def test_rename_collection_calls_update_and_returns_summary():
    data_service = MagicMock()
    data_service.update_collection = AsyncMock(return_value=None)
    service = ResourceService(data_service=data_service)

    result = await service.rename_collection(collection_key="C1", name="Renamed")

    data_service.update_collection.assert_awaited_once_with("C1", name="Renamed")
    assert result == {"updated": True, "collection_key": "C1", "name": "Renamed"}


@pytest.mark.asyncio
async def test_delete_empty_collections_deletes_only_empty_ones():
    data_service = MagicMock()
    data_service.get_collections = AsyncMock(
        return_value=[
            {"key": "C1", "data": {"name": "Empty"}},
            {"key": "C2", "data": {"name": "Has Items"}},
        ]
    )
    data_service.get_collection_items = AsyncMock(
        side_effect=[[], [SimpleNamespace(key="I1", title="Item")]]
    )
    data_service.delete_collection = AsyncMock(return_value=None)
    service = ResourceService(data_service=data_service)

    result = await service.delete_empty_collections(dry_run=False)

    assert result["empty_collections_found"] == 1
    assert result["deleted"] == 1
    data_service.delete_collection.assert_awaited_once_with("C1")
