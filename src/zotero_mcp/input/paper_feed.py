"""Input schema for paper-feed Zotero adapter payloads."""

from __future__ import annotations

from datetime import date, datetime
from typing import Any

from pydantic import BaseModel, Field


class PaperFeedItem(BaseModel):
    """Paper-feed universal item (mirrors paper_feed.core.models.PaperItem)."""

    title: str
    authors: list[str] = Field(default_factory=list)
    abstract: str = Field(default="")
    published_date: date | None = None
    doi: str | None = None
    url: str | None = None
    pdf_url: str | None = None
    source: str
    source_id: str | None = None
    source_type: str
    categories: list[str] = Field(default_factory=list)
    tags: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)

    def to_zotero_item(self) -> dict[str, Any]:
        """Convert to Zotero API item payload (journalArticle)."""
        creators = [
            {"creatorType": "author", "name": author} for author in self.authors
        ]
        tags = [{"tag": tag} for tag in self.tags]
        date_str = self.published_date.isoformat() if self.published_date else None

        item = {
            "itemType": "journalArticle",
            "title": self.title,
            "creators": creators,
            "abstractNote": self.abstract,
            "url": self.url,
            "DOI": self.doi,
            "date": date_str,
            "tags": tags,
            "accessDate": datetime.now().strftime("%Y-%m-%d"),
        }

        return {k: v for k, v in item.items() if v not in (None, "", [])}


class PaperFeedZoteroBatchInput(BaseModel):
    """Batch input compatible with paper-feed Zotero adapter."""

    papers: list[PaperFeedItem] = Field(default_factory=list)
    collection_id: str | None = Field(default=None, description="Zotero collection key")

    def to_zotero_items(self) -> list[dict[str, Any]]:
        """Convert all items to Zotero payloads."""
        return [paper.to_zotero_item() for paper in self.papers]
