# AGENTS.md - Zotero MCP

AI agents working on this codebase should follow these guidelines.

## ⚠️ IMPORTANT: Before Starting Work

**DO NOT** immediately start testing, building, or making changes when asked.

**ALWAYS** consult this AGENTS.md file first to understand:

- How to run tests properly
- Build and lint commands
- Code style guidelines
- Project architecture

This ensures you follow the correct procedures for this specific project.

## Project Overview

**Zotero MCP** is a Model Context Protocol server connecting Zotero research libraries with AI assistants (ChatGPT, OpenAI assistants, etc.). Built with Python 3.10+, FastMCP, and ChromaDB for semantic search.

**Architecture:**
The project follows a modular, layered architecture:

- `src/zotero_mcp/server.py` - Main entry point, registers tools and starts server
- `src/zotero_mcp/cli.py` - Command-line interface with argparse subcommands
- `src/zotero_mcp/tools/` - MCP tool definitions (Search, Items, Annotations, Database, Batch)
- `src/zotero_mcp/services/` - Business logic layer
  - `data_access.py`: Unified Data Access (Local DB / Web API / Better BibTeX)
  - `semantic.py`: Vector search logic (ChromaDB wrapper)
  - `batch_workflow.py`: Batch PDF analysis workflow engine
- `src/zotero_mcp/clients/` - Low-level data adapters
  - `zotero_client.py`: Web/Local API client
  - `local_db.py`: Direct SQLite access
  - `better_bibtex.py`: JSON-RPC client
  - `chroma.py`: ChromaDB vector store client
- `src/zotero_mcp/models/` - Pydantic data models for type safety
- `src/zotero_mcp/utils/` - Configuration, helpers, setup, and updater
- `src/zotero_mcp/formatters/` - Response formatting (Markdown, JSON, BibTeX)

---

## Build/Lint/Test Commands

### Installation (Development)

```bash
# Using uv (recommended - modern Python package manager)
uv sync --group dev
```

### Running the Server

```bash
# Run MCP server (using uv)
uv run zotero-mcp serve

# With transport method
uv run zotero-mcp serve --transport stdio|streamable-http|sse

# Or activate venv first, then run directly
# Windows: .venv\Scripts\activate
# Unix/macOS: source .venv/bin/activate
zotero-mcp serve
```

### Linting & Formatting

```bash
# Format code with ruff (replaces black + isort)
uv run ruff format src/

# Lint with ruff (fast Python linter)
uv run ruff check src/
uv run ruff check --fix src/  # Auto-fix issues

# Type check with ty (extremely fast type checker)
uv run ty check
```

### Testing

```bash
# Run all tests
uv run pytest

# Run single test file
uv run pytest tests/test_foo.py

# Run single test function
uv run pytest tests/test_foo.py::test_function_name

# With verbose output
uv run pytest -v

# Run with coverage
uv run pytest --cov=zotero_mcp --cov-report=html

# Note: Test suite is currently minimal. Focus on manual integration testing
# with real Zotero instances (local + web API) when making changes.
```

### Building

```bash
uv build
```

---

## Code Style Guidelines

### Formatting

- **Ruff** for formatting and import sorting (replaces Black + isort)
- Line length: 88
- Python 3.10+ syntax

### Async First

All tools and I/O operations should be asynchronous (`async/await`).

- Use `await` for data access.
- Wrap synchronous libraries (like `pyzotero`) in `loop.run_in_executor` or `asyncio.to_thread`.

### Naming Conventions

**Core Rules:**
- **Variables/Functions**: `snake_case` (e.g., `search_items`, `item_key`)
- **Classes**: `PascalCase` (e.g., `DataAccessService`, `ZoteroItem`)
- **Constants**: `UPPER_CASE` (e.g., `MAX_LIMIT`, `DEFAULT_TIMEOUT`)
- **Private members**: Prefix with `_` (e.g., `_api_client`, `_format_response`)
- **Pydantic models**: Use descriptive names ending in `Input`/`Response` for tool I/O (e.g., `SearchItemsInput`, `SearchResponse`)

**Additional Guidelines:**
- **Avoid shadowing built-ins**: Don't use parameter names like `format`, `type`, `id` - prefer `response_format`, `item_type`, `item_id`
- **Pydantic model inheritance**: All Pydantic models must inherit from `BaseModel` (not bare classes with `Field`)
- **Module-level loggers**: Use `logger = logging.getLogger(__name__)` (lowercase)

**Known Technical Debt (Do not modify without team discussion):**

The following deviations exist in the codebase but are **intentionally left as-is** to avoid breaking changes:

1. **Public internal state in service classes** (affects API stability):
   - `ZoteroSemanticSearch`: `chroma_client`, `zotero_client`, `config_path`, `db_path`, `update_config`
   - `WorkflowService`: `data_service`, `checkpoint_manager`
   - These SHOULD be private (`_` prefix) per convention but are exposed for backward compatibility

2. **Public internal state in client classes**:
   - `ChromaClient`: `client`, `collection`, `embedding_function`
   - `OpenAIEmbeddingFunction`/`GeminiEmbeddingFunction`: `client`, `types`
   - `BetterBibTeXClient`: `headers`, `base_url`
   - Will be refactored in next major version

When working on these files, maintain the current naming to avoid breaking external code that may depend on these attributes.

### Type Annotations

Use modern Python 3.10+ type hints and Pydantic models:

```python
# Preferred
def func(items: list[dict[str, str]]) -> str | None:
    ...

# For data structures, use Pydantic models
from zotero_mcp.models.items import ZoteroItem
def process_item(item: ZoteroItem) -> str:
    ...
```

### Imports

Order (ruff handles this):

1. Standard library
2. Third-party packages
3. Local imports (use absolute imports `zotero_mcp.xxx`)

```python
import asyncio
from typing import Any

from fastmcp import Context, FastMCP

from zotero_mcp.services import get_data_service
from zotero_mcp.utils.errors import handle_error
```

### Docstrings

Use Google-style docstrings:

```python
def format_creators(creators: list[dict[str, str]]) -> str:
    """
    Format creator names into a string.

    Args:
        creators: List of creator objects from Zotero.

    Returns:
        Formatted string with creator names.
    """
```

### Error Handling

- Use unified error handling from `zotero_mcp.utils.errors`.
- Wrap tool logic in `try/except` blocks calling `handle_error`.

```python
try:
    result = await service.do_something()
except Exception as e:
    return handle_error(e, ctx, "operation name")
```

---

## MCP Tool Patterns

### Defining Tools

Register tools in `src/zotero_mcp/tools/` modules using the `@mcp.tool` decorator.
Tools must be `async`.

```python
@mcp.tool(
    name="zotero_search_items",
    description="Search for items in your Zotero library."
)
async def search_items(
    query: str,
    limit: int = 10,
    *,
    ctx: Context
) -> str:
    """Tool implementation."""
    # Implementation...
```

### Data Access

**NEVER** instantiate clients directly in tools. Use the unified `DataAccessService`.

```python
from zotero_mcp.services import get_data_service

service = get_data_service()
items = await service.search_items(query)
```

### Formatting Responses

Use the formatters provided by the service to ensure consistency.

```python
from zotero_mcp.models.common import ResponseFormat

formatter = service.get_formatter(ResponseFormat.MARKDOWN)
return formatter.format_items(items)
```

---

## Environment Variables

Key configuration variables:

- `ZOTERO_LOCAL` - Use local Zotero API (true/false)
- `ZOTERO_API_KEY` - Web API key
- `ZOTERO_LIBRARY_ID` - Library ID
- `ZOTERO_EMBEDDING_MODEL` - Semantic search model (default/openai/gemini)
- `OPENAI_API_KEY`, `GEMINI_API_KEY` - API keys for embeddings

Configuration is handled by `zotero_mcp.utils.config`. It automatically loads from:

1. Environment variables
2. Standalone config (`~/.config/zotero-mcp/config.json`)
3. Opencode CLI config (`~/.opencode/config.json`)

---

## Key Dependencies

- `fastmcp>=2.14.0` - MCP server framework
- `pyzotero>=1.5.0` - Zotero API client
- `chromadb>=0.4.0` - Vector database for semantic search
- `sentence-transformers>=2.2.0` - Default embeddings
- `pydantic>=2.0.0` - Data validation
- `markitdown[pdf]` - PDF to markdown conversion

---

## Common Patterns

### Adding a New Tool

1. Define the tool function in `src/zotero_mcp/tools/<category>.py`
2. Add the `@mcp.tool` decorator
3. Register the tool in `src/zotero_mcp/tools/__init__.py` inside `register_all_tools()`

### Accessing Data

The `DataAccessService` automatically selects the best source:

- **Local DB**: Used for fast read operations and full-text extraction (if enabled).
- **Better BibTeX**: Used for citation keys and PDF annotations.
- **Web API**: Used for write operations or when local access is unavailable.

---

## Common Gotchas

1. **Local API requires Zotero running** with "Allow other applications" enabled
2. **Better BibTeX plugin** recommended for annotation features
3. **ChromaDB database** stored in `~/.config/zotero-mcp/`
4. **Environment variables** loaded from multiple sources; use `utils.config.load_config()` to ensure all are loaded.
