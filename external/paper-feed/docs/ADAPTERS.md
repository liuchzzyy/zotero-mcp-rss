# Export Adapters

This module provides adapters for exporting `PaperItem` objects to various destinations.

## Available Adapters

### JSONAdapter

Export papers to JSON file format.

**Features:**
- Converts `PaperItem` objects to JSON
- Handles date serialization automatically
- Optional metadata inclusion
- Automatic directory creation
- UTF-8 encoding with proper formatting

**Usage:**

```python
from paper_feed import JSONAdapter
import asyncio

async def export_papers(papers):
    adapter = JSONAdapter()
    result = await adapter.export(
        papers=papers,
        filepath="output/papers.json",
        include_metadata=True,
    )
    print(f"Exported {result['count']} papers to {result['filepath']}")
```

**Parameters:**
- `papers` (List[PaperItem]): Papers to export
- `filepath` (str): Output file path
- `include_metadata` (bool): Include raw metadata field (default: True)

**Returns:**
- `count` (int): Number of papers exported
- `filepath` (str): Absolute path to output file
- `success` (bool): True if export succeeded

### ZoteroAdapter

Export papers to Zotero library via API.

**Features:**
- Converts `PaperItem` to Zotero journalArticle format
- Batch import with error handling
- Optional collection targeting
- Clear error messages if zotero-core not installed

**Dependencies:**
- Requires `zotero-core` package (optional dependency)

**Installation:**

```bash
pip install zotero-core
```

**Usage:**

```python
from paper_feed.adapters import ZoteroAdapter
import asyncio

async def export_to_zotero(papers):
    adapter = ZoteroAdapter(
        library_id="user:123456",
        api_key="your_api_key",
        library_type="user",
    )
    result = await adapter.export(
        papers=papers,
        collection_id="ABC123",  # Optional
    )
    print(f"Exported {result['success_count']}/{result['total']} papers")
    if result['failures']:
        print(f"Failures: {result['failures']}")
```

**Parameters:**
- `papers` (List[PaperItem]): Papers to export
- `collection_id` (str, optional): Zotero collection ID

**Returns:**
- `success_count` (int): Number of successfully imported papers
- `total` (int): Total papers attempted
- `failures` (List[Dict]): List of failed imports with error messages

**Zotero Item Mapping:**

| PaperItem Field | Zotero Field |
|----------------|--------------|
| title | title |
| authors | creators (type: author) |
| abstract | abstractNote |
| url | url |
| doi | DOI |
| published_date | date (ISO format) |
| tags | tags |
| - | accessDate (auto-generated) |

## Implementation Details

### Error Handling

Both adapters implement comprehensive error handling:

- **JSONAdapter**: Catches IO/OSError and re-raises with clear message
- **ZoteroAdapter**: Tracks individual failures in batch operations

### Optional Dependencies

The `ZoteroAdapter` uses Python's ImportError mechanism for optional dependencies:

```python
try:
    from paper_feed.adapters import ZoteroAdapter
    # ZoteroAdapter available
except ImportError:
    # zotero-core not installed
    ZoteroAdapter = None
```

### Date Serialization

`JSONAdapter` automatically converts `date` objects to ISO format strings:

```python
# Before: date(2024, 1, 15)
# After: "2024-01-15"
```

## Testing

Run adapter tests:

```bash
cd external/paper-feed
uv run pytest tests/unit/test_adapters.py -v
```

**Test Coverage:**
- JSON export with/without metadata
- Empty paper list handling
- Directory creation
- Zotero conversion function
- ImportError handling for missing dependencies

## Future Enhancements

Potential additional adapters:
- `BibTeXAdapter` - Export to BibTeX format
- `CSVAdapter` - Export to CSV spreadsheet
- `MarkdownAdapter` - Export to markdown documents
- `NotionAdapter` - Export to Notion database
- `ObsidianAdapter` - Export to Obsidian vault
