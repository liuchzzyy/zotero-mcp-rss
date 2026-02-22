"""
Batch Loader utility for parallel Zotero API calls.
"""

import asyncio
import logging
import tempfile
from pathlib import Path
from typing import Any, cast

from zotero_mcp.clients.zotero.pdf_extractor import MultiModalPDFExtractor
from zotero_mcp.services.zotero.item_service import ItemService

logger = logging.getLogger(__name__)


class BatchLoader:
    """
    Helper to fetch Zotero data in parallel.

    Optimizes performance for Cloud API by:
    1. Fetching bundle components (metadata, fulltext, etc.) concurrently.
    2. Fetching multiple bundles concurrently with a semaphore.
    """

    def __init__(self, item_service: ItemService, concurrency: int = 3):
        """
        Initialize BatchLoader.

        Args:
            item_service: Instance of ItemService
            concurrency: Max concurrent item fetches (default: 3)
        """
        self.item_service = item_service
        self.semaphore = asyncio.Semaphore(concurrency)

    async def get_item_bundle_parallel(
        self,
        item_key: str,
        include_fulltext: bool = True,
        include_annotations: bool = True,
        include_notes: bool = True,
        include_multimodal: bool = False,
    ) -> dict[str, Any]:
        """
        Fetch a single item bundle with parallel component requests.
        """
        # 1. Fetch Item Data (Base)
        # We need item data first to know if we should proceed?
        # Actually, for a bundle, we can try fetching everything.
        # But usually we need metadata first. However, to maximize speed, we fire all.

        tasks = [
            self.item_service.get_item(item_key),  # 0: Metadata
            self.item_service.get_item_children(item_key),  # 1: Children
        ]

        # Optional tasks
        # We'll map results by index
        task_map = {0: "metadata", 1: "children"}
        next_idx = 2

        if include_fulltext:
            tasks.append(self.item_service.get_fulltext(item_key))
            task_map[next_idx] = "fulltext"
            next_idx += 1

        if include_annotations:
            tasks.append(self.item_service.get_annotations(item_key))
            task_map[next_idx] = "annotations"
            next_idx += 1

        # Execute parallel requests
        results = await asyncio.gather(*tasks, return_exceptions=True)

        bundle: dict[str, Any] = {}

        # Process results
        for i, result in enumerate(results):
            key = task_map.get(i)
            if isinstance(result, Exception):
                logger.warning(f"Error fetching {key} for {item_key}: {result}")
                if key == "metadata":
                    # Critical failure
                    raise result
                continue

            if key == "metadata":
                bundle["metadata"] = result
            elif key == "children":
                children = cast(list[dict[str, Any]], result)
                bundle["attachments"] = [
                    c
                    for c in children
                    if c.get("data", {}).get("itemType") == "attachment"
                ]
                if include_notes:
                    bundle["notes"] = [
                        c
                        for c in children
                        if c.get("data", {}).get("itemType") == "note"
                    ]
            elif key == "fulltext":
                bundle["fulltext"] = result
            elif key == "annotations":
                bundle["annotations"] = result
        if include_multimodal:
            attachments = bundle.get("attachments", [])
            bundle["multimodal"] = await self._extract_multimodal_content(
                item_key, attachments
            )

        return bundle

    @staticmethod
    def _get_zotero_storage_dir() -> Path | None:
        """Get Zotero storage directory by auto-detecting data directory."""
        import platform as _platform

        system = _platform.system()
        candidates: list[Path] = []
        if system in ("Darwin", "Windows"):
            candidates.append(Path.home() / "Zotero" / "storage")
        else:
            candidates.append(Path.home() / "Zotero" / "storage")

        for path in candidates:
            if path.is_dir():
                return path
        return None

    def _find_pdf_in_storage(self, attachment_key: str) -> Path | None:
        """Find a PDF file in Zotero storage by attachment key.

        Searches <storage_dir>/<attachment_key>/*.pdf for the first PDF file.
        """
        storage_dir = self._get_zotero_storage_dir()
        if not storage_dir:
            return None
        att_dir = storage_dir / attachment_key
        if not att_dir.is_dir():
            return None
        pdfs = list(att_dir.glob("*.pdf"))
        return pdfs[0] if pdfs else None

    async def _extract_multimodal_content(
        self, item_key: str, attachments: list[dict[str, Any]] | None = None
    ) -> dict[str, Any]:
        """Extract multi-modal content (images, tables) from PDF attachments.

        Args:
            item_key: Zotero item key

        Returns:
            Dictionary with extracted multi-modal content, or empty dict if no PDF
        """
        try:
            # Get attachments to find PDF
            if attachments is None:
                attachments = await self.item_service.get_item_children(item_key)

            # Filter for PDF attachments
            pdf_attachments = [
                a
                for a in attachments
                if a.get("data", {}).get("itemType") == "attachment"
                and a.get("data", {}).get("contentType") == "application/pdf"
            ]

            if not pdf_attachments:
                logger.debug(f"No PDF attachments found for {item_key}")
                return {}

            # Try each PDF attachment until we find one that exists locally
            pdf_path: Path | None = None
            for pdf_att in pdf_attachments:
                pdf_path_info = pdf_att.get("data", {}).get("path")
                attachment_key = pdf_att.get("key") or pdf_att.get(
                    "data", {}
                ).get("key")

                # Strategy 1: Resolve "storage:filename.pdf" via local_client
                if pdf_path_info and pdf_path_info.startswith("storage:"):
                    local_client = self.item_service.local_client
                    if local_client and attachment_key:
                        resolved = local_client._resolve_path(
                            attachment_key, pdf_path_info
                        )
                        if resolved and resolved.exists():
                            pdf_path = resolved
                            break

                # Strategy 2: Direct filesystem lookup by attachment key
                # Works even without local_client or when path is None
                # (e.g. items fetched via Web API)
                if attachment_key:
                    found = self._find_pdf_in_storage(attachment_key)
                    if found:
                        pdf_path = found
                        break

                # Strategy 3: Direct path (non-storage)
                if pdf_path_info and not pdf_path_info.startswith("storage:"):
                    candidate = Path(pdf_path_info)
                    if candidate.exists():
                        pdf_path = candidate
                        break

            # Strategy 4: Download PDF via Zotero Web API (cloud fallback)
            if pdf_path is None or not pdf_path.exists():
                for pdf_att in pdf_attachments:
                    attachment_key = pdf_att.get("key") or pdf_att.get(
                        "data", {}
                    ).get("key")
                    if not attachment_key:
                        continue

                    # Check temp cache first
                    cache_dir = Path(tempfile.gettempdir()) / "zotero-mcp-downloads"
                    cached_pdf = cache_dir / f"{attachment_key}.pdf"
                    if cached_pdf.exists() and cached_pdf.stat().st_size > 0:
                        logger.info(
                            f"Using cached downloaded PDF for {attachment_key}"
                        )
                        pdf_path = cached_pdf
                        break

                    # Download via API
                    logger.info(
                        f"Downloading PDF for {item_key} "
                        f"(attachment {attachment_key}) via Web API..."
                    )
                    pdf_bytes = await self.item_service.download_attachment(
                        attachment_key
                    )
                    if pdf_bytes and len(pdf_bytes) > 100:
                        cache_dir.mkdir(parents=True, exist_ok=True)
                        cached_pdf.write_bytes(pdf_bytes)
                        logger.info(
                            f"Downloaded and cached PDF: {len(pdf_bytes)} bytes "
                            f"-> {cached_pdf}"
                        )
                        pdf_path = cached_pdf
                        break

            if pdf_path is None or not pdf_path.exists():
                logger.debug(f"No PDF found for {item_key} (all strategies exhausted)")
                return {}

            # Extract multi-modal content
            extractor = MultiModalPDFExtractor()
            result = await asyncio.to_thread(
                extractor.extract_elements,
                pdf_path,
            )

            return result

        except Exception as e:
            logger.warning(f"Failed to extract multi-modal content for {item_key}: {e}")
            return {}

    async def fetch_many_bundles(
        self,
        item_keys: list[str],
        include_fulltext: bool = True,
        include_annotations: bool = True,
        include_notes: bool = True,
        include_multimodal: bool = False,
    ) -> list[dict[str, Any]]:
        """
        Fetch multiple bundles in parallel with concurrency control.
        """

        async def _fetch_safe(key: str):
            async with self.semaphore:
                try:
                    return await self.get_item_bundle_parallel(
                        key,
                        include_fulltext,
                        include_annotations,
                        include_notes,
                        include_multimodal,
                    )
                except Exception as e:
                    logger.error(f"Failed to fetch bundle for {key}: {e}")
                    return None

        tasks = [_fetch_safe(key) for key in item_keys]
        results = await asyncio.gather(*tasks)

        # Filter out failed fetches
        return [r for r in results if r is not None]
