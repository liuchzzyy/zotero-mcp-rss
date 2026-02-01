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
            last_update = self.update_config.get("last_update")
            if not last_update:
                return True

            last_update_date = datetime.fromisoformat(last_update)
            return datetime.now() - last_update_date >= timedelta(days=1)
        elif frequency.startswith("every_"):
            try:
                days = int(frequency.split("_")[1])
                last_update = self.update_config.get("last_update")
                if not last_update:
                    return True

                last_update_date = datetime.fromisoformat(last_update)
                return datetime.now() - last_update_date >= timedelta(days=days)
            except (ValueError, IndexError):
                return False

        return False

    def _get_items_from_source(
        self,
        scan_limit: int = 100,
        treated_limit: int | None = None,
        extract_fulltext: bool = False,
        chroma_client: ChromaClient | None = None,
        force_rebuild: bool = False,
    ) -> list[dict[str, Any]]:
        """Get items from either local database or API."""
        if extract_fulltext and is_local_mode():
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

                # TODO: Deduplication logic could go here (similar to original)

                total_to_extract = len(local_items)
                try:
                    sys.stderr.write("Extracting content...\n")
                except Exception:
                    pass

                # Phase 2: extract fulltext if requested
                if extract_fulltext:
                    extracted = 0
                    skipped_existing = 0
                    updated_existing = 0
                    items_to_process = []

                    for it in local_items:
                        should_extract = True

                        if chroma_client and not force_rebuild:
                            existing_metadata = chroma_client.get_document_metadata(
                                it.key
                            )
                            if existing_metadata:
                                chroma_has_fulltext = existing_metadata.get(
                                    "has_fulltext", False
                                )
                                local_has_fulltext = any(
                                    True for _ in reader._iter_attachments(it.item_id)
                                )

                                if not chroma_has_fulltext and local_has_fulltext:
                                    updated_existing += 1
                                else:
                                    should_extract = False
                                    skipped_existing += 1

                        if should_extract:
                            if not it.fulltext:
                                text_result = reader._extract_fulltext(it.item_id)
                                if text_result:
                                    it.fulltext, it.fulltext_source = text_result
                            extracted += 1
                            items_to_process.append(it)

                            if extracted % 25 == 0 and total_to_extract:
                                try:
                                    sys.stderr.write(
                                        f"Extracted content for {extracted}/{total_to_extract} items (skipped {skipped_existing} existing, updating {updated_existing})...\n"
                                    )
                                except Exception:
                                    pass

                    local_items = items_to_process

                else:
                    for it in local_items:
                        it.fulltext = None
                        it.fulltext_source = None

                # Convert to API-compatible format
                api_items: list[dict[str, Any]] = []
                for item in local_items:
                    api_item: dict[str, Any] = {
                        "key": item.key,
                        "version": 0,
                        "data": {
                            "key": item.key,
                            "itemType": item.item_type or "journalArticle",
                            "title": item.title or "",
                            "abstractNote": item.abstract or "",
                            "extra": item.extra or "",
                            "fulltext": item.fulltext or "" if extract_fulltext else "",
                            "fulltextSource": (
                                item.fulltext_source or "" if extract_fulltext else ""
                            ),
                            "dateAdded": item.date_added,
                            "dateModified": item.date_modified,
                            "creators": ZoteroMapper.parse_creators_string(
                                item.creators
                            ),
                        },
                    }

                    if item.notes:
                        api_item["data"]["notes"] = item.notes

                    api_items.append(api_item)

                logger.info(f"Retrieved {len(api_items)} items from local database")
                return api_items

        except Exception as e:
            logger.error(f"Error reading from local database: {e}")
            logger.info("Falling back to API...")
            return self._get_items_from_api(scan_limit)

    def _get_items_from_api(
        self, scan_limit: int = 100, treated_limit: int | None = None
    ) -> list[dict[str, Any]]:
        """Get items from Zotero API with batch scanning."""
        logger.info(
            f"Fetching items from Zotero API (batch: {scan_limit}, max: {treated_limit or 'all'})..."
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
                    raise Exception(
                        "Cannot connect to Zotero local API. Ensure Zotero is running."
                    ) from e
                raise

            if not items:
                break

            filtered_items = [
                item
                for item in items
                if item.get("data", {}).get("itemType") not in ["attachment", "note"]
            ]

            all_items.extend(filtered_items)
            start += batch_size

            if len(items) < batch_size:
                break

        if treated_limit:
            all_items = all_items[:treated_limit]

        logger.info(f"Retrieved {len(all_items)} items from API")
        return all_items

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

            stats["total_items"] = len(all_items)
            logger.info(f"Found {stats['total_items']} items to process")

            try:
                sys.stderr.write(f"Total items to index: {stats['total_items']}\n")
            except Exception:
                pass

            batch_size = 50
            for i in range(0, len(all_items), batch_size):
                batch = all_items[i : i + batch_size]
                batch_stats = self._process_item_batch(batch)

                stats["processed_items"] += batch_stats["processed"]
                stats["added_items"] += batch_stats["added"]
                stats["updated_items"] += batch_stats["updated"]
                stats["skipped_items"] += batch_stats["skipped"]
                stats["errors"] += batch_stats["errors"]

            self.update_config["last_update"] = datetime.now().isoformat()
            self._save_update_config()

            end_time = datetime.now()
            stats["duration"] = str(end_time - start_time)
            stats["end_time"] = end_time.isoformat()

            logger.info(f"Database update completed in {stats['duration']}")
            return stats

        except Exception as e:
            logger.error(f"Error updating database: {e}")
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

                fulltext = item.get("data", {}).get("fulltext", "")
                doc_text = (
                    fulltext
                    if fulltext.strip()
                    else ZoteroMapper.create_document_text(item)
                )
                metadata = ZoteroMapper.create_metadata(item)

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
                logger.error(f"Error adding documents to ChromaDB: {e}")
                stats["errors"] += len(documents)

        return stats

    def search(
        self,
        query: str,
        limit: int = 10,
        filters: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Perform semantic search."""
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
            logger.error(f"Error performing semantic search: {e}")
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

        if not chroma_results.get("ids") or not chroma_results["ids"][0]:
            return enriched

        ids = chroma_results["ids"][0]
        distances = chroma_results.get("distances", [[]])[0]
        documents = chroma_results.get("documents", [[]])[0]
        metadatas = chroma_results.get("metadatas", [[]])[0]

        for i, item_key in enumerate(ids):
            try:
                # Use synchronous pyzotero client here as this runs in thread
                zotero_item = self.zotero_client.item(item_key)

                enriched_result = {
                    "item_key": item_key,
                    "similarity_score": 1 - distances[i] if i < len(distances) else 0,
                    "matched_text": documents[i] if i < len(documents) else "",
                    "metadata": metadatas[i] if i < len(metadatas) else {},
                    "zotero_item": zotero_item,
                    "query": query,
                }

                enriched.append(enriched_result)

            except Exception as e:
                logger.error(f"Error enriching result for item {item_key}: {e}")
                enriched.append(
                    {
                        "item_key": item_key,
                        "similarity_score": (
                            1 - distances[i] if i < len(distances) else 0
                        ),
                        "matched_text": documents[i] if i < len(documents) else "",
                        "metadata": metadatas[i] if i < len(metadatas) else {},
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
    include_fulltext: bool = False,
    limit: int | None = None,
) -> dict[str, Any]:
    """Async wrapper for database update."""
    loop = asyncio.get_event_loop()
    searcher = create_semantic_search()

    return await loop.run_in_executor(
        None,
        lambda: searcher.update_database(
            force_full_rebuild=force_rebuild,
            limit=limit,
            extract_fulltext=include_fulltext,
        ),
    )


async def get_database_status() -> dict[str, Any]:
    """Async wrapper for database status."""
    loop = asyncio.get_event_loop()
    searcher = create_semantic_search()

    return await loop.run_in_executor(None, lambda: searcher.get_database_status())
