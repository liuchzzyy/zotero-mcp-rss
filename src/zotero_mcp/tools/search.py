"""
Search tools for Zotero MCP.

Provides tools for searching the Zotero library:
- zotero_search: Basic keyword search
- zotero_search_by_tag: Tag-based search with include/exclude
- zotero_advanced_search: Multi-field search
- zotero_semantic_search: AI-powered semantic search
- zotero_get_recent: Recently added items
"""

from typing import Literal

from fastmcp import FastMCP, Context

from zotero_mcp.models.common import ResponseFormat
from zotero_mcp.models.search import (
    SearchItemsInput,
    TagSearchInput,
    AdvancedSearchInput,
    SemanticSearchInput,
    RecentItemsInput,
)
from zotero_mcp.services import get_data_service
from zotero_mcp.utils.errors import handle_error


def register_search_tools(mcp: FastMCP) -> None:
    """Register all search tools with the MCP server."""

    @mcp.tool(
        name="zotero_search",
        description="Search for items in your Zotero library by keywords. "
        "Returns matching papers, articles, books, and other items.",
    )
    async def zotero_search(
        query: str,
        limit: int = 20,
        offset: int = 0,
        search_mode: Literal["titleCreatorYear", "everything"] = "titleCreatorYear",
        response_format: Literal["markdown", "json"] = "markdown",
        *,
        ctx: Context,
    ) -> str:
        """
        Search for items in your Zotero library.

        Args:
            query: Search keywords
            limit: Maximum results (1-100)
            offset: Skip this many results for pagination
            search_mode: 'titleCreatorYear' for quick search, 'everything' for full-text
            response_format: Output format ('markdown' or 'json')

        Returns:
            Matching items formatted as markdown or JSON
        """
        try:
            service = get_data_service()
            results = await service.search_items(
                query=query,
                limit=min(limit, 100),
                offset=offset,
                qmode=search_mode,
            )

            formatter = service.get_formatter(ResponseFormat(response_format))
            items_data = [
                {
                    "key": r.key,
                    "title": r.title,
                    "authors": r.authors,
                    "date": r.date,
                    "item_type": r.item_type,
                    "abstract": r.abstract,
                    "doi": r.doi,
                    "tags": r.tags,
                }
                for r in results
            ]

            return formatter.format_search_results(
                items=items_data,
                query=query,
                total=len(results),
                offset=offset,
                limit=limit,
            )

        except Exception as e:
            return handle_error(e, ctx, "search")

    @mcp.tool(
        name="zotero_search_by_tag",
        description="Search items by tags. Supports including required tags and excluding unwanted tags.",
    )
    async def zotero_search_by_tag(
        tags: str,
        exclude_tags: str = "",
        limit: int = 25,
        response_format: Literal["markdown", "json"] = "markdown",
        *,
        ctx: Context,
    ) -> str:
        """
        Search items by tags with include/exclude logic.

        Args:
            tags: Comma-separated list of required tags (AND logic)
            exclude_tags: Comma-separated list of tags to exclude
            limit: Maximum results
            response_format: Output format

        Returns:
            Matching items
        """
        try:
            # Parse tags
            include_tags = [t.strip() for t in tags.split(",") if t.strip()]
            exclude_list = (
                [t.strip() for t in exclude_tags.split(",") if t.strip()]
                if exclude_tags
                else None
            )

            if not include_tags:
                return "Error: Please provide at least one tag to search for."

            service = get_data_service()
            results = await service.search_by_tag(
                tags=include_tags,
                exclude_tags=exclude_list,
                limit=limit,
            )

            formatter = service.get_formatter(ResponseFormat(response_format))
            items_data = [
                {
                    "key": r.key,
                    "title": r.title,
                    "authors": r.authors,
                    "date": r.date,
                    "item_type": r.item_type,
                    "tags": r.tags,
                }
                for r in results
            ]

            tag_query = f"tags={tags}" + (
                f", exclude={exclude_tags}" if exclude_tags else ""
            )
            return formatter.format_search_results(
                items=items_data,
                query=tag_query,
                total=len(results),
            )

        except Exception as e:
            return handle_error(e, ctx, "tag search")

    @mcp.tool(
        name="zotero_advanced_search",
        description="Advanced search with multiple criteria: title, author, year range, item type, tags.",
    )
    async def zotero_advanced_search(
        title: str = "",
        author: str = "",
        year_from: int | None = None,
        year_to: int | None = None,
        item_type: str = "",
        tags: str = "",
        limit: int = 25,
        response_format: Literal["markdown", "json"] = "markdown",
        *,
        ctx: Context,
    ) -> str:
        """
        Advanced search with multiple criteria.

        Args:
            title: Title contains (partial match)
            author: Author name contains
            year_from: Published from year
            year_to: Published to year
            item_type: Filter by type (journalArticle, book, etc.)
            tags: Comma-separated required tags
            limit: Maximum results
            response_format: Output format

        Returns:
            Matching items
        """
        try:
            # Build query from criteria
            query_parts = []
            if title:
                query_parts.append(title)
            if author:
                query_parts.append(author)

            query = " ".join(query_parts) if query_parts else "*"

            service = get_data_service()

            # Get initial results
            results = await service.search_items(
                query=query,
                limit=100,  # Get more for filtering
                qmode="everything",
            )

            # Apply filters
            filtered = []
            for r in results:
                # Year filter
                if year_from or year_to:
                    if r.date:
                        try:
                            year = int(r.date[:4])
                            if year_from and year < year_from:
                                continue
                            if year_to and year > year_to:
                                continue
                        except (ValueError, IndexError):
                            continue
                    else:
                        continue

                # Item type filter
                if item_type and r.item_type != item_type:
                    continue

                # Tag filter
                if tags:
                    required_tags = [t.strip() for t in tags.split(",") if t.strip()]
                    item_tags = r.tags or []
                    if not all(t in item_tags for t in required_tags):
                        continue

                filtered.append(r)
                if len(filtered) >= limit:
                    break

            formatter = service.get_formatter(ResponseFormat(response_format))
            items_data = [
                {
                    "key": r.key,
                    "title": r.title,
                    "authors": r.authors,
                    "date": r.date,
                    "item_type": r.item_type,
                    "abstract": r.abstract,
                    "tags": r.tags,
                }
                for r in filtered
            ]

            # Build query description
            criteria = []
            if title:
                criteria.append(f"title='{title}'")
            if author:
                criteria.append(f"author='{author}'")
            if year_from:
                criteria.append(f"from={year_from}")
            if year_to:
                criteria.append(f"to={year_to}")
            if item_type:
                criteria.append(f"type={item_type}")
            if tags:
                criteria.append(f"tags={tags}")

            query_desc = ", ".join(criteria) if criteria else "all items"

            return formatter.format_search_results(
                items=items_data,
                query=query_desc,
                total=len(filtered),
            )

        except Exception as e:
            return handle_error(e, ctx, "advanced search")

    @mcp.tool(
        name="zotero_semantic_search",
        description="AI-powered semantic search. Finds conceptually similar items using embeddings. "
        "Great for finding papers related to a topic or similar to an abstract.",
    )
    async def zotero_semantic_search(
        query: str,
        limit: int = 10,
        response_format: Literal["markdown", "json"] = "markdown",
        *,
        ctx: Context,
    ) -> str:
        """
        Semantic search using AI embeddings.

        Args:
            query: Natural language query or abstract text
            limit: Maximum results (1-50)
            response_format: Output format

        Returns:
            Conceptually similar items with similarity scores
        """
        try:
            # Import semantic search module
            from zotero_mcp.semantic_search import semantic_search

            results = await semantic_search(
                query=query,
                limit=min(limit, 50),
            )

            if not results:
                return "No results found. Make sure the semantic search database is initialized with 'zotero-mcp update-db'."

            service = get_data_service()
            formatter = service.get_formatter(ResponseFormat(response_format))

            if hasattr(formatter, "format_semantic_results"):
                return formatter.format_semantic_results(
                    items=results,
                    query=query,
                )
            else:
                return formatter.format_search_results(
                    items=results,
                    query=f"semantic: {query}",
                    total=len(results),
                )

        except ImportError:
            return "Error: Semantic search is not available. Run 'zotero-mcp update-db' to initialize."
        except Exception as e:
            return handle_error(e, ctx, "semantic search")

    @mcp.tool(
        name="zotero_get_recent",
        description="Get recently added items from your Zotero library.",
    )
    async def zotero_get_recent(
        limit: int = 10,
        days: int = 30,
        response_format: Literal["markdown", "json"] = "markdown",
        *,
        ctx: Context,
    ) -> str:
        """
        Get recently added items.

        Args:
            limit: Maximum items to return (1-50)
            days: Look back this many days
            response_format: Output format

        Returns:
            Recently added items
        """
        try:
            service = get_data_service()
            results = await service.get_recent_items(
                limit=min(limit, 50),
                days=days,
            )

            formatter = service.get_formatter(ResponseFormat(response_format))
            items_data = [
                {
                    "key": r.key,
                    "title": r.title,
                    "authors": r.authors,
                    "date": r.date,
                    "item_type": r.item_type,
                    "tags": r.tags,
                }
                for r in results
            ]

            return formatter.format_items(
                items=items_data,
                title=f"Recently Added Items (last {days} days)",
            )

        except Exception as e:
            return handle_error(e, ctx, "get recent items")
