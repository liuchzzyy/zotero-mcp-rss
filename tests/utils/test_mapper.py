from zotero_mcp.utils.data.mapper import ZoteroMapper


def test_create_document_text_includes_fulltext_notes_tags_and_annotations():
    item = {
        "key": "ABCD1234",
        "data": {
            "title": "A Study on Zn Batteries",
            "abstractNote": "Abstract text",
            "creators": [{"firstName": "Ada", "lastName": "Lovelace"}],
            "publicationTitle": "Electrochem Journal",
            "DOI": "10.1000/example",
            "url": "https://example.org/paper",
            "extra": "Citation Key: smith2025",
            "tags": [{"tag": "AI/元数据更新"}, {"tag": "battery"}],
            "note": "<p>single note</p>",
            "notes": [{"note": "<div>child note</div>"}],
            "annotations": [
                {
                    "type": "highlight",
                    "text": "important finding",
                    "comment": "check this",
                    "page": "5",
                }
            ],
            "fulltext": "PDF extracted content",
        },
    }

    text = ZoteroMapper.create_document_text(item)

    assert "A Study on Zn Batteries" in text
    assert "Lovelace, Ada" in text
    assert "Abstract text" in text
    assert "Electrochem Journal" in text
    assert "10.1000/example" in text
    assert "https://example.org/paper" in text
    assert "Citation Key: smith2025" in text
    assert "AI/元数据更新 battery" in text
    assert "single note" in text
    assert "child note" in text
    assert "highlight important finding check this 5" in text
    assert "PDF extracted content" in text


