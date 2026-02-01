from fastmcp import Context, FastMCP
from pydantic import BaseModel, Field

from zotero_mcp.models.ingestion import RSSFeed
from zotero_mcp.services.rss.rss_fetcher import RSSFetcher

# Initialize the fetcher globally
rss_fetcher = RSSFetcher()


class RSSFeedRequest(BaseModel):
    url: str = Field(..., description="The URL of the RSS feed to fetch")


class OPMLRequest(BaseModel):
    path: str = Field(..., description="Path to the OPML file containing feed URLs")


class RSSResponse(BaseModel):
    success: bool
    data: RSSFeed | None = None
    error: str | None = None


class MultiRSSResponse(BaseModel):
    success: bool
    count: int
    feeds: list[RSSFeed] = Field(default_factory=list)
    error: str | None = None


def register_rss_tools(mcp: FastMCP) -> None:
    """Register RSS tools with the MCP server."""

    @mcp.tool()
    async def rss_fetch_feed(url: str, ctx: Context) -> RSSResponse:
        """Fetch and parse a single RSS feed.

        Args:
            url: The URL of the RSS feed.
        """
        try:
            feed = await rss_fetcher.fetch_feed(url)
            if not feed:
                return RSSResponse(success=False, error="Failed to fetch or parse feed")

            return RSSResponse(success=True, data=feed)
        except Exception as e:
            return RSSResponse(success=False, error=str(e))

    @mcp.tool()
    async def rss_fetch_from_opml(path: str, ctx: Context) -> MultiRSSResponse:
        """Fetch multiple RSS feeds from an OPML file.

        Args:
            path: Absolute path to the OPML file.
        """
        try:
            feeds = await rss_fetcher.fetch_feeds_from_opml(path)
            return MultiRSSResponse(success=True, count=len(feeds), feeds=feeds)
        except Exception as e:
            return MultiRSSResponse(success=False, count=0, error=str(e))
