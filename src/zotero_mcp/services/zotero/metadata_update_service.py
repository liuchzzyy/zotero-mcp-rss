"""
Service for updating Zotero item metadata from external APIs.

This service enhances Zotero items by fetching complete metadata from
Crossref and OpenAlex APIs and updating items with missing information.
"""

import logging
from typing import Any

from zotero_mcp.services.zotero.metadata_service import MetadataService
from zotero_mcp.services.zotero.item_service import ItemService
from zotero_mcp.services.common.retry import async_retry_with_backoff

logger = logging.getLogger(__name__)

AI_METADATA_TAG = "AI元数据"


class MetadataUpdateService:
    """
    Service for updating Zotero item metadata from external APIs.

    Features:
    - Fetches complete metadata from Crossref/OpenAlex
    - Updates items with missing information
    - Adds 'AI元数据' tag on successful updates
    - Priority: DOI > title > URL for metadata lookup
    """

    def __init__(self, item_service: ItemService, metadata_service: MetadataService):
        """
        Initialize MetadataUpdateService.

        Args:
            item_service: ItemService for Zotero item operations
            metadata_service: MetadataService for API lookups
        """
        self.item_service = item_service
        self.metadata_service = metadata_service

    async def update_item_metadata(
        self, item_key: str
    ) -> dict[str, Any]:
        """
        Update metadata for a single Zotero item.

        Args:
            item_key: Zotero item key

        Returns:
            Dict with update result:
                - success: bool
                - updated: bool (whether metadata was changed)
                - message: str
                - source: str ("crossref" or "openalex" or "none")
        """
        try:
            # Get current item data
            item = await self.item_service.get_item(item_key)
            if not item:
                return {
                    "success": False,
                    "updated": False,
                    "message": f"Item {item_key} not found",
                    "source": "none",
                }

            item_data = item.get("data", {})
            current_doi = item_data.get("DOI", "")
            current_title = item_data.get("title", "")
            current_url = item_data.get("url", "")

            # Check if item already has AI元数据 tag (previously updated successfully)
            existing_tags = item_data.get("tags", [])
            if isinstance(existing_tags[0], dict) if existing_tags else False:
                # Tags are in dict format: [{"tag": "name"}, ...]
                tag_list = [t.get("tag", "") for t in existing_tags]
            else:
                # Tags are in string format: ["tag1", "tag2"]
                tag_list = existing_tags

            if AI_METADATA_TAG in tag_list:
                logger.info(f"  ⊘ Skipping - already has '{AI_METADATA_TAG}' tag")
                return {
                    "success": True,
                    "updated": False,
                    "message": f"Already updated (has '{AI_METADATA_TAG}' tag)",
                    "source": "cached",
                }

            logger.info(
                f"Updating metadata for item: {current_title[:50]} "
                f"(DOI: {current_doi or 'N/A'})"
            )

            # Try to fetch enhanced metadata (priority: DOI > title > URL)
            enhanced_metadata = await self._fetch_enhanced_metadata(
                doi=current_doi,
                title=current_title,
                url=current_url,
            )

            if not enhanced_metadata:
                logger.info(f"  ✗ No enhanced metadata found")
                return {
                    "success": True,
                    "updated": False,
                    "message": "No enhanced metadata found",
                    "source": "none",
                }

            # Build updated item data
            updated_data = self._build_updated_item_data(
                current_data=item_data,
                enhanced_metadata=enhanced_metadata,
            )

            # Check if anything changed
            if not self._has_changes(item_data, updated_data):
                logger.info(f"  → No updates needed")
                return {
                    "success": True,
                    "updated": False,
                    "message": "Item already up-to-date",
                    "source": enhanced_metadata.get("source", "unknown"),
                }

            # Add AI metadata tag
            updated_data = self._add_ai_metadata_tag(updated_data)

            # Prepare full item object for update
            updated_item = {"key": item_key, "data": updated_data}

            # Update the item
            await async_retry_with_backoff(
                lambda: self.item_service.update_item(updated_item),
                description=f"Update item {item_key}",
            )

            logger.info(
                f"  ✓ Updated metadata (source: {enhanced_metadata.get('source')})"
            )
            return {
                "success": True,
                "updated": True,
                "message": f"Updated from {enhanced_metadata.get('source')}",
                "source": enhanced_metadata.get("source"),
            }

        except Exception as e:
            logger.error(f"  ✗ Error updating item {item_key}: {e}")
            return {
                "success": False,
                "updated": False,
                "message": f"Error: {str(e)}",
                "source": "none",
            }

    async def update_all_items(
        self,
        collection_key: str | None = None,
        limit: int | None = None,
    ) -> dict[str, Any]:
        """
        Update metadata for multiple items.

        Args:
            collection_key: Optional collection key to limit updates
            limit: Maximum number of items to process

        Returns:
            Dict with statistics:
                - total: int (total items processed)
                - updated: int (items successfully updated)
                - skipped: int (items with no updates needed)
                - failed: int (items that failed to update)
        """
        logger.info("Starting metadata update for multiple items...")

        # Get items to update
        if collection_key:
            items = await self.item_service.get_collection_items(collection_key)
        else:
            # Get all items (need to implement or use existing method)
            items = await self._get_all_items(limit)

        total = len(items)
        updated = 0
        skipped = 0
        failed = 0

        for idx, item in enumerate(items, 1):
            item_key = item.get("key", "")
            title = item.get("data", {}).get("title", "Unknown")[:50]

            logger.info(f"[{idx}/{total}] Processing: {title}...")

            result = await self.update_item_metadata(item_key)

            if result["success"]:
                if result["updated"]:
                    updated += 1
                else:
                    skipped += 1
            else:
                failed += 1

        logger.info(
            f"Metadata update complete: {updated} updated, "
            f"{skipped} skipped, {failed} failed"
        )

        return {
            "total": total,
            "updated": updated,
            "skipped": skipped,
            "failed": failed,
        }

    async def _fetch_enhanced_metadata(
        self, doi: str, title: str, url: str
    ) -> dict[str, Any] | None:
        """
        Fetch enhanced metadata from APIs with priority: DOI > title > URL.

        Args:
            doi: Item DOI
            title: Item title
            url: Item URL

        Returns:
            Enhanced metadata dict or None
        """
        # Priority 1: Lookup by DOI
        if doi:
            logger.debug(f"  → Looking up by DOI: {doi}")
            metadata = await self.metadata_service.get_metadata_by_doi(doi)
            if metadata:
                return self._metadata_to_dict(metadata)

        # Priority 2: Lookup by title
        if title:
            logger.debug(f"  → Looking up by title: {title[:50]}")
            metadata = await self.metadata_service.lookup_metadata(title)
            if metadata:
                return self._metadata_to_dict(metadata)

        # Priority 3: Could lookup by URL (not implemented yet)
        # URL matching is less reliable, skip for now

        return None

    def _metadata_to_dict(self, metadata) -> dict[str, Any]:
        """Convert ArticleMetadata to dict."""
        return {
            "doi": metadata.doi,
            "title": metadata.title,
            "authors": metadata.authors,
            "journal": metadata.journal,
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
        }

    def _build_updated_item_data(
        self, current_data: dict[str, Any], enhanced_metadata: dict[str, Any]
    ) -> dict[str, Any]:
        """
        Build updated item data by merging current and enhanced metadata.

        Only fills in missing fields, doesn't overwrite existing data.
        """
        updated = current_data.copy()

        # DOI (always update if we have a better one)
        if enhanced_metadata.get("doi") and not updated.get("DOI"):
            updated["DOI"] = enhanced_metadata["doi"]

        # Title (keep current, don't overwrite)
        # Users may have custom titles

        # Authors (update if missing)
        if enhanced_metadata.get("authors") and not updated.get("creators"):
            updated["creators"] = self._convert_authors(enhanced_metadata["authors"])

        # Journal/Publication
        if enhanced_metadata.get("journal") and not updated.get("publicationTitle"):
            updated["publicationTitle"] = enhanced_metadata["journal"]

        # Publisher
        if enhanced_metadata.get("publisher") and not updated.get("publisher"):
            updated["publisher"] = enhanced_metadata["publisher"]

        # Date/Year
        if enhanced_metadata.get("year") and not updated.get("date"):
            updated["date"] = str(enhanced_metadata["year"])

        # Volume
        if enhanced_metadata.get("volume") and not updated.get("volume"):
            updated["volume"] = enhanced_metadata["volume"]

        # Issue
        if enhanced_metadata.get("issue") and not updated.get("issue"):
            updated["issue"] = enhanced_metadata["issue"]

        # Pages
        if enhanced_metadata.get("pages") and not updated.get("pages"):
            updated["pages"] = enhanced_metadata["pages"]

        # Abstract
        if enhanced_metadata.get("abstract") and not updated.get("abstractNote"):
            updated["abstractNote"] = enhanced_metadata["abstract"]

        # URL (use enhanced URL if better)
        if enhanced_metadata.get("url"):
            enhanced_url = enhanced_metadata["url"]
            current_url = updated.get("url", "")
            # Prefer DOI URLs over other URLs
            if not current_url or "doi.org" in enhanced_url:
                updated["url"] = enhanced_url

        # ISSN
        if enhanced_metadata.get("issn") and not updated.get("ISSN"):
            updated["ISSN"] = enhanced_metadata["issn"]

        # Item type (keep current unless it's generic)
        current_type = updated.get("itemType", "")
        enhanced_type = enhanced_metadata.get("item_type", "")
        if current_type in ["", "document"] and enhanced_type:
            updated["itemType"] = enhanced_type

        return updated

    def _convert_authors(self, authors: list[str]) -> list[dict[str, str]]:
        """Convert author string list to Zotero creator format."""
        creators = []
        for author in authors:
            if ", " in author:
                parts = author.split(", ", 1)
                creators.append({
                    "creatorType": "author",
                    "lastName": parts[0],
                    "firstName": parts[1] if len(parts) > 1 else "",
                })
            else:
                creators.append({
                    "creatorType": "author",
                    "name": author,
                })
        return creators

    def _has_changes(
        self, current: dict[str, Any], updated: dict[str, Any]
    ) -> bool:
        """Check if updated data has any changes from current."""
        # Compare key fields
        key_fields = [
            "DOI", "title", "creators", "publicationTitle",
            "publisher", "date", "volume", "issue", "pages",
            "abstractNote", "url", "ISSN", "itemType"
        ]
        for field in key_fields:
            if current.get(field) != updated.get(field):
                return True
        return False

    def _add_ai_metadata_tag(self, item_data: dict[str, Any]) -> dict[str, Any]:
        """Add AI元数据 tag to item."""
        updated = item_data.copy()

        # Get existing tags
        existing_tags = updated.get("tags", [])
        if isinstance(existing_tags[0], dict) if existing_tags else False:
            # Tags are in dict format: [{"tag": "name"}, ...]
            tag_list = [t.get("tag", "") for t in existing_tags]
        else:
            # Tags are in string format: ["tag1", "tag2"]
            tag_list = existing_tags

        # Add AI元数据 tag if not present
        if AI_METADATA_TAG not in tag_list:
            if isinstance(existing_tags[0], dict) if existing_tags else False:
                existing_tags.append({"tag": AI_METADATA_TAG})
            else:
                existing_tags.append(AI_METADATA_TAG)
            updated["tags"] = existing_tags

        return updated

    async def _get_all_items(self, limit: int | None = None) -> list[dict[str, Any]]:
        """Get all items from the library."""
        # This is a placeholder - need to implement proper pagination
        # For now, return empty list
        logger.warning("_get_all_items not fully implemented yet")
        return []
