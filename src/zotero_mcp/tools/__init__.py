"""
MCP Tools for Zotero.

This module registers all Zotero MCP tools with the FastMCP server.
"""

from fastmcp import FastMCP

from .search import register_search_tools
from .items import register_item_tools
from .annotations import register_annotation_tools
from .database import register_database_tools


def register_all_tools(mcp: FastMCP) -> None:
    """
    Register all Zotero MCP tools.

    Args:
        mcp: FastMCP server instance
    """
    register_search_tools(mcp)
    register_item_tools(mcp)
    register_annotation_tools(mcp)
    register_database_tools(mcp)


__all__ = [
    "register_all_tools",
    "register_search_tools",
    "register_item_tools",
    "register_annotation_tools",
    "register_database_tools",
]
