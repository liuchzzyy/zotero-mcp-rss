# Release Notes: v3.0.0 - Modular Architecture

## Summary

Zotero MCP v3.0 introduces a modular architecture, splitting the monolithic codebase into four independent, installable modules. Each module can be used standalone or as part of the full stack.

## New Modules

### paper-feed v1.0.0
Academic paper collection framework.
- RSS feed parsing (arXiv, bioRxiv, Nature, Science, and more)
- Multi-stage filter pipeline (keywords, categories, authors, dates)
- Export adapters (JSON, Zotero)
- OPML file support

### zotero-core v1.0.0
Zotero data access library.
- Complete CRUD operations via Zotero Web API
- Keyword, tag, fulltext, and advanced search
- Semantic search with ChromaDB (optional)
- Hybrid search with Reciprocal Rank Fusion (RRF)
- Pydantic v2 models with full type safety

### paper-analyzer v1.0.0
PDF analysis engine.
- Fast PDF extraction with PyMuPDF (10x faster than pdfplumber)
- Multi-modal support (text + images + tables)
- Multiple LLM providers (DeepSeek, OpenAI-compatible)
- 3 built-in analysis templates (default, multimodal, structured)
- Checkpoint-based batch processing

### zotero-mcp v3.0.0
Lightweight MCP integration layer.
- Bridges all modules into MCP tools
- Unified configuration via `.env` files
- Pydantic-based config with environment variable support

## Test Coverage

| Module | Tests | Status |
|--------|-------|--------|
| paper-feed | 10+ tests | All passing |
| zotero-core | 50+ tests | All passing |
| paper-analyzer | 39 tests | All passing |
| zotero-mcp integration | 15 tests | All passing |

## Migration

See [MIGRATION_GUIDE.md](MIGRATION_GUIDE.md) for upgrading from v2.x.

## Installation

```bash
# Full installation
pip install zotero-mcp[full]

# Minimal (Zotero + analysis)
pip install zotero-mcp

# Individual modules
pip install paper-feed
pip install zotero-core
pip install paper-analyzer
```

## Commit History

```
feat(Task-3.1/3.2/3.3): implement paper-analyzer module
feat(Task-4.1/4.2): implement zotero-mcp integration layer
docs(Task-5.1/5.2/5.3): update docs, migration guide, release prep
```
