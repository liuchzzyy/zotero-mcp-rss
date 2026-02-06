"""
Integration layer for zotero-mcp v3.

Wraps zotero-core, paper-analyzer, and semantic search modules
into a unified MCP tools interface.
"""

from zotero_mcp.integration.mcp_tools import MCPTools
from zotero_mcp.integration.zotero_integration import ZoteroIntegration
from zotero_mcp.integration.analyzer_integration import AnalyzerIntegration

__all__ = [
    "MCPTools",
    "ZoteroIntegration",
    "AnalyzerIntegration",
]
