# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Zotero MCP is a Model Context Protocol (MCP) server that connects AI assistants to Zotero research libraries. It provides semantic search (ChromaDB), PDF analysis via LLMs (DeepSeek/OpenAI/Gemini), annotation extraction, RSS feed ingestion, and Gmail-based paper collection. Built with FastMCP, Python 3.10+, managed by `uv`.

## Key Commands

```bash
uv sync --group dev                    # Install all dependencies
uv run zotero-mcp serve                # Run MCP server (stdio transport)
uv run pytest                          # Run all tests
uv run pytest tests/test_config.py     # Run a specific test file
uv run pytest -k "test_function_name"  # Run a specific test function
uv run ruff check                      # Lint
uv run ruff format                     # Format
uv run ty check                        # Type check
```

## Architecture

Layered architecture with strict separation:

- **Entry** (`server.py`, `cli.py`) - FastMCP initialization, CLI commands, tool registration
- **Tools** (`tools/`) - Thin MCP tool wrappers (`@mcp.tool`) that parse inputs and delegate to Services
- **Services** (`services/`) - Business logic. `DataAccessService` is the central facade ("God Service") that selects backends (Local DB vs Zotero API vs BetterBibTeX) and handles caching (5-min TTL). `SemanticSearch` manages ChromaDB. `WorkflowService` handles batch analysis with checkpoint/resume.
- **Clients** (`clients/`) - Low-level interfaces: `ZoteroAPIClient` (pyzotero), `ChromaClient` (ChromaDB), `LLMClient` (multi-provider), `LocalDatabaseClient` (SQLite), `GmailClient`, `CrossrefClient`
- **Models** (`models/`) - Pydantic models for all data exchange. All tool responses extend `BaseResponse` with `success`/`error` fields.
- **Utils** (`utils/`) - Config loading, caching, HTML beautification, markdown conversion

### Key Patterns

- **Always use `DataAccessService`** instead of calling `ZoteroAPIClient` directly from tools
- **All I/O must be async** (`async/await`). No blocking calls in the event loop.
- **Adding a new MCP tool**: Define Pydantic models in `models/`, implement logic in `services/`, create tool in `tools/` with `@mcp.tool`, register in `tools/__init__.py`
- **Config priority**: Environment vars (`.env`) > `~/.config/zotero-mcp/config.json` > defaults
- **Local vs Web API**: Code must handle both `ZOTERO_LOCAL=true` (faster, direct PDF access) and `false` (remote, rate-limited)

## Code Style

- Ruff for linting and formatting, 88-char line length, target py310
- Type hints required on all functions. Pydantic models for complex data structures.
- `snake_case` (vars/functions), `PascalCase` (classes), `UPPER_CASE` (constants), `_` prefix for private members
- Absolute imports: `from zotero_mcp.services import ...`
- Import order: stdlib > third-party > local (enforced by ruff isort)

## Testing

- pytest with `asyncio_mode = "auto"` (no need for `@pytest.mark.asyncio`)
- Mock external APIs (Zotero, OpenAI) to avoid network calls
- Tests in `tests/`, mirroring source structure

## Identity Requirement (from AGENTS.md)

Address the user as **干饭小伙子** in every response. This is mandatory per project rules.
