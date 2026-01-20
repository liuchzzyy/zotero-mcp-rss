# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [2.1.0] - 2026-01-20

### 🚀 Enhancements

#### Performance & Compatibility
- **Batch Operation Support**: New `zotero_batch_get_metadata` tool for retrieving multiple items in a single call.
- **Response Caching Layer**: Added in-memory caching for read-only tools (default TTL: 5 minutes) to improve performance.
- **Response Converter**: Added backward compatibility layer to convert structured responses to legacy formats (markdown/JSON).
- **Performance Monitoring**: Added metrics collection for tool usage and duration.
- **Streaming Support**: Added utilities for streaming large result sets.

#### New Tools
- `zotero_batch_get_metadata`: Retrieve metadata for up to 50 items at once.

## [2.0.0] - 2026-01-20

### 🎉 Major Release - MCP Standardization

This is a **breaking release** that standardizes all tools to follow MCP best practices with structured Pydantic responses.

### ⚠️ Breaking Changes

#### API Response Format
- **All tools now return structured Pydantic models instead of formatted strings**
- Response format changed from string (markdown/JSON) to structured dictionaries
- All responses include `success` and `error` fields for consistent error handling

**Before (v1.x):**
```python
result = await call_tool("zotero_search", query="AI", limit=10)
# Returns: '{"items": [...]}' (string)
```

**After (v2.0):**
```python
result = await call_tool("zotero_search", params={"query": "AI", "limit": 10})
# Returns: {success: true, results: [...]} (dict)
```

#### Parameter Changes
- All tool parameters must now be passed as a single `params` object
- Field name changes:
  - `items` → `results` (in search responses)
  - `authors` → `creators` (in metadata)
  - `output_format` → `response_format` (consistent naming)

#### Tool Signature Changes
- All tools use Pydantic input models as first parameter
- Context moved to keyword-only second parameter
- Return type changed from `str` to specific Pydantic response models

### ✨ Added

#### New Response Models (14 total)
- `BaseResponse` - Base class with success/error fields
- `PaginatedResponse` - Base for paginated responses
- `SearchResponse` - Search results with pagination
- `SearchResultItem` - Individual search result
- `ItemDetailResponse` - Detailed item metadata
- `FulltextResponse` - Full-text content
- `AnnotationItem` - Single annotation
- `AnnotationsResponse` - Annotations list
- `NotesResponse` - Notes list
- `NoteCreationResponse` - Note creation result
- `CollectionItem` - Single collection
- `CollectionsResponse` - Collections list
- `BundleResponse` - Comprehensive item bundle
- `DatabaseStatusResponse` - Database status
- `DatabaseUpdateResponse` - Database update result

#### New Features
- **Built-in Pagination**: All list operations support `has_more` and `next_offset`
- **Structured Error Handling**: Consistent `{success: false, error: "..."}` format
- **Tool Annotations**: All tools have proper MCP annotations (readOnly, idempotent, etc.)
- **Type Safety**: Full Pydantic validation for inputs and outputs
- **Complete Docstrings**: Google-style docstrings with examples for all tools

#### Documentation
- Added `docs/STRUCTURED-OUTPUT-EXAMPLES.md` - Complete API reference with examples
- Added `docs/MIGRATION-GUIDE.md` - Detailed migration guide from v1.x
- Added `QUICK-REFERENCE.md` - Quick reference card
- Updated `README.md` with structured output features

### 🔧 Changed

#### All 16 Tools Refactored

**Search Tools (5):**
- `zotero_search` - Now returns `SearchResponse` with pagination
- `zotero_search_by_tag` - Now returns `SearchResponse` with pagination
- `zotero_advanced_search` - Now returns `SearchResponse` with pagination
- `zotero_semantic_search` - Now returns `SearchResponse` with similarity scores
- `zotero_get_recent` - Now returns `SearchResponse` with pagination

**Item Tools (5):**
- `zotero_get_metadata` - Now returns `ItemDetailResponse`, supports BibTeX
- `zotero_get_fulltext` - Now returns `FulltextResponse` with word count
- `zotero_get_children` - Now returns structured dict
- `zotero_get_collections` - Now returns `CollectionsResponse`
- `zotero_get_bundle` - Now returns `BundleResponse` with all data

**Annotation Tools (4):**
- `zotero_get_annotations` - Now returns `AnnotationsResponse` with pagination
- `zotero_get_notes` - Now returns `NotesResponse` with HTML cleaning
- `zotero_search_notes` - Now returns `SearchResponse` with context
- `zotero_create_note` - Now returns `NoteCreationResponse` with note key

**Database Tools (2):**
- `zotero_update_database` - Now returns `DatabaseUpdateResponse` with statistics
- `zotero_database_status` - Now returns `DatabaseStatusResponse` with config

### 📝 Improved

- **Error Messages**: More descriptive and structured error responses
- **Pagination**: Automatic calculation of `has_more` and `next_offset`
- **Type Safety**: Full Pydantic validation prevents invalid inputs
- **Documentation**: Complete docstrings with parameter descriptions and examples
- **Code Quality**: Removed unused imports, consistent patterns across all tools

### 🗑️ Removed

- String-based response formatting (replaced with structured models)
- `handle_error()` utility (replaced with structured error responses)
- Direct formatter calls in tools (responses are now structured data)

### 🔄 Migration Guide

**Key Migration Steps:**
1. Wrap all parameters in `params={}` object
2. Check `result["success"]` before processing
3. Use `result["results"]` instead of `result["items"]`
4. Use `result["creators"]` instead of `result["authors"]`
5. Handle pagination with `has_more` and `next_offset` fields

### 📚 Documentation

- **API Examples**: See [`docs/STRUCTURED-OUTPUT-EXAMPLES.md`](./docs/STRUCTURED-OUTPUT-EXAMPLES.md)

---

## [1.x.x] - Previous Versions

See git history for changes in v1.x releases.

### [1.0.0] - Initial Release
- Initial MCP server implementation
- 16 tools for Zotero library access
- Local and web API support
- Semantic search functionality
- PDF annotation extraction
- String-based responses (markdown/JSON)

---

## Migration Timeline

- **v1.x → v2.0**: Breaking changes, see migration guide above
- **Recommended Action**: Update client code to use new structured format
- **Backward Compatibility**: Not available, clean break for better architecture

---

## Links

- [Repository](https://github.com/54yyyu/zotero-mcp)
- [Documentation](./docs/)
- [Issues](https://github.com/54yyyu/zotero-mcp/issues)

---

**Note**: This is a major version update with breaking changes. Please review the migration guide before upgrading.
