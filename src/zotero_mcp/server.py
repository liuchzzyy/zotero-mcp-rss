"""
Zotero MCP Server.

A Model Context Protocol server for Zotero, enabling AI assistants to access
your research library, search for papers, and manage annotations.
"""

from fastmcp import FastMCP

from zotero_mcp.tools import register_all_tools
from zotero_mcp.utils.config import load_config

# Initialize FastMCP server
mcp = FastMCP(
    name="Zotero",
    # description param removed for compatibility
)

# Load configuration
load_config()

# Register all tools
register_all_tools(mcp)


def run() -> None:
    """Run the Zotero MCP server."""
    mcp.run()


if __name__ == "__main__":
    run()
