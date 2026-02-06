"""
MCP Tools registration for the integration layer.

Wraps integration modules as MCP tools for AI assistants.
"""

from __future__ import annotations

from typing import List, Optional

from fastmcp import FastMCP

from zotero_mcp.integration.analyzer_integration import AnalyzerIntegration
from zotero_mcp.integration.zotero_integration import ZoteroIntegration


class MCPTools:
    """
    MCP tool wrapper that registers integration modules as MCP tools.

    Usage:
        config = get_config()
        zotero = ZoteroIntegration(config)
        analyzer = AnalyzerIntegration(config) if config.has_llm else None
        tools = MCPTools(zotero=zotero, analyzer=analyzer)
        tools.register_tools(mcp)
    """

    def __init__(
        self,
        zotero: ZoteroIntegration,
        analyzer: Optional[AnalyzerIntegration] = None,
    ):
        self.zotero = zotero
        self.analyzer = analyzer

    def register_tools(self, mcp: FastMCP) -> None:
        """Register all MCP tools."""
        self._register_item_tools(mcp)
        self._register_collection_tools(mcp)
        self._register_search_tools(mcp)
        if self.analyzer:
            self._register_analysis_tools(mcp)

    def _register_item_tools(self, mcp: FastMCP) -> None:
        """Register Zotero item tools."""
        zotero = self.zotero

        @mcp.tool()
        async def get_items(
            limit: int = 25,
            collection_key: Optional[str] = None,
            tag: Optional[str] = None,
        ) -> str:
            """
            Get Zotero items list.

            Args:
                limit: Maximum number of items to return
                collection_key: Filter by collection key
                tag: Filter by tag
            """
            items = await zotero.get_items(
                limit=limit,
                collection_key=collection_key,
                tag=tag,
            )
            return zotero.format_items(items)

        @mcp.tool()
        async def get_item(item_key: str) -> str:
            """
            Get detailed info for a single Zotero item.

            Args:
                item_key: Zotero item key (8-character alphanumeric)
            """
            item = await zotero.get_item(item_key)
            return zotero.format_item(item)

        @mcp.tool()
        async def create_item(
            item_type: str,
            title: str,
            creators: Optional[List[str]] = None,
            abstract: Optional[str] = None,
            doi: Optional[str] = None,
            url: Optional[str] = None,
            collection_keys: Optional[List[str]] = None,
        ) -> str:
            """
            Create a new Zotero item.

            Args:
                item_type: Item type (journalArticle, book, etc.)
                title: Title
                creators: Author names
                abstract: Abstract text
                doi: DOI
                url: URL
                collection_keys: Collection keys to add item to
            """
            item = await zotero.create_item(
                item_type=item_type,
                title=title,
                creators=creators,
                abstract=abstract,
                doi=doi,
                url=url,
                collection_keys=collection_keys,
            )
            key = item.get("key", "unknown")
            return f"Created item: {key} - {title}"

    def _register_collection_tools(self, mcp: FastMCP) -> None:
        """Register collection management tools."""
        zotero = self.zotero

        @mcp.tool()
        async def get_collections() -> str:
            """Get all Zotero collections."""
            collections = await zotero.get_collections()
            return zotero.format_collections(collections)

        @mcp.tool()
        async def create_collection(
            name: str,
            parent_collection_key: Optional[str] = None,
        ) -> str:
            """
            Create a Zotero collection.

            Args:
                name: Collection name
                parent_collection_key: Parent collection key
            """
            coll = await zotero.create_collection(
                name=name,
                parent_collection_key=parent_collection_key,
            )
            key = coll.get("key", "unknown")
            return f"Created collection: {key} - {name}"

    def _register_search_tools(self, mcp: FastMCP) -> None:
        """Register search tools."""
        zotero = self.zotero

        @mcp.tool()
        async def search_items(query: str, limit: int = 25) -> str:
            """
            Search Zotero items by keyword.

            Args:
                query: Search keywords
                limit: Maximum results
            """
            results = await zotero.search(query, limit)
            return zotero.format_items(results)

    def _register_analysis_tools(self, mcp: FastMCP) -> None:
        """Register PDF analysis tools."""
        analyzer = self.analyzer
        if not analyzer:
            return

        @mcp.tool()
        async def analyze_paper(
            file_path: str,
            template_name: str = "default",
            extract_images: bool = False,
        ) -> str:
            """
            Analyze a PDF paper using LLM.

            Args:
                file_path: Path to PDF file
                template_name: Template name (default, multimodal, structured)
                extract_images: Whether to extract images for multi-modal analysis
            """
            result = await analyzer.analyze_pdf(
                file_path=file_path,
                template_name=template_name,
                extract_images=extract_images,
            )
            return analyzer.format_result(result)

        @mcp.tool()
        async def analyze_text(
            text: str,
            title: str = "Untitled",
            template_name: str = "default",
        ) -> str:
            """
            Analyze paper text using LLM (no PDF extraction).

            Args:
                text: Paper text content
                title: Paper title
                template_name: Template name
            """
            result = await analyzer.analyze_text(
                text=text,
                title=title,
                template_name=template_name,
            )
            return analyzer.format_result(result)
