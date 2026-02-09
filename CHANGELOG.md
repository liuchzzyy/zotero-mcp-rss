# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### 🔥 Removed
- External `paper-feed` module; merged analysis and core logic into main package
- BibTeX export and Better BibTeX integration

### 🔧 Changed
- Unified package layout to align with logseq-mcp style layering

## [2.0.1] - 2026-02-09

### 🔧 Changed
- Metadata lookup priority: DOI → title → URL (Crossref/OpenAlex)
- Type checking now targets Python 3.12 (updated project requirements)
- GitHub repository links and updater endpoints now point to `liuchzzyy/zotero-mcp`

### 🧹 Removed
- RSS/Gmail related remnants (configs, docs, and templates)

### ✅ Quality
- `ruff` and `ty` checks pass on Python 3.12

## [2.5.0] - 2026-02-02

### 🚀 Enhancements

#### Multi-Modal PDF Analysis
- **PDF Content Extraction**: Extract text, images, and tables from PDFs using PyMuPDF (10x faster than pdfplumber)
- **Intelligent LLM Selection**: Auto-select best LLM based on content (Claude CLI for images, DeepSeek for text-only)
- **Image Analysis Support**: Vision-capable LLMs can analyze and reference figures, charts, and diagrams
- **Table Extraction**: Automatic table detection and structured data extraction
- **LLM Capability Registry**: Define and detect capabilities for different LLM providers (DeepSeek, Claude CLI, OpenAI, Gemini)
- **Multi-Modal Templates**: Enhanced analysis templates with figure and table analysis sections
- **Graceful Degradation**: Text-only LLMs receive informative placeholders when images are present
- **Performance Optimization**: 10x faster PDF extraction with PyMuPDF compared to pdfplumber

#### New Dependencies
- **PyMuPDF (fitz)**: High-performance PDF library for fast content extraction
- **PyMuPDF4LLM**: LLM-optimized markdown conversion preserving document structure
- **Pillow**: Image processing for PDF page rendering

### 🔧 Changed

#### Enhanced Analysis Workflow
- **Auto LLM Selection**: `llm_provider="auto"` now detects images and selects Claude CLI or DeepSeek accordingly
- **Multi-Modal Parameter**: `include_multimodal` flag added to all analysis tools (default: True)
- **Structured Notes**: Enhanced note templates support image references and table analysis
- **CLI Improvements**: Added `--multimodal/--no-multimodal` flag to `scan` command

### 🐛 Fixed

#### GitHub Actions Workflows
- **Deduplicate Log Formatting**:
  - Enhanced logs with emoji indicators (🔍, 📊, ✓, ⊘, ✅, 🗑️, ➕, ✗)
  - Distinguished ITEM vs NOTE types in output
  - Removed unwanted quotes from collection names (triple-quote issue fixed)
  - Clarified "准备移动" (prepare to move) vs "实际移动" (actually moved) to avoid confusion
- **Collection Name Display**: Fixed collection name quotes in 3 locations:
  - Workflow parameter passing (`.github/workflows/deduplicate.yml`)
  - Service log output (`duplicate_service.py`)
  - CLI result output (`cli.py`)

### 📝 Documentation

#### New Documentation
- **Multi-Modal Guide**: Comprehensive guide for multi-modal PDF analysis (`docs/MULTIMODAL_ANALYSIS.md`)
- **Implementation Plan**: Detailed plan document for multi-modal feature development
- **Updated README**: Enhanced with multi-modal feature highlights and examples

### ✅ Testing

#### Comprehensive Test Coverage
- **100+ New Tests**: Added extensive test coverage for multi-modal functionality
- **Integration Tests**: End-to-end tests for multi-modal workflow
- **Capability Tests**: LLM capability detection and validation
- **Template Tests**: Multi-modal template formatting tests
- **CLI Tests**: Command-line interface tests for new flags
- **GitHub Actions**: All workflows tested successfully (scan, metadata, deduplicate)

## [2.4.0] - 2026-02-01

### 🚀 Enhancements

#### Duplicate Detection & Removal
- **Smart Deduplication**: New `zotero-mcp deduplicate` command for finding and removing duplicate items
- **Priority Matching**: DOI > Title > URL hierarchy for intelligent duplicate detection
- **Cross-Folder Copy Detection**: Identifies and preserves intentional duplicates (identical metadata in multiple folders)
- **Safe Removal**: Duplicates moved to trash collection (`06_TRASHES` by default), not permanently deleted
- **Preview Mode**: `--dry-run` flag to review duplicates before actual deletion
- **Note/Attachment Protection**: Notes and attachments are never deleted during deduplication
- **Custom Collection Support**: `--trash-collection` option to specify target trash collection

#### Metadata Updates
- **Enhanced Metadata Service**: New `zotero-mcp update-metadata` command to update item metadata from external APIs
- **Crossref/OpenAlex Integration**: Auto-complete missing metadata (authors, title, publication, etc.)
- **Batch Processing**: Process multiple items with configurable limits
- **Tag-based Filtering**: Only update items without "AI元数据" tag

#### Error Handling & Reliability
- **Retry Logic**: Added exponential backoff retry for all API calls (handles 502 errors)
- **PyZotero 429 Handling**: Fixed silent failures from HTTP 429 rate limiting
- **Improved Logging**: Enhanced error messages with Chinese labels and emoji for better clarity
- **API Client Validation**: Convert HTTP status codes to exceptions for proper retry handling

### 🔧 Changed

#### Code Quality
- **Refactored Workflow Service**: Split 185-line `_analyze_single_item` method into focused helper methods
- **Shared Utilities**: Created `collection_scanner.py` for reducing code duplication
- **Type Safety**: Fixed lambda closure bugs (Ruff B023) and type annotation errors
- **Code Simplification**: Extracted configuration objects and pipeline patterns

#### Documentation
- **CLAUDE.md**: Added communication style guidelines and code simplification best practices
- **README.md**: Completely rewritten with modern structure, emoji badges, and updated features
- **CHANGELOG.md**: Updated with latest version information

### 🐛 Fixed

#### Critical Bugs
- **Collection Key Extraction Bug**: Fixed path error in `duplicate_service.py` that caused items to be deleted instead of moved to trash
  - Before: `trash_coll.get("key", "")` (returned empty string)
  - After: `trash_coll.get("data", {}).get("key", "")` (correct path)
- **Lambda Closure Bugs**: Fixed variable capture in loops using default parameters
- **Type Annotation Errors**: Fixed template type mismatches in workflow service

#### GitHub Actions
- **Deduplication Workflow**: Fixed 502 Bad Gateway errors with retry logic
- **Rate Limiting**: Added 1s delay between items to stay under Zotero's ~10 req/s limit

### 📝 Documentation

- Updated README.md with comprehensive feature descriptions
- Added deduplication usage examples and troubleshooting
- Added cross-folder copy detection explanation
- Updated CLAUDE.md with development guidelines

### 🔒 Security

- Fixed potential command injection in collection operations
- Improved validation of user inputs

## [2.3.0] - 2026-01-25

### 🚀 Enhancements

#### Error Handling
- **Enhanced Metadata Matching**: Lowered threshold from 0.7 to 0.6 for better paper matching
- **Increased API Timeout**: Raised from 30s to 45s for slow network conditions
- **Cache Error Tolerance**: GitHub Actions continue even if cache service fails
- **Comprehensive Logging**: Detailed logs with 3-day retention for debugging

### 🔧 Changed

- **Retry Mechanisms**: All API calls use exponential backoff for transient failures

## [2.2.0] - 2026-01-20

### 🔧 Changed

- **Project Structure**: Moved automation scripts to `src/scripts/`
- **Dependencies**: Added `feedparser`, `beautifulsoup4`, `lxml`, and `tenacity`

### 🗑️ Removed

- Unused `streaming.py` utility module
- Unused `response_converter.py` utility module

## [2.1.0] - 2026-01-15

### 🚀 Enhancements

#### Performance & Compatibility
- **Batch Operation Support**: New `zotero_batch_get_metadata` tool for retrieving multiple items
- **Response Caching Layer**: Added in-memory caching for read-only tools (TTL: 5 minutes)
- **Response Converter**: Backward compatibility layer for legacy formats
- **Performance Monitoring**: Metrics collection for tool usage and duration
- **Streaming Support**: Utilities for streaming large result sets

#### New Tools
- `zotero_batch_get_metadata`: Retrieve metadata for up to 50 items at once

## [2.0.0] - 2026-01-10

### 🎉 Major Release - MCP Standardization

**Breaking release** that standardizes all tools to follow MCP best practices with structured Pydantic responses.

### ⚠️ Breaking Changes

#### API Response Format
- **All tools now return structured Pydantic models instead of formatted strings**
- Response format changed from string (markdown/JSON) to structured dictionaries
- All responses include `success` and `error` fields for consistent error handling

**Migration Example:**
```python
# Before (v1.x)
result = await call_tool("zotero_search", query="AI", limit=10)
# Returns: '{"items": [...]}' (string)

# After (v2.0)
result = await call_tool("zotero_search", params={"query": "AI", "limit": 10})
# Returns: {success: true, results: [...]} (dict)
```

#### Parameter Changes
- All tool parameters must now be passed as a single `params` object
- Field name changes: `items` → `results`, `authors` → `creators`

### ✨ Added

#### New Response Models (14 total)
- `BaseResponse`, `PaginatedResponse`, `SearchResponse`
- `ItemDetailResponse`, `FulltextResponse`, `AnnotationItem`
- `AnnotationsResponse`, `NotesResponse`, `NoteCreationResponse`
- `CollectionItem`, `CollectionsResponse`, `BundleResponse`
- `DatabaseStatusResponse`, `DatabaseUpdateResponse`

#### New Features
- **Built-in Pagination**: `has_more` and `next_offset` support
- **Structured Error Handling**: Consistent error format
- **Tool Annotations**: Proper MCP annotations (readOnly, idempotent, etc.)
- **Type Safety**: Full Pydantic validation
- **Complete Docstrings**: Google-style docstrings with examples

### 🔧 Changed

#### All 16 Tools Refactored
- **Search Tools (5)**: `zotero_search`, `zotero_search_by_tag`, `zotero_advanced_search`, `zotero_semantic_search`, `zotero_get_recent`
- **Item Tools (5)**: `zotero_get_metadata`, `zotero_get_fulltext`, `zotero_get_children`, `zotero_get_collections`, `zotero_get_bundle`
- **Annotation Tools (4)**: `zotero_get_annotations`, `zotero_get_notes`, `zotero_search_notes`, `zotero_create_note`
- **Database Tools (2)**: `zotero_update_database`, `zotero_database_status`

### 🗑️ Removed

- String-based response formatting (replaced with structured models)
- `handle_error()` utility (replaced with structured error responses)

### 📚 Documentation

- Added `docs/STRUCTURED-OUTPUT-EXAMPLES.md` - Complete API reference
- Added `docs/MIGRATION-GUIDE.md` - Detailed migration guide from v1.x
- Added `QUICK-REFERENCE.md` - Quick reference card

## [1.0.0] - Initial Release

### ✨ Features

- Initial MCP server implementation
- 16 tools for Zotero library access
- Local and web API support
- Semantic search functionality
- PDF annotation extraction
- String-based responses (markdown/JSON)

---

## Migration Timeline

- **v1.x → v2.0**: Breaking changes, see [Migration Guide](./docs/MIGRATION-GUIDE.md)
- **v2.3 → v2.4**: Enhanced deduplication and metadata updates, backward compatible
- **Recommended Action**: Always review changelog before upgrading

---

## Links

- [Repository](https://github.com/liuchzzyy/zotero-mcp)
- [Documentation](./docs/)
- [Issues](https://github.com/liuchzzyy/zotero-mcp/issues)
- [Releases](https://github.com/liuchzzyy/zotero-mcp/releases)

---

**Note**: For v1.x → v2.0 migration, please review the [Migration Guide](./docs/MIGRATION-GUIDE.md) before upgrading.
