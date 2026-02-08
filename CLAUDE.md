# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Communication Style

**IMPORTANT**: When responding to the user, always address them as **"干饭小伙子"** (which means "Mealtime Young Man" in Chinese) at the beginning of your responses. This is the user's preferred nickname and should be used consistently in all interactions.

Example:
- "干饭小伙子，我已经完成了代码修改..."
- "干饭小伙子，这是你要求的功能..."

## Project Overview

Zotero MCP is a Model Context Protocol (MCP) server that connects AI assistants to Zotero research libraries. It provides semantic search (ChromaDB), PDF analysis via LLMs (DeepSeek/OpenAI/Gemini), annotation extraction, and comprehensive logging.

**Tech Stack:** MCP SDK + FastMCP, Python 3.10+, uv (package manager)

## Key Commands

```bash
# Development
uv sync --all-groups                 # Install all dependencies
uv run zotero-mcp serve             # Run MCP server
uv run zotero-mcp setup             # Configure Zotero MCP

# Semantic Search
uv run zotero-mcp update-db         # Update semantic search database (fast, metadata-only)
uv run zotero-mcp update-db --fulltext  # Update with full-text extraction
uv run zotero-mcp db-status         # Check database status

uv run zotero-mcp scan              # Scan library for unprocessed papers

# Multi-Modal Analysis
uv run zotero-mcp scan --multimodal --llm-provider claude-cli  # Use Claude CLI for image analysis
uv run zotero-mcp scan --no-multimodal --llm-provider deepseek  # Text-only analysis
uv run zotero-mcp scan --llm-provider auto  # Auto-select based on PDF content

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

## Batch Operation Parameters

Several commands support batch scanning with two key parameters:

### `scan_limit`
- **Purpose**: Number of items to fetch per batch from the Zotero API
- **Default**: Varies by command (10-500)
- **Example**: `--scan-limit 100` fetches 100 items at a time from each collection

### `treated_limit`
- **Purpose**: Maximum number of items to actually process (excludes skipped items)
- **Default**: Varies by command (1-1000)
- **Example**: `--treated-limit 20` stops after processing 20 items

### Scanning Logic

**For each collection:**
```python
while processed_count < treated_limit:
    fetch scan_limit items (with pagination offset)
    for each item:
        if item should be skipped (has tag, etc.):
            skip  # Does NOT count towards treated_limit
        else:
            process item
            processed_count += 1

    if fetched items < scan_limit:
        break  # Collection exhausted

    if processed_count >= treated_limit:
        break  # Reached limit, stop all scanning
```

**Key behaviors:**
1. **Collection-level pagination**: Continuously fetches batches within each collection until exhausted
2. **Sequential collection scanning**: Only moves to next collection after current one is fully scanned
3. **Skip logic**: Items with specific tags ("AI分析", "AI元数据") are skipped and don't count towards `treated_limit`
4. **Early termination**: Stops scanning entirely once `treated_limit` is reached

**Command-specific meanings:**

| Command | `scan_limit` | `treated_limit` | Skip Tag | Counts |
|---------|-------------|----------------|----------|--------|
| `scan` | Items per batch | Items needing AI analysis | "AI分析" | Candidates without tag |
| `update-metadata` | Items per batch | Items needing metadata update | "AI元数据" | Items without tag |
| `deduplicate` | Items per batch | **Duplicate items found** | None | Duplicate entries |

**Example:**
```bash
# Scan 100 items at a time, process first 20 needing analysis
uv run zotero-mcp scan --scan-limit 100 --treated-limit 20

# Scan 500 items at a time, process first 1000 needing metadata update
uv run zotero-mcp update-metadata --scan-limit 500 --treated-limit 1000

# Scan 100 items at a time, stop after finding 1 duplicate
uv run zotero-mcp deduplicate --scan-limit 100 --treated-limit 1
```

## Architecture

Layered architecture with strict separation of concerns, organized by domain:

### Entry Layer
- `server.py` - MCP stdio server entrypoint (logseq-mcp aligned)
- `app.py` - FastMCP tool registry (shared by server/CLI)
- `cli.py` - Command-line interface
- `settings.py` - Pydantic Settings (env config)

### Tools Layer (`tools/`)
Thin MCP tool wrappers (`@mcp.tool`) that delegate to Services:
- `annotations.py` - PDF annotation and note tools
- `batch.py` - Batch operation tools
- `collections.py` - Collection management tools
- `database.py` - Semantic search database tools
- `items.py` - Item CRUD tools
- `search.py` - Search tools (keyword, tag, advanced, semantic)
- `workflow.py` - Batch analysis workflow tools

### Services Layer (`services/`)
Business logic organized by domain:

**Domain Services:**
- `zotero/` - Core Zotero operations
  - `ItemService` - CRUD operations, collections, tags
  - `MetadataService` - DOI lookup via Crossref/OpenAlex
  - `SearchService` - Search and semantic search
  - `SemanticSearch` - ChromaDB vector search
- `workflow.py` - Batch analysis with checkpoint/resume
- `data_access.py` - Central facade for backends (Local DB / Zotero API)

### Clients Layer (`clients/`)
External service clients organized by domain:
- `zotero/` - Zotero API, local DB
- `database/` - ChromaDB vector database
- `metadata/` - Crossref, OpenAlex APIs
- `llm/` - LLM providers (DeepSeek, OpenAI, Gemini, Claude CLI)

### Models Layer (`models/`)
Pydantic models organized by domain:
- `common/` - Shared base models (BaseInput, BaseResponse, SearchResponse, etc.)
- `zotero/` - Item/collection/annotation input models
- `workflow/` - Batch operation and analysis models
- `search/` - Search query models
- `database/` - Semantic search models

### Utils Layer (`utils/`)
Utility functions organized by purpose:
- `config/` - Configuration and logging
- `data/` - Data mapping and templates
- `formatting/` - Text formatting and helpers
- `async_helpers/` - Async operations and caching
- `system/` - System utilities and errors

### Formatters Layer (`formatters/`)
Output formatters (Markdown, JSON)

### Key Patterns

1. **Layered Architecture**: Entry → Tools → Services → Clients
2. **Domain Organization**: Each layer organized by domain/purpose
3. **Service Layer First**: Always use services, never call clients directly from tools
4. **Async Everywhere**: All I/O must be async (`async/await`)
5. **Type Safety**: Use Pydantic models for all complex data structures
6. **Config Priority**: Environment vars > `~/.config/zotero-mcp/config.json` > defaults
7. **Absolute Imports**: Always use absolute imports (`from zotero_mcp.services import ...`)

### Data Flow Patterns

- **Tools → Services → Clients**: Tools delegate to Services, which coordinate multiple Clients
- **Backend Selection**: `DataAccessService` auto-selects Local DB (fast reads) vs Zotero API (writes/fallback)
- **Workflow Checkpointing**: `WorkflowService` uses `CheckpointService` for resume-capable batch operations

## Code Style

- **Linter/Formatter**: Ruff
- **Type Checker**: ty
- **Line length**: 88 characters
- **Target Python**: 3.10+
- **Type hints**: Required on all functions
- **Naming**: `snake_case` (variables/functions), `PascalCase` (classes), `UPPER_CASE` (constants)
- **Imports**: Absolute imports only (`from zotero_mcp.services import ...`)

## Code Simplification Best Practices

When working with this codebase, follow these guidelines to maintain code simplicity:

1. **Keep functions focused**: Single responsibility per function. If a function exceeds 50-100 lines, consider breaking it down.

2. **Avoid duplication**: Before writing new code, check if similar patterns exist. Examples:
   - Collection scanning with pagination: Use `scan_collections()`
   - Item conversion: Consolidate duplicate mapping logic
   - Error handling: Use consistent patterns across services

4. **Extract configuration objects**: For functions with many parameters (>5), consider using a dataclass or Pydantic model to group related parameters.

5. **Pipeline pattern**: For multi-step processing (e.g., fetch → validate → transform → save), break down into smaller methods that can be tested independently.

6. **Example - WorkflowService simplification**: The `_analyze_single_item` method was refactored from 185 lines into focused helpers:
   - `_should_skip_item()` - Skip condition checks
   - `_extract_bundle_context()` - Context extraction
   - `_validate_context()` - Context validation
   - `_call_llm_analysis()` - LLM interaction
   - `_delete_old_notes()` - Note cleanup
   - `_generate_html_note()` - Note formatting
   - `_save_note()` - Note persistence

This makes the code more testable, readable, and easier to modify.

## Adding a New MCP Tool

1. Define Pydantic models in `models/` for request/response
2. Implement business logic in `services/`
3. Create tool wrapper in `tools/` with `@mcp.tool` decorator
4. Register in `tools/__init__.py`

## Multi-Modal PDF Analysis

### Overview

The multi-modal analysis feature enables LLMs to analyze PDF content beyond text, including images (figures, charts, diagrams) and tables. This is particularly useful for research papers where visual content contains critical information.

### LLM Provider Capabilities

Different LLM providers have different capabilities:

| Provider | Vision Support | Use Case |
|----------|---------------|----------|
| `claude-cli` | ✅ Yes | Best for papers with figures/charts |
| `deepseek` | ❌ No | Text-only, fastest/cheapest |

### Auto-Selection Logic

When `llm_provider="auto"`:
1. **If PDF has images/tables**: Select `claude-cli` (if available) for multi-modal analysis
2. **If PDF is text-only**: Select `deepseek` for faster, cheaper text analysis
3. **Fallback**: If preferred LLM unavailable, gracefully degrade to available options

### Usage Examples

```bash
# Auto-select based on PDF content
uv run zotero-mcp scan --llm-provider auto --multimodal

# Force Claude CLI for multi-modal analysis
uv run zotero-mcp scan --llm-provider claude-cli --multimodal

# Text-only analysis (skip image extraction)
uv run zotero-mcp scan --llm-provider deepseek --no-multimodal

# Specify collection and limits
uv run zotero-mcp scan \
  --source-collection "00_INBOXS" \
  --treated-limit 10 \
  --llm-provider auto \
  --multimodal
```

### How It Works

1. **Content Extraction**: PyMuPDF extracts text, images (as base64), and tables
2. **Capability Detection**: Checks if selected LLM supports vision
3. **Template Selection**: Uses multi-modal template if LLM supports vision, text-only otherwise
4. **Analysis**: LLM analyzes content with appropriate context
5. **Note Generation**: Creates structured HTML note with figure/table references

### Performance

- **PyMuPDF**: 10x faster than pdfplumber for content extraction
- **Base64 Encoding**: Images encoded inline (no external storage needed)
- **Graceful Degradation**: Text-only LLMs receive placeholders instead of crashing

### Configuration

Multi-modal analysis is controlled by:
- `--multimodal/--no-multimodal`: Enable/disable image/table extraction (default: enabled)
- `--llm-provider`: Select LLM provider or use "auto" for intelligent selection
- LLM capability registry in `clients/llm/capabilities.py`

## Troubleshooting

**Import errors**: Run `uv sync --all-groups`
**Type errors**: Run `uv run ty check`
**Lint errors**: Run `uv run ruff check --fix`
**Debug mode**: Set `DEBUG=true` in `.env` or environment

### Common Gotchas

- **Zotero local API**: Requires Zotero 7+ desktop running with "Allow other applications to communicate" enabled
- **Semantic search empty**: Run `zotero-mcp update-db` to initialize database
- **API timeout**: Default is 45s; may need adjustment for slow networks
- **Creator name errors**: Long author lists are auto-truncated to avoid HTTP 413
- **Zotero API 429 rate limiting (pyzotero)**: pyzotero (v1.8.0) silently swallows HTTP 429 errors — it sets an internal backoff but does NOT raise an exception, returning malformed data instead. This causes `'int' object has no attribute 'get'` crashes in downstream code. The fix is:
  1. **API client layer** (`clients/zotero/api_client.py`): `_check_api_result()` converts int status codes to `RuntimeError` so retry mechanisms can detect "429" and backoff
  2. **Service layer** (`services/zotero/search_service.py`): defensive `isinstance(items, int)` checks return empty results
  3. **Caller layer**: wrap search calls with try/except and retry on 429 as needed

## Additional Documentation

- `README.md` - User-facing documentation
- `CONTRIBUTING.md` - Contribution guidelines (Conventional Commits, PR workflow)
- `.env.example` - Configuration template with detailed comments
- `docs/GITHUB_ACTIONS_GUIDE.md` - Workflow automation guide
