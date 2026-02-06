# Migration Guide: v2.x to v3.0

## Overview

Zotero MCP v3.0 introduces a modular architecture. The monolithic codebase has been split into four independent modules:

| Module | Purpose | PyPI Package |
|--------|---------|-------------|
| `paper-feed` | RSS/Gmail paper collection | `pip install paper-feed` |
| `zotero-core` | Zotero API access (CRUD, search) | `pip install zotero-core` |
| `paper-analyzer` | PDF analysis with LLM | `pip install paper-analyzer` |
| `zotero-mcp` | MCP integration layer | `pip install zotero-mcp` |

## Breaking Changes

### 1. Module Independence

**Before (v2.x):** Everything in one package.

```python
from zotero_mcp.services.rss import RSSService
from zotero_mcp.services.workflow import WorkflowService
from zotero_mcp.services.zotero.item_service import ItemService
```

**After (v3.0):** Separate modules with clean imports.

```python
# Paper collection
from paper_feed import RSSSource, FilterPipeline

# Zotero access
from zotero_core.services.item_service import ItemService

# PDF analysis
from paper_analyzer import PDFAnalyzer
from paper_analyzer.clients import DeepSeekClient
```

### 2. Configuration

**Before (v2.x):** JSON config at `~/.config/zotero-mcp/config.json`

**After (v3.0):** Environment variables or `.env` file (JSON config still supported as fallback)

```bash
# .env file
ZOTERO_LIBRARY_ID=your_library_id
ZOTERO_API_KEY=your_api_key
LLM_PROVIDER=deepseek
LLM_API_KEY=your_llm_key
```

### 3. CLI Commands

CLI commands remain the same. The `zotero-mcp` CLI is still the main entry point:

```bash
zotero-mcp serve          # Start MCP server
zotero-mcp setup          # Configure
zotero-mcp scan           # Scan for unprocessed papers
zotero-mcp update-db      # Update semantic search index
zotero-mcp rss fetch      # Fetch RSS feeds
```

## Installation Migration

### Minimal (Zotero access + PDF analysis)

```bash
pip install zotero-mcp
```

This installs `zotero-core` and `paper-analyzer` as dependencies.

### Full (with paper collection)

```bash
pip install zotero-mcp[full]
```

This also installs `paper-feed`.

### Individual Modules

```bash
# Just paper collection (no Zotero dependency)
pip install paper-feed

# Just Zotero access
pip install zotero-core

# Just PDF analysis
pip install paper-analyzer
```

## Code Migration Examples

### RSS Feed Processing

```python
# === Before (v2.x) ===
from zotero_mcp.services.rss import RSSService
service = RSSService()
await service.fetch_feeds()

# === After (v3.0) ===
from paper_feed import RSSSource, FilterPipeline, FilterCriteria

source = RSSSource("https://arxiv.org/rss/cs.AI")
papers = await source.fetch_papers(limit=50)

criteria = FilterCriteria(keywords=["machine learning"])
filtered = await FilterPipeline().filter(papers, criteria)
```

### PDF Analysis

```python
# === Before (v2.x) ===
from zotero_mcp.services.workflow import WorkflowService
service = WorkflowService()
await service.analyze_items(collection_key="ABC123")

# === After (v3.0) ===
from paper_analyzer import PDFAnalyzer
from paper_analyzer.clients import DeepSeekClient

llm = DeepSeekClient(api_key="your-key")
analyzer = PDFAnalyzer(llm_client=llm)
result = await analyzer.analyze("paper.pdf")
print(result.summary)
```

### Zotero Item Access

```python
# === Before (v2.x) ===
from zotero_mcp.services.zotero.item_service import ItemService
from zotero_mcp.services import get_data_service
service = get_data_service()

# === After (v3.0) ===
from zotero_core.clients.zotero_client import ZoteroClient
from zotero_core.services.item_service import ItemService

client = ZoteroClient(library_id="...", api_key="...")
service = ItemService(client)
item = await service.get_item("ABCD1234")
```

### Search

```python
# === Before (v2.x) ===
from zotero_mcp.services.zotero.search_service import SearchService

# === After (v3.0) ===
from zotero_core.services.hybrid_search import HybridSearchService

search = HybridSearchService(keyword_search=..., semantic_search=...)
results = await search.search("neural networks", search_mode="hybrid")
```

## New Features in v3.0

### Standalone Module Usage

Each module works independently without the full stack:

```python
# Use paper-feed without Zotero
from paper_feed import RSSSource, JSONAdapter
papers = await RSSSource("https://arxiv.org/rss/cs.AI").fetch_papers()
await JSONAdapter().export(papers, "papers.json")

# Use paper-analyzer without Zotero
from paper_analyzer import PDFAnalyzer, PDFExtractor
from paper_analyzer.clients import DeepSeekClient
result = await PDFAnalyzer(llm_client=DeepSeekClient(api_key="...")).analyze("paper.pdf")
```

### Hybrid Search with RRF

New Reciprocal Rank Fusion algorithm for combining keyword and semantic search:

```python
from zotero_core.services.hybrid_search import HybridSearchService

# Combines keyword + semantic results using RRF scoring
results = await hybrid_search.search("transformers attention", search_mode="hybrid")
```

### Analysis Templates

Customizable analysis templates:

```python
from paper_analyzer import PDFAnalyzer
from paper_analyzer.templates import TemplateManager

mgr = TemplateManager()
# Built-in: "default", "multimodal", "structured" (JSON output)
result = await analyzer.analyze("paper.pdf", template_name="structured")
```

## FAQ

**Q: Do I need to change my MCP client configuration?**
A: No. The `zotero-mcp serve` command works the same way.

**Q: Will my existing config.json still work?**
A: Yes, as a fallback. But we recommend migrating to `.env` files.

**Q: Can I use the old import paths?**
A: No. The internal module structure has changed. Follow the migration examples above.

**Q: Is the semantic search database compatible?**
A: Yes. The ChromaDB database format is unchanged.
