from datetime import datetime

from pydantic import BaseModel, Field


class RSSItem(BaseModel):
    """Represents a single item/article in an RSS feed."""

    title: str
    link: str
    description: str | None = None
    content: str | None = None
    pub_date: datetime | None = None
    author: str | None = None
    categories: list[str] = Field(default_factory=list)
    guid: str | None = None
    source_title: str | None = None
    source_url: str | None = None
    doi: str | None = None


class RSSFeed(BaseModel):
    """Represents a parsed RSS feed."""

    title: str
    link: str
    description: str | None = None
    items: list[RSSItem] = Field(default_factory=list)
    last_updated: datetime | None = None
