# zotero-core

A standalone Python library for comprehensive Zotero data access, providing complete CRUD operations, search capabilities, and metadata management for Zotero research libraries.

## Features

- **Complete Zotero Web API Access**: Full support for all Zotero API endpoints
- **CRUD Operations**: Create, read, update, and delete items, collections, and tags
- **Hybrid Search**: Combine keyword search with semantic search using Reciprocal Rank Fusion (RRF)
- **Metadata Enrichment**: Automatic metadata lookup via Crossref and OpenAlex APIs
- **Duplicate Detection**: Smart duplicate detection based on DOI, title, and authors
- **Semantic Search**: Optional vector-based semantic search using ChromaDB
- **Type Safety**: Full Pydantic v2 model validation
- **Async Support**: Async/await for all I/O operations

## Installation

This is a local development module. Install in editable mode:

```bash
cd modules/zotero-core
pip install -e .
```

For semantic search support:

```bash
pip install -e ".[semantic]"
```

For development:

```bash
pip install -e ".[all]"
```

## Quick Start

```python
import asyncio
from zotero_core import ZoteroService, Item

async def main():
    # Initialize service
    service = ZoteroService(
        library_id="your_library_id",
        api_key="your_api_key",
        library_type="user"  # or "group"
    )

    # Fetch an item
    item = await service.get_item("ABCD1234")
    print(f"Title: {item.title}")

    # Search items
    results = await service.search_items("machine learning", limit=10)
    for item in results:
        print(f"- {item.title}")

    # Create a new item
    new_item = Item(
        item_type="journalArticle",
        title="My Paper",
        creators=[{"firstName": "John", "lastName": "Doe", "creatorType": "author"}],
        date="2024",
        doi="10.1234/example.doi"
    )
    created = await service.create_item(new_item)
    print(f"Created item with key: {created.key}")

if __name__ == "__main__":
    asyncio.run(main())
```

## API Reference

### Models

#### Item
```python
from zotero_core.models import Item

item = Item(
    key="ABCD1234",
    item_type="journalArticle",
    title="Paper Title",
    creators=[
        {"firstName": "Jane", "lastName": "Smith", "creatorType": "author"}
    ],
    abstract="Paper abstract...",
    date="2024",
    doi="10.1234/example.doi",
    tags=["research", "important"],
    collections=["ABC123"]
)
```

#### Collection
```python
from zotero_core.models import Collection

collection = Collection(
    key="ABC123",
    name="My Research",
    parent_key="DEF456"  # Optional, for sub-collections
)
```

#### Tag
```python
from zotero_core.models import Tag

tag = Tag(
    tag="important",
    count=42
)
```

### Services

#### ZoteroService
Main service for Zotero operations:

```python
service = ZoteroService(library_id="...", api_key="...")

# CRUD operations
item = await service.get_item(key)
items = await service.get_items(limit=20)
new_item = await service.create_item(item_data)
updated = await service.update_item(key, data)
await service.delete_item(key)

# Search
results = await service.search_items(query)
results = await service.search_by_tags(tags)
results = await service.semantic_search(query)

# Collections
collections = await service.get_collections()
collection = await service.create_collection(name, parent_key)
await service.delete_collection(key)

# Tags
tags = await service.get_tags()
```

#### SearchService
Advanced search capabilities:

```python
from zotero_core import SearchService

search_service = SearchService(zotero_service)

# Keyword search
results = await search_service.keyword_search(
    query="machine learning",
    mode="titleCreatorYear"
)

# Tag-based search
results = await search_service.tag_search(["research", "important"])

# Advanced search
results = await search_service.advanced_search([
    {"field": "title", "operation": "contains", "value": "climate"},
    {"field": "date", "operation": "isGreaterThan", "value": "2020"}
])

# Hybrid search (keyword + semantic)
results = await search_service.hybrid_search(
    query="neural networks",
    keyword_weight=0.5,
    semantic_weight=0.5
)
```

#### MetadataService
Metadata enrichment:

```python
from zotero_core import MetadataService

metadata_service = MetadataService()

# Enrich item with Crossref data
enriched = await metadata_service.enrich_with_crossref(item)

# Enrich with OpenAlex data
enriched = await metadata_service.enrich_with_openalex(item)

# Auto-enrich (tries both sources)
enriched = await metadata_service.auto_enrich(item)
```

## Configuration

The library supports configuration via environment variables or constructor parameters:

```python
# Via environment variables
# ZOTERO_LIBRARY_ID=your_library_id
# ZOTERO_API_KEY=your_api_key
# ZOTERO_LIBRARY_TYPE=user

service = ZoteroService()

# Or via constructor
service = ZoteroService(
    library_id="your_library_id",
    api_key="your_api_key",
    library_type="user",
    api_timeout=45,
    retry_attempts=3
)
```

## Development

```bash
# Install development dependencies
pip install -e ".[all]"

# Run tests
pytest

# Run tests with coverage
pytest --cov=src/zotero_core

# Format code
ruff format src/

# Check code
ruff check src/

# Type check
ty check src/
```

## Architecture

The library follows a layered architecture:

- **Models**: Pydantic models for data validation
- **Services**: Business logic and orchestration
- **Clients**: Low-level API clients (Zotero API, Crossref, OpenAlex, ChromaDB)

## License

MIT License - See LICENSE file for details

## Contributing

Contributions are welcome! Please read CONTRIBUTING.md for guidelines.
