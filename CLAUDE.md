# CLAUDE.md

This file provides guidance for Claude Code (claude.ai/code) when working with this repository.

## Project Overview

Zotero MCP is a Model Context Protocol (MCP) server that connects AI assistants to Zotero research libraries. It provides semantic search (ChromaDB), PDF analysis via LLMs (DeepSeek/OpenAI/Gemini), annotation extraction, RSS feed ingestion, Gmail-based paper collection, and comprehensive logging.

**Tech Stack:** FastMCP, Python 3.10+, uv (package manager)

## Key Commands

```bash
# Development
uv sync --all-groups                 # Install all dependencies
uv run zotero-mcp serve             # Run MCP server
uv run zotero-mcp setup             # Configure Zotero MCP

# Testing
uv run pytest                       # Run all tests
uv run pytest -v                    # Verbose output
uv run pytest --cov=src             # With coverage

# Code Quality
uv run ruff check                   # Lint code
uv run ruff format                  # Format code
uv run ruff check --fix             # Auto-fix issues
uv run ty check                     # Type check
```

## Architecture

Layered architecture with strict separation of concerns:

- **Entry** (`server.py`, `cli.py`) - FastMCP initialization, CLI commands
- **Tools** (`tools/`) - Thin MCP tool wrappers (`@mcp.tool`) that delegate to Services
- **Services** (`services/`) - Business logic layer
  - `DataAccessService` - Central facade for backends (Local DB / Zotero API)
  - `SemanticSearch` - ChromaDB vector search
  - `WorkflowService` - Batch analysis with checkpoint/resume
  - `RSSService` / `GmailService` - Feed and email processing
- **Clients** (`clients/`) - Low-level external service interfaces (Zotero API, ChromaDB, LLMs)
- **Models** (`models/`) - Pydantic models for type-safe data exchange
- **Formatters** (`formatters/`) - Output formatters (Markdown, JSON, BibTeX)
- **Utils** (`utils/`) - Shared utilities (config, logging, templates)

### Key Patterns

1. **Service Layer First**: Always use `DataAccessService` instead of calling clients directly
2. **Async Everywhere**: All I/O must be async (`async/await`)
3. **Type Safety**: Use Pydantic models for all complex data structures
4. **Config Priority**: Environment vars > `~/.config/zotero-mcp/config.json` > defaults

## Code Style

- **Linter/Formatter**: Ruff
- **Type Checker**: ty
- **Line length**: 88 characters
- **Target Python**: 3.10+
- **Type hints**: Required on all functions
- **Naming**: `snake_case` (variables/functions), `PascalCase` (classes), `UPPER_CASE` (constants)
- **Imports**: Absolute imports only (`from zotero_mcp.services import ...`)

## Adding a New MCP Tool

1. Define Pydantic models in `models/` for request/response
2. Implement business logic in `services/`
3. Create tool wrapper in `tools/` with `@mcp.tool` decorator
4. Register in `tools/__init__.py`

## Troubleshooting

**Import errors**: Run `uv sync --all-groups`
**Type errors**: Run `uv run ty check`
**Lint errors**: Run `uv run ruff check --fix`
**Debug mode**: Set `DEBUG=true` in `.env` or environment

## Additional Documentation

- `README.md` - User-facing documentation
- `CHANGELOG.md` - Version history
- `CONTRIBUTING.md` - Contribution guidelines
- `.env.example` - Configuration template with detailed comments
