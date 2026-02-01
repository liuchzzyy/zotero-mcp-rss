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

            # Prepare full item object for update - preserve version and other top-level fields
            updated_item = item.copy()
            updated_item["data"] = updated_data

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
        scan_limit: int = 100,
        treated_limit: int | None = None,
    ) -> dict[str, Any]:
        """
        Update metadata for multiple items with batch scanning.

        Args:
            collection_key: Optional collection key to limit updates
            scan_limit: Number of items to fetch per batch from API
            treated_limit: Maximum total number of items to process (excludes skipped)

        Returns:
            Dict with statistics:
                - total: int (total items scanned)
                - updated: int (items successfully updated)
                - skipped: int (items with no updates needed)
                - failed: int (items that failed to update)
        """
        logger.info(
            f"Starting metadata update for multiple items "
            f"(batch: {scan_limit}, max: {treated_limit or 'all'})"
        )

        updated = 0
        skipped = 0
        failed = 0
        total_processed = 0  # Only counts items that were actually processed
        total_scanned = 0

        if collection_key:
            # Single collection mode
            logger.info(f"Scanning collection: {collection_key}")
            offset = 0

            while True:
                # Check if we've processed enough items
                if treated_limit and total_processed >= treated_limit:
                    break

                # Fetch batch from API
                items = await self.item_service.get_collection_items(
                    collection_key, limit=scan_limit, start=offset
                )

                if not items:
                    break  # No more items

                total_scanned += len(items)

                # Process each item
                for item in items:
                    # Check if we've processed enough items
                    if treated_limit and total_processed >= treated_limit:
                        break

                    # Quick check: skip if already has AI元数据 tag
                    existing_tags = item.tags or []
                    tag_list = [
                        t.get("tag", "") if isinstance(t, dict) else t
                        for t in existing_tags
                    ]

                    if AI_METADATA_TAG in tag_list:
                        skipped += 1
                        continue

                    # Process the item
                    total_processed += 1
                    result = await self.update_item_metadata(item.key)

                    if result["success"]:
                        if result["updated"]:
                            updated += 1
                        else:
                            skipped += 1
                    else:
                        failed += 1

                # If we got fewer items than scan_limit, we've exhausted the collection
                if len(items) < scan_limit:
                    break

                offset += scan_limit

                logger.info(
                    f"  Progress: {total_processed} processed, {updated} updated, "
                    f"{skipped} skipped (scanned: {total_scanned})"
                )
        else:
            # Scan all collections in order
            logger.info("Scanning all collections in name order...")
            collections = await self.item_service.get_sorted_collections()

            for coll in collections:
                # Check if we've processed enough items
                if treated_limit and total_processed >= treated_limit:
                    break

                coll_key = coll["key"]
                coll_name = coll.get("data", {}).get("name", "")
                logger.info(f"Scanning collection: {coll_name}")

                # Keep fetching batches from this collection
                offset = 0
                while True:
                    # Check if we've processed enough items
                    if treated_limit and total_processed >= treated_limit:
                        break

                    # Fetch batch from API
                    items = await self.item_service.get_collection_items(
                        coll_key, limit=scan_limit, start=offset
                    )

                    if not items:
                        break  # No more items in this collection

                    total_scanned += len(items)

                    # Process each item
                    for item in items:
                        # Check if we've processed enough items
                        if treated_limit and total_processed >= treated_limit:
                            break

                        # Quick check: skip if already has AI元数据 tag
                        existing_tags = item.tags or []
                        tag_list = [
                            t.get("tag", "") if isinstance(t, dict) else t
                            for t in existing_tags
                        ]

                        if AI_METADATA_TAG in tag_list:
                            skipped += 1
                            continue

                        # Process the item
                        total_processed += 1
                        result = await self.update_item_metadata(item.key)

                        if result["success"]:
                            if result["updated"]:
                                updated += 1
                            else:
                                skipped += 1
                        else:
                            failed += 1

                    # If we got fewer items than scan_limit, we've exhausted this collection
                    if len(items) < scan_limit:
                        break

                    offset += scan_limit

                logger.info(
                    f"  Collection '{coll_name}': {total_processed} processed, "
                    f"{updated} updated, {skipped} skipped"
                )

                # Early exit if we've processed enough
                if treated_limit and total_processed >= treated_limit:
                    logger.info(f"Reached treated_limit ({treated_limit}), stopping scan")
                    break

        logger.info(
            f"Metadata update complete: {updated} updated, "
            f"{skipped} skipped, {failed} failed (scanned: {total_scanned})"
        )

        return {
            "total": total_scanned,
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
            # Additional fields
            "language": metadata.language,
            "rights": metadata.rights,
            "short_title": metadata.short_title,
            "series": metadata.series,
            "edition": metadata.edition,
            "place": metadata.place,
            # Extra metadata
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

        Overwrites existing fields with API data (except title).
        Includes enhanced fields from Crossref/OpenAlex APIs.
        """
        updated = current_data.copy()

        # DOI (always overwrite with API data)
        if enhanced_metadata.get("doi"):
            updated["DOI"] = enhanced_metadata["doi"]

        # Title (keep current, don't overwrite)
        # Users may have custom titles, so we preserve them

        # Authors (overwrite with API data)
        if enhanced_metadata.get("authors"):
            updated["creators"] = self._convert_authors(enhanced_metadata["authors"])

        # Journal/Publication (overwrite with API data)
        if enhanced_metadata.get("journal"):
            updated["publicationTitle"] = enhanced_metadata["journal"]

        # Journal abbreviation (overwrite with API data)
        if enhanced_metadata.get("journal_abbrev"):
            updated["journalAbbreviation"] = enhanced_metadata["journal_abbrev"]

        # Publisher (overwrite with API data)
        if enhanced_metadata.get("publisher"):
            updated["publisher"] = enhanced_metadata["publisher"]

        # Date/Year (overwrite with API data)
        if enhanced_metadata.get("year"):
            updated["date"] = str(enhanced_metadata["year"])

        # Volume (overwrite with API data)
        if enhanced_metadata.get("volume"):
            updated["volume"] = enhanced_metadata["volume"]

        # Issue (overwrite with API data)
        if enhanced_metadata.get("issue"):
            updated["issue"] = enhanced_metadata["issue"]

        # Pages (overwrite with API data)
        if enhanced_metadata.get("pages"):
            updated["pages"] = enhanced_metadata["pages"]

        # Abstract (overwrite with API data)
        if enhanced_metadata.get("abstract"):
            updated["abstractNote"] = enhanced_metadata["abstract"]

        # URL (use enhanced URL if better)
        if enhanced_metadata.get("url"):
            enhanced_url = enhanced_metadata["url"]
            current_url = updated.get("url", "")
            # Prefer DOI URLs over other URLs
            if not current_url or "doi.org" in enhanced_url:
                updated["url"] = enhanced_url

        # ISSN (overwrite with API data)
        if enhanced_metadata.get("issn"):
            updated["ISSN"] = enhanced_metadata["issn"]

        # Additional Zotero fields
        if enhanced_metadata.get("language"):
            updated["language"] = enhanced_metadata["language"]

        if enhanced_metadata.get("rights"):
            updated["rights"] = enhanced_metadata["rights"]

        if enhanced_metadata.get("short_title"):
            updated["shortTitle"] = enhanced_metadata["short_title"]

        if enhanced_metadata.get("series"):
            updated["series"] = enhanced_metadata["series"]

        if enhanced_metadata.get("edition"):
            updated["edition"] = enhanced_metadata["edition"]

        if enhanced_metadata.get("place"):
            updated["place"] = enhanced_metadata["place"]

        # Build "Extra" field for additional metadata
        extra_parts = []

        # Preserve existing Extra field content
        existing_extra = updated.get("extra", "")
        if existing_extra:
            extra_parts.append(existing_extra)

        # Add citation count
        if enhanced_metadata.get("citation_count") is not None:
            extra_parts.append(f"Citation Count: {enhanced_metadata['citation_count']}")

        # Add subjects/keywords
        for subject in enhanced_metadata.get("subjects", []):
            extra_parts.append(f"Subject: {subject}")

        # Add funders
        for funder in enhanced_metadata.get("funders", []):
            extra_parts.append(f"Funder: {funder}")

        # Add PDF URL
        if enhanced_metadata.get("pdf_url"):
            extra_parts.append(f"Full-text PDF: {enhanced_metadata['pdf_url']}")

        # Update Extra field
        if extra_parts:
            updated["extra"] = "\n".join(extra_parts)
        elif "extra" in updated:
            # Remove empty Extra field
            del updated["extra"]

        # Item type (overwrite if current is generic)
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
        # Compare key fields including enhanced fields
        key_fields = [
            "DOI", "title", "creators", "publicationTitle", "journalAbbreviation",
            "publisher", "date", "volume", "issue", "pages",
            "abstractNote", "url", "ISSN", "itemType",
            # Additional fields
            "language", "rights", "shortTitle", "series", "edition", "place", "extra",
        ]
        for field in key_fields:
            if current.get(field) != updated.get(field):
                return True
        return False

    def _add_ai_metadata_tag(self, item_data: dict[str, Any]) -> dict[str, Any]:
        """Add AI元数据 tag to item."""
        updated = item_data.copy()

        # Get existing tags - always convert to dict format [{"tag": "name"}, ...]
        existing_tags = updated.get("tags", [])
        if isinstance(existing_tags[0], dict) if existing_tags else False:
            # Tags are already in dict format
            tag_list = [t.get("tag", "") for t in existing_tags]
        else:
            # Tags are in string format - convert to dict format
            existing_tags = [{"tag": tag} for tag in existing_tags]
            tag_list = existing_tags

        # Add AI元数据 tag if not present
        if AI_METADATA_TAG not in tag_list:
            existing_tags.append({"tag": AI_METADATA_TAG})
            updated["tags"] = existing_tags

        return updated

    async def _get_all_items(
        self, scan_limit: int = 100, treated_limit: int | None = None
    ) -> list[dict[str, Any]]:
        """Get all items from the library with batch scanning in collection order."""
        logger.info(
            f"Fetching items from all collections in order (batch: {scan_limit}, max: {treated_limit or 'all'})"
        )

        all_items = []
        seen_keys = set()

        # Get collections sorted by name
        collections = await self.item_service.get_sorted_collections()

        for coll in collections:
            # Check if we've reached the treated_limit
            if treated_limit and len(all_items) >= treated_limit:
                break

            coll_key = coll["key"]
            coll_name = coll.get("data", {}).get("name", "")
            logger.info(f"Scanning collection: {coll_name}")

            # Keep fetching batches from this collection until treated_limit or exhausted
            offset = 0
            collection_count = 0
            while True:
                # Check if we've reached the treated_limit
                if treated_limit and len(all_items) >= treated_limit:
                    break

                # Fetch batch from API
                items = await self.item_service.get_collection_items(
                    coll_key, limit=scan_limit, start=offset
                )

                if not items:
                    break  # No more items in this collection

                # Filter duplicates and convert to dict
                for item in items:
                    if item.key not in seen_keys:
                        seen_keys.add(item.key)
                        collection_count += 1
                        all_items.append(
                            {
                                "key": item.key,
                                "data": {
                                    "title": item.title,
                                    "DOI": item.doi,
                                    "url": item.url,
                                },
                            }
                        )

                        # Check if we've reached the treated_limit
                        if treated_limit and len(all_items) >= treated_limit:
                            break

                # If we got fewer items than scan_limit, we've exhausted this collection
                if len(items) < scan_limit:
                    break

                offset += scan_limit

            logger.info(f"  Collection '{coll_name}': {collection_count} items")

        logger.info(f"Retrieved {len(all_items)} items from all collections")
        return all_items

    async def _get_collection_items_batch(
        self,
        collection_key: str,
        scan_limit: int = 100,
        treated_limit: int | None = None,
    ) -> list[dict[str, Any]]:
        """Get items from a collection with batch scanning."""
        all_items = []
        offset = 0
        seen_keys = set()

        while True:
            # Check if we've reached the treated_limit
            if treated_limit and len(all_items) >= treated_limit:
                break

            # Fetch batch from API
            items = await self.item_service.get_collection_items(
                collection_key, limit=scan_limit, start=offset
            )

            if not items:
                break  # No more items

            # Filter duplicates and convert to dict
            for item in items:
                if item.key not in seen_keys:
                    seen_keys.add(item.key)
                    all_items.append(
                        {
                            "key": item.key,
                            "data": {
                                "title": item.title,
                                "DOI": item.doi,
                                "url": item.url,
                            },
                        }
                    )

                    # Check if we've reached the treated_limit
                    if treated_limit and len(all_items) >= treated_limit:
                        break

            # If we got fewer items than scan_limit, we've exhausted the collection
            if len(items) < scan_limit:
                break

            offset += scan_limit

        logger.info(
            f"Retrieved {len(all_items)} items from collection in batches of {scan_limit}"
        )
        return all_items
