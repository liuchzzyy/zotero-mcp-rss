"""
Zotero data mapping utilities.

This module handles transformation of Zotero items between different formats
(API, Local DB, Semantic Search Documents).
"""

import re
from typing import Any

from zotero_mcp.utils.formatting.helpers import format_creators


class ZoteroMapper:
    """Helper class for mapping Zotero data."""

    @staticmethod
    def create_document_text(item: dict[str, Any]) -> str:
        """
        Create searchable text from a Zotero item.

        Args:
            item: Zotero item dictionary

        Returns:
            Combined text for semantic indexing
        """
        data = item.get("data", {})

        # Extract key fields for semantic search
        title = data.get("title", "")
        abstract = data.get("abstractNote", "")

        # Format creators as text
        creators = data.get("creators", [])
        creators_text = format_creators(creators)

        # Additional searchable content
        extra_fields = []

        # Publication details
        if publication := data.get("publicationTitle"):
            extra_fields.append(publication)

        # Tags
        if tags := data.get("tags"):
            tag_text = " ".join([tag.get("tag", "") for tag in tags])
            extra_fields.append(tag_text)

        # Note content (if available)
        if note := data.get("note"):
            # Clean HTML from notes
            note_text = re.sub(r"<[^>]+>", "", note)
            extra_fields.append(note_text)

        # Combine all text fields
        text_parts = [title, creators_text, abstract] + extra_fields
        return " ".join(filter(None, text_parts))

    @staticmethod
    def create_metadata(item: dict[str, Any]) -> dict[str, Any]:
        """
        Create metadata for a Zotero item for ChromaDB.

        Args:
            item: Zotero item dictionary

        Returns:
            Metadata dictionary
        """
        data = item.get("data", {})

        metadata = {
            "item_key": item.get("key", ""),
            "item_type": data.get("itemType", ""),
            "title": data.get("title", ""),
            "date": data.get("date", ""),
            "date_added": data.get("dateAdded", ""),
            "date_modified": data.get("dateModified", ""),
            "creators": format_creators(data.get("creators", [])),
            "publication": data.get("publicationTitle", ""),
            "url": data.get("url", ""),
            "doi": data.get("DOI", ""),
        }
        # If local fulltext field exists, add markers so we can filter later
        if data.get("fulltext"):
            metadata["has_fulltext"] = True
            if data.get("fulltextSource"):
                metadata["fulltext_source"] = data.get("fulltextSource")

        # Add tags as a single string
        if tags := data.get("tags"):
            metadata["tags"] = " ".join([tag.get("tag", "") for tag in tags])
        else:
            metadata["tags"] = ""

        # Add citation key if available
        extra = data.get("extra", "")
        citation_key = ""
        for line in extra.split("\n"):
            if line.lower().startswith(("citation key:", "citationkey:")):
                citation_key = line.split(":", 1)[1].strip()
                break
        metadata["citation_key"] = citation_key

        return metadata

    @staticmethod
    def parse_creators_string(creators_str: str | None) -> list[dict[str, str]]:
        """
        Parse creators string from local DB into API format.

        Args:
            creators_str: Semicolon-separated creators string (e.g. "Smith, John; Doe, Jane")

        Returns:
            List of creator dictionaries
        """
        if not creators_str:
            return []

        creators = []
        for creator in creators_str.split(";"):
            creator = creator.strip()
            if not creator:
                continue

            if "," in creator:
                last, first = creator.split(",", 1)
                creators.append(
                    {
                        "creatorType": "author",
                        "firstName": first.strip(),
                        "lastName": last.strip(),
                    }
                )
            else:
                creators.append(
                    {
                        "creatorType": "author",
                        "name": creator,
                    }
                )

        return creators


# Convenience function for backward compatibility
def map_zotero_item(item: dict[str, Any]) -> tuple[str, dict[str, Any]]:
    """
    Map a Zotero item to document text and metadata.

    This is a convenience function that creates a ZoteroMapper instance
    and calls both create_document_text and create_metadata.

    Args:
        item: Zotero item dictionary

    Returns:
        Tuple of (document_text, metadata)
    """
    mapper = ZoteroMapper()
    document_text = mapper.create_document_text(item)
    metadata = mapper.create_metadata(item)
    return document_text, metadata
