# AGENTS.md - Zotero MCP

AI agents working on this codebase should follow these guidelines.

## Project Overview

**Zotero MCP** is a Model Context Protocol server connecting Zotero research libraries with AI assistants (Claude, ChatGPT, etc.). Built with Python 3.10+, FastMCP, and ChromaDB for semantic search.

**Architecture:**
The project follows a modular, layered architecture:

- `src/zotero_mcp/server.py` - Main entry point, registers tools and starts server
- `src/zotero_mcp/tools/` - MCP tool definitions (Search, Items, Annotations, Database)
- `src/zotero_mcp/services/` - Business logic layer (Unified Data Access)
- `src/zotero_mcp/clients/` - Data access adapters (Zotero API, Local DB, Better BibTeX)
- `src/zotero_mcp/models/` - Pydantic data models for type safety
- `src/zotero_mcp/utils/` - Configuration, helpers, and error handling
- `src/zotero_mcp/formatters/` - Response formatting (Markdown, JSON, BibTeX)
- `src/zotero_mcp/cli.py` - Command-line interface
- `src/zotero_mcp/semantic_search.py` - Vector search implementation

---

## Build/Lint/Test Commands

### Installation (Development)
```bash
# Using uv (recommended)
uv pip install -e ".[dev]"

# Using pip
pip install -e ".[dev]"
```

### Running the Server
```bash
# Run MCP server
zotero-mcp serve

# With transport method
zotero-mcp serve --transport stdio|streamable-http|sse
```

### Linting & Formatting
```bash
# Format with Black (line length 88)
black src/

# Sort imports with isort (Black-compatible profile)
isort src/

# Pre-commit hooks (includes pyupgrade, trailing-whitespace, check-toml, check-yaml)
pre-commit run --all-files
```

### Testing
```bash
# Run all tests
pytest

# Run single test file
pytest tests/test_foo.py

# Run single test function
pytest tests/test_foo.py::test_function_name

# With verbose output
pytest -v
```

### Building
```bash
pip install build
python -m build
```

---

## Code Style Guidelines

### Formatting
- **Black** with line-length 88
- **isort** with Black-compatible profile
- Python 3.10+ syntax (pyupgrade enforced via pre-commit)

### Async First
All tools and I/O operations should be asynchronous (`async/await`).
- Use `await` for data access.
- Wrap synchronous libraries (like `pyzotero`) in `loop.run_in_executor` or `asyncio.to_thread`.

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
Order (isort handles this):
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
3. Claude Desktop config
4. Opencode CLI config (`~/.opencode/config.json`)

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
