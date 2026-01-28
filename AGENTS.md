# AGENTS.md - Zotero MCP Developer Guide

**Core Directive**: Consult this file BEFORE making changes. Commit changes to local git after each modification.

## 🔒 Workflow Mandatory Requirement

**CRITICAL**: After completing any significant task, session, or modification, **YOU MUST SAVE ALL CHANGES TO THE LOCAL GIT REPOSITORY**.

- **Command**: `git add . && git commit -m "feat/fix: <description>"`
- **Frequency**: At the end of every logical unit of work.
- **Goal**: Ensure no progress is lost and the repository state is always clean.

## 🚀 Quick Start

```bash
# Install dependencies
uv sync --group dev

# Run server (dev mode)
uv run zotero-mcp serve

# Run all tests
uv run pytest

# Run a specific test file
uv run pytest tests/test_config.py

# Run a specific test function
uv run pytest -k "test_function_name"

# Run type check
uv run ty check

# Lint and Format
uv run ruff check
uv run ruff format
```

## 🏗️ Architecture

The codebase follows a layered architecture to separate concerns:

| Layer | Path | Description |
|-------|------|-------------|
| **Entry** | `src/zotero_mcp/server.py`, `cli.py` | Application entry points. Initializes `FastMCP` and registers tools. |
| **Tools** | `src/zotero_mcp/tools/` | MCP tool definitions. **Thin wrappers** that parse inputs and call Services. |
| **Services** | `src/zotero_mcp/services/` | Core business logic. Orchestrates Clients and handles complex operations. |
| **Clients** | `src/zotero_mcp/clients/` | Low-level interfaces to external systems (Zotero API, ChromaDB, LLM). |
| **Models** | `src/zotero_mcp/models/` | Pydantic models for type-safe data exchange and validation. |
| **Utils** | `src/zotero_mcp/utils/` | Shared helpers, configuration loading, and caching logic. |

**Key Components:**
- **`data_access.py`**: The "God Service" for data retrieval. Handles caching and backend selection (API vs Local DB).
- **`semantic.py`**: Manages Vector DB (ChromaDB) interactions for semantic search.
- **`workflow.py`**: Manages long-running batch analysis tasks.

## 📏 Code Style Guidelines

### 1. General
- **Formatting**: We use `ruff format`. Keep line length to **88 characters**.
- **Linting**: We use `ruff check`. Fix all warnings before committing.
- **Type Safety**: Strictly use Python type hints. Use `Pydantic` models for all complex data structures, especially tool inputs/outputs.

### 2. Imports
- Use absolute imports for project files: `from zotero_mcp.services import ...`
- Imports are sorted automatically by `ruff`.
- Grouping: Standard Lib > Third Party > Local (`zotero_mcp`).

### 3. Naming Conventions
- **Variables/Functions**: `snake_case` (e.g., `get_item_metadata`)
- **Classes**: `PascalCase` (e.g., `ZoteroAPIClient`)
- **Constants**: `UPPER_CASE` (e.g., `DEFAULT_TIMEOUT`)
- **Private Members**: Prefix with `_` (e.g., `_cache`, `_internal_method`)

### 4. Asynchronous Programming
- **Rule**: All I/O operations (API calls, DB reads, File reads) **MUST** be `async/await`.
- Use `asyncio` for concurrency where appropriate.
- Avoid blocking calls in the main event loop.

### 5. Error Handling
- Use `try/except` blocks in Clients and Services to catch external errors.
- Log errors using `logger.error()` with context.
- Propagate exceptions when the Tool needs to report failure to the LLM, or return a structured error response.

## 🧪 Testing Strategy

- **Unit Tests**: Place in `tests/`. Mirror source structure.
- **Fixtures**: Use `pytest` fixtures for setup/teardown.
- **Mocks**: Mock external APIs (Zotero, OpenAI) to avoid network calls during tests.

## 📝 Common Patterns & Pitfalls

### Pydantic Models
- **Access**: Use dot notation `item.key` instead of dictionary access `item['key']`.
- **Validation**: Let Pydantic handle input validation. define constraints in fields.

### Data Access
- **Preferred Access**: Use `DataAccessService` instead of calling `ZoteroAPIClient` directly in tools.
- **Caching**: `DataAccessService` has internal caching for collections/tags. Be aware of TTL (5 mins).
- **Configuration Validation**: `DataAccessService` validates critical environment variables (`ZOTERO_API_KEY`, `ZOTERO_LIBRARY_ID`) on initialization when running in Web API mode (`ZOTERO_LOCAL=false`). It logs warnings if they are missing.

### Local vs Web API
- Code should handle both `ZOTERO_LOCAL=true` and `false`.
- **Local**: Faster, supports full-text extraction directly from PDF files.
- **Web**: Slower, rate-limited, but works remotely.

### Configuration
- Priority: Environment Vars > `~/.config/zotero-mcp/config.json` > Defaults.
- Do not hardcode API keys or paths.

## 🤖 Agent Instructions
- **When creating a new tool**:
    1. Define Input/Output Pydantic models in `models/`.
    2. Implement logic in a Service (create new service if needed).
    3. Create tool definition in `tools/` using `@mcp.tool`.
    4. Register tool in `tools/__init__.py`.
- **When refactoring**:
    1. Check for duplicate logic (use `grep`).
    2. Ensure no regression in type safety (`uv run ty check`).
