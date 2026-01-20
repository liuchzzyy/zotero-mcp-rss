# Structured Output Examples - Zotero MCP

This document provides examples of the new structured output format for all Zotero MCP tools.

## Overview

All Zotero MCP tools now return structured Pydantic models instead of formatted strings. This provides:
- **Type safety** - Full type checking for all responses
- **Consistency** - All responses follow the same structure
- **Machine-readable** - Easy to parse and process programmatically
- **Error handling** - Consistent error reporting with success/error fields
- **Pagination** - Built-in support for large result sets

## Common Response Fields

All responses inherit from `BaseResponse` and include:

```typescript
{
  "success": true,      // Always present: true on success, false on error
  "error": null,        // Present only when success=false, contains error message
  "message": "..."      // Optional: Human-readable status message
}
```

## Search Tools

### zotero_search

**Input:**
```json
{
  "query": "machine learning",
  "qmode": "titleCreatorYear",
  "limit": 5,
  "offset": 0
}
```

**Output:**
```json
{
  "success": true,
  "query": "machine learning",
  "count": 5,
  "total_count": 23,
  "has_more": true,
  "next_offset": 5,
  "results": [
    {
      "key": "ABC123XYZ",
      "title": "Deep Learning for Computer Vision",
      "creators": ["Smith, J.", "Doe, A."],
      "year": 2023,
      "item_type": "journalArticle",
      "date_added": "2024-01-15T10:30:00Z",
      "snippet": "...machine learning techniques...",
      "tags": ["AI", "Computer Vision"],
      "raw_data": { /* full item data */ }
    }
    // ... 4 more results
  ]
}
```

### zotero_semantic_search

**Input:**
```json
{
  "query": "applications of neural networks in medicine",
  "limit": 10,
  "similarity_threshold": 0.7
}
```

**Output:**
```json
{
  "success": true,
  "query": "applications of neural networks in medicine",
  "count": 10,
  "total_count": 10,
  "has_more": false,
  "next_offset": null,
  "results": [
    {
      "key": "DEF456GHI",
      "title": "Neural Networks in Medical Diagnosis",
      "creators": ["Johnson, M."],
      "year": 2024,
      "item_type": "journalArticle",
      "date_added": "2024-03-20T14:15:00Z",
      "snippet": "...medical applications...",
      "similarity_score": 0.89,
      "raw_data": { /* full item data */ }
    }
    // ... 9 more results
  ]
}
```

## Item Tools

### zotero_get_metadata

**Input:**
```json
{
  "item_key": "ABC123XYZ",
  "format": "json"
}
```

**Output:**
```json
{
  "success": true,
  "item_key": "ABC123XYZ",
  "title": "Deep Learning for Computer Vision",
  "creators": ["Smith, J.", "Doe, A."],
  "year": 2023,
  "item_type": "journalArticle",
  "publication": "Nature Machine Intelligence",
  "volume": "10",
  "issue": "3",
  "pages": "245-267",
  "doi": "10.1038/s42256-023-00123-4",
  "url": "https://doi.org/10.1038/s42256-023-00123-4",
  "abstract": "This paper presents...",
  "tags": ["AI", "Computer Vision", "Deep Learning"],
  "date_added": "2024-01-15T10:30:00Z",
  "date_modified": "2024-01-20T08:45:00Z",
  "raw_data": { /* complete item data */ }
}
```

**Input (BibTeX format):**
```json
{
  "item_key": "ABC123XYZ",
  "format": "bibtex"
}
```

**Output:**
```json
{
  "success": true,
  "item_key": "ABC123XYZ",
  "title": "Deep Learning for Computer Vision",
  "format": "bibtex",
  "raw_data": {
    "bibtex": "@article{smith2023deep,\n  title={Deep Learning for Computer Vision},\n  author={Smith, J. and Doe, A.},\n  journal={Nature Machine Intelligence},\n  volume={10},\n  number={3},\n  pages={245--267},\n  year={2023},\n  publisher={Nature Publishing Group}\n}"
  }
}
```

### zotero_get_fulltext

**Input:**
```json
{
  "item_key": "ABC123XYZ"
}
```

**Output:**
```json
{
  "success": true,
  "item_key": "ABC123XYZ",
  "has_fulltext": true,
  "content": "Deep Learning for Computer Vision\n\nAbstract\nThis paper presents...\n\n1. Introduction\nRecent advances in...",
  "word_count": 8543,
  "indexed": true
}
```

### zotero_get_bundle

**Input:**
```json
{
  "item_key": "ABC123XYZ",
  "include_fulltext": true,
  "include_bibtex": true
}
```

**Output:**
```json
{
  "success": true,
  "metadata": {
    "item_key": "ABC123XYZ",
    "title": "Deep Learning for Computer Vision",
    "creators": ["Smith, J.", "Doe, A."],
    "year": 2023,
    // ... full metadata
  },
  "attachments": [
    {
      "key": "ATT123",
      "title": "Full Text PDF",
      "contentType": "application/pdf",
      "path": "storage/ABC123XYZ/Smith et al. - 2023.pdf"
    }
  ],
  "notes": [
    {
      "key": "NOTE123",
      "content": "Important methodology section on page 5",
      "dateAdded": "2024-01-16T09:00:00Z"
    }
  ],
  "annotations": [
    {
      "type": "highlight",
      "text": "Convolutional neural networks...",
      "comment": "Key definition",
      "page": 3,
      "color": "yellow"
    }
  ],
  "fulltext": "Deep Learning for Computer Vision\n\nAbstract...",
  "bibtex": "@article{smith2023deep,\n  title={...},\n  ...\n}"
}
```

## Annotation Tools

### zotero_get_annotations

**Input:**
```json
{
  "item_key": "ABC123XYZ",
  "annotation_type": "highlight",
  "limit": 10,
  "offset": 0
}
```

**Output:**
```json
{
  "success": true,
  "item_key": "ABC123XYZ",
  "count": 10,
  "total_count": 23,
  "has_more": true,
  "next_offset": 10,
  "annotations": [
    {
      "type": "highlight",
      "text": "Convolutional neural networks are particularly effective for image classification tasks.",
      "comment": "Key finding",
      "page": "3",
      "color": "yellow"
    },
    {
      "type": "highlight",
      "text": "Training on ImageNet dataset...",
      "comment": null,
      "page": "5",
      "color": "green"
    }
    // ... 8 more annotations
  ]
}
```

### zotero_get_notes

**Input:**
```json
{
  "item_key": "ABC123XYZ",
  "limit": 5
}
```

**Output:**
```json
{
  "success": true,
  "item_key": "ABC123XYZ",
  "count": 3,
  "total_count": 3,
  "has_more": false,
  "next_offset": null,
  "notes": [
    {
      "note_key": "NOTE123",
      "content": "Methodology section on page 5 describes the CNN architecture...",
      "full_content": "Methodology section on page 5 describes the CNN architecture in detail...",
      "raw_html": "<p>Methodology section on page 5...</p>"
    }
    // ... 2 more notes
  ]
}
```

### zotero_search_notes

**Input:**
```json
{
  "query": "methodology",
  "case_sensitive": false,
  "limit": 10
}
```

**Output:**
```json
{
  "success": true,
  "query": "methodology",
  "count": 5,
  "total_count": 5,
  "has_more": false,
  "next_offset": null,
  "results": [
    {
      "key": "ABC123XYZ",
      "title": "Deep Learning for Computer Vision",
      "creators": [],
      "item_type": "note",
      "snippet": "...describes the methodology for training CNNs on large datasets...",
      "raw_data": {
        "type": "note",
        "item_key": "ABC123XYZ",
        "note_key": "NOTE123",
        "context": "...the methodology for training..."
      }
    }
    // ... 4 more results
  ]
}
```

### zotero_create_note

**Input:**
```json
{
  "item_key": "ABC123XYZ",
  "content": "The methodology section provides valuable insights into CNN architecture design.",
  "tags": ["methodology", "cnn", "architecture"]
}
```

**Output:**
```json
{
  "success": true,
  "note_key": "NOTE456",
  "parent_key": "ABC123XYZ",
  "message": "Note created successfully with key: NOTE456"
}
```

## Database Tools

### zotero_update_database

**Input:**
```json
{
  "force_rebuild": false,
  "extract_fulltext": true,
  "limit": null
}
```

**Output:**
```json
{
  "success": true,
  "items_processed": 150,
  "items_added": 25,
  "items_updated": 10,
  "duration_seconds": 45.3,
  "message": "Full-text content indexed\nProcessed 150 items\nAdded 25 new items\nUpdated 10 items\nCompleted in 45.3 seconds"
}
```

### zotero_database_status

**Input:**
```json
{}
```

**Output:**
```json
{
  "success": true,
  "exists": true,
  "item_count": 523,
  "last_updated": "2024-01-20T13:45:30Z",
  "embedding_model": "openai",
  "model_name": "text-embedding-3-small",
  "fulltext_enabled": true,
  "auto_update": true,
  "update_frequency": "daily",
  "message": "Database initialized with 523 items\nLast updated: 2024-01-20T13:45:30Z\nEmbedding model: openai\nModel name: text-embedding-3-small\nAuto-update: Enabled (daily)\nFull-text indexing: Enabled"
}
```

## Error Responses

All tools return consistent error responses when something goes wrong:

### Example: Item Not Found
```json
{
  "success": false,
  "error": "Item not found: INVALID_KEY",
  "item_key": "INVALID_KEY",
  // ... other required fields with default values
}
```

### Example: Search Error
```json
{
  "success": false,
  "error": "Search error: Database connection failed",
  "query": "machine learning",
  "count": 0,
  "results": []
}
```

### Example: Note Creation Error
```json
{
  "success": false,
  "error": "Note creation error: Invalid parent item key",
  "note_key": "",
  "parent_key": "INVALID"
}
```

## Pagination Example

When working with large result sets, use offset and limit:

### Request 1: First page
```json
{
  "query": "machine learning",
  "limit": 10,
  "offset": 0
}
```

**Response:**
```json
{
  "success": true,
  "count": 10,
  "total_count": 45,
  "has_more": true,
  "next_offset": 10,
  "results": [ /* 10 items */ ]
}
```

### Request 2: Next page
```json
{
  "query": "machine learning",
  "limit": 10,
  "offset": 10
}
```

**Response:**
```json
{
  "success": true,
  "count": 10,
  "total_count": 45,
  "has_more": true,
  "next_offset": 20,
  "results": [ /* next 10 items */ ]
}
```

## Benefits of Structured Responses

1. **Type Safety**: Responses are validated by Pydantic
2. **Consistency**: All tools follow the same structure
3. **Error Handling**: Errors are always in the same format
4. **Pagination**: Built-in support for large datasets
5. **Machine-Readable**: Easy to parse programmatically
6. **Extensible**: New fields can be added without breaking changes

## Migration from Old Format

The new structured format replaces the previous string-based responses. The `success` field now explicitly indicates operation status, and `error` contains details if something went wrong.
