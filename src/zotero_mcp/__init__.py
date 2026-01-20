"""
Zotero MCP.

A Model Context Protocol server for Zotero research libraries.
"""

from ._version import __version__
from .server import mcp, run

__all__ = ["__version__", "mcp", "run"]
