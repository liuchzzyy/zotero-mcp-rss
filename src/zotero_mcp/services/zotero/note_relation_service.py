"""DeepSeek-powered note relation analysis and metadata update service."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from datetime import UTC, datetime
import html
import json
import os
import re
from typing import Any

from zotero_mcp.services.common.pagination import iter_offset_batches
from zotero_mcp.services.common.retry import async_retry_with_backoff
from zotero_mcp.services.data_access import DataAccessService
from zotero_mcp.utils.config.logging import get_logger
from zotero_mcp.utils.formatting.helpers import normalize_item_key

logger = get_logger(__name__)

_SKIPPED_ITEM_TYPES = {"attachment", "annotation", "note"}
_DEFAULT_SCAN_BATCH_SIZE = 50
_DEFAULT_SCORE_BATCH_SIZE = 10
_DEFAULT_TOP_K = 5
_DEFAULT_MAX_LLM_CANDIDATES = 200
_DEFAULT_SEMANTIC_POOL = 300
_DEFAULT_SEMANTIC_QUERY_CHARS = 1800
_DEFAULT_NOTE_FETCH_CONCURRENCY = 8


@dataclass
class _CandidateNote:
    note_key: str
    parent_item_key: str
    parent_item_title: str
    note_text: str


class NoteRelationService:
    """Analyze one note against other notes and write Zotero related metadata."""

    def __init__(self, data_service: DataAccessService | None = None):
        self.data_service = data_service or DataAccessService()
        self._deepseek_client: Any | None = None
        self._deepseek_model = os.getenv("DEEPSEEK_MODEL", "deepseek-chat")
        self._use_semantic_candidates = self._read_bool_env(
            "NOTE_RELATION_USE_SEMANTIC_CANDIDATES",
            True,
        )
        self._semantic_pool = self._read_positive_int_env(
            "NOTE_RELATION_SEMANTIC_POOL",
            _DEFAULT_SEMANTIC_POOL,
        )
        self._semantic_query_chars = self._read_positive_int_env(
            "NOTE_RELATION_SEMANTIC_QUERY_CHARS",
            _DEFAULT_SEMANTIC_QUERY_CHARS,
        )
        self._max_llm_candidates = self._read_positive_int_env(
            "NOTE_RELATION_MAX_LLM_CANDIDATES",
            _DEFAULT_MAX_LLM_CANDIDATES,
        )
        self._note_fetch_concurrency = self._read_positive_int_env(
            "NOTE_RELATION_NOTE_FETCH_CONCURRENCY",
            _DEFAULT_NOTE_FETCH_CONCURRENCY,
        )

    async def relate_note(
        self,
        note_key: str,
        *,
        collection: str = "all",
        dry_run: bool = False,
        bidirectional: bool = True,
        top_k: int = _DEFAULT_TOP_K,
    ) -> dict[str, Any]:
        """Analyze note relevance and optionally write relations + note section."""
        target_note_key = normalize_item_key(note_key)
        target_item = await self.data_service.get_item(target_note_key)
        target_data = target_item.get("data", {})
        if str(target_data.get("itemType", "")).lower() != "note":
            raise ValueError(f"Item {target_note_key} is not a note")

        target_note_text = self._clean_note_html(str(target_data.get("note", "")))
        if not target_note_text.strip():
            raise ValueError(f"Target note {target_note_key} has empty content")

        collection_query = collection.strip()
        if not collection_query:
            raise ValueError("--collection cannot be empty")

        resolved_collection_key: str | None = None
        resolved_collection_name: str | None = None
        if collection_query.lower() != "all":
            resolved_collection_key, resolved_collection_name = (
                await self._resolve_collection_by_name(collection_query)
            )

        candidates, scanned_items, scanned_notes, candidate_source = (
            await self._collect_candidates(
                target_note_key=target_note_key,
                target_note_text=target_note_text,
                collection_key=resolved_collection_key,
            )
        )
        candidate_total_raw = len(candidates)
        candidates_for_scoring = self._prefilter_candidates(
            target_note_text=target_note_text,
            candidates=candidates,
        )

        scored_candidates = await self._score_candidates_with_deepseek(
            target_note_text=target_note_text,
            candidates=candidates_for_scoring,
        )
        scored_candidates.sort(
            key=lambda item: float(item.get("relevance_score", 0.0)),
            reverse=True,
        )
        top_candidates = scored_candidates[: max(1, top_k)]
        await self._fill_missing_parent_titles(top_candidates)

        relation_errors: list[dict[str, str]] = []
        target_relations_changed = False
        bidirectional_relation_updates = 0
        target_note_updated = False

        if not dry_run:
            candidate_keys = [
                str(candidate.get("note_key", "")).strip().upper()
                for candidate in top_candidates
                if candidate.get("note_key")
            ]
            target_relations_changed = self._merge_dc_relation_uris(
                item=target_item,
                related_item_keys=candidate_keys,
            )
            target_data = target_item.setdefault("data", {})
            existing_note_html = str(target_data.get("note", ""))
            target_data["note"] = self._append_relation_section(
                existing_note_html=existing_note_html,
                collection_key=resolved_collection_key,
                collection_name=resolved_collection_name,
                top_candidates=top_candidates,
            )
            target_note_updated = True
            await self.data_service.update_item(target_item)

            if bidirectional:
                for candidate in top_candidates:
                    candidate_key = str(candidate.get("note_key", "")).strip().upper()
                    if not candidate_key:
                        continue
                    try:
                        candidate_item = await self.data_service.get_item(candidate_key)
                        changed = self._merge_dc_relation_uris(
                            item=candidate_item,
                            related_item_keys=[target_note_key],
                        )
                        if changed:
                            await self.data_service.update_item(candidate_item)
                            bidirectional_relation_updates += 1
                    except Exception as exc:  # pragma: no cover - defensive
                        relation_errors.append(
                            {"note_key": candidate_key, "error": str(exc)}
                        )

        success = len(relation_errors) == 0
        return {
            "success": success,
            "note_key": target_note_key,
            "collection_key": resolved_collection_key,
            "collection_name": resolved_collection_name,
            "dry_run": dry_run,
            "bidirectional": bidirectional,
            "candidate_source": candidate_source,
            "scanned_items": scanned_items,
            "scanned_notes": scanned_notes,
            "candidate_total": len(scored_candidates),
            "candidate_total_raw": candidate_total_raw,
            "candidate_scored": len(candidates_for_scoring),
            "top_k": min(max(1, top_k), _DEFAULT_TOP_K),
            "count": len(top_candidates),
            "candidates": top_candidates,
            "target_note_updated": target_note_updated,
            "target_relations_changed": target_relations_changed,
            "bidirectional_relation_updates": bidirectional_relation_updates,
            "relation_errors": relation_errors,
        }

    async def _collect_candidates(
        self,
        *,
        target_note_key: str,
        target_note_text: str,
        collection_key: str | None,
    ) -> tuple[list[_CandidateNote], int, int, str]:
        scanned_items = 0
        candidates: list[_CandidateNote] = []
        seen_note_keys: set[str] = set()
        allowed_parent_keys: set[str] | None = None
        parent_title_map: dict[str, str] = {}

        if collection_key:
            parent_title_map, scanned_items = (
                await self._collect_collection_parent_titles(collection_key)
            )
            allowed_parent_keys = set(parent_title_map)

        if self._use_semantic_candidates:
            semantic_candidates = await self._collect_candidates_from_semantic(
                target_note_key=target_note_key,
                target_note_text=target_note_text,
                allowed_parent_keys=allowed_parent_keys,
                parent_title_map=parent_title_map,
            )
            if semantic_candidates:
                semantic_scanned_items = (
                    scanned_items
                    if collection_key
                    else len({c.parent_item_key for c in semantic_candidates})
                )
                return (
                    semantic_candidates,
                    semantic_scanned_items,
                    len(semantic_candidates),
                    "semantic",
                )

        scanned_notes = 0
        observed_parent_keys: set[str] = set()

        async def fetch_note_page(offset: int, limit: int) -> list[Any]:
            return await self.data_service.get_all_items(
                limit=limit,
                start=offset,
                item_type="note",
            )

        async for _, notes in iter_offset_batches(
            fetch_note_page,
            batch_size=_DEFAULT_SCAN_BATCH_SIZE,
            start=0,
        ):
            scanned_notes += len(notes)
            for note_item in notes:
                note_key = str(getattr(note_item, "key", "")).strip().upper()
                if (
                    not note_key
                    or note_key == target_note_key
                    or note_key in seen_note_keys
                ):
                    continue

                data = getattr(note_item, "raw_data", None)
                if not isinstance(data, dict):
                    continue

                parent_key = str(data.get("parentItem", "")).strip().upper()
                if not parent_key:
                    continue
                if (
                    allowed_parent_keys is not None
                    and parent_key not in allowed_parent_keys
                ):
                    continue
                observed_parent_keys.add(parent_key)

                note_text = self._clean_note_html(str(data.get("note", ""))).strip()
                if not note_text:
                    continue

                seen_note_keys.add(note_key)
                candidates.append(
                    _CandidateNote(
                        note_key=note_key,
                        parent_item_key=parent_key,
                        parent_item_title=parent_title_map.get(parent_key, ""),
                        note_text=note_text,
                    )
                )

        if not collection_key:
            scanned_items = len(observed_parent_keys)

        return candidates, scanned_items, scanned_notes, "scan"

    async def _collect_candidates_from_semantic(
        self,
        *,
        target_note_key: str,
        target_note_text: str,
        allowed_parent_keys: set[str] | None,
        parent_title_map: dict[str, str],
    ) -> list[_CandidateNote]:
        query_text = self._truncate(
            target_note_text,
            self._semantic_query_chars,
        ).strip()
        if not query_text:
            return []

        try:
            from zotero_mcp.services.zotero.semantic_search import (
                create_semantic_search,
            )
        except Exception:
            return []

        loop = asyncio.get_running_loop()
        try:
            payload = await loop.run_in_executor(
                None,
                lambda: create_semantic_search().search(
                    query=query_text,
                    limit=self._semantic_pool,
                    filters={"fragment_type": "note"},
                ),
            )
        except Exception as exc:
            logger.info(
                "Semantic candidate retrieval failed, fallback to scan: %s",
                exc,
            )
            return []

        semantic_results = (
            payload.get("results", []) if isinstance(payload, dict) else []
        )
        if not isinstance(semantic_results, list) or not semantic_results:
            return []

        best_by_note: dict[str, dict[str, Any]] = {}
        for result in semantic_results:
            if not isinstance(result, dict):
                continue
            metadata = result.get("metadata", {})
            if not isinstance(metadata, dict):
                continue
            if str(metadata.get("fragment_type", "")).strip().lower() != "note":
                continue

            note_key = str(metadata.get("source_key", "")).strip().upper()
            if not note_key or note_key == target_note_key:
                continue

            parent_key = str(metadata.get("item_key", "")).strip().upper()
            if not parent_key:
                continue
            if (
                allowed_parent_keys is not None
                and parent_key not in allowed_parent_keys
            ):
                continue

            try:
                similarity_score = float(result.get("similarity_score", 0.0))
            except (TypeError, ValueError):
                similarity_score = 0.0

            normalized = {
                "note_key": note_key,
                "parent_item_key": parent_key,
                "parent_item_title": (
                    parent_title_map.get(parent_key)
                    or str(metadata.get("title", "")).strip()
                ),
                "fallback_text": self._clean_note_html(
                    str(result.get("matched_text", ""))
                ).strip(),
                "score": similarity_score,
            }

            existing = best_by_note.get(note_key)
            if existing is None or similarity_score > float(
                existing.get("score", 0.0)
            ):
                best_by_note[note_key] = normalized

        if not best_by_note:
            return []

        ranked = sorted(
            best_by_note.values(),
            key=lambda row: (
                float(row.get("score", 0.0)),
                str(row.get("note_key", "")),
            ),
            reverse=True,
        )

        note_text_map = await self._fetch_note_texts_for_candidates(ranked)

        candidates: list[_CandidateNote] = []
        for row in ranked:
            note_key = str(row.get("note_key", ""))
            note_text = note_text_map.get(note_key, "").strip()
            if not note_text:
                note_text = str(row.get("fallback_text", "")).strip()
            if not note_text:
                continue
            candidates.append(
                _CandidateNote(
                    note_key=note_key,
                    parent_item_key=str(row.get("parent_item_key", "")),
                    parent_item_title=str(row.get("parent_item_title", "")),
                    note_text=note_text,
                )
            )

        return candidates

    async def _fetch_note_texts_for_candidates(
        self, ranked_rows: list[dict[str, Any]]
    ) -> dict[str, str]:
        note_text_map: dict[str, str] = {}
        semaphore = asyncio.Semaphore(self._note_fetch_concurrency)

        async def fetch_one(row: dict[str, Any]) -> tuple[str, str]:
            note_key = str(row.get("note_key", "")).strip().upper()
            fallback = str(row.get("fallback_text", "")).strip()
            if not note_key:
                return "", ""
            async with semaphore:
                try:
                    item = await self.data_service.get_item(note_key)
                except Exception:
                    return note_key, fallback
            data = item.get("data", item) if isinstance(item, dict) else {}
            note_html = str(data.get("note", ""))
            note_text = self._clean_note_html(note_html).strip()
            return note_key, note_text or fallback

        tasks = [fetch_one(row) for row in ranked_rows]
        results = await asyncio.gather(*tasks)
        for note_key, note_text in results:
            if note_key and note_text:
                note_text_map[note_key] = note_text
        return note_text_map

    async def _collect_collection_parent_titles(
        self, collection_key: str
    ) -> tuple[dict[str, str], int]:
        parent_titles: dict[str, str] = {}
        scanned_items = 0

        async def fetch_page(offset: int, limit: int) -> list[Any]:
            return await self.data_service.get_collection_items(
                collection_key=collection_key,
                limit=limit,
                start=offset,
            )

        async for _, items in iter_offset_batches(
            fetch_page,
            batch_size=_DEFAULT_SCAN_BATCH_SIZE,
            start=0,
        ):
            scanned_items += len(items)
            for item in items:
                item_key = str(getattr(item, "key", "")).strip().upper()
                item_type = str(getattr(item, "item_type", "")).strip().lower()
                if not item_key or item_type in _SKIPPED_ITEM_TYPES:
                    continue
                parent_titles[item_key] = str(getattr(item, "title", "") or "Untitled")

        return parent_titles, scanned_items

    def _prefilter_candidates(
        self,
        *,
        target_note_text: str,
        candidates: list[_CandidateNote],
    ) -> list[_CandidateNote]:
        if len(candidates) <= self._max_llm_candidates:
            return candidates

        target_tokens = self._tokenize_for_prefilter(target_note_text)
        ranked: list[tuple[float, str, _CandidateNote]] = []
        for candidate in candidates:
            candidate_tokens = self._tokenize_for_prefilter(candidate.note_text)
            if not target_tokens or not candidate_tokens:
                score = 0.0
            else:
                overlap = len(target_tokens & candidate_tokens)
                ratio = overlap / max(1, min(len(target_tokens), len(candidate_tokens)))
                score = overlap + ratio
            ranked.append((score, candidate.note_key, candidate))

        ranked.sort(key=lambda row: (row[0], row[1]), reverse=True)
        return [row[2] for row in ranked[: self._max_llm_candidates]]

    async def _fill_missing_parent_titles(
        self, candidates: list[dict[str, Any]]
    ) -> None:
        key_to_title: dict[str, str] = {}
        keys_to_fetch = sorted(
            {
                str(candidate.get("parent_item_key", "")).strip().upper()
                for candidate in candidates
                if str(candidate.get("parent_item_key", "")).strip()
                and not str(candidate.get("parent_item_title", "")).strip()
            }
        )

        for item_key in keys_to_fetch:
            key_to_title[item_key] = "Untitled"
            try:
                payload = await self.data_service.get_item(item_key)
            except Exception:
                continue
            data = payload.get("data", payload) if isinstance(payload, dict) else {}
            key_to_title[item_key] = str(data.get("title") or "Untitled")

        for candidate in candidates:
            current_title = str(candidate.get("parent_item_title", "")).strip()
            if current_title:
                continue
            item_key = str(candidate.get("parent_item_key", "")).strip().upper()
            candidate["parent_item_title"] = key_to_title.get(item_key, "Untitled")

    @staticmethod
    def _tokenize_for_prefilter(text: str) -> set[str]:
        tokens = re.findall(r"[A-Za-z0-9]{2,}|[\u4e00-\u9fff]{1,4}", text.lower())
        return set(tokens)

    @staticmethod
    def _read_positive_int_env(name: str, default: int) -> int:
        raw = os.getenv(name, "")
        if not raw.strip():
            return default
        try:
            value = int(raw)
        except ValueError:
            return default
        return value if value >= 1 else default

    @staticmethod
    def _read_bool_env(name: str, default: bool) -> bool:
        raw = os.getenv(name, "").strip().lower()
        if not raw:
            return default
        if raw in {"1", "true", "yes", "on"}:
            return True
        if raw in {"0", "false", "no", "off"}:
            return False
        return default

    async def _score_candidates_with_deepseek(
        self,
        *,
        target_note_text: str,
        candidates: list[_CandidateNote],
    ) -> list[dict[str, Any]]:
        if not candidates:
            return []

        scored: list[dict[str, Any]] = []
        for start in range(0, len(candidates), _DEFAULT_SCORE_BATCH_SIZE):
            batch = candidates[start : start + _DEFAULT_SCORE_BATCH_SIZE]
            llm_results = await self._request_batch_scores_from_deepseek(
                target_note_text=target_note_text,
                batch=batch,
            )

            for candidate in batch:
                default_reasons = ["DeepSeek response missing this note in results."]
                llm_payload = llm_results.get(
                    candidate.note_key,
                    {
                        "relevance_score": 0.0,
                        "rating": "D",
                        "hit_reasons": default_reasons,
                        "scoring": "No score returned.",
                    },
                )
                scored.append(
                    {
                        "note_key": candidate.note_key,
                        "parent_item_key": candidate.parent_item_key,
                        "parent_item_title": candidate.parent_item_title,
                        "relevance_score": float(llm_payload["relevance_score"]),
                        "rating": str(llm_payload["rating"]),
                        "hit_reasons": list(llm_payload["hit_reasons"]),
                        "scoring": str(llm_payload["scoring"]),
                    }
                )

        return scored

    async def _request_batch_scores_from_deepseek(
        self,
        *,
        target_note_text: str,
        batch: list[_CandidateNote],
    ) -> dict[str, dict[str, Any]]:
        if not batch:
            return {}

        target_excerpt = self._truncate(target_note_text, 5000)
        candidates_payload = [
            {
                "note_key": candidate.note_key,
                "parent_item_key": candidate.parent_item_key,
                "parent_item_title": candidate.parent_item_title,
                "content": self._truncate(candidate.note_text, 1800),
            }
            for candidate in batch
        ]

        prompt = (
            "你是 Zotero 笔记相关性评估器。请严格按 JSON 输出，不要输出任何额外文本。\n"
            "你要评估目标 note 与候选 note 的相关性，分数范围 0-100。\n"
            "返回格式:\n"
            '{\n'
            '  "results": [\n'
            "    {\n"
            '      "note_key": "候选note key",\n'
            '      "relevance_score": 0-100 的数字,\n'
            '      "rating": "A|B|C|D",\n'
            '      "hit_reasons": ["命中原因1", "命中原因2"],\n'
            '      "scoring": "评分说明，1句"\n'
            "    }\n"
            "  ]\n"
            "}\n"
            "评分标准: 主题一致性、方法/概念重叠、结论关联度。\n"
            "请覆盖全部候选 note_key。\n\n"
            "目标note内容:\n"
            f"{target_excerpt}\n\n"
            "候选notes:\n"
            f"{json.dumps(candidates_payload, ensure_ascii=False)}"
        )

        raw = await self._call_deepseek(prompt)
        payload = self._extract_json_payload(raw)
        results = payload.get("results")
        if not isinstance(results, list):
            raise ValueError("DeepSeek response missing 'results' array")

        normalized: dict[str, dict[str, Any]] = {}
        for result in results:
            if not isinstance(result, dict):
                continue
            note_key = str(result.get("note_key", "")).strip().upper()
            if not note_key:
                continue
            raw_score = result.get("relevance_score", 0)
            score = self._normalize_score(raw_score)
            hit_reasons = result.get("hit_reasons", [])
            if not isinstance(hit_reasons, list):
                hit_reasons = [str(hit_reasons)]
            reasons = [
                str(reason).strip() for reason in hit_reasons if str(reason).strip()
            ]
            if not reasons:
                reasons = ["No reason returned by DeepSeek."]
            rating = str(result.get("rating", self._rating_from_score(score))).strip()
            if not rating:
                rating = self._rating_from_score(score)
            normalized[note_key] = {
                "relevance_score": score,
                "rating": rating,
                "hit_reasons": reasons[:3],
                "scoring": str(result.get("scoring", "")).strip() or "No details.",
            }

        return normalized

    async def _call_deepseek(self, prompt: str) -> str:
        async def _invoke() -> str:
            client = self._get_deepseek_client()
            response = await client.chat.completions.create(
                model=self._deepseek_model,
                messages=[
                    {
                        "role": "system",
                        "content": (
                            "你是严格的 JSON 生成器。"
                            "回答必须是可解析 JSON，不允许 markdown 代码块。"
                        ),
                    },
                    {"role": "user", "content": prompt},
                ],
                temperature=0.1,
                max_tokens=2400,
            )
            content = response.choices[0].message.content
            if not content:
                raise ValueError("Empty response from DeepSeek")
            return content

        return await async_retry_with_backoff(
            _invoke,
            retries=2,
            base_delay=1.0,
            max_delay=6.0,
            description="note relation scoring",
        )

    def _get_deepseek_client(self) -> Any:
        if self._deepseek_client is not None:
            return self._deepseek_client

        api_key = os.getenv("DEEPSEEK_API_KEY")
        if not api_key:
            raise ValueError("DEEPSEEK_API_KEY is required for note relevance scoring")

        base_url = os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com")
        try:
            from openai import AsyncOpenAI
        except ImportError as exc:  # pragma: no cover - environment dependent
            raise ImportError(
                "openai package is required for DeepSeek scoring."
            ) from exc

        self._deepseek_client = AsyncOpenAI(api_key=api_key, base_url=base_url)
        return self._deepseek_client

    async def _resolve_collection_by_name(self, name_query: str) -> tuple[str, str]:
        normalized_query = name_query.strip()
        if not normalized_query:
            raise ValueError("Collection name cannot be empty")

        collections = await self.data_service.get_collections()
        if not collections:
            raise ValueError("No collections found in library")

        exact_name_matches: list[tuple[str, str]] = []
        for collection in collections:
            key = str(collection.get("key", "")).strip()
            name = str(collection.get("data", {}).get("name", "")).strip()
            if name.lower() == normalized_query.lower():
                exact_name_matches.append((key, name))
        if len(exact_name_matches) == 1:
            return exact_name_matches[0]
        if len(exact_name_matches) > 1:
            choices = ", ".join(f"{name}({key})" for key, name in exact_name_matches)
            raise ValueError(f"Collection name is ambiguous: {choices}")

        fuzzy_matches: list[tuple[str, str]] = []
        for collection in collections:
            key = str(collection.get("key", "")).strip()
            name = str(collection.get("data", {}).get("name", "")).strip()
            if normalized_query.lower() in name.lower():
                fuzzy_matches.append((key, name))
        if len(fuzzy_matches) == 1:
            return fuzzy_matches[0]
        if len(fuzzy_matches) > 1:
            choices = ", ".join(f"{name}({key})" for key, name in fuzzy_matches[:10])
            raise ValueError(f"Collection query is ambiguous: {choices}")

        raise ValueError(f"Collection not found: {name_query}")

    def _merge_dc_relation_uris(
        self,
        *,
        item: dict[str, Any],
        related_item_keys: list[str],
    ) -> bool:
        data = item.setdefault("data", {})
        item_key = str(item.get("key") or data.get("key") or "").strip().upper()
        if not item_key:
            return False

        relations = data.get("relations")
        if not isinstance(relations, dict):
            relations = {}

        existing = self._as_uri_list(relations.get("dc:relation"))
        existing_set = set(existing)
        changed = False
        for related_key in related_item_keys:
            normalized_key = str(related_key).strip().upper()
            if not normalized_key or normalized_key == item_key:
                continue
            uri = self._item_uri(normalized_key)
            if uri in existing_set:
                continue
            existing.append(uri)
            existing_set.add(uri)
            changed = True

        if not changed:
            return False

        relations["dc:relation"] = existing[0] if len(existing) == 1 else existing
        data["relations"] = relations
        return True

    def _item_uri(self, item_key: str) -> str:
        api_client = self.data_service.api_client
        owner = "groups" if api_client.library_type == "group" else "users"
        return f"http://zotero.org/{owner}/{api_client.library_id}/items/{item_key}"

    @staticmethod
    def _as_uri_list(raw: Any) -> list[str]:
        if isinstance(raw, str):
            return [raw]
        if isinstance(raw, list):
            return [str(value) for value in raw if str(value).strip()]
        return []

    def _append_relation_section(
        self,
        *,
        existing_note_html: str,
        collection_key: str | None,
        collection_name: str | None,
        top_candidates: list[dict[str, Any]],
    ) -> str:
        timestamp = datetime.now(UTC).strftime("%Y-%m-%d %H:%M:%S UTC")
        if collection_key:
            scope = f"{collection_name or collection_key} ({collection_key})"
        else:
            scope = "all"

        parts: list[str] = [
            f"<h4>AI Note Relevance Analysis ({html.escape(timestamp)})</h4>",
            f"<p><strong>Scope:</strong> {html.escape(scope)}</p>",
        ]
        if not top_candidates:
            parts.append("<p>No related notes found.</p>")
        else:
            parts.append("<ol>")
            for candidate in top_candidates:
                note_key = html.escape(str(candidate.get("note_key", "")))
                item_title = html.escape(str(candidate.get("parent_item_title", "")))
                score = float(candidate.get("relevance_score", 0.0))
                rating = html.escape(str(candidate.get("rating", "")))
                scoring = html.escape(str(candidate.get("scoring", "")))
                reasons = candidate.get("hit_reasons", [])
                if not isinstance(reasons, list):
                    reasons = [str(reasons)]
                reason_items = "".join(
                    f"<li>{html.escape(str(reason))}</li>"
                    for reason in reasons
                    if str(reason).strip()
                )
                if not reason_items:
                    reason_items = "<li>No reason.</li>"
                parts.append(
                    "<li>"
                    f"<p><strong>{note_key}</strong> ({item_title})</p>"
                    f"<p>Relevance Score: {score:.2f} / 100 | Rating: {rating}</p>"
                    f"<p>Scoring: {scoring}</p>"
                    f"<p>Hit Reasons:</p><ul>{reason_items}</ul>"
                    "</li>"
                )
            parts.append("</ol>")

        section_html = "\n".join(parts)
        if not existing_note_html.strip():
            return section_html
        return f"{existing_note_html.rstrip()}\n\n{section_html}"

    @staticmethod
    def _clean_note_html(note_html: str) -> str:
        cleaned = re.sub(r"<[^>]+>", "", note_html)
        return html.unescape(cleaned).strip()

    @staticmethod
    def _truncate(text: str, max_chars: int) -> str:
        if len(text) <= max_chars:
            return text
        return text[:max_chars] + "\n...[truncated]..."

    @staticmethod
    def _normalize_score(raw: Any) -> float:
        try:
            score = float(raw)
        except (TypeError, ValueError):
            score = 0.0
        return max(0.0, min(100.0, score))

    @staticmethod
    def _rating_from_score(score: float) -> str:
        if score >= 85:
            return "A"
        if score >= 70:
            return "B"
        if score >= 55:
            return "C"
        return "D"

    @staticmethod
    def _extract_json_payload(raw: str) -> dict[str, Any]:
        text = raw.strip()
        if text.startswith("```"):
            fenced = re.search(r"```(?:json)?\s*(.*?)```", text, flags=re.DOTALL)
            if fenced:
                text = fenced.group(1).strip()
        try:
            payload = json.loads(text)
            if isinstance(payload, dict):
                return payload
        except json.JSONDecodeError:
            pass

        start = text.find("{")
        end = text.rfind("}")
        if start >= 0 and end > start:
            payload = json.loads(text[start : end + 1])
            if isinstance(payload, dict):
                return payload
        raise ValueError("Failed to parse JSON from DeepSeek response")
