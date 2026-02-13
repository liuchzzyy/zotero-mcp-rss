"""
Service for updating Zotero item metadata from external APIs.

This service enhances Zotero items by fetching complete metadata from
Crossref and OpenAlex APIs and updating items with missing information.
"""

import html
import logging
import re
from typing import Any

from zotero_mcp.services.common.retry import async_retry_with_backoff
from zotero_mcp.services.zotero.item_service import ItemService
from zotero_mcp.services.zotero.metadata_service import MetadataService

logger = logging.getLogger(__name__)

AI_METADATA_TAG = "AI元数据"
_SKIPPED_ITEM_TYPES = {"attachment", "note", "annotation"}

# Mapping from enhanced metadata keys to Zotero item data keys
_METADATA_FIELD_MAP = {
    "doi": "DOI",
    "journal": "publicationTitle",
    "journal_abbrev": "journalAbbreviation",
    "publisher": "publisher",
    "volume": "volume",
    "issue": "issue",
    "pages": "pages",
    "abstract": "abstractNote",
    "issn": "ISSN",
    "language": "language",
    "rights": "rights",
    "short_title": "shortTitle",
    "series": "series",
    "edition": "edition",
    "place": "place",
}
_PERIODICAL_ITEM_TYPES = {
    "journalArticle",
    "magazineArticle",
    "newspaperArticle",
    "conferencePaper",
    "preprint",
}
_PERIODICAL_ONLY_FIELDS = {
    "publicationTitle",
    "journalAbbreviation",
    "volume",
    "issue",
    "pages",
    "ISSN",
}

# Key fields to check for changes between current and updated data
_KEY_FIELDS = [
    "DOI",
    "title",
    "creators",
    "publicationTitle",
    "journalAbbreviation",
    "publisher",
    "date",
    "volume",
    "issue",
    "pages",
    "abstractNote",
    "url",
    "ISSN",
    "itemType",
    "language",
    "rights",
    "shortTitle",
    "series",
    "edition",
    "place",
    "extra",
]


def _has_value(value: Any) -> bool:
    """Whether a metadata value should be treated as present."""
    if value is None:
        return False
    if isinstance(value, str):
        return bool(value.strip())
    if isinstance(value, (list, dict, set, tuple)):
        return len(value) > 0
    return True


def _to_extra_text(value: Any) -> str:
    """Serialize metadata value for Zotero extra field."""
    if isinstance(value, list):
        return ", ".join(str(v) for v in value if _has_value(v))
    if isinstance(value, dict):
        return ", ".join(f"{k}={v}" for k, v in value.items() if _has_value(v))
    return str(value)


def _extract_tag_names(tags: list) -> list[str]:
    """Extract tag names from either dict or string format."""
    if not tags:
        return []
    if isinstance(tags[0], dict):
        return [t.get("tag", "") for t in tags]
    return tags


def _clean_html_title(title: str) -> str:
    """
    Clean HTML tags and entities from a title.

    Removes HTML tags (like <strong>, <sub>, <sup>) and decodes
    HTML entities (&amp;, &lt;, etc.) to prepare titles for
    metadata API searches.

    Args:
        title: Title string that may contain HTML.

    Returns:
        Cleaned title string without HTML tags or entities.

    Examples:
        >>> _clean_html_title("<strong>Tuning</strong> Co–Co")
        'Tuning Co–Co'
        >>> _clean_html_title("H&lt;sub&gt;2&lt;/sub&gt;O")
        'H₂O'
    """
    if not title:
        return ""

    # Remove HTML tags
    cleaned = re.sub(r"<[^>]+>", "", title)

    # Decode HTML entities
    try:
        cleaned = html.unescape(cleaned)
    except Exception:
        pass

    # Clean up extra whitespace
    cleaned = re.sub(r"\s+", " ", cleaned).strip()

    return cleaned


class MetadataUpdateService:
    """
    Service for updating Zotero item metadata from external APIs.

    Fetches complete metadata from Crossref/OpenAlex, updates items with
    missing information, and adds 'AI元数据' tag on successful updates.
    """

    def __init__(self, item_service: ItemService, metadata_service: MetadataService):
        self.item_service = item_service
        self.metadata_service = metadata_service

    async def update_item_metadata(
        self, item_key: str, dry_run: bool = False
    ) -> dict[str, Any]:
        """
        Update metadata for a single Zotero item.

        Args:
            item_key: Zotero item key
            dry_run: If True, preview changes without applying them

        Returns:
            Dict with update result (success, updated, message, source)
        """
        try:
            item = await self.item_service.get_item(item_key)
            if not item:
                return {
                    "success": False,
                    "updated": False,
                    "message": f"Item {item_key} not found",
                    "source": "none",
                }

            item_data = item.get("data", {})
            item_type = item_data.get("itemType", "")

            if item_type in _SKIPPED_ITEM_TYPES:
                logger.info(f"  Skipping unsupported item type: {item_type}")
                return {
                    "success": True,
                    "updated": False,
                    "message": f"Skipped unsupported item type: {item_type}",
                    "source": "none",
                }

            # Check if already processed
            tag_names = _extract_tag_names(item_data.get("tags", []))
            if AI_METADATA_TAG in tag_names:
                logger.info(f"  Skipping - already has '{AI_METADATA_TAG}' tag")
                return {
                    "success": True,
                    "updated": False,
                    "message": f"Already updated (has '{AI_METADATA_TAG}' tag)",
                    "source": "cached",
                }

            current_title = item_data.get("title", "")
            logger.info(
                f"Updating metadata for item: {current_title[:50]} "
                f"(DOI: {item_data.get('DOI') or 'N/A'})"
            )

            # Fetch enhanced metadata (priority: DOI > title > URL)
            enhanced_metadata = await self._fetch_enhanced_metadata(
                doi=item_data.get("DOI", ""),
                title=current_title,
                url=item_data.get("url", ""),
            )

            if not enhanced_metadata:
                logger.info("  No enhanced metadata found")
                return {
                    "success": True,
                    "updated": False,
                    "message": "No enhanced metadata found",
                    "source": "none",
                }

            # Build updated item data
            updated_data = self._build_updated_item_data(item_data, enhanced_metadata)

            # Check if anything changed
            if not self._has_changes(item_data, updated_data):
                logger.info("  No updates needed")
                return {
                    "success": True,
                    "updated": False,
                    "message": "Item already up-to-date",
                    "source": enhanced_metadata.get("source", "unknown"),
                }

            # Add AI metadata tag
            updated_data = self._add_ai_metadata_tag(updated_data)

            # Prepare full item object for update
            updated_item = item.copy()
            updated_item["data"] = updated_data

            if dry_run:
                source = enhanced_metadata.get("source")
                logger.info(f"  [DRY RUN] Would update metadata (source: {source})")
                return {
                    "success": True,
                    "updated": True,
                    "message": f"[DRY RUN] Would update from {source}",
                    "source": source,
                }

            await async_retry_with_backoff(
                lambda: self.item_service.update_item(updated_item),
                description=f"Update item {item_key}",
            )

            source = enhanced_metadata.get("source")
            logger.info(f"  Updated metadata (source: {source})")
            return {
                "success": True,
                "updated": True,
                "message": f"Updated from {source}",
                "source": source,
            }

        except Exception as e:
            err_text = str(e).strip() or repr(e)
            logger.error(f"  Error updating item {item_key}: {err_text}")
            return {
                "success": False,
                "updated": False,
                "message": f"Error: {err_text}",
                "source": "none",
            }

    async def update_all_items(
        self,
        collection_key: str | None = None,
        scan_limit: int = 100,
        treated_limit: int | None = None,
        dry_run: bool = False,
    ) -> dict[str, Any]:
        """
        Update metadata for multiple items with batch scanning.

        Args:
            collection_key: Optional collection key to limit updates
            scan_limit: Number of items to fetch per batch from API
            treated_limit: Maximum items to process (excludes skipped)
            dry_run: If True, preview changes without applying them

        Returns:
            Dict with statistics:
            - total: parent/top-level items scanned
            - processed_candidates: candidate parent items actually processed
            - updated/skipped/failed/ai_metadata_tagged
        """
        logger.info(
            f"Starting metadata update "
            f"(batch: {scan_limit}, max: {treated_limit or 'all'})"
        )
        if dry_run:
            logger.info("DRY RUN MODE: No changes will be applied")

        updated = 0
        skipped = 0
        failed = 0
        ai_metadata_tagged = 0
        total_processed = 0
        total_scanned = 0

        if collection_key:
            collection_keys = [collection_key]
        else:
            logger.info("Scanning all collections in name order...")
            collections = await self.item_service.get_sorted_collections()
            collection_keys = [coll["key"] for coll in collections]

        for coll_key in collection_keys:
            if treated_limit and total_processed >= treated_limit:
                logger.info(f"Reached treated_limit ({treated_limit}), stopping scan")
                break

            scanned, proc, upd, skip, fail, ai_tagged = await self._process_collection(
                coll_key=coll_key,
                scan_limit=scan_limit,
                treated_limit=treated_limit,
                total_processed=total_processed,
                dry_run=dry_run,
            )
            total_scanned += scanned
            total_processed += proc
            updated += upd
            skipped += skip
            failed += fail
            ai_metadata_tagged += ai_tagged

            logger.info(
                f"  Progress: {total_processed} processed, {updated} updated, "
                f"{skipped} skipped, {ai_metadata_tagged} with '{AI_METADATA_TAG}' "
                f"(items scanned: {total_scanned})"
            )

        logger.info(
            f"Metadata update complete: {updated} updated, "
            f"{skipped} skipped, {failed} failed, "
            f"{ai_metadata_tagged} with '{AI_METADATA_TAG}' "
            f"(items scanned: {total_scanned})"
        )

        return {
            "items": total_scanned,
            "total": total_scanned,
            "processed_candidates": total_processed,
            "updated": updated,
            "skipped": skipped,
            "failed": failed,
            "ai_metadata_tagged": ai_metadata_tagged,
        }

    async def _process_collection(
        self,
        coll_key: str,
        scan_limit: int,
        treated_limit: int | None,
        total_processed: int,
        dry_run: bool,
    ) -> tuple[int, int, int, int, int, int]:
        """
        Process a single collection for metadata updates.

        Returns:
            Tuple of (
                scanned_parent,
                processed,
                updated,
                skipped,
                failed,
                ai_metadata_tagged,
            )
        """
        scanned = 0
        processed = 0
        updated = 0
        skipped = 0
        failed = 0
        ai_metadata_tagged = 0
        offset = 0

        while True:
            if treated_limit and total_processed + processed >= treated_limit:
                break

            items = await async_retry_with_backoff(
                lambda c=coll_key, limit=scan_limit, start=offset: self.item_service.get_collection_items(
                    c, limit=limit, start=start
                ),
                description=f"Scan collection {coll_key} (offset {offset})",
            )
            if not items:
                break

            parent_items = [
                item for item in items if item.item_type not in _SKIPPED_ITEM_TYPES
            ]
            scanned += len(parent_items)

            for item in parent_items:
                if treated_limit and total_processed + processed >= treated_limit:
                    break

                # Quick check: skip if already has AI元数据 tag
                tag_names = _extract_tag_names(item.tags or [])
                if AI_METADATA_TAG in tag_names:
                    skipped += 1
                    ai_metadata_tagged += 1
                    continue

                processed += 1
                result = await self.update_item_metadata(item.key, dry_run=dry_run)

                if result["success"]:
                    if result["updated"]:
                        updated += 1
                    else:
                        skipped += 1
                else:
                    failed += 1

            if len(items) < scan_limit:
                break

            offset += scan_limit

        return (
            scanned,
            processed,
            updated,
            skipped,
            failed,
            ai_metadata_tagged,
        )

    async def _fetch_enhanced_metadata(
        self, doi: str, title: str, url: str
    ) -> dict[str, Any] | None:
        """Fetch enhanced metadata from APIs with priority: DOI > title > URL."""
        if doi:
            logger.debug(f"  Looking up by DOI: {doi}")
            metadata = await self.metadata_service.get_metadata_by_doi(doi)
            if metadata:
                return self._metadata_to_dict(metadata)
            # Optimization: when DOI is provided, avoid extra title/URL fallbacks.
            # A valid DOI should uniquely identify a record if the source indexes it.
            return None

        if title:
            # Clean HTML tags and entities from title before searching
            clean_title = _clean_html_title(title)
            if clean_title != title:
                logger.info(f"  Cleaned HTML from title: '{title[:40]}...' -> '{clean_title[:40]}...'")
            logger.debug(f"  Looking up by title: {clean_title[:50]}")
            metadata = await self.metadata_service.lookup_metadata(title=clean_title)
            if metadata:
                return self._metadata_to_dict(metadata)

        if url:
            logger.debug("  Looking up by URL")
            metadata = await self.metadata_service.lookup_metadata(url=url)
            if metadata:
                return self._metadata_to_dict(metadata)

        return None

    def _metadata_to_dict(self, metadata) -> dict[str, Any]:
        """Convert ArticleMetadata to dict with enhanced fields."""
        return {
            "doi": metadata.doi,
            "title": metadata.title,
            "authors": metadata.authors,
            "journal": metadata.journal,
            "journal_abbrev": metadata.journal_abbrev,
            "publisher": metadata.publisher,
            "year": metadata.year,
            "volume": metadata.volume,
            "issue": metadata.issue,
            "pages": metadata.pages,
            "abstract": metadata.abstract,
            "url": metadata.url,
            "issn": metadata.issn,
            "item_type": metadata.item_type,
            "source": metadata.source,
            "language": metadata.language,
            "rights": metadata.rights,
            "short_title": metadata.short_title,
            "series": metadata.series,
            "edition": metadata.edition,
            "place": metadata.place,
            "citation_count": metadata.citation_count,
            "subjects": metadata.subjects,
            "funders": metadata.funders,
            "pdf_url": metadata.pdf_url,
        }

    def _build_updated_item_data(
        self, current_data: dict[str, Any], enhanced_metadata: dict[str, Any]
    ) -> dict[str, Any]:
        """
        Build updated item data by merging current and enhanced metadata.

        Source-specific merge strategy:
        - crossref: overwrite existing mapped fields
        - openalex: only fill missing mapped fields
        Any metadata not applied to standard Zotero fields is appended to "extra".
        """
        updated = current_data.copy()
        current_item_type = updated.get("itemType", "")
        source = str(enhanced_metadata.get("source", "")).lower()
        overwrite_mode = source == "crossref"
        applied_meta_keys: set[str] = set()

        # Clean HTML tags from current title if present
        current_title = updated.get("title", "")
        if current_title and "<" in current_title:
            clean_title = _clean_html_title(current_title)
            if clean_title != current_title:
                logger.info(f"  Cleaning HTML from title: '{current_title[:40]}...' -> '{clean_title[:40]}...'")
                updated["title"] = clean_title

        # Apply simple field mappings according to source strategy.
        for meta_key, zotero_key in _METADATA_FIELD_MAP.items():
            meta_value = enhanced_metadata.get(meta_key)
            if not _has_value(meta_value):
                continue
            if zotero_key not in updated:
                continue
            if (
                zotero_key in _PERIODICAL_ONLY_FIELDS
                and current_item_type not in _PERIODICAL_ITEM_TYPES
            ):
                continue
            current_value = updated.get(zotero_key)
            should_apply = overwrite_mode or not _has_value(current_value)
            if should_apply:
                updated[zotero_key] = meta_value
                applied_meta_keys.add(meta_key)

        # Title: crossref overwrites; openalex supplements when missing.
        if _has_value(enhanced_metadata.get("title")) and "title" in updated:
            should_apply_title = overwrite_mode or not _has_value(updated.get("title"))
            if should_apply_title:
                updated["title"] = str(enhanced_metadata["title"]).strip()
                applied_meta_keys.add("title")

        # Authors: crossref overwrites; openalex supplements when missing.
        if _has_value(enhanced_metadata.get("authors")):
            current_creators = updated.get("creators", [])
            should_apply_authors = overwrite_mode or not _has_value(current_creators)
            if should_apply_authors:
                updated["creators"] = self._convert_authors(enhanced_metadata["authors"])
                applied_meta_keys.add("authors")

        # Date/Year: crossref overwrites; openalex supplements when missing.
        if _has_value(enhanced_metadata.get("year")) and "date" in updated:
            should_apply_year = overwrite_mode or not _has_value(updated.get("date"))
            if should_apply_year:
                updated["date"] = str(enhanced_metadata["year"])
                applied_meta_keys.add("year")

        # URL: crossref overwrites; openalex supplements when missing.
        if _has_value(enhanced_metadata.get("url")) and "url" in updated:
            should_apply_url = overwrite_mode or not _has_value(updated.get("url"))
            if should_apply_url:
                updated["url"] = enhanced_metadata["url"]
                applied_meta_keys.add("url")

        # Item type: crossref can overwrite generic type; openalex only supplements.
        current_type = updated.get("itemType", "")
        enhanced_type = enhanced_metadata.get("item_type", "")
        if _has_value(enhanced_type):
            if overwrite_mode:
                if current_type in ("", "document") or current_type != enhanced_type:
                    updated["itemType"] = enhanced_type
                    applied_meta_keys.add("item_type")
            else:
                if current_type in ("", "document"):
                    updated["itemType"] = enhanced_type
                    applied_meta_keys.add("item_type")

        # Build "Extra" field:
        # 1) keep existing extra
        # 2) keep explicit extended metadata lines
        # 3) append unmatched non-empty metadata entries
        extra_parts = []
        existing_extra = updated.get("extra", "")
        if existing_extra:
            extra_parts.append(existing_extra)

        if enhanced_metadata.get("citation_count") is not None:
            extra_parts.append(f"Citation Count: {enhanced_metadata['citation_count']}")
            applied_meta_keys.add("citation_count")
        for subject in enhanced_metadata.get("subjects", []):
            extra_parts.append(f"Subject: {subject}")
        if enhanced_metadata.get("subjects"):
            applied_meta_keys.add("subjects")
        for funder in enhanced_metadata.get("funders", []):
            extra_parts.append(f"Funder: {funder}")
        if enhanced_metadata.get("funders"):
            applied_meta_keys.add("funders")
        if enhanced_metadata.get("pdf_url"):
            extra_parts.append(f"Full-text PDF: {enhanced_metadata['pdf_url']}")
            applied_meta_keys.add("pdf_url")

        ignored_meta_keys = {"source", "raw_data"}
        for meta_key, meta_value in enhanced_metadata.items():
            if meta_key in ignored_meta_keys or meta_key in applied_meta_keys:
                continue
            if not _has_value(meta_value):
                continue
            value_text = _to_extra_text(meta_value)
            if value_text:
                label = meta_key.replace("_", " ").title()
                extra_parts.append(f"{label}: {value_text}")

        if extra_parts:
            updated["extra"] = "\n".join(extra_parts)
        elif "extra" in updated:
            del updated["extra"]

        return updated

    def _convert_authors(self, authors: list[str]) -> list[dict[str, str]]:
        """Convert author string list to Zotero creator format."""
        creators = []
        for author in authors:
            if ", " in author:
                parts = author.split(", ", 1)
                creators.append(
                    {
                        "creatorType": "author",
                        "lastName": parts[0],
                        "firstName": parts[1] if len(parts) > 1 else "",
                    }
                )
            else:
                creators.append({"creatorType": "author", "name": author})
        return creators

    def _has_changes(self, current: dict[str, Any], updated: dict[str, Any]) -> bool:
        """Check if updated data has any changes from current."""
        return any(
            current.get(field_name) != updated.get(field_name)
            for field_name in _KEY_FIELDS
        )

    def _add_ai_metadata_tag(self, item_data: dict[str, Any]) -> dict[str, Any]:
        """Add AI元数据 tag to item."""
        updated = item_data.copy()
        existing_tags = updated.get("tags", [])

        # Normalize to dict format [{"tag": "name"}, ...]
        if existing_tags and isinstance(existing_tags[0], str):
            existing_tags = [{"tag": tag} for tag in existing_tags]

        tag_names = {t.get("tag", "") for t in existing_tags}
        if AI_METADATA_TAG not in tag_names:
            existing_tags.append({"tag": AI_METADATA_TAG})

        updated["tags"] = existing_tags
        return updated
