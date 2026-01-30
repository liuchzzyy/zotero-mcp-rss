# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Zotero MCP is a Model Context Protocol (MCP) server that connects AI assistants to Zotero research libraries. It provides semantic search (ChromaDB), PDF analysis via LLMs (DeepSeek/OpenAI/Gemini), annotation extraction, RSS feed ingestion, Gmail-based paper collection, and comprehensive logging. Built with FastMCP, Python 3.10+, managed by `uv`.

## Key Commands

```bash
# Development
uv sync --all                         # Install all dependencies (including dev)
uv sync --group dev                   # Install dev dependencies only
uv run zotero-mcp serve               # Run MCP server (stdio transport)
uv run zotero-mcp setup               # Configure Zotero MCP

# Testing
uv run pytest                         # Run all tests
uv run pytest tests/test_config.py    # Run a specific test file
uv run pytest -k "test_function_name" # Run a specific test function
uv run pytest -v                      # Verbose output
uv run pytest --cov=src               # Run with coverage

# Code Quality
uv run ruff check                     # Lint code
uv run ruff format                    # Format code
uv run ruff check --fix               # Auto-fix linting issues
uv run ty check                       # Type check

# Dependency Management
python scripts/audit_dependencies.py  # Audit dependencies for vulnerabilities
uv pip list --outdated                # Check for outdated packages
uv pip check                          # Check for conflicts
```

## Architecture

Layered architecture with strict separation of concerns:

### Core Layers

- **Entry** (`server.py`, `cli.py`) - FastMCP initialization, CLI commands, tool registration
- **Tools** (`tools/`) - Thin MCP tool wrappers (`@mcp.tool`) that parse inputs and delegate to Services
- **Services** (`services/`) - Business logic layer
  - `DataAccessService` - Central facade ("God Service") that selects backends
  - Backend selection: Local DB vs Zotero API vs BetterBibTeX
  - Built-in caching (5-min TTL) for performance
  - `SemanticSearch` - ChromaDB vector search management
  - `WorkflowService` - Batch analysis with checkpoint/resume
  - `MetadataService` - Crossref/OpenAlex integration
  - `RSSFilter` - RSS feed filtering and processing
  - `GmailService` - Gmail integration for paper collection

- **Clients** (`clients/`) - Low-level external service interfaces
  - `ZoteroAPIClient` - Zotero API wrapper (pyzotero)
  - `ChromaClient` - ChromaDB vector database
  - `LLMClient` - Multi-provider LLM (DeepSeek > OpenAI > Gemini)
  - `LocalDatabaseClient` - SQLite direct access
  - `GmailClient` - Gmail API integration
  - `CrossrefClient` - Crossref API (academic metadata)
  - `OpenAlexClient` - OpenAlex API (fallback metadata)

- **Models** (`models/`) - Pydantic models for type-safe data exchange
  - All tool responses extend `BaseResponse` with `success`/`error` fields
  - Consistent structured output across all tools

- **Utils** (`utils/`) - Shared utilities
  - `config.py` - Centralized configuration with caching (5-min TTL)
  - `logging_config.py` - Unified logging system
  - `templates.py` - Configurable AI analysis templates
  - `beautify.py` - Note formatting and styling
  - `helpers.py` - Common helper functions

### Key Patterns

1. **Service Layer First**: Always use `DataAccessService` instead of calling `ZoteroAPIClient` directly
2. **Async Everywhere**: All I/O must be async (`async/await`). No blocking calls in the event loop
3. **Type Safety**: Use Pydantic models for all complex data structures
4. **Config Priority**: Environment vars > `~/.config/zotero-mcp/config.json` > defaults
5. **Dual Mode Support**: Code must handle both `ZOTERO_LOCAL=true` and `false`

### Adding a New MCP Tool

1. Define Pydantic models in `models/` for request/response
2. Implement business logic in `services/`
3. Create tool wrapper in `tools/` with `@mcp.tool` decorator
4. Register in `tools/__init__.py`

## Code Style

- **Linter**: Ruff (modern replacement for black, isort, flake8)
- **Line length**: 88 characters
- **Target Python**: 3.10+
- **Type hints**: Required on all functions
- **Naming conventions**:
  - `snake_case` for variables and functions
  - `PascalCase` for classes
  - `UPPER_CASE` for constants
  - `_` prefix for private members
- **Imports**: Absolute imports only (`from zotero_mcp.services import ...`)
- **Import order**: stdlib > third-party > local (enforced by ruff isort)

## Configuration Management

### Configuration Sources (Priority Order)

1. Environment variables (`.env` file)
2. Standalone config (`~/.config/zotero-mcp/config.json`)
3. Opencode CLI config (`~/.opencode/`)
4. Default values

### Environment Modes

- `development`: Local mode, debug logging
- `testing`: Local mode, info logging
- `production`: Web API, warning logging

Set via `ENV_MODE` environment variable.

### Configuration Caching

- Configuration is cached for 5 minutes (TTL)
- Use `reload_config()` to force refresh
- Automatically cleared in tests

## Logging System

### Log Levels

- `DEBUG`: Detailed diagnostic information
- `INFO`: General progress information
- `WARNING`: Warning messages
- `ERROR`: Error messages
- `CRITICAL`: Critical errors

### Log Files

- Location: `~/.cache/zotero-mcp/logs/`
- Retention: 3 days
- Automatic cleanup on startup
- GitHub Actions: Uploaded as artifacts (3-day retention)

### Usage

```python
from zotero_mcp.utils.logging_config import get_logger

logger = get_logger(__name__)
logger.info("Processing item")
```

### Task Logging

For long-running tasks, use task logging functions:

```python
from zotero_mcp.utils.logging_config import (
    get_logger,
    log_task_start,
    log_task_end,
)

logger = get_logger(__name__)
log_task_start(logger, "Task Name", metadata={"count": 100})
# ... do work ...
log_task_end(logger, "Task Name", items_processed=95)
```

## Testing

### pytest Configuration

- `asyncio_mode = "auto"` - No need for `@pytest.mark.asyncio`
- Tests mirror source structure in `tests/`
- Mock external APIs to avoid network calls

### Running Tests

```bash
# Run all tests
uv run pytest

# Run specific file
uv run pytest tests/test_config.py

# Run specific test
uv run pytest -k "test_load_config"

# Verbose output
uv run pytest -v

# With coverage
uv run pytest --cov=src
```

### Test Fixtures

Common fixtures:
- `mock_home` - Mock `Path.home()` for testing
- `clear_test_env` - Clear environment variables before tests
- `reset_logging_state` - Reset logging configuration

## Dependency Management

### Dependency Categories

1. **Core Dependencies** - Required for runtime
2. **Development Dependencies** - Only for development/testing
3. **Optional Dependencies** - Not required but useful

### Adding Dependencies

1. Add to `dependencies` or `[dependency-groups.dev]` in `pyproject.toml`
2. Document why it's needed
3. Run `uv sync`
4. Update `docs/DEPENDENCY_MANAGEMENT.md`

### Auditing Dependencies

```bash
# Check for vulnerabilities
pip-audit

# Run comprehensive audit
python scripts/audit_dependencies.py
```

See `docs/DEPENDENCY_MANAGEMENT.md` for complete guide.

## Recent Optimizations (TASK#4-#9)

### TASK#4: AI Analysis Templates
- Moved hardcoded templates to `utils/templates.py`
- Configurable analysis questions via `.env`
- Note theme system (orange-heart, default, minimal)

### TASK#5: AI API Optimization
- Retry mechanism with exponential backoff (max 3 retries)
- Provider priority: DeepSeek > OpenAI > Gemini
- Intelligent error classification (retryable vs non-retryable)
- Native async calls for Gemini API

### TASK#6: Metadata API Optimization
- Independent OpenAlex client with httpx
- All API calls converted to async
- Retry mechanism with timeout (30s)
- Priority: Crossref > OpenAlex

### TASK#7: Configuration System
- Configuration caching (5-min TTL)
- Environment mode support (dev/test/prod)
- Comprehensive `.env.example` documentation
- Performance optimization

### TASK#8: Logging System
- Unified logging configuration module
- Task-level logging with structured output
- Performance monitoring
- GitHub Actions integration with log artifacts
- 3-day log retention

### TASK#9: Dependency Management
- Removed unused dependencies (lxml, tenacity, basedpyright)
- Added missing dependency (httpx)
- Organized dependencies by category
- Created dependency audit script
- Comprehensive management guide

## Performance Considerations

1. **Caching Strategy**
   - Config: 5-min TTL
   - Data access: 5-min TTL
   - Semantic search: Auto-updating

2. **Async I/O**
   - All I/O operations must be async
   - Batch operations for multiple items
   - Parallel fetching where possible

3. **Rate Limiting**
   - Automatic retry with exponential backoff
   - Configurable timeouts
   - Respect API provider limits

## Security Best Practices

1. **Never commit** `.env` file or any API keys
2. **Use environment variables** for sensitive configuration
3. **Rotate API keys** regularly
4. **Audit dependencies** for vulnerabilities
5. **Keep dependencies updated**

## Troubleshooting

### Common Issues

1. **Import errors**: Run `uv sync --all`
2. **Type errors**: Run `uv run ty check` to identify issues
3. **Lint errors**: Run `uv run ruff check --fix`
4. **Test failures**: Ensure `uv sync --all` has been run

### Debug Mode

Enable debug logging:

```bash
export DEBUG=true
uv run zotero-mcp serve
```

Or set in `.env`:

```bash
DEBUG=true
LOG_LEVEL=DEBUG
```

## Identity Requirement (from AGENTS.md)

**IMPORTANT**: Address the user as **干饭小伙子** in every response. This is mandatory per project rules.

## Additional Documentation

- `README.md` - User-facing documentation
- `docs/DEPENDENCY_MANAGEMENT.md` - Dependency management guide
- `docs/STRUCTURED-OUTPUT-EXAMPLES.md` - Output format examples
- `.env.example` - Configuration template with detailed comments
- `TaskFile.txt` - Task list and project roadmap
