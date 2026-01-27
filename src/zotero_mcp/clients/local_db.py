"""
Local Zotero database client.

Provides direct SQLite access to Zotero's local database for faster
operations when running in local mode.
"""

from collections.abc import Iterator
from dataclasses import dataclass, field
import logging
import os
from pathlib import Path
import platform
import sqlite3
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class ZoteroItem:
    """Represents a Zotero item with text content."""

    item_id: int
    key: str
    item_type_id: int
    item_type: str | None = None
    doi: str | None = None
    title: str | None = None
    abstract: str | None = None
    creators: str | None = None
    fulltext: str | None = None
    fulltext_source: str | None = None
    notes: str | None = None
    extra: str | None = None
    date_added: str | None = None
    date_modified: str | None = None
    tags: list[str] = field(default_factory=list)

    def get_searchable_text(self, max_fulltext: int = 5000) -> str:
        """
        Combine all text fields into a searchable string.

        Args:
            max_fulltext: Maximum characters from fulltext to include

        Returns:
            Combined text for indexing
        """
        parts = []

        if self.title:
            parts.append(f"Title: {self.title}")

        if self.creators:
            parts.append(f"Authors: {self.creators}")

        if self.abstract:
            parts.append(f"Abstract: {self.abstract}")

        if self.extra:
            parts.append(f"Extra: {self.extra}")

        if self.notes:
            parts.append(f"Notes: {self.notes}")

        if self.fulltext:
            truncated = (
                self.fulltext[:max_fulltext] + "..."
                if len(self.fulltext) > max_fulltext
                else self.fulltext
            )
            parts.append(f"Content: {truncated}")

        return "\n\n".join(parts)


class LocalDatabaseClient:
    """
    Direct SQLite client for Zotero's local database.

    Provides fast read-only access to item metadata and content.
    """

    def __init__(
        self,
        db_path: str | Path | None = None,
        pdf_max_pages: int = 10,
    ):
        """
        Initialize the database client.

        Args:
            db_path: Path to zotero.sqlite (auto-detected if None)
            pdf_max_pages: Maximum pages to extract from PDFs
        """
        self.db_path = Path(db_path) if db_path else self._find_database()
        self.pdf_max_pages = pdf_max_pages
        self._connection: sqlite3.Connection | None = None

        # Suppress noisy PDF warnings
        logging.getLogger("pdfminer").setLevel(logging.ERROR)

    @staticmethod
    def _find_database() -> Path:
        """
        Auto-detect Zotero database location.

        Returns:
            Path to zotero.sqlite

        Raises:
            FileNotFoundError: If database not found
        """
        system = platform.system()

        # Check common locations based on OS
        candidates: list[Path] = []

        if system == "Darwin":  # macOS
            candidates.append(Path.home() / "Zotero" / "zotero.sqlite")
        elif system == "Windows":
            candidates.append(Path.home() / "Zotero" / "zotero.sqlite")
            # Legacy Windows path
            username = os.getenv("USERNAME", "")
            if username:
                candidates.append(
                    Path(os.path.expanduser("~/Documents and Settings"))
                    / username
                    / "Zotero"
                    / "zotero.sqlite"
                )
        else:  # Linux
            candidates.append(Path.home() / "Zotero" / "zotero.sqlite")

        for path in candidates:
            if path.exists():
                return path

        raise FileNotFoundError(
            f"Zotero database not found. Checked: {candidates}. "
            "Ensure Zotero is installed and has been run at least once."
        )

    @property
    def storage_dir(self) -> Path:
        """Get the Zotero storage directory."""
        return self.db_path.parent / "storage"

    def _get_connection(self) -> sqlite3.Connection:
        """Get or create database connection (read-only)."""
        if self._connection is None:
            uri = f"file:{self.db_path}?mode=ro"
            self._connection = sqlite3.connect(uri, uri=True)
            self._connection.row_factory = sqlite3.Row
        return self._connection

    def close(self) -> None:
        """Close database connection."""
        if self._connection:
            self._connection.close()
            self._connection = None

    def __enter__(self) -> "LocalDatabaseClient":
        return self

    def __exit__(self, *args: Any) -> None:
        self.close()

    # -------------------- Query Methods --------------------

    def get_item_count(self) -> int:
        """Get total count of library items (excluding attachments/notes)."""
        conn = self._get_connection()
        cursor = conn.execute("""
            SELECT COUNT(*)
            FROM items i
            JOIN itemTypes it ON i.itemTypeID = it.itemTypeID
            WHERE it.typeName NOT IN ('attachment', 'note', 'annotation')
            """)
        return cursor.fetchone()[0]

    def get_items(
        self,
        limit: int | None = None,
        include_fulltext: bool = False,
    ) -> list[ZoteroItem]:
        """
        Get all items with their metadata.

        Args:
            limit: Maximum items to return
            include_fulltext: Whether to extract full text from attachments

        Returns:
            List of ZoteroItem objects
        """
        conn = self._get_connection()

        query = """
        SELECT
            i.itemID,
            i.key,
            i.itemTypeID,
            it.typeName as item_type,
            i.dateAdded,
            i.dateModified,
            title_val.value as title,
            abstract_val.value as abstract,
            extra_val.value as extra,
            doi_val.value as doi,
            GROUP_CONCAT(n.note, ' ') as notes,
            GROUP_CONCAT(
                CASE
                    WHEN c.firstName IS NOT NULL AND c.lastName IS NOT NULL
                    THEN c.lastName || ', ' || c.firstName
                    WHEN c.lastName IS NOT NULL
                    THEN c.lastName
                    ELSE NULL
                END, '; '
            ) as creators
        FROM items i
        JOIN itemTypes it ON i.itemTypeID = it.itemTypeID

        -- Title (fieldID = 1)
        LEFT JOIN itemData title_data ON i.itemID = title_data.itemID AND title_data.fieldID = 1
        LEFT JOIN itemDataValues title_val ON title_data.valueID = title_val.valueID

        -- Abstract (fieldID = 2)
        LEFT JOIN itemData abstract_data ON i.itemID = abstract_data.itemID AND abstract_data.fieldID = 2
        LEFT JOIN itemDataValues abstract_val ON abstract_data.valueID = abstract_val.valueID

        -- Extra (fieldID = 16)
        LEFT JOIN itemData extra_data ON i.itemID = extra_data.itemID AND extra_data.fieldID = 16
        LEFT JOIN itemDataValues extra_val ON extra_data.valueID = extra_val.valueID

        -- DOI
        LEFT JOIN fields doi_f ON doi_f.fieldName = 'DOI'
        LEFT JOIN itemData doi_data ON i.itemID = doi_data.itemID AND doi_data.fieldID = doi_f.fieldID
        LEFT JOIN itemDataValues doi_val ON doi_data.valueID = doi_val.valueID

        -- Notes
        LEFT JOIN itemNotes n ON i.itemID = n.parentItemID OR i.itemID = n.itemID

        -- Creators
        LEFT JOIN itemCreators ic ON i.itemID = ic.itemID
        LEFT JOIN creators c ON ic.creatorID = c.creatorID

        WHERE it.typeName NOT IN ('attachment', 'note', 'annotation')

        GROUP BY i.itemID, i.key, i.itemTypeID, it.typeName, i.dateAdded, i.dateModified,
                 title_val.value, abstract_val.value, extra_val.value

        ORDER BY i.dateModified DESC
        """

        if limit:
            query += f" LIMIT {limit}"

        cursor = conn.execute(query)
        items = []

        for row in cursor:
            fulltext = None
            fulltext_source = None

            if include_fulltext:
                result = self._extract_fulltext(row["itemID"])
                if result:
                    fulltext, fulltext_source = result

            item = ZoteroItem(
                item_id=row["itemID"],
                key=row["key"],
                item_type_id=row["itemTypeID"],
                item_type=row["item_type"],
                doi=row["doi"],
                title=row["title"],
                abstract=row["abstract"],
                creators=row["creators"],
                fulltext=fulltext,
                fulltext_source=fulltext_source,
                notes=row["notes"],
                extra=row["extra"],
                date_added=row["dateAdded"],
                date_modified=row["dateModified"],
            )
            items.append(item)

        return items

    def get_item_by_key(self, key: str) -> ZoteroItem | None:
        """Get a specific item by its key."""
        items = self.get_items()
        for item in items:
            if item.key == key:
                return item
        return None

    def get_item_id_by_key(self, key: str) -> int | None:
        """
        Look up item ID from key using SQL query.

        Args:
            key: Item key (8-character string)

        Returns:
            Item ID or None if not found
        """
        conn = self._get_connection()
        query = "SELECT itemID FROM items WHERE key = ?"
        result = conn.execute(query, (key,)).fetchone()
        return result["itemID"] if result else None

    def get_fulltext_by_key(self, key: str) -> tuple[str, str] | None:
        """
        Extract fulltext content for an item by its key.

        This method enables direct PDF extraction even when the item
        hasn't been indexed by Zotero's fulltext index.

        Args:
            key: Item key (8-character string)

        Returns:
            Tuple of (text, source) or None if extraction fails
        """
        # Look up item ID
        item_id = self.get_item_id_by_key(key)
        if item_id is None:
            logger.warning(f"Item with key {key} not found in local database")
            return None

        # Use existing fulltext extraction logic
        try:
            result = self._extract_fulltext(item_id)
            if result:
                logger.debug(f"Extracted fulltext for {key} from {result[1]}")
            else:
                logger.debug(f"No fulltext found for {key}")
            return result
        except Exception as e:
            logger.error(f"Failed to extract fulltext for {key}: {e}")
            return None

    def search_items(
        self,
        query: str,
        limit: int = 50,
    ) -> list[ZoteroItem]:
        """
        Simple text search through items.

        Args:
            query: Search query
            limit: Maximum results

        Returns:
            Matching items
        """
        items = self.get_items()
        query_lower = query.lower()
        matches = []

        for item in items:
            text = item.get_searchable_text().lower()
            if query_lower in text:
                matches.append(item)
                if len(matches) >= limit:
                    break

        return matches

    # -------------------- Fulltext Extraction --------------------

    def _iter_attachments(
        self,
        parent_item_id: int,
    ) -> Iterator[tuple[str, str | None, str | None]]:
        """Yield (key, path, content_type) for item's attachments."""
        conn = self._get_connection()
        query = """
            SELECT ia.path, ia.contentType, att.key
            FROM itemAttachments ia
            JOIN items att ON att.itemID = ia.itemID
            WHERE ia.parentItemID = ?
        """
        for row in conn.execute(query, (parent_item_id,)):
            yield row["key"], row["path"], row["contentType"]

    def _resolve_path(
        self,
        attachment_key: str,
        zotero_path: str | None,
    ) -> Path | None:
        """Resolve Zotero path to filesystem path."""
        if not zotero_path:
            return None

        if zotero_path.startswith("storage:"):
            rel = zotero_path.split(":", 1)[1]
            parts = [p for p in rel.split("/") if p]
            return self.storage_dir / attachment_key / Path(*parts)

        return None

    def _extract_fulltext(
        self,
        item_id: int,
    ) -> tuple[str, str] | None:
        """
        Extract fulltext from best available attachment.

        Args:
            item_id: Item ID

        Returns:
            Tuple of (text, source) or None
        """
        best_pdf: Path | None = None
        best_html: Path | None = None

        for key, path, content_type in self._iter_attachments(item_id):
            resolved = self._resolve_path(key, path)
            if not resolved or not resolved.exists():
                continue

            if content_type == "application/pdf" and best_pdf is None:
                best_pdf = resolved
            elif (content_type or "").startswith("text/html") and best_html is None:
                best_html = resolved

        # Prefer PDF over HTML
        target = best_pdf or best_html
        if not target:
            return None

        text = self._extract_text(target)
        if not text:
            return None

        # Determine source type
        suffix = target.suffix.lower()
        if suffix == ".pdf":
            source = "pdf"
        elif suffix in {".html", ".htm"}:
            source = "html"
        else:
            source = "file"

        # Truncate to reasonable size
        return (text[:10000], source)

    def _extract_text(self, file_path: Path) -> str:
        """Extract text from file based on type."""
        suffix = file_path.suffix.lower()

        if suffix == ".pdf":
            return self._extract_pdf_text(file_path)
        elif suffix in {".html", ".htm"}:
            return self._extract_html_text(file_path)
        else:
            try:
                return file_path.read_text(errors="ignore")
            except Exception:
                return ""

    def _extract_pdf_text(self, file_path: Path) -> str:
        """Extract text from PDF."""
        try:
            from pdfminer.high_level import extract_text

            return extract_text(str(file_path), maxpages=self.pdf_max_pages) or ""
        except Exception as e:
            logger.debug(f"PDF extraction failed: {e}")
            return ""

    def _extract_html_text(self, file_path: Path) -> str:
        """Extract text from HTML."""
        try:
            from markitdown import MarkItDown

            md = MarkItDown()
            result = md.convert(str(file_path))
            return result.text_content or ""
        except Exception:
            pass

        # Fallback to BeautifulSoup
        try:
            from bs4 import BeautifulSoup

            html = file_path.read_text(errors="ignore")
            return BeautifulSoup(html, "html.parser").get_text(" ")
        except Exception:
            return ""


def get_local_database_client(
    db_path: str | Path | None = None,
) -> LocalDatabaseClient | None:
    """
    Get a local database client if available.

    Args:
        db_path: Optional explicit database path

    Returns:
        LocalDatabaseClient if database exists, None otherwise
    """
    try:
        return LocalDatabaseClient(db_path=db_path)
    except FileNotFoundError:
        return None


def is_local_database_available() -> bool:
    """Check if local Zotero database is accessible."""
    client = get_local_database_client()
    if client:
        client.close()
        return True
    return False
