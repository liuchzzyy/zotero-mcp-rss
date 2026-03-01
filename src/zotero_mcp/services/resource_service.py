"""Service layer for CLI resource operations."""

from __future__ import annotations

import html
from pathlib import Path
import re
from typing import Any

from zotero_mcp.services.data_access import DataAccessService
from zotero_mcp.services.zotero.note_relation_service import NoteRelationService


class ResourceService:
    """Business operations for item/note/annotation/pdf/collection commands."""

    def __init__(self, data_service: DataAccessService | None = None):
        self.data_service = data_service or DataAccessService()

    # -------------------- Item operations --------------------

    async def get_item(self, item_key: str) -> dict[str, Any]:
        return await self.data_service.get_item(item_key)

    async def list_items(
        self,
        limit: int,
        offset: int,
        item_type: str | None = None,
    ) -> dict[str, Any]:
        results = await self.data_service.get_all_items(
            limit=limit,
            start=offset,
            item_type=item_type,
        )
        return {"count": len(results), "items": [item.model_dump() for item in results]}

    async def list_item_children(
        self,
        item_key: str,
        item_type: str | None = None,
    ) -> dict[str, Any]:
        children = await self.data_service.get_item_children(
            item_key, item_type=item_type
        )
        return {"count": len(children), "children": children}

    async def get_item_fulltext(self, item_key: str) -> dict[str, Any]:
        fulltext = await self.data_service.get_fulltext(item_key)
        return {"item_key": item_key, "fulltext": fulltext}

    async def get_item_bundle(
        self,
        item_key: str,
        include_fulltext: bool,
        include_annotations: bool,
        include_notes: bool,
    ) -> dict[str, Any]:
        return await self.data_service.get_item_bundle(
            item_key=item_key,
            include_fulltext=include_fulltext,
            include_annotations=include_annotations,
            include_notes=include_notes,
        )

    async def delete_item(self, item_key: str) -> dict[str, Any]:
        return await self.data_service.delete_item(item_key)

    async def update_item(self, payload: dict[str, Any]) -> dict[str, Any]:
        return await self.data_service.update_item(payload)

    async def create_items(
        self, payload: dict[str, Any] | list[dict[str, Any]]
    ) -> dict[str, Any]:
        items = payload if isinstance(payload, list) else [payload]
        return await self.data_service.create_items(items)

    async def add_tags_to_item(self, item_key: str, tags: list[str]) -> dict[str, Any]:
        return await self.data_service.add_tags_to_item(item_key, tags)

    async def add_item_to_collection(
        self, collection_key: str, item_key: str
    ) -> dict[str, Any]:
        return await self.data_service.add_item_to_collection(collection_key, item_key)

    async def remove_item_from_collection(
        self, collection_key: str, item_key: str
    ) -> dict[str, Any]:
        return await self.data_service.remove_item_from_collection(
            collection_key, item_key
        )

    # -------------------- Note operations --------------------

    async def list_notes(
        self, item_key: str, limit: int, offset: int
    ) -> dict[str, Any]:
        notes = await self.data_service.get_notes(item_key)
        total = len(notes)
        sliced = notes[offset : offset + limit]
        return {"total": total, "count": len(sliced), "notes": sliced}

    async def create_note(
        self, item_key: str, content: str, tags: list[str] | None = None
    ) -> dict[str, Any]:
        return await self.data_service.create_note(
            parent_key=item_key,
            content=content,
            tags=tags or [],
        )

    async def delete_note(self, note_key: str) -> dict[str, Any]:
        result = await self.data_service.delete_item(note_key)
        return {"deleted": True, "note_key": note_key, "result": result}

    async def search_notes(self, query: str, limit: int, offset: int) -> dict[str, Any]:
        candidates = await self.data_service.search_items(
            query,
            limit=max(limit * 2, 50),
            offset=0,
            qmode="everything",
        )
        hits: list[dict[str, Any]] = []
        query_lower = query.lower()

        for item in candidates:
            notes = await self.data_service.get_notes(item.key)
            for note in notes:
                data = note.get("data", {})
                raw_note = str(data.get("note", ""))
                if query_lower in raw_note.lower():
                    hits.append(
                        {
                            "item_key": item.key,
                            "item_title": item.title,
                            "note_key": data.get("key", ""),
                            "note": raw_note,
                        }
                    )

        total = len(hits)
        sliced = hits[offset : offset + limit]
        return {
            "query": query,
            "total": total,
            "count": len(sliced),
            "results": sliced,
        }

    async def relate_note(
        self,
        note_key: str,
        collection: str,
        dry_run: bool,
        bidirectional: bool,
    ) -> dict[str, Any]:
        service = NoteRelationService(data_service=self.data_service)
        return await service.relate_note(
            note_key=note_key,
            collection=collection,
            dry_run=dry_run,
            bidirectional=bidirectional,
            top_k=5,
        )

    # -------------------- Annotation operations --------------------

    @staticmethod
    def _clean_note_html(note_html: str) -> str:
        cleaned = re.sub(r"<[^>]+>", "", note_html)
        return html.unescape(cleaned).strip()

    @staticmethod
    def _annotation_payload(annotation: dict[str, Any]) -> dict[str, Any]:
        data = annotation.get("data", annotation)
        return {
            "annotation_key": data.get("key", ""),
            "annotation_type": data.get("annotationType", data.get("type", "")),
            "text": data.get("annotationText", data.get("text", "")),
            "comment": data.get("annotationComment", data.get("comment", "")),
            "page_label": data.get("annotationPageLabel", data.get("page", "")),
            "color": data.get("annotationColor", data.get("color", "")),
        }

    async def list_annotations(
        self,
        item_key: str,
        annotation_type: str,
        limit: int,
        offset: int,
    ) -> dict[str, Any]:
        annotations = await self.data_service.get_annotations(item_key)
        if annotation_type != "all":
            annotations = [
                annotation
                for annotation in annotations
                if annotation.get("data", {}).get("annotationType", "").lower()
                == annotation_type.lower()
            ]
        total = len(annotations)
        sliced = annotations[offset : offset + limit]
        return {
            "item_key": item_key,
            "total": total,
            "count": len(sliced),
            "annotations": sliced,
        }

    async def create_annotation(
        self,
        item_key: str,
        annotation_type: str,
        text: str,
        comment: str | None = None,
        page_label: str | None = None,
        color: str | None = None,
    ) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "itemType": "annotation",
            "parentItem": item_key,
            "annotationType": annotation_type,
            "annotationText": text,
        }
        if comment:
            payload["annotationComment"] = comment
        if page_label:
            payload["annotationPageLabel"] = page_label
        if color:
            payload["annotationColor"] = color
        return await self.data_service.create_items([payload])

    async def search_annotations(
        self,
        query: str,
        limit: int,
        offset: int,
        annotation_type: str = "all",
    ) -> dict[str, Any]:
        candidates = await self.data_service.search_items(
            query,
            limit=max(limit * 2, 50),
            offset=0,
            qmode="everything",
        )
        query_lower = query.lower()
        matches: list[dict[str, Any]] = []

        for item in candidates:
            try:
                annotations = await self.data_service.get_annotations(item.key)
            except Exception:
                continue

            for annotation in annotations:
                data = annotation.get("data", annotation)
                current_type = str(
                    data.get("annotationType", data.get("type", ""))
                ).lower()
                if annotation_type != "all" and current_type != annotation_type.lower():
                    continue

                ann_text = str(data.get("annotationText", data.get("text", "")))
                ann_comment = str(
                    data.get("annotationComment", data.get("comment", ""))
                )
                haystack = f"{ann_text}\n{ann_comment}".lower()
                if query_lower not in haystack:
                    continue

                payload = self._annotation_payload(annotation)
                payload["item_key"] = item.key
                payload["item_title"] = item.title
                matches.append(payload)

        total = len(matches)
        sliced = matches[offset : offset + limit]
        return {
            "query": query,
            "annotation_type": annotation_type,
            "total": total,
            "count": len(sliced),
            "results": sliced,
        }

    async def delete_annotation(self, annotation_key: str) -> dict[str, Any]:
        result = await self.data_service.delete_item(annotation_key)
        return {
            "deleted": True,
            "annotation_key": annotation_key,
            "result": result,
        }

    # -------------------- PDF operations --------------------

    async def list_pdfs(self, item_key: str, limit: int, offset: int) -> dict[str, Any]:
        children = await self.data_service.get_item_children(
            item_key=item_key, item_type="attachment"
        )
        pdfs = [
            child
            for child in children
            if child.get("data", {}).get("contentType") == "application/pdf"
        ]
        total = len(pdfs)
        sliced = pdfs[offset : offset + limit]
        return {
            "item_key": item_key,
            "total": total,
            "count": len(sliced),
            "pdfs": sliced,
        }

    async def upload_attachment(
        self,
        item_key: str,
        file_path: str,
        title: str | None = None,
    ) -> dict[str, Any]:
        return await self.upload_pdf(
            item_key=item_key,
            file_path=file_path,
            title=title,
        )

    async def upload_pdf(
        self,
        item_key: str,
        file_path: str,
        title: str | None = None,
    ) -> dict[str, Any]:
        path = Path(file_path).expanduser()
        if not path.exists():
            raise FileNotFoundError(f"PDF file not found: {path}")
        if not path.is_file():
            raise ValueError(f"Path is not a file: {path}")
        if path.suffix.lower() != ".pdf":
            raise ValueError(f"Only PDF files are supported: {path}")

        resolved_path = str(path.resolve())
        upload_result = await self.data_service.item_service.upload_attachment(
            parent_key=item_key,
            file_path=resolved_path,
            title=title,
        )

        attachment_keys = self._extract_attachment_keys(upload_result)
        success = False
        if isinstance(upload_result, dict):
            if "successful" in upload_result:
                success = len(attachment_keys) > 0
            elif upload_result.get("success") is True:
                success = True
            else:
                success = len(attachment_keys) > 0

        return {
            "success": success,
            "item_key": item_key,
            "file_path": resolved_path,
            "title": title or path.name,
            "attachment_keys": attachment_keys,
            "result": upload_result,
        }

    @staticmethod
    def _extract_attachment_keys(upload_result: Any) -> list[str]:
        if not isinstance(upload_result, dict):
            return []
        successful = upload_result.get("successful")
        if not isinstance(successful, dict):
            return []

        keys: list[str] = []
        for value in successful.values():
            if isinstance(value, str) and value:
                keys.append(value)
                continue
            if not isinstance(value, dict):
                continue
            key = value.get("key")
            if not key and isinstance(value.get("data"), dict):
                key = value["data"].get("key")
            if key:
                keys.append(str(key))
        return keys

    async def delete_pdf(self, item_key: str) -> dict[str, Any]:
        result = await self.data_service.delete_item(item_key)
        return {"deleted": True, "item_key": item_key, "result": result}

    async def search_pdfs(self, query: str, limit: int, offset: int) -> dict[str, Any]:
        candidates = await self.data_service.search_items(
            query,
            limit=max(limit * 2, 50),
            offset=0,
            qmode="everything",
        )
        query_lower = query.lower()
        hits: list[dict[str, Any]] = []

        for item in candidates:
            try:
                attachments = await self.data_service.get_item_children(
                    item_key=item.key,
                    item_type="attachment",
                )
            except Exception:
                continue

            for attachment in attachments:
                data = attachment.get("data", {})
                content_type = data.get("contentType", "")
                if content_type != "application/pdf":
                    continue

                title = str(data.get("title", ""))
                filename = str(data.get("filename", ""))
                if query_lower not in f"{title}\n{filename}\n{item.title}".lower():
                    continue

                hits.append(
                    {
                        "item_key": item.key,
                        "item_title": item.title,
                        "attachment_key": data.get("key", ""),
                        "attachment_title": title,
                        "filename": filename,
                        "content_type": content_type,
                    }
                )

        total = len(hits)
        sliced = hits[offset : offset + limit]
        return {
            "query": query,
            "total": total,
            "count": len(sliced),
            "results": sliced,
        }

    # -------------------- Collection operations --------------------

    async def list_collections(self) -> dict[str, Any]:
        collections = await self.data_service.get_collections()
        return {"count": len(collections), "collections": collections}

    async def find_collections(self, name: str, exact: bool = False) -> dict[str, Any]:
        matches = await self.data_service.find_collection_by_name(
            name, exact_match=exact
        )
        return {"count": len(matches), "collections": matches}

    async def create_collection(
        self,
        name: str,
        parent_key: str | None = None,
    ) -> dict[str, Any]:
        return await self.data_service.create_collection(name, parent_key=parent_key)

    async def rename_collection(self, collection_key: str, name: str) -> dict[str, Any]:
        await self.data_service.update_collection(collection_key, name=name)
        return {"updated": True, "collection_key": collection_key, "name": name}

    async def move_collection(
        self,
        collection_key: str,
        parent_key: str | None,
    ) -> dict[str, Any]:
        await self.data_service.update_collection(collection_key, parent_key=parent_key)
        return {
            "updated": True,
            "collection_key": collection_key,
            "parent_key": parent_key,
        }

    async def delete_collection(self, collection_key: str) -> dict[str, Any]:
        await self.data_service.delete_collection(collection_key)
        return {"deleted": True, "collection_key": collection_key}

    async def delete_empty_collections(
        self,
        dry_run: bool = True,
        limit: int | None = None,
    ) -> dict[str, Any]:
        collections = await self.data_service.get_collections()
        scanned = 0
        empty: list[dict[str, Any]] = []
        scan_errors: list[dict[str, str]] = []

        for collection in collections:
            if limit and len(empty) >= limit:
                break

            key = collection.get("key", "")
            data = collection.get("data", {})
            name = data.get("name", collection.get("name", "Unknown"))
            scanned += 1

            try:
                items = await self.data_service.get_collection_items(
                    collection_key=key,
                    limit=1,
                    start=0,
                )
            except Exception as exc:
                scan_errors.append({"collection_key": key, "error": str(exc)})
                continue

            if not items:
                empty.append({"collection_key": key, "name": name})

        if dry_run:
            return {
                "dry_run": True,
                "total_collections_scanned": scanned,
                "empty_collections_found": len(empty),
                "empty_collections": empty,
                "scan_errors": scan_errors,
            }

        deleted = 0
        failed = 0
        failures: list[dict[str, str]] = []
        for entry in empty:
            collection_key = entry["collection_key"]
            try:
                await self.data_service.delete_collection(collection_key)
                deleted += 1
            except Exception as exc:
                failed += 1
                failures.append(
                    {
                        "collection_key": collection_key,
                        "error": str(exc),
                    }
                )

        return {
            "dry_run": False,
            "total_collections_scanned": scanned,
            "empty_collections_found": len(empty),
            "deleted": deleted,
            "failed": failed,
            "failures": failures,
            "scan_errors": scan_errors,
        }

    async def list_collection_items(
        self,
        collection_key: str,
        limit: int,
        offset: int,
    ) -> dict[str, Any]:
        results = await self.data_service.get_collection_items(
            collection_key,
            limit=limit,
            start=offset,
        )
        return {"count": len(results), "items": [item.model_dump() for item in results]}
