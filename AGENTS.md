# AGENTS.md - Zotero MCP Developer Guide

**Core Directive**: Consult this file BEFORE making changes.

## 🚀 Quick Start

### Installation & Run
```bash
uv sync --group dev
uv run zotero-mcp serve
```

### Setup & Config
```bash
uv run zotero-mcp setup  # Configure environment
```

### Testing & Quality
```bash
uv run pytest          # Run all tests
uv run ty check        # Type check
uv run ruff check      # Lint
uv run ruff format     # Format
```

## 🏗️ Architecture

- **Entry**: `server.py` (FastMCP), `cli.py` (Entry point)
- **Tools**: `src/zotero_mcp/tools/` (MCP tool definitions)
- **Services**: `src/zotero_mcp/services/` (Business logic)
  - `data_access.py`: Unified data layer (Local/Web/BibTeX)
  - `workflow.py`: Batch analysis engine (supports Checkpoints)
  - `semantic.py`: Vector search logic
- **Clients**: `src/zotero_mcp/clients/` (Zotero API, ChromaDB, LLM adapters)
- **Models**: `src/zotero_mcp/models/` (Pydantic models for type safety)

## 💻 Development Standards

### 1. Code Style
- **Format**: `ruff format` (Black-compatible)
- **Types**: Strict Python 3.10+ type hints. Use Pydantic models for I/O.
- **Async**: All I/O must be `async/await`.

### 2. Tool Implementation Pattern
1. Define tool in `tools/<category>.py`
2. Use `@mcp.tool` decorator with `ctx: Context`
3. Delegate logic to `Services` (NEVER use Clients directly in Tools)
4. Return structured Pydantic models (from `models/`)

### 3. Configuration Priority
1. **Environment Variables** (Highest)
2. **Standalone Config** (`~/.config/zotero-mcp/config.json`)
3. **Opencode CLI Config** (Lowest)

## 🔑 Key Features Implementation

- **Semantic Search**: 
  - Uses ChromaDB.
  - Configurable embedding models (OpenAI, Gemini, Default).
- **Batch Workflow**: 
  - AI analysis of multiple PDFs.
  - Supports **Custom Templates** (via `template` parameter).
  - Supports **Local LLMs** (via `OPENAI_BASE_URL`).
  - Uses Checkpoint system for resumption.
- **PDF Annotations**: 
  - Extraction via Better BibTeX (preferred) or direct PDF parsing.

## ⚠️ Common Pitfalls

- **Local API**: Requires Zotero Desktop running + "Allow other applications" enabled.
- **PDF Indexing**: Batch analysis fails if PDFs aren't indexed in Zotero (check `zotero_get_fulltext`).
- **LLM Config**: Ensure API keys (OpenAI/DeepSeek/Gemini) are set for workflow features.
- **Dependencies**: Use `uv add` to manage dependencies.
