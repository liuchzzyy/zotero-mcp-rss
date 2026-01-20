# Migration Guide: String to Structured Responses

**Version**: 2.0.0  
**Date**: 2026-01-20

This guide helps you migrate from the old string-based response format to the new structured Pydantic response format.

---

## Overview

Zotero MCP has been refactored to return structured Pydantic models instead of formatted strings. This provides better type safety, consistency, and machine-readability.

## Breaking Changes Summary

| Aspect | Old Format | New Format |
|--------|-----------|------------|
| **Return Type** | `str` (formatted markdown/JSON) | Pydantic models (dict-like) |
| **Parameters** | Individual parameters | Single `params` object |
| **Error Handling** | String error messages | Structured `{success: false, error: "..."}` |
| **Pagination** | Manual offset calculation | Built-in `has_more`, `next_offset` |

---

## Migration Steps

### Step 1: Update Tool Calls

#### Before (Old Format)
```python
result = await mcp_client.call_tool(
    "zotero_search",
    query="machine learning",
    limit=10,
    response_format="json"
)
# result is a string: '{"items": [...]}'
```

#### After (New Format)
```python
result = await mcp_client.call_tool(
    "zotero_search",
    params={
        "query": "machine learning",
        "limit": 10,
        "response_format": "json"
    }
)
# result is a dict: {"success": true, "results": [...]}
```

### Step 2: Parse Responses

#### Before (Old Format)
```python
# Result was a string that needed parsing
import json
result_str = await mcp_client.call_tool("zotero_search", ...)
if result_str.startswith("Error:"):
    handle_error(result_str)
else:
    data = json.loads(result_str)  # Manual parsing needed
```

#### After (New Format)
```python
# Result is already a structured dict
result = await mcp_client.call_tool("zotero_search", ...)
if not result["success"]:
    handle_error(result["error"])
else:
    items = result["results"]  # Direct access
```

### Step 3: Handle Errors

#### Before (Old Format)
```python
result = await mcp_client.call_tool("zotero_get_metadata", item_key="ABC123")
if result.startswith("❌") or "error" in result.lower():
    # String parsing needed to detect errors
    print(f"Error occurred: {result}")
```

#### After (New Format)
```python
result = await mcp_client.call_tool(
    "zotero_get_metadata",
    params={"item_key": "ABC123"}
)
if not result["success"]:
    # Structured error handling
    print(f"Error: {result['error']}")
else:
    print(f"Title: {result['title']}")
```

### Step 4: Implement Pagination

#### Before (Old Format)
```python
# Manual pagination
offset = 0
limit = 10
all_results = []

while True:
    result = await mcp_client.call_tool(
        "zotero_search",
        query="ML",
        limit=limit,
        offset=offset
    )
    data = json.loads(result)
    if not data["items"]:
        break
    all_results.extend(data["items"])
    offset += limit
```

#### After (New Format)
```python
# Built-in pagination support
offset = 0
limit = 10
all_results = []

while True:
    result = await mcp_client.call_tool(
        "zotero_search",
        params={
            "query": "ML",
            "limit": limit,
            "offset": offset
        }
    )
    if not result["success"]:
        break
    
    all_results.extend(result["results"])
    
    if not result["has_more"]:
        break
    
    offset = result["next_offset"]  # Use provided offset
```

---

## Tool-by-Tool Migration

### Search Tools

#### zotero_search

**Before:**
```python
result = await call_tool(
    "zotero_search",
    query="AI",
    limit=5,
    qmode="everything",
    response_format="json"
)
# Returns: '{"items": [{"title": "...", ...}], "count": 5}'
```

**After:**
```python
result = await call_tool(
    "zotero_search",
    params={
        "query": "AI",
        "limit": 5,
        "qmode": "everything",
        "response_format": "json"
    }
)
# Returns: {
#   "success": true,
#   "query": "AI",
#   "count": 5,
#   "total_count": 23,
#   "has_more": true,
#   "next_offset": 5,
#   "results": [...]
# }
```

#### zotero_semantic_search

**Before:**
```python
result = await call_tool(
    "zotero_semantic_search",
    query="neural networks",
    limit=10,
    response_format="markdown"
)
# Returns: "# Semantic Search Results\n\n1. Title..."
```

**After:**
```python
result = await call_tool(
    "zotero_semantic_search",
    params={
        "query": "neural networks",
        "limit": 10,
        "response_format": "json"
    }
)
# Returns: {
#   "success": true,
#   "results": [
#     {
#       "key": "ABC123",
#       "title": "...",
#       "similarity_score": 0.89
#     }
#   ]
# }
```

### Item Tools

#### zotero_get_metadata

**Before:**
```python
result = await call_tool(
    "zotero_get_metadata",
    item_key="ABC123",
    response_format="json"
)
# Returns: '{"title": "...", "authors": [...], ...}'
```

**After:**
```python
result = await call_tool(
    "zotero_get_metadata",
    params={
        "item_key": "ABC123",
        "format": "json"  # Note: 'format' not 'response_format'
    }
)
# Returns: {
#   "success": true,
#   "item_key": "ABC123",
#   "title": "...",
#   "creators": [...],
#   "year": 2023,
#   ...
# }
```

**BibTeX format:**
```python
result = await call_tool(
    "zotero_get_metadata",
    params={
        "item_key": "ABC123",
        "format": "bibtex"
    }
)
# Returns: {
#   "success": true,
#   "item_key": "ABC123",
#   "title": "...",
#   "format": "bibtex",
#   "raw_data": {
#     "bibtex": "@article{...}"
#   }
# }
```

#### zotero_get_fulltext

**Before:**
```python
result = await call_tool(
    "zotero_get_fulltext",
    item_key="ABC123",
    response_format="markdown"
)
# Returns: "# Full Text\n\nAbstract\n..."
```

**After:**
```python
result = await call_tool(
    "zotero_get_fulltext",
    params={"item_key": "ABC123"}
)
# Returns: {
#   "success": true,
#   "item_key": "ABC123",
#   "has_fulltext": true,
#   "content": "Abstract\n...",
#   "word_count": 5432,
#   "indexed": true
# }
```

### Annotation Tools

#### zotero_get_annotations

**Before:**
```python
result = await call_tool(
    "zotero_get_annotations",
    item_key="ABC123",
    annotation_type="highlight",
    response_format="json"
)
# Returns: '[{"type": "highlight", "text": "...", ...}]'
```

**After:**
```python
result = await call_tool(
    "zotero_get_annotations",
    params={
        "item_key": "ABC123",
        "annotation_type": "highlight",
        "limit": 10
    }
)
# Returns: {
#   "success": true,
#   "item_key": "ABC123",
#   "count": 10,
#   "total_count": 23,
#   "has_more": true,
#   "next_offset": 10,
#   "annotations": [
#     {
#       "type": "highlight",
#       "text": "...",
#       "comment": "...",
#       "page": "5",
#       "color": "yellow"
#     }
#   ]
# }
```

#### zotero_create_note

**Before:**
```python
result = await call_tool(
    "zotero_create_note",
    item_key="ABC123",
    content="My note",
    tags="tag1,tag2"
)
# Returns: "✅ Note created successfully!\n\n**Note Key:** `NOTE456`"
```

**After:**
```python
result = await call_tool(
    "zotero_create_note",
    params={
        "item_key": "ABC123",
        "content": "My note",
        "tags": ["tag1", "tag2"]  # Array instead of comma-separated
    }
)
# Returns: {
#   "success": true,
#   "note_key": "NOTE456",
#   "parent_key": "ABC123",
#   "message": "Note created successfully with key: NOTE456"
# }
```

### Database Tools

#### zotero_update_database

**Before:**
```python
result = await call_tool(
    "zotero_update_database",
    force_rebuild=False,
    include_fulltext=True
)
# Returns: "# Database Update Complete\n\n**Items Processed:** 150"
```

**After:**
```python
result = await call_tool(
    "zotero_update_database",
    params={
        "force_rebuild": False,
        "extract_fulltext": True
    }
)
# Returns: {
#   "success": true,
#   "items_processed": 150,
#   "items_added": 25,
#   "items_updated": 10,
#   "duration_seconds": 45.3,
#   "message": "Processed 150 items..."
# }
```

---

## Common Patterns

### Pattern 1: Check Success Before Processing

```python
result = await call_tool("zotero_search", params={...})

# Always check success first
if not result.get("success", True):  # Default to True for backward compat
    logger.error(f"Tool failed: {result.get('error', 'Unknown error')}")
    return None

# Process successful result
return result["results"]
```

### Pattern 2: Handle Pagination

```python
def get_all_results(query: str):
    all_items = []
    offset = 0
    limit = 50
    
    while True:
        result = await call_tool(
            "zotero_search",
            params={
                "query": query,
                "limit": limit,
                "offset": offset
            }
        )
        
        if not result["success"]:
            break
        
        all_items.extend(result["results"])
        
        if not result["has_more"]:
            break
        
        offset = result["next_offset"]
    
    return all_items
```

### Pattern 3: Extract Specific Fields

```python
# Old: Parse string and extract
result_str = await call_tool(...)
data = json.loads(result_str)
titles = [item["title"] for item in data["items"]]

# New: Direct access
result = await call_tool(...)
if result["success"]:
    titles = [item["title"] for item in result["results"]]
```

---

## Response Format Changes

### Changed Field Names

| Tool | Old Field | New Field |
|------|-----------|-----------|
| All search tools | `items` | `results` |
| `zotero_get_metadata` | `authors` | `creators` |
| All list tools | *(calculated)* | `has_more`, `next_offset` |

### New Common Fields

All responses now include:
- `success` - Boolean indicating success/failure
- `error` - Error message (only when success=false)
- `message` - Optional human-readable status

All list responses include:
- `count` - Number of items in this response
- `total_count` - Total number of items available
- `has_more` - Boolean indicating if more results exist
- `next_offset` - Offset for next page (null if no more results)

---

## TypeScript Type Definitions

If you're using TypeScript, here are the new response types:

```typescript
// Common response type
interface BaseResponse {
  success: boolean;
  error?: string;
  message?: string;
}

// Search response
interface SearchResponse extends BaseResponse {
  query: string;
  count: number;
  total_count: number;
  has_more: boolean;
  next_offset: number | null;
  results: SearchResultItem[];
}

// Item metadata response
interface ItemDetailResponse extends BaseResponse {
  item_key: string;
  title: string;
  creators: string[];
  year?: number;
  item_type: string;
  publication?: string;
  doi?: string;
  url?: string;
  abstract?: string;
  tags: string[];
  date_added?: string;
  date_modified?: string;
  raw_data: any;
}

// Annotations response
interface AnnotationsResponse extends BaseResponse {
  item_key: string;
  count: number;
  total_count: number;
  has_more: boolean;
  next_offset: number | null;
  annotations: AnnotationItem[];
}

interface AnnotationItem {
  type: string;
  text?: string;
  comment?: string;
  page?: string;
  color?: string;
}
```

---

## Testing Your Migration

### Test Checklist

- [ ] All tool calls use `params` object instead of individual parameters
- [ ] All responses check `success` field before processing
- [ ] Error handling uses `result["error"]` instead of string parsing
- [ ] Pagination uses `has_more` and `next_offset` fields
- [ ] Field names updated (e.g., `items` → `results`, `authors` → `creators`)
- [ ] Tags passed as arrays instead of comma-separated strings (for create_note)
- [ ] BibTeX format uses `format="bibtex"` parameter

### Example Test

```python
async def test_migration():
    # Test successful call
    result = await call_tool(
        "zotero_search",
        params={"query": "test", "limit": 1}
    )
    assert result["success"] == True
    assert "results" in result
    assert "has_more" in result
    
    # Test error handling
    result = await call_tool(
        "zotero_get_metadata",
        params={"item_key": "INVALID"}
    )
    assert result["success"] == False
    assert "error" in result
    
    print("✅ Migration tests passed!")
```

---

## Rollback Plan

If you need to temporarily revert to the old format, you can:

1. Pin to the previous version in your dependencies
2. Create a wrapper function that converts new responses to old format
3. Use a compatibility layer (see example below)

### Compatibility Layer Example

```python
def convert_to_old_format(tool_name: str, new_result: dict) -> str:
    """Convert new structured response to old string format."""
    
    if not new_result.get("success", True):
        return f"Error: {new_result.get('error', 'Unknown error')}"
    
    # Convert search results
    if "results" in new_result:
        items = new_result["results"]
        return json.dumps({"items": items, "count": len(items)})
    
    # Convert metadata
    if "item_key" in new_result and "title" in new_result:
        return json.dumps(new_result)
    
    # Default: return JSON string
    return json.dumps(new_result)
```

---

## Getting Help

- **Documentation**: See [STRUCTURED-OUTPUT-EXAMPLES.md](./STRUCTURED-OUTPUT-EXAMPLES.md)
- **Issues**: Report migration issues on GitHub
- **Examples**: Check `examples/` directory for updated code samples

---

**Migration completed? Don't forget to update your tests and documentation!** ✅
