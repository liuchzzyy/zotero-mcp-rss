"""MCP Server entry point with logseq-aligned architecture."""

from __future__ import annotations

import asyncio
from collections.abc import Sequence

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import Prompt, TextContent, Tool

from zotero_mcp.handlers import PromptHandler, ToolHandler
from zotero_mcp.settings import settings
from zotero_mcp.utils.config import load_config
from zotero_mcp.utils.config.logging import initialize_logging


async def serve() -> None:
    """Run the Zotero MCP server."""
    initialize_logging()
    load_config()

    server = Server(settings.server_name)
    tool_handler = ToolHandler()
    prompt_handler = PromptHandler()

    @server.list_tools()
    async def list_tools() -> list[Tool]:
        return tool_handler.get_tools()

    @server.call_tool()
    async def call_tool(name: str, arguments: dict) -> Sequence[TextContent]:
        return await tool_handler.handle_tool(name, arguments)

    @server.list_prompts()
    async def list_prompts() -> list[Prompt]:
        return prompt_handler.get_prompts()

    @server.get_prompt()
    async def get_prompt(name: str, arguments: dict | None):
        return await prompt_handler.handle_prompt(name, arguments)

    options = server.create_initialization_options()
    async with stdio_server() as (read_stream, write_stream):
        await server.run(read_stream, write_stream, options, raise_exceptions=True)


def run() -> None:
    """Run the Zotero MCP server."""
    asyncio.run(serve())


if __name__ == "__main__":
    run()
