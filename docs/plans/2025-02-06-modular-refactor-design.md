# Zotero MCP Modular Refactor Design

**Date**: 2025-02-06
**Author**: Refactor Planning
**Status**: Draft

## Executive Summary

This document outlines the comprehensive refactoring plan to modularize the Zotero MCP monolithic codebase into four independent, reusable packages. The refactoring follows a three-phase approach over 3-5 months, prioritizing maintainability, testability, and independent usability of each module.

## Goals

1. **Separation of Concerns**: Each module has a single, well-defined responsibility
2. **Independent Usability**: Modules can be used standalone without Zotero MCP
3. **Improved Testability**: Smaller, focused modules are easier to test
4. **Better Maintainability**: Clear boundaries between components
5. **Future Extensibility**: Easy to add new features or replace modules

## Module Architecture

### Overview Diagram

```
┌─────────────────────────────────────────────────────────┐
│                    Zotero MCP Server                     │
│                 (FastMCP + CLI entry)                    │
└─────────────────────────────────────────────────────────┘
                         │
        ┌────────────────┼────────────────┐
        │                │                │
        ▼                ▼                ▼
┌─────────────┐  ┌──────────────┐  ┌─────────────┐
│paper-feed   │  │  zotero-core │  │paper-analyzer│
│ (数据采集)   │  │  (Zotero)    │  │  (PDF分析)   │
└─────────────┘  └──────────────┘  └─────────────┘
```

### Module Dependencies

```
paper-feed      ◄────────┐
    │                    │
    │ (适配器)           │
    ▼                    │
zotero-core      ◄────────┤
    │                    │
    ▼                    │
paper-analyzer  ─────────┤
                         │
                         │ (都可选)
                         ▼
                   zotero-mcp
```

## Module Details

### 1. paper-feed (通用论文采集库)

**Repository**: `paper-feed`
**Version**: `1.0.0`
**License**: MIT

**Purpose**: Independent academic paper data source collection framework

#### Core Features

1. **Data Source Abstraction**
   - RSS feeds (arXiv, biorXiv, Nature, Science, etc.)
   - Email alerts (Google Scholar, journal TOCs)
   - Extensible for future sources (Web scraping, direct APIs)

2. **Multi-Stage Filtering Pipeline**
   - Stage 1: Category-based fast filtering
   - Stage 2: Keyword matching (any/all/weighted modes)
   - Stage 3: AI semantic filtering (LLM-powered)

3. **Export Adapters**
   - Zotero adapter
   - JSON adapter
   - Future: Notion, Obsidian, etc.

#### Data Models

```python
class Paper(BaseModel):
    """Universal paper model, not dependent on Zotero"""
    title: str
    authors: List[str]
    abstract: str
    published_date: Optional[date]
    doi: Optional[str]
    url: str
    source: str  # "arXiv", "Google Scholar", etc.
    pdf_url: Optional[str]
    tags: List[str]
    metadata: Dict[str, Any]  # Extension fields
```

#### Directory Structure

```
paper-feed/
├── src/paper_feed/
│   ├── __init__.py
│   ├── core/
│   │   ├── models.py          # Paper, FilterConfig, FilterResult
│   │   ├── source.py          # PaperSource abstract
│   │   └── adapter.py         # ExportAdapter abstract
│   ├── sources/
│   │   ├── rss/               # RSS implementation
│   │   │   ├── fetcher.py     # RSS feed fetching
│   │   │   └── parser.py      # RSS parsing to Paper models
│   │   └── email/             # Email implementation
│   │       ├── gmail/         # Gmail client
│   │       └── imap/          # Generic IMAP
│   ├── filters/
│   │   ├── pipeline.py        # MultiStageFilter
│   │   ├── category.py        # CategoryFilterStage
│   │   ├── keyword.py         # KeywordFilterStage
│   │   └── ai_filter.py       # AIFilterStage
│   ├── adapters/
│   │   ├── zotero.py          # ZoteroAdapter
│   │   ├── json.py            # JSONAdapter
│   │   └── __init__.py
│   └── cli.py                 # Independent CLI tool
├── tests/
│   ├── unit/
│   ├── integration/
│   └── fixtures/
├── examples/
│   └── basic_usage.py
├── pyproject.toml
├── README.md
└── LICENSE
```

#### Usage Example

```python
from paper_feed import RSSSource, MultiStageFilter, ZoteroAdapter, FilterCriteria

# 1. Fetch from RSS
source = RSSSource("https://arxiv.org/rss/cs.AI")
papers = await source.fetch_papers()

# 2. Multi-stage filter
criteria = FilterCriteria(
    keywords=["machine learning", "deep learning"],
    categories=["cs.AI", "cs.LG"],
    ai_interests=["transformer architectures", "LLM"],
    min_relevance_score=0.7
)
filtered = await MultiStageFilter().filter(papers, criteria)

# 3. Export to Zotero
adapter = ZoteroAdapter(library_id="user_123", api_key="...")
result = await adapter.export(filtered.papers)
print(f"Exported {result.success_count} papers to Zotero")
```

#### Dependencies

```toml
[project]
dependencies = [
    "feedparser>=6.0.0",
    "google-api-python-client>=2.0.0",
    "pydantic>=2.0.0",
    "httpx>=0.25.0",
    "beautifulsoup4>=4.0.0",
]

[project.optional-dependencies]
llm = [
    "openai>=1.0.0",  # For AI filtering
]
```

---

### 2. zotero-core (Zotero数据访问)

**Repository**: `zotero-core`
**Version**: `1.0.0`
**License**: MIT

**Purpose**: Focused Zotero data operations

#### Core Features

1. **Zotero API Access**
   - Web API client (pyzotero)
   - Local database client (optional, for Zotero 7+)
   - Automatic backend selection

2. **CRUD Services**
   - ItemService: Create, read, update, delete items
   - CollectionService: Manage collections
   - TagService: Tag operations
   - MetadataService: DOI lookup via Crossref/OpenAlex

3. **Enhanced Search**
   - Hybrid search service (keyword + semantic)
   - Reciprocal Rank Fusion (RRF) algorithm
   - Smart query builder for advanced searches

4. **Utilities**
   - PDF content extraction (PyMuPDF)
   - Duplicate detection
   - Data mapping and formatting

#### Directory Structure

```
zotero-core/
├── src/zotero_core/
│   ├── __init__.py
│   ├── clients/
│   │   ├── api.py             # Zotero API client
│   │   ├── local_db.py        # Local database client
│   │   └── pdf_extractor.py   # PDF extraction
│   ├── services/
│   │   ├── item_service.py
│   │   ├── collection_service.py
│   │   ├── tag_service.py
│   │   ├── metadata_service.py
│   │   ├── search_service.py  # Enhanced search
│   │   ├── hybrid_search.py   # Hybrid search with RRF
│   │   └── duplicate_service.py
│   ├── models/
│   │   ├── items.py
│   │   ├── collections.py
│   │   └── common.py
│   ├── utils/
│   │   ├── config.py
│   │   ├── formatting.py
│   │   └── retry.py
│   └── cli.py                 # Standalone CLI
├── tests/
├── pyproject.toml
├── README.md
└── LICENSE
```

#### Hybrid Search Implementation

```python
class HybridSearchService:
    """Hybrid search service (keyword + semantic)"""

    def __init__(self, item_service: ItemService):
        self.item_service = item_service
        self.semantic_search = None  # Optional, if semantic-search installed

    async def search(
        self,
        query: str,
        search_mode: str = "hybrid",
        top_k: int = 10,
        collection_key: Optional[str] = None
    ) -> SearchResults:
        """
        search_mode:
        - "keyword": Pure keyword search (Zotero API)
        - "semantic": Pure semantic search (requires semantic-search module)
        - "hybrid": Hybrid search (RRF fusion)
        """

    async def _hybrid_search_rrf(
        self,
        query: str,
        top_k: int,
        collection_key: Optional[str]
    ) -> SearchResults:
        """
        Reciprocal Rank Fusion (RRF) algorithm
        Reference: ZotSeek implementation
        """
        # 1. Keyword search
        keyword_results = await self._keyword_search(query, top_k * 2, collection_key)

        # 2. Semantic search (if available)
        if self.semantic_search:
            semantic_results = await self._semantic_search(query, top_k * 2, collection_key)
        else:
            semantic_results = []

        # 3. RRF fusion
        fused_scores = self._rrf_fusion(keyword_results, semantic_results, k=60)

        # 4. Sort and return top_k
        sorted_results = sorted(fused_scores.items(), key=lambda x: x[1], reverse=True)[:top_k]

        return SearchResults(...)

    def _rrf_fusion(
        self,
        keyword_results: List[Item],
        semantic_results: List[Item],
        k: int = 60
    ) -> dict[Item, float]:
        """
        RRF formula: score = Σ(1 / (k + rank_i))

        Fuse rankings from two search methods
        """
        scores = {}

        # Contribution from keyword search
        for rank, item in enumerate(keyword_results, 1):
            scores[item] = scores.get(item, 0) + 1 / (k + rank)

        # Contribution from semantic search
        for rank, item in enumerate(semantic_results, 1):
            scores[item] = scores.get(item, 0) + 1 / (k + rank)

        return scores
```

#### Dependencies

```toml
[project]
dependencies = [
    "pyzotero>=1.8.0",
    "PyMuPDF>=1.23.0",
    "requests>=2.31.0",
    "pydantic>=2.0.0",
    "python-bibtex>=1.4.0",
]

[project.optional-dependencies]
semantic = [
    "chromadb>=0.4.0",  # For semantic search
]
```

---

### 3. paper-analyzer (PDF分析引擎)

**Repository**: `paper-analyzer`
**Version**: `1.0.0`
**License**: MIT

**Purpose**: PDF content extraction and AI analysis

#### Core Features

1. **Content Extraction**
   - Text extraction (PyMuPDF)
   - Image extraction (base64 encoded)
   - Table extraction
   - Multi-modal content support

2. **LLM Analysis**
   - Multi-provider support (DeepSeek, OpenAI, Gemini, Claude)
   - Customizable analysis templates
   - Batch processing with checkpoint/resume
   - Multi-modal analysis (text + images)

3. **Workflow Management**
   - Checkpoint system for interruptible workflows
   - Progress tracking
   - Error handling and retry logic

#### Directory Structure

```
paper-analyzer/
├── src/paper_analyzer/
│   ├── __init__.py
│   ├── extractors/
│   │   ├── pdf_extractor.py   # PyMuPDF wrapper
│   │   ├── markdown.py        # Markdown conversion
│   │   └── multimodal.py      # Multi-modal extraction
│   ├── analyzers/
│   │   ├── llm_analyzer.py    # LLM analysis
│   │   └── templates.py       # Prompt templates
│   ├── clients/
│   │   └── llm/               # LLM providers
│   │       ├── base.py
│   │       ├── deepseek.py
│   │       ├── openai.py
│   │       ├── gemini.py
│   │       └── claude.py
│   ├── services/
│   │   ├── workflow.py        # Batch processing
│   │   └── checkpoint.py      # Checkpoint management
│   ├── models/
│   │   └── analysis.py
│   └── cli.py
├── tests/
├── pyproject.toml
├── README.md
└── LICENSE
```

#### Dependencies

```toml
[project]
dependencies = [
    "PyMuPDF>=1.23.0",
    "pydantic>=2.0.0",
    "httpx>=0.25.0",
]

[project.optional-dependencies]
deepseek = ["openai>=1.0.0"]  # DeepSeek uses OpenAI-compatible API
openai = ["openai>=1.0.0"]
gemini = ["google-generativeai>=0.3.0"]
claude = ["anthropic>=0.18.0"]
all = ["paper-analyzer[deepseek,openai,gemini,claude]"]
```

---

### 4. zotero-mcp (主项目 - 集成层)

**Repository**: `zotero-mcp`
**Version**: `3.0.0`
**License**: MIT

**Purpose**: Lightweight integration layer for MCP protocol

#### Simplified Structure

```
zotero-mcp/
├── src/zotero_mcp/
│   ├── __init__.py
│   ├── server.py              # FastMCP server
│   ├── cli.py                 # CLI entry point
│   └── integration/
│       ├── mcp_tools.py       # MCP tool wrappers (thin layer)
│       ├── config.py          # Configuration
│       └── __init__.py
├── tests/
│   └── integration/
│       └── test_mcp_tools.py
├── pyproject.toml
├── README.md
├── CLAUDE.md
└── LICENSE
```

#### Dependencies

```toml
[project]
dependencies = [
    "fastmcp>=2.14.0",
    "zotero-core>=1.0.0",
]

[project.optional-dependencies]
ingestion = ["paper-feed>=1.0.0"]
analysis = ["paper-analyzer>=1.0.0"]
full = ["zotero-mcp[ingestion,analysis]"]
```

#### User Installation Options

```bash
# Minimal installation (core features only)
pip install zotero-mcp

# Full installation (all features)
pip install zotero-mcp[full]

# À la carte
pip install zotero-mcp[ingestion]  # Core + paper feed
pip install zotero-mcp[analysis]  # Core + PDF analysis
```

---

### 5. future-feat/semantic-search (归档)

**Purpose**: Semantic search functionality (archived, not in core)

#### Directory Structure

```
future-feat/
└── semantic-search/
    ├── src/semantic_search/
    │   ├── __init__.py
    │   ├── chroma_client.py
    │   ├── embedder.py
    │   └── search.py
    ├── tests/
    ├── pyproject.toml
    └── README.md
```

#### Usage

```bash
# Optional installation
cd future-feat/semantic-search
pip install .

# Use with zotero-core
from zotero_core import HybridSearchService
from semantic_search import ChromaEmbedder

search_service = HybridSearchService(...)
search_service.semantic_search = ChromaEmbedder(...)
results = await search_service.search("query", search_mode="hybrid")
```

---

## Implementation Phases

### Phase 1: Preparation and Isolation (Weeks 1-2)

**Goal**: Create module boundaries without breaking existing functionality

#### Tasks

1. **Create `future-feat/semantic-search/` directory**
   - Move semantic search related code
   - Independent `pyproject.toml`
   - Update imports

2. **Create compatibility layer**
   - Preserve old import paths with deprecation warnings
   - Ensure existing tests pass
   - No breaking changes yet

3. **Update dependencies**
   - Make `chromadb` optional in main project
   - Document migration path

**Success Criteria**:
- ✅ All 140 tests still pass
- ✅ Can install and run normally
- ✅ Semantic search available via optional install

---

### Phase 2: Module Extraction (Weeks 3-10)

#### 2.1 paper-feed Module (Weeks 3-5)

**Tasks**:
1. Create `paper-feed/` repository structure
2. Implement `Paper` model (not Zotero-dependent)
3. Implement `MultiStageFilter` pipeline:
   - `CategoryFilterStage`
   - `KeywordFilterStage` (any/all/weighted modes)
   - `AIFilterStage` (based on existing `ai_filter.py`)
4. Implement sources:
   - RSS fetcher and parser
   - Gmail client
5. Implement adapters:
   - `ZoteroAdapter` (uses `zotero-core`)
   - `JSONAdapter`
6. Create independent CLI
7. Write comprehensive tests
8. Documentation and examples

**Success Criteria**:
- ✅ Can be used standalone: `pip install paper-feed`
- ✅ All filter stages working correctly
- ✅ Test coverage > 80%
- ✅ Documentation complete

#### 2.2 zotero-core Module (Weeks 5-7)

**Tasks**:
1. Create `zotero-core/` repository structure
2. Implement services:
   - `ItemService`, `CollectionService`, `TagService`
   - `MetadataService` (Crossref/OpenAlex)
   - `HybridSearchService` with RRF algorithm
   - `SmartQueryBuilder`
3. Implement clients:
   - Zotero API client
   - PDF extractor
4. Create standalone CLI
5. Write comprehensive tests
6. Documentation

**Success Criteria**:
- ✅ Can be used standalone: `pip install zotero-core`
- ✅ Hybrid search working (with/without semantic-search)
- ✅ Test coverage > 80%
- ✅ API documentation complete

#### 2.3 paper-analyzer Module (Weeks 7-10)

**Tasks**:
1. Create `paper-analyzer/` repository structure
2. Implement extractors:
   - PDF content extraction (PyMuPDF)
   - Multi-modal extraction (images, tables)
3. Implement analyzers:
   - LLM analyzer service
   - Template management
4. Implement LLM clients:
   - DeepSeek, OpenAI, Gemini, Claude
5. Implement workflow service:
   - Checkpoint system
   - Batch processing
6. Create standalone CLI
7. Write comprehensive tests
8. Documentation

**Success Criteria**:
- ✅ Can be used standalone: `pip install paper-analyzer`
- ✅ Multi-modal analysis working
- ✅ Checkpoint/resume working
- ✅ Test coverage > 80%

---

### Phase 3: Main Project Simplification (Weeks 11-12)

**Goal**: Refactor main project to lightweight integration layer

#### Tasks

1. **Remove business logic**
   - Delete code moved to modules
   - Update imports to use modules
   - Remove redundant utilities

2. **Simplify to integration layer**
   - Keep only FastMCP server setup
   - Keep CLI entry point
   - Keep thin MCP tool wrappers

3. **Update dependencies**
   - Depend on `zotero-core`
   - Optional `paper-feed` and `paper-analyzer`
   - Remove direct dependencies on module internals

4. **Update tests**
   - Focus on integration tests
   - Test module interactions
   - Remove redundant unit tests (now in modules)

5. **Update documentation**
   - Update README with new architecture
   - Update CLAUDE.md
   - Create migration guide
   - Update examples

**Success Criteria**:
- ✅ Main project < 2000 lines (excluding tests)
- ✅ All integration tests passing
- ✅ Documentation complete
- ✅ Backward compatibility maintained

---

## Migration Guide

### For Users

#### Before (v2.5.0)

```bash
pip install zotero-mcp
zotero-mcp serve  # All features included
```

#### After (v3.0.0)

```bash
# Option 1: Minimal (core features only)
pip install zotero-mcp

# Option 2: Full (all features)
pip install zotero-mcp[full]

# Option 3: À la carte
pip install zotero-mcp[ingestion]  # Core + paper feed
pip install zotero-mcp[analysis]  # Core + PDF analysis

# Optional: Semantic search
cd future-feat/semantic-search && pip install .
```

### For Developers

#### Using paper-feed Standalone

```python
from paper_feed import RSSSource, MultiStageFilter, FilterCriteria

# Fetch and filter papers
source = RSSSource("https://arxiv.org/rss/cs.AI")
papers = await source.fetch_papers()

criteria = FilterCriteria(
    keywords=["machine learning"],
    ai_interests=["transformer architectures"]
)
filtered = await MultiStageFilter().filter(papers, criteria)

# Export
for paper in filtered.papers:
    print(f"{paper.title} - {paper.url}")
```

#### Using zotero-core Standalone

```python
from zotero_core import ZoteroClient, HybridSearchService

client = ZoteroClient(library_id="user_123", api_key="...")
search_service = HybridSearchService(client)

# Hybrid search
results = await search_service.search(
    "machine learning interpretability",
    search_mode="hybrid",
    top_k=10
)
```

#### Using paper-analyzer Standalone

```python
from paper_analyzer import PDFAnalyzer, DeepSeekClient

analyzer = PDFAnalyzer(llm_client=DeepSeekClient(...))
result = analyzer.analyze("paper.pdf")

print(result.summary)
print(result.key_points)
```

---

## Testing Strategy

### Unit Tests

Each module will have comprehensive unit tests:
- **paper-feed**: Filter stages, sources, adapters
- **zotero-core**: Services, clients, search
- **paper-analyzer**: Extractors, analyzers, workflows
- **zotero-mcp**: Integration tests

### Integration Tests

Test module interactions:
- paper-feed → zotero-core export
- zotero-core → paper-analyzer processing
- End-to-end workflows

### Test Coverage Targets

- **paper-feed**: > 80%
- **zotero-core**: > 80%
- **paper-analyzer**: > 80%
- **zotero-mcp**: > 70% (integration focused)

---

## Risks and Mitigations

### Risk 1: Breaking Changes

**Mitigation**:
- Compatibility layer in Phase 1
- Comprehensive migration guide
- Deprecation warnings

### Risk 2: Test Regressions

**Mitigation**:
- Continuous testing throughout refactoring
- Baseline: 140 passing tests
- Incremental migration

### Risk 3: Timeline Overrun

**Mitigation**:
- Phased approach (can stop after any phase)
- Clear success criteria
- Regular progress reviews

### Risk 4: Module API Drift

**Mitigation**:
- Design APIs before implementation
- Versioned releases
- Clear API documentation

---

## Success Metrics

### Code Quality

- **Lines of Code per Module**: < 5000 lines
- **Test Coverage**: > 80% for all modules
- **Documentation**: 100% API coverage

### Usability

- **Independent Installation**: All modules can be installed separately
- **Standalone Usage**: All modules can be used without zotero-mcp
- **Examples**: At least 3 usage examples per module

### Maintainability

- **Module Independence**: No circular dependencies
- **API Stability**: Clear versioning and deprecation policy
- **Documentation**: Complete README, API docs, and migration guide

---

## Timeline

| Phase | Duration | Deliverable |
|-------|----------|-------------|
| **Phase 1** | Weeks 1-2 | Semantic search isolated, tests passing |
| **Phase 2a** | Weeks 3-5 | paper-feed module complete |
| **Phase 2b** | Weeks 5-7 | zotero-core module complete |
| **Phase 2c** | Weeks 7-10 | paper-analyzer module complete |
| **Phase 3** | Weeks 11-12 | Main project simplified |

**Total**: 12 weeks (3 months)

---

## Next Steps

1. **Review and approve this design**
2. **Create Phase 1 task list**
3. **Set up repositories**:
   - `paper-feed`
   - `zotero-core`
   - `paper-analyzer`
4. **Begin Phase 1 implementation**

---

## References

- [ZotSeek - RRF Algorithm](https://github.com/introfini/ZotSeek)
- [paper-firehose - Paper Filtering](https://github.com/zrbyte/paper-firehose)
- [paperscraper - Multi-source Collection](https://github.com/jannisborn/paperscraper)
- [findpapers - Deduplication](https://github.com/jonatasgrosman/findpapers)
- Current Zotero MCP codebase analysis (24,000 lines, 102 files)

---

**Document Version**: 1.0
**Last Updated**: 2025-02-06
