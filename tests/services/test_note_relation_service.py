from __future__ import annotations

import copy
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from zotero_mcp.services.zotero.note_relation_service import (
    NoteRelationService,
    _CandidateNote,
)


@pytest.mark.asyncio
async def test_relate_note_dry_run_uses_collection_name_and_keeps_top5():
    data_service = MagicMock()
    data_service.api_client = SimpleNamespace(library_type="user", library_id="123")
    data_service.get_item = AsyncMock(
        return_value={
            "key": "TARGET01",
            "data": {
                "key": "TARGET01",
                "itemType": "note",
                "note": "<p>Target note content</p>",
            },
        }
    )
    data_service.get_collections = AsyncMock(
        return_value=[{"key": "COLL001", "data": {"name": "My Collection"}}]
    )
    data_service.get_collection_items = AsyncMock(
        side_effect=[
            [
                SimpleNamespace(
                    key="ITEM001",
                    item_type="journalArticle",
                    title="Paper A",
                )
            ],
        ]
    )
    data_service.update_item = AsyncMock()

    service = NoteRelationService(data_service=data_service)
    service._collect_candidates_from_semantic = AsyncMock(  # type: ignore[method-assign]
        return_value=[
            _CandidateNote("N1", "ITEM001", "Paper A", "candidate one"),
            _CandidateNote("N2", "ITEM001", "Paper A", "candidate two"),
            _CandidateNote("N3", "ITEM001", "Paper A", "candidate three"),
            _CandidateNote("N4", "ITEM001", "Paper A", "candidate four"),
            _CandidateNote("N5", "ITEM001", "Paper A", "candidate five"),
            _CandidateNote("N6", "ITEM001", "Paper A", "candidate six"),
        ]
    )
    service._score_candidates_with_deepseek = AsyncMock(  # type: ignore[method-assign]
        return_value=[
            {
                "note_key": "N1",
                "parent_item_key": "ITEM001",
                "parent_item_title": "Paper A",
                "relevance_score": 96.0,
                "rating": "A",
                "hit_reasons": ["r1"],
                "scoring": "s1",
            },
            {
                "note_key": "N2",
                "parent_item_key": "ITEM001",
                "parent_item_title": "Paper A",
                "relevance_score": 90.0,
                "rating": "A",
                "hit_reasons": ["r2"],
                "scoring": "s2",
            },
            {
                "note_key": "N3",
                "parent_item_key": "ITEM001",
                "parent_item_title": "Paper A",
                "relevance_score": 85.0,
                "rating": "B",
                "hit_reasons": ["r3"],
                "scoring": "s3",
            },
            {
                "note_key": "N4",
                "parent_item_key": "ITEM001",
                "parent_item_title": "Paper A",
                "relevance_score": 80.0,
                "rating": "B",
                "hit_reasons": ["r4"],
                "scoring": "s4",
            },
            {
                "note_key": "N5",
                "parent_item_key": "ITEM001",
                "parent_item_title": "Paper A",
                "relevance_score": 75.0,
                "rating": "B",
                "hit_reasons": ["r5"],
                "scoring": "s5",
            },
            {
                "note_key": "N6",
                "parent_item_key": "ITEM001",
                "parent_item_title": "Paper A",
                "relevance_score": 60.0,
                "rating": "C",
                "hit_reasons": ["r6"],
                "scoring": "s6",
            },
        ]
    )

    result = await service.relate_note(
        note_key="TARGET01",
        collection="My Collection",
        dry_run=True,
        bidirectional=True,
    )

    assert result["collection_key"] == "COLL001"
    assert result["count"] == 5
    assert result["candidate_total"] == 6
    assert [c["note_key"] for c in result["candidates"]] == [
        "N1",
        "N2",
        "N3",
        "N4",
        "N5",
    ]
    assert result["candidate_source"] == "semantic"
    data_service.update_item.assert_not_awaited()


@pytest.mark.asyncio
async def test_relate_note_rejects_collection_key_input():
    data_service = MagicMock()
    data_service.api_client = SimpleNamespace(library_type="user", library_id="123")
    data_service.get_item = AsyncMock(
        return_value={
            "key": "TARGET01",
            "data": {
                "key": "TARGET01",
                "itemType": "note",
                "note": "<p>Target note content</p>",
            },
        }
    )
    data_service.get_collections = AsyncMock(
        return_value=[{"key": "COLL001", "data": {"name": "My Collection"}}]
    )

    service = NoteRelationService(data_service=data_service)

    with pytest.raises(ValueError, match="Collection not found: COLL001"):
        await service.relate_note(
            note_key="TARGET01",
            collection="COLL001",
            dry_run=True,
            bidirectional=True,
        )


@pytest.mark.asyncio
async def test_relate_note_updates_only_target_note_content():
    data_service = MagicMock()
    data_service.api_client = SimpleNamespace(library_type="user", library_id="123")

    items_by_key = {
        "TARGET01": {
            "key": "TARGET01",
            "data": {
                "key": "TARGET01",
                "itemType": "note",
                "note": "<p>target note</p>",
                "relations": {},
            },
        },
        "CAND001": {
            "key": "CAND001",
            "data": {
                "key": "CAND001",
                "itemType": "note",
                "note": "<p>candidate one</p>",
                "relations": {},
            },
        },
        "CAND002": {
            "key": "CAND002",
            "data": {
                "key": "CAND002",
                "itemType": "note",
                "note": "<p>candidate two</p>",
                "relations": {},
            },
        },
    }

    async def fake_get_item(key: str):
        return copy.deepcopy(items_by_key[key])

    data_service.get_item = AsyncMock(side_effect=fake_get_item)
    data_service.update_item = AsyncMock(return_value={"ok": True})

    service = NoteRelationService(data_service=data_service)
    service._collect_candidates_from_semantic = AsyncMock(  # type: ignore[method-assign]
        return_value=[
            _CandidateNote("CAND001", "ITEM001", "Paper A", "candidate one"),
            _CandidateNote("CAND002", "ITEM001", "Paper A", "candidate two"),
        ]
    )
    service._score_candidates_with_deepseek = AsyncMock(  # type: ignore[method-assign]
        return_value=[
            {
                "note_key": "CAND001",
                "parent_item_key": "ITEM001",
                "parent_item_title": "Paper A",
                "relevance_score": 95.0,
                "rating": "A",
                "hit_reasons": ["same topic"],
                "scoring": "high overlap",
            },
            {
                "note_key": "CAND002",
                "parent_item_key": "ITEM001",
                "parent_item_title": "Paper A",
                "relevance_score": 88.0,
                "rating": "A",
                "hit_reasons": ["same method"],
                "scoring": "close content",
            },
        ]
    )

    result = await service.relate_note(
        note_key="TARGET01",
        collection="all",
        dry_run=False,
        bidirectional=True,
    )

    assert result["target_note_updated"] is True
    assert result["count"] == 2

    updated_payloads = [
        call.args[0] for call in data_service.update_item.await_args_list
    ]
    assert len(updated_payloads) == 3
    assert "AI Note Relevance Analysis" in updated_payloads[0]["data"]["note"]
    assert "AI Note Relevance Analysis" not in updated_payloads[1]["data"]["note"]
    assert "AI Note Relevance Analysis" not in updated_payloads[2]["data"]["note"]


@pytest.mark.asyncio
async def test_relate_note_prefilters_candidates_before_llm(monkeypatch):
    monkeypatch.setenv("NOTE_RELATION_MAX_LLM_CANDIDATES", "2")

    data_service = MagicMock()
    data_service.api_client = SimpleNamespace(library_type="user", library_id="123")
    data_service.get_item = AsyncMock(
        return_value={
            "key": "TARGET01",
            "data": {
                "key": "TARGET01",
                "itemType": "note",
                "note": "<p>alpha keyword target</p>",
            },
        }
    )
    service = NoteRelationService(data_service=data_service)
    service._collect_candidates_from_semantic = AsyncMock(  # type: ignore[method-assign]
        return_value=[
            _CandidateNote("N1", "I1", "", "alpha text"),
            _CandidateNote("N2", "I2", "", "alpha beta text"),
            _CandidateNote("N3", "I3", "", "gamma text"),
        ]
    )
    service._score_candidates_with_deepseek = AsyncMock(  # type: ignore[method-assign]
        return_value=[
            {
                "note_key": "N2",
                "parent_item_key": "I2",
                "parent_item_title": "",
                "relevance_score": 90.0,
                "rating": "A",
                "hit_reasons": ["r2"],
                "scoring": "s2",
            },
            {
                "note_key": "N1",
                "parent_item_key": "I1",
                "parent_item_title": "",
                "relevance_score": 80.0,
                "rating": "B",
                "hit_reasons": ["r1"],
                "scoring": "s1",
            },
        ]
    )

    result = await service.relate_note(note_key="TARGET01", dry_run=True)

    score_call = service._score_candidates_with_deepseek.await_args.kwargs
    assert len(score_call["candidates"]) == 2
    assert result["candidate_total_raw"] == 3
    assert result["candidate_scored"] == 2


@pytest.mark.asyncio
async def test_relate_note_uses_semantic_candidates():
    data_service = MagicMock()
    data_service.api_client = SimpleNamespace(library_type="user", library_id="123")
    data_service.get_item = AsyncMock(
        return_value={
            "key": "TARGET01",
            "data": {
                "key": "TARGET01",
                "itemType": "note",
                "note": "<p>semantic target text</p>",
            },
        }
    )

    service = NoteRelationService(data_service=data_service)
    service._collect_candidates_from_semantic = AsyncMock(  # type: ignore[method-assign]
        return_value=[
            _CandidateNote(
                note_key="N1",
                parent_item_key="I1",
                parent_item_title="Paper A",
                note_text="candidate from semantic",
            )
        ]
    )
    service._score_candidates_with_deepseek = AsyncMock(  # type: ignore[method-assign]
        return_value=[
            {
                "note_key": "N1",
                "parent_item_key": "I1",
                "parent_item_title": "Paper A",
                "relevance_score": 92.0,
                "rating": "A",
                "hit_reasons": ["semantic hit"],
                "scoring": "high semantic overlap",
            }
        ]
    )

    result = await service.relate_note(note_key="TARGET01", dry_run=True)

    assert result["candidate_source"] == "semantic"
