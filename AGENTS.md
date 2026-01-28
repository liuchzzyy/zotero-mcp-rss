# AGENTS.md - Zotero MCP Developer Guide

**Core Directive**: Consult this file BEFORE making changes. Commit changes to local git after each modification.

## Quick Start

```bash
uv sync --group dev          # Install dependencies
uv run zotero-mcp serve      # Run server
uv run pytest                # Test
uv run ty check              # Type check
uv run ruff check && uv run ruff format  # Lint & format
```

## Architecture

| Layer | Path | Description |
|-------|------|-------------|
| Entry | `server.py`, `cli.py` | FastMCP server, CLI entry |
| Tools | `src/zotero_mcp/tools/` | MCP tool definitions |
| Services | `src/zotero_mcp/services/` | Business logic |
| Clients | `src/zotero_mcp/clients/` | Zotero API, ChromaDB, LLM |
| Models | `src/zotero_mcp/models/` | Pydantic models |
| Scripts | `src/scripts/` | GitHub Actions automation |

**Key Services**: `data_access.py` (unified data layer), `workflow.py` (batch analysis), `semantic.py` (vector search), `rss/` (feed integration)

## Development Standards

1. **Code Style**: `ruff format`, strict type hints, Pydantic for I/O
2. **Async**: All I/O must be `async/await`
3. **Tool Pattern**: `@mcp.tool` → delegate to Services → return Pydantic models
4. **Config Priority**: Environment Variables > `~/.config/zotero-mcp/config.json` > Opencode CLI

## Common Pitfalls

- **Local API**: Requires Zotero Desktop + "Allow other applications" enabled
- **Pydantic Models**: `SearchResultItem` etc. are Pydantic models, use `.attribute` not `.get()`
- **PDF Indexing**: Batch analysis fails if PDFs not indexed (check `zotero_get_fulltext`)
- **Dependencies**: Use `uv add` to manage
