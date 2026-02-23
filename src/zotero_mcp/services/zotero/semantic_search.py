"""
Semantic search functionality for Zotero MCP.

This module provides semantic search capabilities by integrating ChromaDB
with the existing Zotero client to enable vector-based similarity search
over research libraries.
"""

import asyncio
from contextlib import contextmanager
from datetime import datetime, timedelta
import json
import logging
import os
from pathlib import Path
import re
import sys
from typing import Any

from zotero_mcp.clients.database import ChromaClient, create_chroma_client
from zotero_mcp.clients.zotero import (
    LocalDatabaseClient,
    get_zotero_client,
)
from zotero_mcp.utils.config import get_config_path
from zotero_mcp.utils.data.mapper import ZoteroMapper
from zotero_mcp.utils.formatting.helpers import is_local_mode

logger = logging.getLogger(__name__)


@contextmanager
def suppress_stdout():
    """Context manager to suppress stdout temporarily."""
    with open(os.devnull, "w") as devnull:
        old_stdout = sys.stdout
        sys.stdout = devnull
        try:
            yield
        finally:
            sys.stdout = old_stdout


class ZoteroSemanticSearch:
    """Semantic search interface for Zotero libraries using ChromaDB."""

    DEFAULT_CHUNK_SIZE = 1800
    DEFAULT_CHUNK_OVERLAP = 200
    DEFAULT_MAX_SOURCE_CHARS = 200_000

    def __init__(
        self,
        chroma_client: ChromaClient | None = None,
        config_path: str | None = None,
        db_path: str | None = None,
    ):
        """
        Initialize semantic search.

        Args:
            chroma_client: Optional ChromaClient instance
            config_path: Path to configuration file
            db_path: Optional path to Zotero database (overrides config file)
        """
        self.chroma_client = chroma_client or create_chroma_client(config_path)
        # Use sync client for internal compatibility with existing logic
        self.zotero_client = get_zotero_client().client
        self.config_path = config_path
        self.db_path = db_path  # CLI override for Zotero database path

        # Load update configuration
        self.update_config = self._load_update_config()
        self.extraction_config = self._load_extraction_config()

    def _load_update_config(self) -> dict[str, Any]:
        """Load update configuration from file or use defaults."""
        config = {
            "auto_update": False,
            "update_frequency": "manual",
            "last_update": None,
            "update_days": 7,
        }

        if self.config_path and os.path.exists(self.config_path):
            try:
                with open(self.config_path) as f:
                    file_config = json.load(f)
                    config.update(
                        file_config.get("semantic_search", {}).get("update_config", {})
                    )
            except Exception as e:
                logger.warning(f"Error loading update config: {e}")

        return config

    def _save_update_config(self) -> None:
        """Save update configuration to file."""
        if not self.config_path:
            return

        config_dir = Path(self.config_path).parent
        config_dir.mkdir(parents=True, exist_ok=True)

        # Load existing config or create new one
        full_config = {}
        if os.path.exists(self.config_path):
            try:
                with open(self.config_path) as f:
                    full_config = json.load(f)
            except Exception:
                pass

        # Update semantic search config
        if "semantic_search" not in full_config:
            full_config["semantic_search"] = {}

        full_config["semantic_search"]["update_config"] = self.update_config

        try:
            with open(self.config_path, "w") as f:
                json.dump(full_config, f, indent=2)
        except Exception as e:
            logger.error(f"Error saving update config: {e}")

    @staticmethod
    def _positive_int(value: Any, default: int) -> int:
        """Parse a positive integer with safe fallback."""
        try:
            parsed = int(value)
            if parsed > 0:
                return parsed
        except Exception:
            pass
        return default

    def _load_extraction_config(self) -> dict[str, int]:
        """Load extraction/chunking configuration with safe defaults."""
        config = {
            "chunk_size": self.DEFAULT_CHUNK_SIZE,
            "chunk_overlap": self.DEFAULT_CHUNK_OVERLAP,
            "max_source_chars": self.DEFAULT_MAX_SOURCE_CHARS,
        }

        if self.config_path and os.path.exists(self.config_path):
            try:
                with open(self.config_path) as f:
                    file_config = json.load(f)
                extraction = (
                    file_config.get("semantic_search", {}).get("extraction", {})
                )
                if isinstance(extraction, dict):
                    config["chunk_size"] = self._positive_int(
                        extraction.get("chunk_size"),
                        config["chunk_size"],
                    )
                    config["chunk_overlap"] = self._positive_int(
                        extraction.get("chunk_overlap"),
                        config["chunk_overlap"],
                    )
                    config["max_source_chars"] = self._positive_int(
                        extraction.get("max_source_chars"),
                        config["max_source_chars"],
                    )
            except Exception as e:
                logger.warning(f"Error loading extraction config: {e}")

        if config["chunk_overlap"] >= config["chunk_size"]:
            config["chunk_overlap"] = max(1, config["chunk_size"] // 4)

        return config

    def _parse_last_update(self) -> datetime | None:
        """Parse `last_update` from config, returning None when invalid/missing."""
        raw_last_update = self.update_config.get("last_update")
        if not raw_last_update:
            return None

        try:
            return datetime.fromisoformat(str(raw_last_update))
        except (TypeError, ValueError):
            logger.warning(f"Invalid last_update timestamp: {raw_last_update!r}")
            return None

    def should_update_database(self) -> bool:
        """Check if the database should be updated based on configuration."""
        if not self.update_config.get("auto_update", False):
            return False

        frequency = self.update_config.get("update_frequency", "manual")

        if frequency == "manual":
            return False
        elif frequency == "startup":
            return True
        elif frequency == "daily":
            last_update_date = self._parse_last_update()
            if last_update_date is None:
                return True

            return datetime.now() - last_update_date >= timedelta(days=1)
        elif frequency.startswith("every_"):
            try:
                days = int(frequency.split("_")[1])
                if days <= 0:
                    logger.warning(f"Invalid update frequency days: {days}")
                    return False

                last_update_date = self._parse_last_update()
                if last_update_date is None:
                    return True

                return datetime.now() - last_update_date >= timedelta(days=days)
            except (ValueError, IndexError):
                return False

        return False

    @staticmethod
    def _strip_html(text: str) -> str:
        """Remove HTML tags from note content."""
        return re.sub(r"<[^>]+>", "", text)

    def _chunk_text(
        self,
        text: str,
    ) -> list[str]:
        """Split text into overlapping chunks for fragment indexing."""
        if not text:
            return []

        chunk_size = self._positive_int(
            self.extraction_config.get("chunk_size"),
            self.DEFAULT_CHUNK_SIZE,
        )
        overlap = self._positive_int(
            self.extraction_config.get("chunk_overlap"),
            self.DEFAULT_CHUNK_OVERLAP,
        )
        max_source_chars = self._positive_int(
            self.extraction_config.get("max_source_chars"),
            self.DEFAULT_MAX_SOURCE_CHARS,
        )

        if max_source_chars > 0 and len(text) > max_source_chars:
            logger.warning(
                "Source text too large (%s chars), truncating to %s before chunking",
                len(text),
                max_source_chars,
            )
            text = text[:max_source_chars]

        if chunk_size <= 0:
            chunk_size = self.DEFAULT_CHUNK_SIZE

        safe_overlap = max(0, min(overlap, chunk_size - 1))
        chunks: list[str] = []
        text_len = len(text)
        start = 0
        while start < text_len and text[start].isspace():
            start += 1

        end_limit = text_len
        while end_limit > start and text[end_limit - 1].isspace():
            end_limit -= 1

        if start >= end_limit:
            return []

        while start < end_limit:
            end = min(start + chunk_size, end_limit)
            if end < end_limit:
                soft_floor = min(start + 200, end)
                paragraph_break = text.rfind("\n\n", soft_floor, end)
                whitespace_break = text.rfind(" ", soft_floor, end)
                split_at = max(paragraph_break, whitespace_break)
                if split_at > start:
                    end = split_at

            if end <= start:
                end = min(start + chunk_size, end_limit)
                if end <= start:
                    break

            chunk = text[start:end].strip()
            if chunk:
                chunks.append(chunk)

            if end >= end_limit:
                break
            next_start = end - safe_overlap
            start = next_start if next_start > start else end

        return chunks

    def _build_fragment_record(
        self,
        parent_item: dict[str, Any],
        fragment_type: str,
        source_key: str,
        source_label: str,
        text: str,
        chunk_index: int,
        chunk_count: int,
    ) -> dict[str, Any]:
        """Build an indexable fragment record for ChromaDB."""
        parent_metadata = ZoteroMapper.create_metadata(parent_item)
        parent_key = str(parent_metadata.get("item_key") or parent_item.get("key", ""))
        safe_source_key = source_key or source_label or "unknown"

        fragment_id = (
            f"{parent_key}::{fragment_type}::{safe_source_key}::{chunk_index}"
        )

        metadata = dict(parent_metadata)
        metadata.update(
            {
                "fragment_type": fragment_type,
                "source_key": safe_source_key,
                "source_label": source_label,
                "chunk_index": chunk_index,
                "chunk_count": chunk_count,
            }
        )

        return {
            "key": fragment_id,
            "__semantic_fragment__": True,
            "document": text.strip(),
            "metadata": metadata,
        }

    def _collect_local_fragment_records(
        self,
        reader: LocalDatabaseClient,
        item: Any,
        parent_item: dict[str, Any],
        extract_fulltext: bool,
    ) -> list[dict[str, Any]]:
        """Collect note/pdf fragments for one parent item from local storage."""
        records: list[dict[str, Any]] = []

        note_index = 0
        for note in reader.get_item_notes(item.item_id):
            try:
                note_text = self._strip_html(str(note.get("note", ""))).strip()
                if not note_text:
                    continue

                note_index += 1
                note_key = str(note.get("key") or f"note-{note_index}")
                chunks = self._chunk_text(note_text)
                for idx, chunk in enumerate(chunks, start=1):
                    records.append(
                        self._build_fragment_record(
                            parent_item=parent_item,
                            fragment_type="note",
                            source_key=note_key,
                            source_label=f"note-{note_index}",
                            text=chunk,
                            chunk_index=idx,
                            chunk_count=len(chunks),
                        )
                    )
            except MemoryError:
                logger.warning(
                    "Skipping note fragments for item %s due MemoryError", item.key
                )
                continue
            except Exception as e:
                logger.warning(
                    "Skipping one note fragment source for item %s: %s", item.key, e
                )
                continue

        if not extract_fulltext:
            return records

        for pdf_key, pdf_path in reader.iter_pdf_attachments(item.item_id):
            try:
                pdf_text = reader._extract_pdf_text(pdf_path).strip()
                if not pdf_text:
                    continue

                chunks = self._chunk_text(pdf_text)
                for idx, chunk in enumerate(chunks, start=1):
                    records.append(
                        self._build_fragment_record(
                            parent_item=parent_item,
                            fragment_type="pdf",
                            source_key=pdf_key,
                            source_label=pdf_path.name,
                            text=chunk,
                            chunk_index=idx,
                            chunk_count=len(chunks),
                        )
                    )
            except MemoryError:
                logger.warning(
                    "Skipping pdf fragments for item %s attachment %s due MemoryError",
                    item.key,
                    pdf_key,
                )
                continue
            except Exception as e:
                logger.warning(
                    "Skipping one pdf fragment source for item %s attachment %s: %s",
                    item.key,
                    pdf_key,
                    e,
                )
                continue

        return records

    def _get_items_from_source(
        self,
        scan_limit: int = 100,
        treated_limit: int | None = None,
        extract_fulltext: bool = False,
        chroma_client: ChromaClient | None = None,
        force_rebuild: bool = False,
    ) -> list[dict[str, Any]]:
        """Get items from either local database or API."""
        if is_local_mode():
            return self._get_items_from_local_db(
                scan_limit,
                treated_limit,
                extract_fulltext=extract_fulltext,
                chroma_client=chroma_client,
                force_rebuild=force_rebuild,
            )
        else:
            return self._get_items_from_api(scan_limit, treated_limit)

    def _get_items_from_local_db(
        self,
        scan_limit: int = 100,
        treated_limit: int | None = None,
        extract_fulltext: bool = False,
        chroma_client: ChromaClient | None = None,
        force_rebuild: bool = False,
    ) -> list[dict[str, Any]]:
        """Get items from local Zotero database."""
        logger.info("Fetching items from local Zotero database...")

        try:
            # Load per-run config
            pdf_max_pages = None
            zotero_db_path = self.db_path
            try:
                if self.config_path and os.path.exists(self.config_path):
                    with open(self.config_path) as _f:
                        _cfg = json.load(_f)
                        semantic_cfg = _cfg.get("semantic_search", {})
                        pdf_max_pages = semantic_cfg.get("extraction", {}).get(
                            "pdf_max_pages"
                        )
                        if not zotero_db_path:
                            zotero_db_path = semantic_cfg.get("zotero_db_path")
            except Exception:
                pass

            # Use new LocalDatabaseClient wrapper
            with (
                suppress_stdout(),
                LocalDatabaseClient(
                    db_path=zotero_db_path, pdf_max_pages=pdf_max_pages or 10
                ) as reader,
            ):
                # Phase 1: fetch metadata only (fast)
                sys.stderr.write("Scanning local Zotero database for items...\n")

                # Get items using the new client method
                local_items = reader.get_items(
                    limit=treated_limit, include_fulltext=False
                )
                candidate_count = len(local_items)
                sys.stderr.write(f"Found {candidate_count} candidate items.\n")

                try:
                    sys.stderr.write(
                        "Building item + fragment documents from local storage...\n"
                    )
                except Exception:
                    pass

                # Convert to API-compatible format
                api_items: list[dict[str, Any]] = []
                fragment_records: list[dict[str, Any]] = []
                total_local_items = len(local_items)
                for idx_item, item in enumerate(local_items, start=1):
                    api_item: dict[str, Any] = {
                        "key": item.key,
                        "version": 0,
                        "data": {
                            "key": item.key,
                            "itemType": item.item_type or "journalArticle",
                            "title": item.title or "",
                            "abstractNote": item.abstract or "",
                            "extra": item.extra or "",
                            "fulltext": "",
                            "fulltextSource": "",
                            "dateAdded": item.date_added,
                            "dateModified": item.date_modified,
                            "creators": ZoteroMapper.parse_creators_string(
                                item.creators
                            ),
                        },
                    }

                    if item.notes:
                        api_item["data"]["note"] = item.notes
                        api_item["data"]["notes"] = item.notes
                    if item.tags:
                        api_item["data"]["tags"] = [{"tag": tag} for tag in item.tags]
                    if item.annotations:
                        api_item["data"]["annotations"] = item.annotations

                    api_items.append(api_item)
                    fragment_records.extend(
                        self._collect_local_fragment_records(
                            reader=reader,
                            item=item,
                            parent_item=api_item,
                            extract_fulltext=extract_fulltext,
                        )
                    )
                    try:
                        pct_items = (
                            idx_item / total_local_items * 100
                            if total_local_items
                            else 100.0
                        )
                        sys.stderr.write(
                            "Prepared local documents: "
                            f"{idx_item}/{total_local_items} "
                            f"({pct_items:.1f}%), "
                            f"fragments={len(fragment_records)}\n"
                        )
                    except Exception:
                        pass

                logger.info(
                    "Prepared %s parent items and %s fragment documents from local DB",
                    len(api_items),
                    len(fragment_records),
                )
                return [*api_items, *fragment_records]

        except Exception as e:
            logger.exception(f"Error reading from local database: {e}")
            logger.info("Falling back to API...")
            return self._get_items_from_api(
                scan_limit=scan_limit,
                treated_limit=treated_limit,
            )

    def _get_items_from_api(
        self, scan_limit: int = 100, treated_limit: int | None = None
    ) -> list[dict[str, Any]]:
        """Get items from Zotero API with batch scanning."""
        logger.info(
            "Fetching items from Zotero API "
            f"(batch: {scan_limit}, max: {treated_limit or 'all'})..."
        )

        batch_size = scan_limit
        start = 0
        all_items = []

        while True:
            batch_params = {"start": start, "limit": batch_size}
            if treated_limit and len(all_items) >= treated_limit:
                break

            try:
                items = self.zotero_client.items(**batch_params)
            except Exception as e:
                if "Connection refused" in str(e):
                    raise RuntimeError(
                        "Cannot connect to Zotero local API. Ensure Zotero is running."
                    ) from e
                raise

            if not items:
                break

            filtered_items = [
                item
                for item in items
                if item.get("data", {}).get("itemType")
                not in ["attachment", "note", "annotation"]
            ]

            all_items.extend(filtered_items)
            start += batch_size

            if len(items) < batch_size:
                break

        if treated_limit:
            all_items = all_items[:treated_limit]

        logger.info(f"Retrieved {len(all_items)} items from API")
        return all_items

    def update_database(
        self,
        force_full_rebuild: bool = False,
        scan_limit: int = 100,
        treated_limit: int | None = None,
        extract_fulltext: bool = False,
    ) -> dict[str, Any]:
        """Update the semantic search database."""
        logger.info("Starting database update...")
        start_time = datetime.now()

        stats: dict[str, Any] = {
            "total_items": 0,
            "total_fragments": 0,
            "total_documents": 0,
            "processed_items": 0,
            "added_items": 0,
            "updated_items": 0,
            "skipped_items": 0,
            "errors": 0,
            "start_time": start_time.isoformat(),
            "duration": None,
        }

        try:
            if force_full_rebuild:
                logger.info("Force rebuilding database...")
                self.chroma_client.reset_collection()

            all_items = self._get_items_from_source(
                scan_limit=scan_limit,
                treated_limit=treated_limit,
                extract_fulltext=extract_fulltext,
                chroma_client=self.chroma_client if not force_full_rebuild else None,
                force_rebuild=force_full_rebuild,
            )

            total_fragments = sum(
                1 for item in all_items if bool(item.get("__semantic_fragment__"))
            )
            stats["total_fragments"] = total_fragments
            stats["total_items"] = len(all_items) - total_fragments
            stats["total_documents"] = len(all_items)
            logger.info(
                "Found %s parent items and %s fragments to process",
                stats["total_items"],
                stats["total_fragments"],
            )

            try:
                sys.stderr.write(
                    f"Total documents to index: {stats['total_documents']}\n"
                )
            except Exception:
                pass

            batch_size = 50
            total_docs = len(all_items)
            total_batches = (
                (total_docs + batch_size - 1) // batch_size if total_docs else 0
            )
            for batch_idx, i in enumerate(range(0, total_docs, batch_size), start=1):
                batch = all_items[i : i + batch_size]
                batch_stats = self._process_item_batch(batch)

                stats["processed_items"] += batch_stats["processed"]
                stats["added_items"] += batch_stats["added"]
                stats["updated_items"] += batch_stats["updated"]
                stats["skipped_items"] += batch_stats["skipped"]
                stats["errors"] += batch_stats["errors"]

                try:
                    pct = (
                        (stats["processed_items"] + stats["skipped_items"])
                        / total_docs
                        * 100
                        if total_docs
                        else 100.0
                    )
                    sys.stderr.write(
                        "Indexing progress: "
                        f"batch {batch_idx}/{total_batches}, "
                        f"processed={stats['processed_items']}, "
                        f"skipped={stats['skipped_items']}, "
                        f"errors={stats['errors']}, "
                        f"{pct:.1f}%\n"
                    )
                except Exception:
                    pass

            self.update_config["last_update"] = datetime.now().isoformat()
            self._save_update_config()

            end_time = datetime.now()
            stats["duration"] = str(end_time - start_time)
            stats["end_time"] = end_time.isoformat()

            logger.info(f"Database update completed in {stats['duration']}")
            return stats

        except Exception as e:
            logger.exception(f"Error updating database: {e}")
            stats["error"] = str(e)
            return stats

    def _process_item_batch(self, items: list[dict[str, Any]]) -> dict[str, int]:
        """Process a batch of items."""
        stats = {"processed": 0, "added": 0, "updated": 0, "skipped": 0, "errors": 0}

        documents = []
        metadatas = []
        ids = []

        for item in items:
            try:
                item_key = item.get("key", "")
                if not item_key:
                    stats["skipped"] += 1
                    continue

                if item.get("__semantic_fragment__"):
                    doc_text = str(item.get("document", ""))
                    raw_metadata = item.get("metadata", {})
                    metadata = (
                        dict(raw_metadata) if isinstance(raw_metadata, dict) else {}
                    )
                    metadata.setdefault("fragment_type", "fragment")
                else:
                    doc_text = ZoteroMapper.create_document_text(item)
                    metadata = ZoteroMapper.create_metadata(item)
                    metadata.setdefault("fragment_type", "item")

                if not doc_text.strip():
                    stats["skipped"] += 1
                    continue

                documents.append(doc_text)
                metadatas.append(metadata)
                ids.append(item_key)

                stats["processed"] += 1

            except Exception as e:
                logger.error(f"Error processing item {item.get('key', 'unknown')}: {e}")
                stats["errors"] += 1

        if documents:
            try:
                self.chroma_client.upsert_documents(documents, metadatas, ids)
                stats["added"] += len(documents)
            except Exception as e:
                logger.exception(f"Error adding documents to ChromaDB: {e}")
                stats["errors"] += len(documents)

        return stats

    @staticmethod
    def _first_nested_list(values: Any) -> list[Any]:
        """Safely unwrap Chroma nested-list fields."""
        if isinstance(values, list) and values and isinstance(values[0], list):
            return values[0]
        return []

    def search(
        self,
        query: str,
        limit: int = 10,
        filters: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Perform semantic search."""
        if limit <= 0:
            return {
                "query": query,
                "limit": limit,
                "filters": filters,
                "results": [],
                "total_found": 0,
            }

        try:
            results = self.chroma_client.search(
                query_texts=[query],
                n_results=limit,
                where=filters,
            )

            enriched_results = self._enrich_search_results(results, query)

            return {
                "query": query,
                "limit": limit,
                "filters": filters,
                "results": enriched_results,
                "total_found": len(enriched_results),
            }

        except Exception as e:
            logger.exception(f"Error performing semantic search: {e}")
            return {
                "query": query,
                "results": [],
                "error": str(e),
            }

    def _enrich_search_results(
        self, chroma_results: dict[str, Any], query: str
    ) -> list[dict[str, Any]]:
        """Enrich ChromaDB results with full Zotero item data."""
        enriched = []

        ids = self._first_nested_list(chroma_results.get("ids"))
        if not ids:
            return enriched

        distances = self._first_nested_list(chroma_results.get("distances"))
        documents = self._first_nested_list(chroma_results.get("documents"))
        metadatas = self._first_nested_list(chroma_results.get("metadatas"))

        for i, result_id in enumerate(ids):
            try:
                raw_metadata = metadatas[i] if i < len(metadatas) else {}
                metadata = dict(raw_metadata) if isinstance(raw_metadata, dict) else {}
                parent_item_key = str(metadata.get("item_key") or result_id)

                # Use synchronous pyzotero client here as this runs in thread
                zotero_item = self.zotero_client.item(parent_item_key)

                enriched_result = {
                    "item_key": parent_item_key,
                    "result_id": result_id,
                    "similarity_score": 1 - distances[i] if i < len(distances) else 0,
                    "matched_text": documents[i] if i < len(documents) else "",
                    "metadata": metadata,
                    "zotero_item": zotero_item,
                    "query": query,
                }

                enriched.append(enriched_result)

            except Exception as e:
                raw_metadata = metadatas[i] if i < len(metadatas) else {}
                metadata = dict(raw_metadata) if isinstance(raw_metadata, dict) else {}
                parent_item_key = str(metadata.get("item_key") or result_id)
                logger.error(f"Error enriching result for item {parent_item_key}: {e}")
                enriched.append(
                    {
                        "item_key": parent_item_key,
                        "result_id": result_id,
                        "similarity_score": (
                            1 - distances[i] if i < len(distances) else 0
                        ),
                        "matched_text": documents[i] if i < len(documents) else "",
                        "metadata": metadata,
                        "query": query,
                        "error": str(e),
                    }
                )

        return enriched

    def get_database_status(self) -> dict[str, Any]:
        """Get status information about the semantic search database."""
        collection_info = self.chroma_client.get_collection_info()

        return {
            "collection_info": collection_info,
            "update_config": self.update_config,
            "should_update": self.should_update_database(),
            "last_update": self.update_config.get("last_update"),
            "exists": collection_info.get("count", 0) > 0,
            "item_count": collection_info.get("count", 0),
            "embedding_model": collection_info.get("embedding_model", "unknown"),
        }


def create_semantic_search(
    config_path: str | None = None, db_path: str | None = None
) -> ZoteroSemanticSearch:
    """Create a ZoteroSemanticSearch instance."""
    if not config_path:
        config_path = str(get_config_path() / "config.json")

    return ZoteroSemanticSearch(config_path=config_path, db_path=db_path)


# -------------------- Async Wrapper Functions --------------------


async def semantic_search(
    query: str, limit: int = 10, filters: dict[str, Any] | None = None
) -> list[dict[str, Any]]:
    """
    Async wrapper for semantic search.

    Returns simplified list of results compatible with MCP tools.
    """
    loop = asyncio.get_event_loop()
    searcher = create_semantic_search()

    result = await loop.run_in_executor(
        None, lambda: searcher.search(query, limit, filters)
    )

    # Transform to simplified format for MCP tools
    simplified = []
    for item in result.get("results", []):
        zotero_item = item.get("zotero_item", {})
        simplified.append(
            {
                "key": item.get("item_key"),
                "similarity_score": item.get("similarity_score"),
                "matched_text": item.get("matched_text"),
                "data": zotero_item.get("data", {}),
                # Flatten some fields for easier access
                "title": zotero_item.get("data", {}).get("title"),
                "itemType": zotero_item.get("data", {}).get("itemType"),
            }
        )

    return simplified


async def update_database(
    force_rebuild: bool = False,
    include_fulltext: bool = True,
    limit: int | None = None,
) -> dict[str, Any]:
    """Async wrapper for database update."""
    loop = asyncio.get_event_loop()
    searcher = create_semantic_search()

    return await loop.run_in_executor(
        None,
        lambda: searcher.update_database(
            force_full_rebuild=force_rebuild,
            treated_limit=limit,
            extract_fulltext=include_fulltext,
        ),
    )


async def get_database_status() -> dict[str, Any]:
    """Async wrapper for database status."""
    loop = asyncio.get_event_loop()
    searcher = create_semantic_search()

    return await loop.run_in_executor(None, lambda: searcher.get_database_status())
