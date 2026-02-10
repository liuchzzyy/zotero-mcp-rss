"""
Batch Loader utility for parallel Zotero API calls.
"""

import asyncio
import logging
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

            # Get local path from first PDF attachment
            first_pdf = pdf_attachments[0]
            pdf_path_info = first_pdf.get("data", {}).get("path")
            if not pdf_path_info:
                logger.debug(f"No path info for PDF attachment in {item_key}")
                return {}

            # Resolve Zotero storage path to filesystem path
            # Format: "storage:filename.pdf" -> <storage_dir>/<attachment_key>/filename.pdf
            if pdf_path_info.startswith("storage:"):
                local_client = self.item_service.local_client
                attachment_key = first_pdf.get("key") or first_pdf.get("data", {}).get(
                    "key"
                )
                if local_client and attachment_key:
                    resolved = local_client._resolve_path(
                        attachment_key, pdf_path_info
                    )
                    if resolved and resolved.exists():
                        pdf_path = resolved
                    else:
                        logger.debug(
                            f"Local PDF path resolution failed for {item_key}"
                        )
                        return {}
                else:
                    logger.debug(
                        f"Local PDF path resolution requires LocalDatabaseClient for {item_key}"
                    )
                    return {}

            # If we have a direct path, try extraction
            if not pdf_path_info.startswith("storage:"):
                pdf_path = Path(pdf_path_info)
            if not pdf_path.exists():
                logger.debug(f"PDF file does not exist: {pdf_path}")
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
