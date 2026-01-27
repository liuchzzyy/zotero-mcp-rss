"""
Better BibTeX JSON-RPC client.

Provides access to Zotero via the Better BibTeX plugin's JSON-RPC API
for citation keys, BibTeX export, and annotations.
"""

import json
import logging
from typing import Any

import requests

logger = logging.getLogger(__name__)

# Better BibTeX translator IDs
TRANSLATOR_BIBTEX = "ca65189f-8815-4afe-8c8b-8c7c15f0edca"
TRANSLATOR_CSL_JSON = "36a3b0b5-bad0-4a04-b79b-441c7cef77db"


class BetterBibTeXClient:
    """
    Client for Better BibTeX JSON-RPC API.

    Requires Zotero to be running with Better BibTeX plugin installed.
    """

    def __init__(
        self,
        port: int = 23119,
        timeout: int = 30,
    ):
        """
        Initialize Better BibTeX client.

        Args:
            port: Zotero connector port (23119 for Zotero, 24119 for Juris-M)
            timeout: Request timeout in seconds
        """
        self.port = port
        self.timeout = timeout
        self.base_url = f"http://127.0.0.1:{port}/better-bibtex/json-rpc"
        self.headers = {
            "Content-Type": "application/json",
            "Accept": "application/json",
            "User-Agent": "python/zotero-mcp",
        }

    def _make_request(
        self,
        method: str,
        params: list[Any] | None = None,
    ) -> Any:
        """
        Make a JSON-RPC request.

        Args:
            method: RPC method name
            params: Method parameters

        Returns:
            Result from the RPC call

        Raises:
            ConnectionError: If Zotero is not running
            Exception: If RPC call fails
        """
        payload = {
            "jsonrpc": "2.0",
            "method": method,
            "params": params or [],
            "id": 1,
        }

        try:
            response = requests.post(
                self.base_url,
                headers=self.headers,
                data=json.dumps(payload),
                timeout=self.timeout,
            )
            response.raise_for_status()
            data = response.json()

            if "error" in data:
                error = data["error"]
                msg = error.get("message", "Unknown error")
                error_data = error.get("data", "")
                if error_data:
                    msg = f"{msg}: {error_data}"
                raise Exception(f"RPC error: {msg}")

            return data.get("result")

        except requests.exceptions.ConnectionError as e:
            raise ConnectionError(
                "Cannot connect to Zotero. Is Zotero running with Better BibTeX?"
            ) from e
        except requests.exceptions.Timeout as e:
            raise ConnectionError("Zotero request timed out") from e

    def is_available(self) -> bool:
        """
        Check if Zotero is running and Better BibTeX is accessible.

        Returns:
            True if available, False otherwise
        """
        try:
            response = requests.get(
                f"http://127.0.0.1:{self.port}/better-bibtex/cayw?probe=true",
                headers=self.headers,
                timeout=5,
            )
            return response.text == "ready"
        except Exception:
            return False

    # -------------------- Citation Key Methods --------------------

    def search_by_citekey(
        self,
        query: str,
        limit: int = 10,
    ) -> list[dict[str, Any]]:
        """
        Search items by citation key or query.

        Args:
            query: Search query
            limit: Maximum results

        Returns:
            List of matching items with citekeys
        """
        try:
            results = self._make_request("item.search", [query])
            if not results:
                return []

            items = []
            for item in results[:limit]:
                if item.get("citekey"):
                    items.append(
                        {
                            "citekey": item["citekey"],
                            "title": item.get("title", "Untitled"),
                            "creators": item.get("creators", []),
                            "year": item.get("year"),
                            "library_id": item.get("libraryID"),
                            "item_key": item.get("itemKey"),
                        }
                    )

            return items

        except Exception as e:
            logger.warning(f"Citation key search failed: {e}")
            return []

    def get_citekey(
        self,
        item_key: str,
        library_id: int = 1,
    ) -> str | None:
        """
        Get the citation key for an item.

        Args:
            item_key: Zotero item key
            library_id: Library ID

        Returns:
            Citation key if found
        """
        try:
            item_keys = [f"{library_id}:{item_key}"]
            result = self._make_request("item.citationkey", [item_keys])

            if result:
                full_key = f"{library_id}:{item_key}"
                return result.get(full_key)

            return None

        except Exception as e:
            logger.warning(f"Failed to get citekey: {e}")
            return None

    # -------------------- Export Methods --------------------

    def export_bibtex(
        self,
        item_key: str,
        library_id: int = 1,
    ) -> str:
        """
        Export BibTeX for an item.

        Args:
            item_key: Zotero item key
            library_id: Library ID

        Returns:
            BibTeX string
        """
        try:
            # Get citation key first
            citekey = self.get_citekey(item_key, library_id)
            if not citekey:
                raise ValueError(f"No citation key for item: {item_key}")

            # Export using citation key
            result = self._make_request(
                "item.export",
                [[citekey], TRANSLATOR_BIBTEX],
            )

            if isinstance(result, str):
                return result
            elif isinstance(result, list) and result:
                return str(result[0]) if result[0] else ""
            elif isinstance(result, dict) and "bibtex" in result:
                return result["bibtex"]

            return str(result) if result else ""

        except Exception as e:
            logger.warning(f"BibTeX export failed: {e}")
            return ""

    def export_csl_json(
        self,
        citekey: str,
        library_id: int | None = None,
    ) -> dict[str, Any] | None:
        """
        Export item as CSL-JSON.

        Args:
            citekey: Citation key
            library_id: Optional library ID

        Returns:
            CSL-JSON data if successful
        """
        try:
            params = [[citekey], TRANSLATOR_CSL_JSON]
            if library_id is not None:
                params.append(library_id)  # type: ignore

            result = self._make_request("item.export", params)

            if isinstance(result, list) and len(result) > 2:
                try:
                    data = json.loads(result[2])
                    items = data.get("items", [])
                    return items[0] if items else None
                except (json.JSONDecodeError, IndexError):
                    pass

            if isinstance(result, dict) and "items" in result:
                items = result["items"]
                return items[0] if items else None

            return None

        except Exception as e:
            logger.warning(f"CSL-JSON export failed: {e}")
            return None

    # -------------------- Annotation Methods --------------------

    def get_attachments(
        self,
        citekey: str,
        library_id: int = 1,
    ) -> list[dict[str, Any]]:
        """
        Get attachments for an item.

        Args:
            citekey: Citation key
            library_id: Library ID

        Returns:
            List of attachment data
        """
        try:
            return (
                self._make_request(
                    "item.attachments",
                    [citekey, library_id],
                )
                or []
            )
        except Exception as e:
            logger.warning(f"Failed to get attachments: {e}")
            return []

    def get_annotations(
        self,
        citekey: str,
        library_id: int = 1,
    ) -> list[dict[str, Any]]:
        """
        Get all annotations for an item's attachments.

        Args:
            citekey: Citation key
            library_id: Library ID

        Returns:
            List of processed annotations
        """
        annotations = []

        attachments = self.get_attachments(citekey, library_id)
        for attachment in attachments:
            attachment_annotations = attachment.get("annotations", [])
            for ann in attachment_annotations:
                processed = self._process_annotation(ann, attachment)
                if processed:
                    annotations.append(processed)

        return annotations

    def _process_annotation(
        self,
        annotation: dict[str, Any],
        attachment: dict[str, Any],
    ) -> dict[str, Any] | None:
        """
        Process a raw annotation into a structured format.

        Args:
            annotation: Raw annotation data
            attachment: Parent attachment data

        Returns:
            Processed annotation dict
        """
        try:
            ann_type = annotation.get("annotationType", "unknown")
            text = annotation.get("annotationText", "")
            comment = annotation.get("annotationComment", "")
            color = annotation.get("annotationColor", "")
            page_label = annotation.get("annotationPageLabel", "1")

            # Parse position data
            position = annotation.get("annotationPosition", {})
            if isinstance(position, str):
                try:
                    position = json.loads(position)
                except json.JSONDecodeError:
                    position = {}

            page = 1
            if isinstance(position, dict) and "pageIndex" in position:
                page = position["pageIndex"] + 1

            return {
                "id": annotation.get("key", ""),
                "type": ann_type,
                "text": text,
                "comment": comment,
                "color": color,
                "page": page,
                "page_label": page_label,
                "date_modified": annotation.get("dateModified", ""),
                "attachment_key": attachment.get("itemKey", ""),
                "attachment_title": attachment.get("title", ""),
            }

        except Exception as e:
            logger.warning(f"Failed to process annotation: {e}")
            return None


def get_better_bibtex_client(port: int = 23119) -> BetterBibTeXClient | None:
    """
    Get a Better BibTeX client if available.

    Args:
        port: Zotero connector port

    Returns:
        BetterBibTeXClient if Zotero is running, None otherwise
    """
    client = BetterBibTeXClient(port=port)
    if client.is_available():
        return client
    return None
