"""
MCP Tools for Zotero.

This module registers all Zotero MCP tools with the FastMCP server.
"""

from fastmcp import FastMCP

from .annotations import register_annotation_tools
from .batch import register_batch_tools
from .collections import register_collection_tools
from .database import register_database_tools
from .items import register_item_tools
from .search import register_search_tools
from .workflow import register_workflow_tools
from .rss import register_rss_tools


def register_all_tools(mcp: FastMCP) -> None:
    """
    Register all Zotero MCP tools.

    Args:
        mcp: FastMCP server instance
    """
    register_search_tools(mcp)
    register_item_tools(mcp)
    register_annotation_tools(mcp)
    register_collection_tools(mcp)
    register_database_tools(mcp)
    register_batch_tools(mcp)
    register_workflow_tools(mcp)
    register_rss_tools(mcp)


__all__ = [
    "register_all_tools",
    "register_search_tools",
    "register_item_tools",
    "register_annotation_tools",
    "register_collection_tools",
    "register_database_tools",
    "register_batch_tools",
    "register_workflow_tools",
    "register_rss_tools",
]
