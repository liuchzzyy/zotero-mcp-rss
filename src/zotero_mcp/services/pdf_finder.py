"""
Find PDFs and supporting information for Zotero items or external references.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import re
import tempfile
from pathlib import Path
from typing import Any
from urllib.parse import urljoin, urlparse

import httpx
from bs4 import BeautifulSoup

from zotero_mcp.models.common.responses import FileLink
from zotero_mcp.services.zotero.metadata_service import MetadataService
from zotero_mcp.utils.formatting.helpers import DOI_PATTERN

logger = logging.getLogger(__name__)

_DEFAULT_SUPPORTING_KEYWORDS = [
    "supplement",
    "supplementary",
    "supporting information",
    "supporting info",
    "supporting",
    "supp info",
    "supplemental",
    "appendix",
    "additional file",
    "additional files",
    "data availability",
    "dataset",
]

_DEFAULT_SUPPORTING_EXTENSIONS = {
    ".pdf",
    ".zip",
    ".rar",
    ".7z",
    ".tar",
    ".gz",
    ".csv",
    ".tsv",
    ".xlsx",
    ".xls",
    ".docx",
    ".doc",
    ".pptx",
    ".ppt",
}

_DEFAULT_MAX_PDF_DOWNLOADS = 1
_DEFAULT_MAX_SUPPLEMENTARY_DOWNLOADS = 5
_DEFAULT_MAX_SUPPLEMENTARY_LINKS = 5


def _normalize_doi(value: str | None) -> str | None:
    if not value:
        return None
    value = value.strip()
    value = re.sub(r"^https?://doi\.org/", "", value, flags=re.IGNORECASE)
    value = re.sub(r"^doi:\s*", "", value, flags=re.IGNORECASE)
    return value.strip() or None


def _extract_doi_from_text(value: str | None) -> str | None:
    if not value:
        return None
    match = DOI_PATTERN.search(value)
    if not match:
        return None
    return _normalize_doi(match.group(0))


def _looks_like_pdf_url(value: str | None) -> bool:
    if not value:
        return False
    parsed = urlparse(value)
    path = parsed.path.lower()
    return path.endswith(".pdf") or "pdf" in parsed.query.lower()


def _is_supporting_label(value: str | None) -> bool:
    if not value:
        return False
    text = value.lower()
    return any(keyword in text for keyword in _get_supporting_keywords())


def _has_supporting_extension(value: str | None) -> bool:
    if not value:
        return False
    path = urlparse(value).path.lower()
    for ext in _get_supporting_extensions():
        if path.endswith(ext):
            return True
    return False


def _ensure_scheme(url: str) -> str:
    if url.startswith("http://") or url.startswith("https://"):
        return url
    return f"https://{url}"


def _parse_env_list(value: str | None) -> list[str]:
    if not value:
        return []
    raw = value.strip()
    if not raw:
        return []
    if raw.startswith("["):
        try:
            data = json.loads(raw)
            if isinstance(data, list):
                return [str(item).strip() for item in data if str(item).strip()]
        except json.JSONDecodeError:
            return []
    parts = re.split(r"[;,]", raw)
    return [part.strip() for part in parts if part.strip()]


def _get_supporting_keywords() -> list[str]:
    env_value = os.getenv("ZOTERO_PDF_SI_KEYWORDS")
    keywords = _parse_env_list(env_value)
    return keywords or _DEFAULT_SUPPORTING_KEYWORDS


def _get_supporting_extensions() -> set[str]:
    env_value = os.getenv("ZOTERO_PDF_SI_EXTENSIONS")
    extensions = _parse_env_list(env_value)
    if not extensions:
        return set(_DEFAULT_SUPPORTING_EXTENSIONS)
    normalized = set()
    for ext in extensions:
        ext = ext.lower().strip()
        if not ext:
            continue
        if not ext.startswith("."):
            ext = f".{ext}"
        normalized.add(ext)
    return normalized


def _sanitize_filename(value: str, fallback: str = "download") -> str:
    name = value.strip() if value else fallback
    name = re.sub(r"[^\w\-. ]+", "_", name)
    name = re.sub(r"\s+", " ", name).strip()
    return name or fallback


def _get_download_timeout() -> float:
    raw = os.getenv("ZOTERO_PDF_DOWNLOAD_TIMEOUT", "60")
    try:
        value = float(raw)
        return value if value > 0 else 60.0
    except ValueError:
        return 60.0


def _get_download_retries() -> int:
    raw = os.getenv("ZOTERO_PDF_DOWNLOAD_RETRIES", "2")
    try:
        value = int(raw)
        return max(value, 0)
    except ValueError:
        return 2


def _get_download_backoff() -> float:
    raw = os.getenv("ZOTERO_PDF_DOWNLOAD_RETRY_BACKOFF", "1.5")
    try:
        value = float(raw)
        return value if value > 0 else 1.5
    except ValueError:
        return 1.5


def _get_download_proxy() -> str | None:
    return os.getenv("ZOTERO_PDF_PROXY")


class PdfSiFinder:
    """Locate PDFs and supporting information from Zotero and external sources."""

    def __init__(self, metadata_service: MetadataService | None = None):
        self.metadata_service = metadata_service or MetadataService()

    async def find(
        self,
        *,
        item_key: str | None,
        doi: str | None,
        title: str | None,
        url: str | None,
        include_scihub: bool,
        scihub_base_url: str | None,
        download_pdfs: bool,
        download_supplementary: bool,
        attach_to_zotero: bool,
        dry_run: bool,
        data_service: Any,
    ) -> tuple[list[FileLink], list[FileLink], dict[str, Any], dict[str, Any]]:
        pdfs: list[FileLink] = []
        supplementary: list[FileLink] = []
        warnings: list[str] = []
        sources: set[str] = set()

        resolved_item_key = item_key.strip().upper() if item_key else None
        resolved_doi = _normalize_doi(doi) or _extract_doi_from_text(url)
        resolved_title = title
        resolved_url = url

        if resolved_url and _looks_like_pdf_url(resolved_url):
            pdfs.append(
                FileLink(
                    url=resolved_url,
                    title=resolved_title,
                    filename=None,
                    content_type="application/pdf",
                    source="input_url",
                    item_key=resolved_item_key,
                )
            )
            sources.add("input_url")

        if resolved_item_key:
            try:
                item = await data_service.get_item(resolved_item_key)
                data = item.get("data", {}) if isinstance(item, dict) else {}
                resolved_title = resolved_title or data.get("title")
                resolved_url = resolved_url or data.get("url")
                resolved_doi = resolved_doi or _normalize_doi(data.get("DOI"))
            except Exception as exc:
                warnings.append(f"Failed to fetch item {resolved_item_key}: {exc}")

            try:
                children = await data_service.get_item_children(resolved_item_key)
            except Exception as exc:
                warnings.append(
                    f"Failed to fetch attachments for {resolved_item_key}: {exc}"
                )
                children = []

            for child in children:
                child_data = child.get("data", {})
                if child_data.get("itemType") != "attachment":
                    continue
                title_value = (
                    child_data.get("title")
                    or child_data.get("filename")
                    or "Attachment"
                )
                filename = child_data.get("filename")
                content_type = child_data.get("contentType")
                link_mode = child_data.get("linkMode")
                attachment_url = child_data.get("url")
                path_value = child_data.get("path")
                attachment_key = child_data.get("key")
                is_pdf = (
                    content_type == "application/pdf"
                    or (filename and filename.lower().endswith(".pdf"))
                    or _looks_like_pdf_url(attachment_url)
                )
                is_supporting = _is_supporting_label(title_value) or _is_supporting_label(
                    filename
                ) or _is_supporting_label(attachment_url)
                is_supporting = is_supporting or _has_supporting_extension(
                    attachment_url or filename
                )

                link = FileLink(
                    url=attachment_url,
                    title=title_value,
                    filename=filename,
                    content_type=content_type,
                    source="zotero_attachment",
                    item_key=resolved_item_key,
                    attachment_key=attachment_key,
                    link_mode=link_mode,
                    path=path_value,
                )

                if is_pdf and not is_supporting:
                    pdfs.append(link)
                    sources.add("zotero_attachment")
                elif is_supporting:
                    supplementary.append(link)
                    sources.add("zotero_attachment")

        if not pdfs:
            metadata = await self.metadata_service.lookup_metadata(
                title=resolved_title,
                url=resolved_url,
                doi=resolved_doi,
            )
            if metadata:
                sources.add(metadata.source or "metadata")
                resolved_title = resolved_title or metadata.title
                resolved_url = resolved_url or metadata.url
                resolved_doi = resolved_doi or metadata.doi
                if metadata.pdf_url:
                    pdfs.append(
                        FileLink(
                            url=metadata.pdf_url,
                            title=metadata.title or resolved_title,
                            filename=None,
                            content_type="application/pdf",
                            source=metadata.source or "metadata",
                            item_key=resolved_item_key,
                        )
                    )

        if include_scihub:
            scihub_base = (
                scihub_base_url
                or os.getenv("ZOTERO_SCIHUB_BASE_URL")
                or os.getenv("ZOTERO_SCIHUB_URL")
                or os.getenv("SCIHUB_BASE_URL")
                or os.getenv("SCIHUB_URL")
            )
            if resolved_doi and scihub_base:
                scihub_url = (
                    f"{_ensure_scheme(scihub_base).rstrip('/')}/{resolved_doi}"
                )
                pdfs.append(
                    FileLink(
                        url=scihub_url,
                        title=resolved_title,
                        filename=None,
                        content_type="application/pdf",
                        source="scihub",
                        item_key=resolved_item_key,
                    )
                )
                sources.add("scihub")
            elif resolved_doi and not scihub_base:
                warnings.append("Sci-Hub base URL not configured.")

        landing_url = resolved_url or (
            f"https://doi.org/{resolved_doi}" if resolved_doi else None
        )
        if landing_url:
            scraped = await self._scrape_supporting_links(
                landing_url, max_items=_DEFAULT_MAX_SUPPLEMENTARY_LINKS
            )
            if scraped:
                supplementary.extend(scraped)
                sources.add("landing_page")

        pdfs = self._dedupe_links(pdfs)
        supplementary = self._dedupe_links(supplementary)

        downloads_meta = {
            "downloaded": [],
            "attached": [],
            "download_errors": [],
            "attach_errors": [],
        }

        if download_pdfs or download_supplementary:
            if attach_to_zotero and not resolved_item_key:
                warnings.append("Attachment upload requires item_key.")
            if download_pdfs and pdfs:
                result = await self._download_and_attach(
                    links=pdfs,
                    item_key=resolved_item_key,
                    data_service=data_service,
                    max_files=_DEFAULT_MAX_PDF_DOWNLOADS,
                    kind="pdf",
                    dry_run=dry_run,
                    attach_to_zotero=attach_to_zotero,
                )
                downloads_meta["downloaded"].extend(result["downloaded"])
                downloads_meta["attached"].extend(result["attached"])
                downloads_meta["download_errors"].extend(result["download_errors"])
                downloads_meta["attach_errors"].extend(result["attach_errors"])

            if download_supplementary and supplementary:
                result = await self._download_and_attach(
                    links=supplementary,
                    item_key=resolved_item_key,
                    data_service=data_service,
                    max_files=_DEFAULT_MAX_SUPPLEMENTARY_DOWNLOADS,
                    kind="supplementary",
                    dry_run=dry_run,
                    attach_to_zotero=attach_to_zotero,
                )
                downloads_meta["downloaded"].extend(result["downloaded"])
                downloads_meta["attached"].extend(result["attached"])
                downloads_meta["download_errors"].extend(result["download_errors"])
                downloads_meta["attach_errors"].extend(result["attach_errors"])

        meta = {
            "item_key": resolved_item_key,
            "doi": resolved_doi,
            "title": resolved_title,
            "url": resolved_url,
            "warnings": warnings,
            "sources": sorted(sources),
        }
        return pdfs, supplementary, meta, downloads_meta

    async def _scrape_supporting_links(
        self, landing_url: str, max_items: int = 10
    ) -> list[FileLink]:
        try:
            async with httpx.AsyncClient(timeout=20.0) as client:
                response = await client.get(landing_url, follow_redirects=True)
                response.raise_for_status()
        except Exception as exc:
            logger.debug("Failed to fetch landing page %s: %s", landing_url, exc)
            return []

        soup = BeautifulSoup(response.text, "html.parser")
        found: list[FileLink] = []

        for anchor in soup.find_all("a", href=True):
            if len(found) >= max_items:
                break
            href = anchor.get("href", "").strip()
            if not href or href.startswith("#"):
                continue
            label = anchor.get_text(" ", strip=True)
            full_url = urljoin(str(response.url), href)
            if not (
                _is_supporting_label(label)
                or _is_supporting_label(href)
                or _has_supporting_extension(full_url)
            ):
                continue
            found.append(
                FileLink(
                    url=full_url,
                    title=label or "Supporting information",
                    filename=None,
                    content_type=None,
                    source="landing_page",
                    item_key=None,
                )
            )

        return found

    def _dedupe_links(self, links: list[FileLink]) -> list[FileLink]:
        seen: set[str] = set()
        unique: list[FileLink] = []
        for link in links:
            key = link.url or f"{link.title}:{link.filename}"
            if key in seen:
                continue
            seen.add(key)
            unique.append(link)
        return unique

    async def _download_and_attach(
        self,
        *,
        links: list[FileLink],
        item_key: str | None,
        data_service: Any,
        max_files: int,
        kind: str,
        dry_run: bool,
        attach_to_zotero: bool,
    ) -> dict[str, list]:
        downloaded: list[FileLink] = []
        attached: list[FileLink] = []
        download_errors: list[str] = []
        attach_errors: list[str] = []

        candidates = [
            link
            for link in links
            if link.url and link.source != "zotero_attachment"
        ]

        if kind == "supplementary":
            candidates = [
                link
                for link in candidates
                if link.url and _has_supporting_extension(link.url)
            ]

        if max_files <= 0:
            return {
                "downloaded": downloaded,
                "attached": attached,
                "download_errors": download_errors,
                "attach_errors": attach_errors,
            }

        download_dir = os.getenv("ZOTERO_PDF_DOWNLOAD_DIR")
        keep_files = bool(download_dir)
        base_dir = Path(download_dir) if download_dir else None
        if base_dir:
            base_dir.mkdir(parents=True, exist_ok=True)

        temp_dir: tempfile.TemporaryDirectory[str] | None = None
        if base_dir is None:
            temp_dir = tempfile.TemporaryDirectory()
            base_dir = Path(temp_dir.name)

        timeout = _get_download_timeout()
        retries = _get_download_retries()
        backoff = _get_download_backoff()
        proxy = _get_download_proxy()

        client_kwargs = {"timeout": timeout, "follow_redirects": True}
        if proxy:
            client_kwargs["proxies"] = proxy

        async with httpx.AsyncClient(**client_kwargs) as client:
            for link in candidates[:max_files]:
                attempt = 0
                downloaded_file = None
                last_error: Exception | None = None
                while attempt <= retries and downloaded_file is None:
                    try:
                        downloaded_file = await self._download_file(
                            client=client,
                            link=link,
                            target_dir=base_dir,
                            kind=kind,
                        )
                    except Exception as exc:
                        last_error = exc
                    if downloaded_file is None:
                        attempt += 1
                        if attempt <= retries:
                            await asyncio.sleep(backoff * (2 ** (attempt - 1)))

                if downloaded_file is None:
                    error_msg = (
                        f"Failed to download {link.url}: {last_error}"
                        if last_error
                        else f"Failed to download {link.url}"
                    )
                    download_errors.append(error_msg)
                    continue

                if downloaded_file is None:
                    download_errors.append(
                        f"Failed to download {link.url}: no file"
                    )
                    continue

                downloaded_link = FileLink(
                    url=link.url,
                    title=link.title,
                    filename=downloaded_file.name,
                    content_type=link.content_type,
                    source=link.source,
                    item_key=item_key,
                    path=str(downloaded_file),
                )
                downloaded.append(downloaded_link)

                if dry_run or not attach_to_zotero or not item_key:
                    continue

                try:
                    result = await data_service.item_service.upload_attachment(
                        parent_key=item_key,
                        file_path=str(downloaded_file),
                        title=link.title or downloaded_file.name,
                    )
                    attachment_key = None
                    for item in result.get("success", []):
                        attachment_key = item.get("key")
                        break
                    attached.append(
                        FileLink(
                            url=link.url,
                            title=link.title or downloaded_file.name,
                            filename=downloaded_file.name,
                            content_type=link.content_type,
                            source="uploaded",
                            item_key=item_key,
                            attachment_key=attachment_key,
                            path=str(downloaded_file) if keep_files else None,
                        )
                    )
                except Exception as exc:
                    attach_errors.append(
                        f"Failed to attach {downloaded_file.name}: {exc}"
                    )

        if temp_dir and not keep_files:
            temp_dir.cleanup()

        return {
            "downloaded": downloaded,
            "attached": attached,
            "download_errors": download_errors,
            "attach_errors": attach_errors,
        }

    async def _download_file(
        self,
        *,
        client: httpx.AsyncClient,
        link: FileLink,
        target_dir: Path,
        kind: str,
    ) -> Path | None:
        response = await client.get(link.url)
        response.raise_for_status()
        content_type = response.headers.get("content-type", "").lower()

        if "text/html" in content_type and kind == "pdf":
            resolved = self._extract_pdf_url_from_html(
                response.text, str(response.url)
            )
            if resolved and resolved != link.url:
                response = await client.get(resolved)
                response.raise_for_status()
                content_type = response.headers.get("content-type", "").lower()

        if kind == "pdf":
            url_path = urlparse(str(response.url)).path.lower()
            if "pdf" not in content_type and not url_path.endswith(".pdf"):
                return None

        filename = self._resolve_filename(
            response=response,
            link=link,
            content_type=content_type,
            kind=kind,
        )
        target_path = self._unique_path(target_dir / filename)

        with target_path.open("wb") as handle:
            async for chunk in response.aiter_bytes():
                handle.write(chunk)

        return target_path

    def _extract_pdf_url_from_html(self, html_text: str, base_url: str) -> str | None:
        soup = BeautifulSoup(html_text, "html.parser")
        for selector in ["iframe", "embed"]:
            tag = soup.find(selector)
            if tag and tag.get("src"):
                src = tag.get("src")
                if src and ".pdf" in src:
                    return urljoin(base_url, src)
        for anchor in soup.find_all("a", href=True):
            href = anchor.get("href")
            if href and ".pdf" in href:
                return urljoin(base_url, href)
        return None

    def _resolve_filename(
        self,
        *,
        response: httpx.Response,
        link: FileLink,
        content_type: str,
        kind: str,
    ) -> str:
        disposition = response.headers.get("content-disposition", "")
        match = re.search(r'filename="?([^";]+)"?', disposition)
        if match:
            return _sanitize_filename(match.group(1))

        url_path = urlparse(str(response.url)).path
        if url_path:
            name = Path(url_path).name
            if name:
                return _sanitize_filename(name)

        title = link.title or link.filename or kind
        ext = ".pdf" if kind == "pdf" else ""
        if kind == "supplementary" and link.url:
            path = urlparse(link.url).path
            ext = Path(path).suffix or ext
        if content_type and kind == "pdf" and not ext:
            ext = ".pdf"
        return _sanitize_filename(title) + ext

    def _unique_path(self, path: Path) -> Path:
        if not path.exists():
            return path
        stem = path.stem
        suffix = path.suffix
        for idx in range(1, 1000):
            candidate = path.with_name(f"{stem}-{idx}{suffix}")
            if not candidate.exists():
                return candidate
        return path.with_name(f"{stem}-{os.getpid()}{suffix}")
