from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel, Field


class RSSItem(BaseModel):
    """Represents a single item/article in an RSS feed."""

    title: str
    link: str
    description: Optional[str] = None
    content: Optional[str] = None
    pub_date: Optional[datetime] = None
    author: Optional[str] = None
    categories: List[str] = Field(default_factory=list)
    guid: Optional[str] = None
    source_title: Optional[str] = None
    source_url: Optional[str] = None


class RSSFeed(BaseModel):
    """Represents a parsed RSS feed."""

    title: str
    link: str
    description: Optional[str] = None
    items: List[RSSItem] = Field(default_factory=list)
    last_updated: Optional[datetime] = None
