# Zotero MCP 模块化重构实施计划

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 将 zotero-mcp 单体应用重构为 4 个独立模块（paper-feed, zotero-core, paper-analyzer, zotero-mcp），提升可维护性、可测试性和可复用性。

**Architecture:**
- **paper-feed**: 独立的学术论文采集框架（RSS/Gmail/过滤），作为独立 PyPI 包发布
- **zotero-core**: Zotero 数据访问层（CRUD/搜索/元数据），保留在 zotero-mcp org
- **paper-analyzer**: PDF 分析引擎（提取/LLM），保留在 zotero-mcp org
- **zotero-mcp**: 轻量级 MCP 集成层，整合上述模块

**Tech Stack:**
- FastMCP, Pydantic v2, PyMuPDF, pyzotero, OpenAI-compatible APIs
- 模块间通过 pip 依赖解耦
- .env 文件统一配置管理

---

## Phase 0: 准备阶段（Week 0）

### Task 0.1: 创建 Git Worktree

**目标**: 创建隔离的开发环境，不影响主分支

**Files:**
- Create: Git worktree directory

**Step 1: 创建 worktree**
```bash
cd zotero-mcp
git worktree add ../zotero-mcp-modular main
cd ../zotero-mcp-modular
```

**Step 2: 验证 worktree**
```bash
git branch
# 应该看到 worktree 标记
pwd
# 应该在 ../zotero-mcp-modular
```

**Step 3: 创建必要的目录结构**
```bash
mkdir -p docs/plans
mkdir -p external
```

**Step 4: Commit worktree setup**
```bash
git add .
git commit -m "chore: create modular refactor worktree"
```

---

## Phase 1: paper-feed 独立化（Week 1-5）

### Task 1.1: 创建 paper-feed 独立仓库结构

**Files:**
- Create: `external/paper-feed/README.md`
- Create: `external/paper-feed/pyproject.toml`
- Create: `external/paper-feed/src/paper_feed/__init__.py`
- Create: `external/paper-feed/src/paper_feed/core/__init__.py`
- Create: `external/paper-feed/src/paper_feed/core/models.py`
- Create: `external/paper-feed/src/paper_feed/core/base.py`

**Step 1: 创建 README.md**
```markdown
# paper-feed

Academic paper collection framework supporting RSS feeds and Gmail alerts.

## Installation

```bash
pip install paper-feed
```

## Quick Start

```python
from paper_feed import RSSSource, FilterPipeline, JSONAdapter

# Fetch from arXiv
source = RSSSource("https://arxiv.org/rss/cs.AI")
papers = await source.fetch_papers()

# Filter
criteria = FilterCriteria(keywords=["machine learning"])
filtered = await FilterPipeline().filter(papers, criteria)

# Export
await JSONAdapter().export(filtered.papers, "papers.json")
```

## Features

- RSS feed parsing (arXiv, bioRxiv, Nature, Science)
- Gmail alert parsing (Google Scholar, journal TOCs)
- Multi-stage filtering (keyword + AI semantic)
- Flexible export adapters (Zotero, JSON, etc.)
```

**Step 2: 创建 pyproject.toml**
```toml
[project]
name = "paper-feed"
version = "1.0.0"
description = "Academic paper collection from RSS and Gmail alerts"
readme = "README.md"
requires-python = ">=3.10"
dependencies = [
    "feedparser>=6.0.0",
    "pydantic>=2.0.0",
    "httpx>=0.25.0",
    "python-dateutil>=2.8.0",
    "beautifulsoup4>=4.12.0",
]

[project.optional-dependencies]
gmail = [
    "ezgmail>=0.1.0",
]
llm = [
    "openai>=1.0.0",
]
zotero = [
    "zotero-core>=1.0.0",
]
all = ["paper-feed[gmail,llm,zotero]"]

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[project.scripts]
paper-feed = "paper_feed.cli:main"
```

**Step 3: 创建核心模型文件**
```python
# external/paper-feed/src/paper_feed/core/models.py
from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
from datetime import date

class PaperItem(BaseModel):
    """通用论文模型（不依赖 Zotero）"""
    title: str
    authors: List[str] = Field(default_factory=list)
    abstract: str = Field(default="")
    published_date: Optional[date] = None
    doi: Optional[str] = None
    url: str
    pdf_url: Optional[str] = None
    source: str
    source_id: Optional[str] = None
    source_type: str  # "rss" or "email"
    categories: List[str] = Field(default_factory=list)
    tags: List[str] = Field(default_factory=list)
    metadata: Dict[str, Any] = Field(default_factory=dict)
```

**Step 4: 创建抽象基类**
```python
# external/paper-feed/src/paper_feed/core/base.py
from abc import ABC, abstractmethod
from typing import AsyncIterator, List
from ..core.models import PaperItem

class PaperSource(ABC):
    """论文数据源抽象基类"""
    source_name: str = "base"
    source_type: str = "base"

    @abstractmethod
    async def fetch_papers(
        self, limit: Optional[int] = None, since: Optional[date] = None
    ) -> List[PaperItem]:
        """从该数据源获取论文"""
        pass

class ExportAdapter(ABC):
    """导出适配器抽象基类"""
    @abstractmethod
    async def export(self, papers: List[PaperItem], **kwargs):
        """导出论文到目标系统"""
        pass
```

**Step 5: Commit**
```bash
cd external/paper-feed
git init
git add .
git commit -m "feat: initialize paper-feed project structure"
```

---

### Task 1.2: 实现 RSS 数据源

**Files:**
- Create: `external/paper-feed/src/paper_feed/sources/__init__.py`
- Create: `external/paper-feed/src/paper_feed/sources/rss.py`
- Create: `external/paper-feed/src/paper_feed/sources/rss_parser.py`
- Create: `external/paper-feed/tests/unit/test_rss_source.py`

**Step 1: 实现 RSSParser 工具类**
```python
# external/paper-feed/src/paper_feed/sources/rss_parser.py
import feedparser
from typing import Dict, Any
from ..core.models import PaperItem

class RSSParser:
    """RSS feed 解析器"""

    def parse(self, entry: Dict[str, Any], source_name: str) -> PaperItem:
        """将 feedparser entry 解析为 PaperItem"""

        # 提取作者
        authors = []
        if "authors" in entry:
            authors = [a.get("name", "") for a in entry.authors]
        elif "author" in entry:
            authors = [entry.author]

        # 提取日期
        published_date = None
        if "published_parsed" in entry:
            import datetime
            published_date = datetime.date(
                entry.published_parsed.tm_year,
                entry.published_parsed.tm_mon,
                entry.published_parsed.tm_mday
            )

        # 提取标签
        tags = []
        if "tags" in entry:
            tags = [t.term for t in entry.tags]

        return PaperItem(
            title=entry.get("title", ""),
            authors=authors,
            abstract=entry.get("summary", ""),
            published_date=published_date,
            doi=self._extract_doi(entry),
            url=entry.get("link", ""),
            pdf_url=self._extract_pdf_url(entry),
            source=source_name,
            source_id=entry.get("id", ""),
            source_type="rss",
            tags=tags,
            categories=tags,  # arXiv categories
            metadata={"raw": entry}
        )

    def _extract_doi(self, entry: Dict[str, Any]) -> str:
        """从 entry 中提取 DOI"""
        # 检查 dc_identifier
        if "dc_identifier" in entry:
            return entry.dc_identifier
        # 检查链接中的 DOI
        link = entry.get("link", "")
        if "doi.org/" in link:
            return link.split("doi.org/")[-1]
        return ""

    def _extract_pdf_url(self, entry: Dict[str, Any]) -> str:
        """从 entry 中提取 PDF 链接"""
        # 检查 pdf 链接
        for link in entry.get("links", []):
            if link.get("type", "") == "application/pdf":
                return link.href
        # 检查 arXiv PDF 链接
        link = entry.get("link", "")
        if "arxiv.org/abs/" in link:
            return link.replace("/abs/", "/pdf/")
        return ""
```

**Step 2: 实现 RSSSource**
```python
# external/paper-feed/src/paper_feed/sources/rss.py
import httpx
from typing import Optional, List
from datetime import date
from ..core.base import PaperSource
from ..core.models import PaperItem
from .rss_parser import RSSParser

class RSSSource(PaperSource):
    """RSS feed 数据源"""
    source_name = "rss"
    source_type = "rss"

    def __init__(
        self, feed_url: str, source_name: Optional[str] = None,
        user_agent: str = "paper-feed/1.0", timeout: int = 30
    ):
        self.feed_url = feed_url
        self.source_name = source_name or self._detect_source_name(feed_url)
        self.user_agent = user_agent
        self.timeout = timeout
        self.parser = RSSParser()

    def _detect_source_name(self, url: str) -> str:
        """从 URL 自动检测来源名称"""
        if "arxiv.org" in url:
            return "arXiv"
        elif "biorxiv.org" in url:
            return "bioRxiv"
        elif "nature.com" in url:
            return "Nature"
        elif "science.org" in url:
            return "Science"
        from urllib.parse import urlparse
        return urlparse(url).netloc

    async def fetch_papers(
        self, limit: Optional[int] = None, since: Optional[date] = None
    ) -> List[PaperItem]:
        """从 RSS feed 获取论文"""
        papers = []

        # 获取 RSS feed
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.get(
                self.feed_url,
                headers={"User-Agent": self.user_agent},
                follow_redirects=True
            )
            response.raise_for_status()
            feed_content = response.text

        # 使用 feedparser 解析
        import feedparser
        feed = feedparser.parse(feed_content)

        # 处理 entries
        for entry in feed.entries:
            if limit and len(papers) >= limit:
                break

            try:
                paper = self.parser.parse(entry, self.source_name)

                # 日期过滤
                if since and paper.published_date:
                    if paper.published_date < since:
                        continue

                papers.append(paper)
            except Exception as e:
                print(f"Error parsing entry: {e}")
                continue

        return papers
```

**Step 3: 编写测试**
```python
# external/paper-feed/tests/unit/test_rss_source.py
import pytest
from paper_feed.sources.rss import RSSSource

@pytest.mark.asyncio
async def test_rss_source_fetch():
    """测试 RSS 获取"""
    source = RSSSource("https://export.arxiv.org/rss/cs.AI")
    papers = await source.fetch_papers(limit=5)

    assert len(papers) > 0
    assert papers[0].title != ""
    assert papers[0].source == "arXiv"

@pytest.mark.asyncio
async def test_rss_parser():
    """测试 RSS 解析"""
    source = RSSSource("https://export.arxiv.org/rss/cs.AI")
    papers = await source.fetch_papers(limit=1)

    paper = papers[0]
    assert paper.authors is not None
    assert paper.source_type == "rss"
```

**Step 4: 运行测试**
```bash
cd external/paper-feed
pytest tests/unit/test_rss_source.py -v
# Expected: FAIL (no implementation yet)
```

**Step 5: Commit**
```bash
git add -A
git commit -m "feat: implement RSS source with parser"
```

---

### Task 1.3: 实现过滤管道

**Files:**
- Create: `external/paper-feed/src/paper_feed/filters/__init__.py`
- Create: `external/paper-feed/src/paper_feed/filters/pipeline.py`
- Create: `external/paper-feed/src/paper_feed/filters/keyword.py`
- Create: `external/paper-feed/src/paper_feed/filters/ai_filter.py`
- Create: `external/paper-feed/tests/unit/test_filters.py`

**Step 1: 创建过滤模型**
```python
# external/paper-feed/src/paper_feed/core/models.py (添加)
class FilterCriteria(BaseModel):
    """过滤条件配置"""
    keywords: List[str] = Field(default_factory=list)
    keyword_mode: str = Field(default="any")
    exclude_keywords: List[str] = Field(default_factory=list)
    ai_interests: List[str] = Field(default_factory=list)
    min_relevance_score: float = Field(default=0.6, ge=0.0, le=1.0)

class FilterResult(BaseModel):
    """过滤执行结果"""
    papers: List[PaperItem] = Field(default_factory=list)
    total_evaluated: int = Field(default=0)
    filtered_count: int = Field(default=0)
```

**Step 2: 实现关键词过滤**
```python
# external/paper-feed/src/paper_feed/filters/keyword.py
from typing import List, Tuple
from ..core.models import PaperItem, FilterCriteria

class KeywordFilterStage:
    """关键词匹配过滤"""

    def is_applicable(self, criteria: FilterCriteria) -> bool:
        return len(criteria.keywords) > 0 or len(criteria.exclude_keywords) > 0

    async def filter(
        self, papers: List[PaperItem], criteria: FilterCriteria
    ) -> Tuple[List[PaperItem], List[str]]:
        """按关键词过滤"""
        filtered = []

        for paper in papers:
            # 排除关键词
            if criteria.exclude_keywords:
                text = f"{paper.title} {paper.abstract}".lower()
                if any(kw.lower() in text for kw in criteria.exclude_keywords):
                    continue

            # 必需关键词
            if criteria.keywords:
                score = self._calculate_score(paper, criteria.keywords, criteria.keyword_mode)
                if score > 0:
                    filtered.append(paper)
            else:
                filtered.append(paper)

        return filtered, [f"Keyword filtered: {len(filtered)} remaining"]

    def _calculate_score(self, paper: PaperItem, keywords: List[str], mode: str) -> int:
        """计算关键词匹配分数"""
        title_text = paper.title.lower()
        abstract_text = paper.abstract.lower()
        all_text = f"{title_text} {abstract_text}"

        return sum(1 for kw in keywords if kw.lower() in all_text)
```

**Step 3: 实现过滤管道**
```python
# external/paper-feed/src/paper_feed/filters/pipeline.py
from typing import List
from ..core.models import FilterCriteria, FilterResult
from .keyword import KeywordFilterStage

class FilterPipeline:
    """两级过滤管道"""

    def __init__(self, llm_client=None):
        self.stages = [KeywordFilterStage()]
        # AI filter stage optional

    async def filter(
        self, papers: List[PaperItem], criteria: FilterCriteria
    ) -> FilterResult:
        """应用两级过滤"""
        filtered = papers

        for stage in self.stages:
            if not stage.is_applicable(criteria):
                continue
            filtered, _ = await stage.filter(filtered, criteria)

            if not filtered:
                break

        return FilterResult(
            papers=filtered,
            total_evaluated=len(papers),
            filtered_count=len(papers) - len(filtered)
        )
```

**Step 4: 测试**
```bash
cd external/paper-feed
pytest tests/unit/test_filters.py -v
```

**Step 5: Commit**
```bash
git add -A
git commit -m "feat: implement filter pipeline with keyword stage"
```

---

### Task 1.4: 实现 Zotero 导出适配器

**Files:**
- Create: `external/paper-feed/src/paper_feed/adapters/__init__.py`
- Create: `external/paper-feed/src/paper_feed/adapters/zotero.py`
- Create: `external/paper-feed/tests/integration/test_zotero_adapter.py`

**Step 1: 实现 ZoteroAdapter**
```python
# external/paper-feed/src/paper_feed/adapters/zotero.py
from typing import List, Optional
from ..core.base import ExportAdapter
from ..core.models import PaperItem

class ZoteroAdapter(ExportAdapter):
    """导出到 Zotero（使用 zotero-core）"""

    def __init__(self, library_id: str, api_key: str, library_type: str = "user"):
        self.library_id = library_id
        self.api_key = api_key
        self.library_type = library_type

    async def export(
        self, papers: List[PaperItem], collection_id: Optional[str] = None
    ):
        """导出论文到 Zotero"""
        try:
            from zotero_core import ItemService
        except ImportError:
            raise ImportError(
                "zotero-core is required for Zotero export. "
                "Install with: pip install paper-feed[zotero]"
            )

        service = ItemService(
            library_id=self.library_id,
            api_key=self.api_key,
            library_type=self.library_type
        )

        success_count = 0
        for paper in papers:
            try:
                item_data = self._paper_to_zotero_item(paper)
                await service.create_item(item_data, [collection_id] if collection_id else None)
                success_count += 1
            except Exception as e:
                print(f"Failed to export {paper.title}: {e}")

        return {"success_count": success_count, "total": len(papers)}

    def _paper_to_zotero_item(self, paper: PaperItem) -> dict:
        """将 PaperItem 转换为 Zotero item 格式"""
        return {
            "itemType": "journalArticle",
            "title": paper.title,
            "creators": [{"creatorType": "author", "name": name} for name in paper.authors],
            "abstractNote": paper.abstract,
            "url": paper.url,
            "DOI": paper.doi,
            "date": paper.published_date.isoformat() if paper.published_date else "",
            "tags": [{"tag": tag} for tag in paper.tags]
        }
```

**Step 2: Commit**
```bash
git add -A
git commit -m "feat: implement Zotero export adapter"
```

---

### Task 1.5: 发布 paper-feed 到 PyPI

**Files:**
- Create: `external/paper-feed/.github/workflows/publish.yml`
- Modify: `external/paper-feed/README.md`

**Step 1: 创建发布工作流**
```yaml
# external/paper-feed/.github/workflows/publish.yml
name: Publish to PyPI

on:
  release:
    types: [published]

jobs:
  publish:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - uses: actions/setup-python@v4
        with:
          python-version: '3.10'
      - name: Install build dependencies
        run: |
          pip install build twine
      - name: Build package
        run: python -m build
      - name: Publish to PyPI
        env:
          TWINE_USERNAME: __token__
          TWINE_PASSWORD: ${{ secrets.PYPI_API_TOKEN }}
        run: twine upload dist/*
```

**Step 2: 测试本地构建**
```bash
cd external/paper-feed
pip install build twine
python -m build
twine check dist/*
```

**Step 3: 发布到 PyPI**
```bash
# 实际发布时执行
twine upload dist/*
```

**Step 4: 更新 README 添加安装说明**
```markdown
## Installation

### Basic (RSS + JSON export)
```bash
pip install paper-feed
```

### With Zotero export
```bash
pip install paper-feed[zotero]
```

### With Gmail support
```bash
pip install paper-feed[gmail]
```

### Full features
```bash
pip install paper-feed[all]
```
```

**Step 5: Commit**
```bash
git add -A
git commit -m "chore: add PyPI publishing workflow"
```

---

## Phase 2: 提取 zotero-core 模块（Week 6-10）

### Task 2.1: 创建 zotero-core 模块结构

**Files:**
- Create: `modules/zotero-core/README.md`
- Create: `modules/zotero-core/pyproject.toml`
- Create: `modules/zotero-core/src/zotero_core/__init__.py`
- Create: `modules/zotero-core/src/zotero_core/models/__init__.py`

**Step 1: 创建 README.md**
```markdown
# zotero-core

Zotero data access library providing complete CRUD, search, and metadata management.

## Installation

```bash
pip install zotero-core
```

## Features

- Complete Zotero Web API access
- CRUD operations for items, collections, tags
- Hybrid search (keyword + semantic with RRF)
- Metadata enrichment via Crossref/OpenAlex
- Duplicate detection
```

**Step 2: 创建 pyproject.toml**
```toml
[project]
name = "zotero-core"
version = "1.0.0"
description = "Zotero data access library"
dependencies = [
    "pyzotero>=1.8.0",
    "pydantic>=2.0.0",
    "httpx>=0.25.0",
]

[project.optional-dependencies]
semantic = ["chromadb>=0.4.0"]
all = ["zotero-core[semantic]"]
```

**Step 3: 从主项目迁移核心模型**
```bash
# 复制现有模型
cp ../src/models/common.py modules/zotero-core/src/zotero_core/models/base.py
cp ../src/models/zotero/*.py modules/zotero-core/src/zotero_core/models/

# 重构导入
# 移除对 zotero_mcp 内部模块的依赖
```

**Step 4: Commit**
```bash
cd modules/zotero-core
git init
git add .
git commit -m "feat: initialize zotero-core module structure"
```

---

### Task 2.2: 实现 ItemService

**Files:**
- Create: `modules/zotero-core/src/zotero_core/services/__init__.py`
- Create: `modules/zotero-core/src/zotero_core/services/item_service.py`
- Create: `modules/zotero-core/tests/unit/test_item_service.py`

**Step 1: 从主项目迁移 ItemService**
```bash
# 从现有代码迁移
cp ../src/services/zotero/item_service.py modules/zotero-core/src/zotero_core/services/

# 调整导入路径
# 将 from zotero_mcp.clients 改为 from zotero_core.clients
```

**Step 2: 测试**
```bash
cd modules/zotero-core
pytest tests/unit/test_item_service.py -v
```

**Step 3: Commit**
```bash
git add -A
git commit -m "feat: implement ItemService with CRUD operations"
```

---

### Task 2.3: 实现 HybridSearchService (RRF)

**Files:**
- Create: `modules/zotero-core/src/zotero_core/services/hybrid_search.py`
- Create: `modules/zotero-core/tests/unit/test_hybrid_search.py`

**Step 1: 实现 RRF 融合算法**
```python
# modules/zotero-core/src/zotero_core/services/hybrid_search.py
from typing import List, Dict, Optional
from ..models import Item, SearchQuery, SearchResult

class HybridSearchService:
    """混合搜索服务 (Reciprocal Rank Fusion)"""

    def __init__(self, keyword_search, semantic_search=None):
        self.keyword_search = keyword_search
        self.semantic_search = semantic_search

    async def search(
        self, query: str, search_mode: str = "hybrid", top_k: int = 10
    ) -> SearchResult:
        """执行混合搜索"""
        if search_mode == "keyword":
            return await self._keyword_search(query, top_k)
        elif search_mode == "semantic":
            return await self._semantic_search(query, top_k)
        else:
            return await self._hybrid_search_rrf(query, top_k)

    async def _hybrid_search_rrf(self, query: str, top_k: int, k: int = 60):
        """RRF 融合"""
        keyword_results = await self._keyword_search(query, top_k * 2)
        semantic_results = await self._semantic_search(query, top_k * 2) if self.semantic_search else []

        # RRF: score = Σ(1 / (k + rank_i))
        scores: Dict[Item, float] = {}

        for rank, item in enumerate(keyword_results.items, 1):
            scores[item] = scores.get(item, 0) + 1 / (k + rank)

        for rank, item in enumerate(semantic_results, 1):
            scores[item] = scores.get(item, 0) + 1 / (k + rank)

        # 排序
        sorted_items = sorted(scores.items(), key=lambda x: x[1], reverse=True)[:top_k]
        return [item for item, score in sorted_items]
```

**Step 2: 测试 RRF**
```python
# modules/zotero-core/tests/unit/test_hybrid_search.py
import pytest
from zotero_core.services.hybrid_search import HybridSearchService

@pytest.mark.asyncio
async def test_rrf_fusion():
    """测试 RRF 融合算法"""
    # Mock keyword and semantic results
    keyword_results = ["A", "B", "C", "D"]
    semantic_results = ["C", "A", "D", "E"]

    # Expected: A > C > B > D > E (based on RRF scores)
    # Verify fusion logic
```

**Step 3: Commit**
```bash
git add -A
git commit -m "feat: implement HybridSearchService with RRF algorithm"
```

---

## Phase 3: 提取 paper-analyzer 模块（Week 11-15）

### Task 3.1: 创建 paper-analyzer 模块结构

**Files:**
- Create: `modules/paper-analyzer/README.md`
- Create: `modules/paper-analyzer/pyproject.toml`
- Create: `modules/paper-analyzer/src/paper_analyzer/__init__.py`

**Step 1: 创建 README.md**
```markdown
# paper-analyzer

PDF paper analysis engine with multi-modal content extraction and LLM-powered analysis.

## Installation

```bash
pip install paper-analyzer
```

## Features

- Fast PDF extraction (PyMuPDF)
- Multi-modal support (text + images + tables)
- Multiple LLM providers (DeepSeek, OpenAI-compatible)
- Checkpoint-based batch processing
- Customizable analysis templates
```

**Step 2: 创建 pyproject.toml**
```toml
[project]
name = "paper-analyzer"
version = "1.0.0"
description = "PDF paper analysis engine with LLM"
dependencies = [
    "PyMuPDF>=1.23.0",
    "pydantic>=2.0.0",
    "httpx>=0.25.0",
]

[project.optional-dependencies]
deepseek = ["openai>=1.0.0"]
openai = ["openai>=1.0.0"]
all = ["paper-analyzer[deepseek,openai]"]
```

**Step 3: Commit**
```bash
cd modules/paper-analyzer
git init
git add .
git commit -m "feat: initialize paper-analyzer module structure"
```

---

### Task 3.2: 实现 PDFExtractor

**Files:**
- Create: `modules/paper-analyzer/src/paper_analyzer/extractors/__init__.py`
- Create: `modules/paper-analyzer/src/paper_analyzer/extractors/pdf_extractor.py`
- Create: `modules/paper-analyzer/tests/unit/test_extractor.py`

**Step 1: 从主项目迁移 PDFExtractor**
```bash
# 迁移现有提取代码
cp ../src/services/workflow.py modules/paper-analyzer/src/paper_analyzer/extractors/pdf_extractor.py

# 提取提取逻辑,移除工作流部分
# 简化为独立的提取器类
```

**Step 2: 测试提取性能**
```python
# modules/paper-analyzer/tests/unit/test_extractor.py
import pytest
from paper_analyzer.extractors import PDFExtractor

@pytest.mark.asyncio
async def test_extract_text_only():
    """测试纯文本提取"""
    extractor = PDFExtractor(extract_images=False)
    content = await extractor.extract("test_paper.pdf")

    assert content.text != ""
    assert len(content.text_by_page) > 0

@pytest.mark.asyncio
async def test_extract_with_images():
    """测试多模态提取"""
    extractor = PDFExtractor(extract_images=True)
    content = await extractor.extract("test_paper.pdf")

    assert content.has_images
    assert len(content.images) > 0
```

**Step 3: Commit**
```bash
git add -A
git commit -m "feat: implement PDFExtractor with PyMuPDF"
```

---

### Task 3.3: 实现 LLM 客户端

**Files:**
- Create: `modules/paper-analyzer/src/paper_analyzer/clients/__init__.py`
- Create: `modules/paper-analyzer/src/paper_analyzer/clients/base.py`
- Create: `modules/paper-analyzer/src/paper_analyzer/clients/openai.py`
- Create: `modules/paper-analyzer/src/paper_analyzer/clients/deepseek.py`

**Step 1: 实现基类和 OpenAI 客户端**
```python
# modules/paper-analyzer/src/paper_analyzer/clients/base.py
from abc import ABC, abstractmethod

class BaseLLMClient(ABC):
    @abstractmethod
    async def analyze(self, prompt: str, system_prompt: str = None, images: List[str] = None):
        pass

    @abstractmethod
    def supports_vision(self) -> bool:
        pass
```

```python
# modules/paper-analyzer/src/paper_analyzer/clients/openai.py
import httpx
from typing import List, Optional
from .base import BaseLLMClient

class OpenAIClient(BaseLLMClient):
    def __init__(self, api_key: str, base_url: str = "https://api.openai.com/v1", model: str = "gpt-3.5-turbo"):
        self.api_key = api_key
        self.base_url = base_url
        self.model = model

    async def analyze(self, prompt: str, system_prompt: str = None, images: List[str] = None):
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})

        if images and self.supports_vision():
            content = [{"type": "text", "text": prompt}]
            for img in images:
                content.append({"type": "image_url", "image_url": {"url": f"data:image/png;base64,{img}"}})
            messages.append({"role": "user", "content": content})
        else:
            messages.append({"role": "user", "content": prompt})

        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{self.base_url}/chat/completions",
                json={"model": self.model, "messages": messages},
                headers={"Authorization": f"Bearer {self.api_key}"}
            )
            response.raise_for_status()
            return response.json()["choices"][0]["message"]["content"]

    def supports_vision(self) -> bool:
        return "gpt-4" in self.model or "vision" in self.model
```

**Step 2: 实现 DeepSeek 客户端**
```python
# modules/paper-analyzer/src/paper_analyzer/clients/deepseek.py
from .openai import OpenAIClient

class DeepSeekClient(OpenAIClient):
    def __init__(self, api_key: str, model: str = "deepseek-chat"):
        super().__init__(
            api_key=api_key,
            base_url="https://api.deepseek.com/v1",
            model=model
        )

    def supports_vision(self) -> bool:
        return False  # DeepSeek 当前不支持视觉
```

**Step 3: Commit**
```bash
git add -A
git commit -m "feat: implement LLM clients (OpenAI, DeepSeek)"
```

---

## Phase 4: 重构 zotero-mcp 集成层（Week 16-19）

### Task 4.1: 重构 zotero-mcp 主项目

**Files:**
- Modify: `pyproject.toml`
- Modify: `src/zotero_mcp/server.py`
- Modify: `src/zotero_mcp/cli.py`
- Create: `src/zotero_mcp/config.py`
- Create: `src/zotero_mcp/integration/__init__.py`

**Step 1: 更新 pyproject.toml 依赖**
```toml
# zotero-mcp/pyproject.toml
[project]
name = "zotero-mcp"
version = "3.0.0"
dependencies = [
    "fastmcp>=2.14.0",
    "pydantic>=2.0.0",
    "python-dotenv>=1.0.0",
    # 核心模块
    "zotero-core>=1.0.0",
    "paper-analyzer>=1.0.0",
]

[project.optional-dependencies]
ingestion = ["paper-feed>=1.0.0"]
full = ["zotero-mcp[ingestion]"]
```

**Step 2: 创建配置管理**
```python
# src/zotero_mcp/config.py
import os
from dotenv import load_dotenv
from pydantic import BaseModel

class Config(BaseModel):
    zotero_library_id: str
    zotero_api_key: str
    llm_api_key: str = ""
    llm_provider: str = "deepseek"

    @classmethod
    def load(cls):
        load_dotenv()
        return cls()

def get_config() -> Config:
    return Config.load()
```

**Step 3: 重构服务器入口**
```python
# src/zotero_mcp/server.py
from fastmcp import FastMCP
from .config import get_config
from .integration import MCPTools

def create_server() -> FastMCP:
    config = get_config()
    mcp = FastMCP(name="zotero-mcp", version="3.0.0")

    # 初始化集成层
    tools = MCPTools(config)
    tools.register_tools(mcp)

    return mcp

def main():
    mcp = create_server()
    mcp.run(transport="stdio")
```

**Step 4: 测试服务器启动**
```bash
# 创建 .env 文件
cat > .env << EOF
ZOTERO_LIBRARY_ID=user_123
ZOTERO_API_KEY=test_key
LLM_API_KEY=test_llm_key
EOF

# 测试启动
python -m zotero_mcp.server
# Expected: Server starts without errors
```

**Step 5: Commit**
```bash
git add -A
git commit -m "refactor: restructure zotero-mcp as integration layer"
```

---

### Task 4.2: 实现集成层

**Files:**
- Create: `src/zotero_mcp/integration/mcp_tools.py`
- Create: `src/zotero_mcp/integration/zotero_integration.py`
- Create: `src/zotero_mcp/integration/analyzer_integration.py`

**Step 1: 实现 Zotero 集成**
```python
# src/zotero_mcp/integration/zotero_integration.py
from zotero_core import ItemService, SearchService, CollectionService
from ..config import get_config

class ZoteroIntegration:
    def __init__(self):
        config = get_config()
        self.item_service = ItemService(
            library_id=config.zotero_library_id,
            api_key=config.zotero_api_key
        )
        # ... 初始化其他服务
```

**Step 2: 实现 Analyzer 集成**
```python
# src/zotero_mcp/integration/analyzer_integration.py
from paper_analyzer import PDFAnalyzer
from paper_analyzer.clients.deepseek import DeepSeekClient
from ..config import get_config

class AnalyzerIntegration:
    def __init__(self):
        config = get_config()
        llm_client = DeepSeekClient(api_key=config.llm_api_key)
        self.analyzer = PDFAnalyzer(llm_client=llm_client)
```

**Step 3: 测试集成**
```bash
pytest tests/integration/test_zotero_integration.py -v
```

**Step 4: Commit**
```bash
git add -A
git commit -m "feat: implement integration layer for zotero-core and paper-analyzer"
```

---

## Phase 5: 文档和发布（Week 20）

### Task 5.1: 更新所有 README 文档

**Files:**
- Modify: `README.md` (zotero-mcp)
- Modify: `external/paper-feed/README.md`
- Modify: `modules/zotero-core/README.md`
- Modify: `modules/paper-analyzer/README.md`

**Step 1: 更新主 README**
```markdown
# zotero-mcp

Modular Zotero integration for AI assistants via Model Context Protocol.

## Architecture

```
zotero-mcp (integration layer)
├── zotero-core (Zotero data access)
├── paper-analyzer (PDF analysis)
└── paper-feed (paper collection, optional)
```

## Installation

### Core (Zotero access + PDF analysis)
```bash
pip install zotero-mcp
```

### Full (with paper collection)
```bash
pip install zotero-mcp[full]
```

## Configuration

Create `.env` file:
```bash
ZOTERO_LIBRARY_ID=user_123
ZOTERO_API_KEY=your_key
LLM_API_KEY=your_llm_key
```
```

**Step 2: 添加架构图和使用示例**
```markdown
## Module Usage

### Standalone paper-feed
```bash
pip install paper-feed
python -c "
from paper_feed import RSSSource, FilterPipeline
source = RSSSource('https://arxiv.org/rss/cs.AI')
papers = await source.fetch_papers()
"
```

### Standalone zotero-core
```bash
pip install zotero-core
python -c "
from zotero_core import ItemService
service = ItemService(library_id='...', api_key='...')
items = await service.get_items()
"
```

### Standalone paper-analyzer
```bash
pip install paper-analyzer
python -c "
from paper_analyzer import PDFAnalyzer, DeepSeekClient
analyzer = PDFAnalyzer(llm_client=DeepSeekClient(...))
result = await analyzer.analyze('paper.pdf')
"
```
```

**Step 3: Commit**
```bash
git add README.md
git commit -m "docs: update README with modular architecture"
```

---

### Task 5.2: 创建迁移指南

**Files:**
- Create: `docs/MIGRATION_GUIDE.md`

**Step 1: 编写迁移指南**
```markdown
# Migration Guide: v2.x → v3.0

## Breaking Changes

### 1. Module Independence

**Before (v2.x):**
```python
from zotero_mcp.services.rss import RSSService
```

**After (v3.0):**
```python
# Install separately
pip install paper-feed

from paper_feed import RSSSource
```

### 2. Configuration

**Before:** `~/.config/zotero-mcp/config.json`

**After:** `.env` file in project directory

### 3. CLI Changes

**Before:** `zotero-mcp rss fetch`

**After:**
```bash
# Option 1: Use paper-feed directly
paper-feed fetch --rss https://arxiv.org/rss/cs.AI

# Option 2: Install full zotero-mcp
pip install zotero-mcp[full]
zotero-mcp rss-fetch
```

## Installation Migration

### Minimal Installation
```bash
# Just Zotero access
pip install zotero-mcp
```

### Full Installation
```bash
# All features
pip install zotero-mcp[full]
```

## Code Migration

### RSS Fetching
```python
# Before
from zotero_mcp.services.rss import RSSService
service = RSSService()
await service.fetch_feeds()

# After
from paper_feed import RSSSource
source = RSSSource("https://arxiv.org/rss/cs.AI")
papers = await source.fetch_papers()
```

### PDF Analysis
```python
# Before
from zotero_mcp.services.workflow import WorkflowService
service = WorkflowService()
await service.analyze_items()

# After
from paper_analyzer import PDFAnalyzer, DeepSeekClient
analyzer = PDFAnalyzer(llm_client=DeepSeekClient(...))
await analyzer.analyze("paper.pdf")
```
```

**Step 2: Commit**
```bash
git add docs/MIGRATION_GUIDE.md
git commit -m "docs: add migration guide for v3.0"
```

---

### Task 5.3: 发布所有模块

**Files:**
- Modify: `external/paper-feed/pyproject.toml` (version = "1.0.0")
- Modify: `modules/zotero-core/pyproject.toml` (version = "1.0.0")
- Modify: `modules/paper-analyzer/pyproject.toml` (version = "1.0.0")
- Modify: `zotero-mcp/pyproject.toml` (version = "3.0.0")

**Step 1: 发布 paper-feed**
```bash
cd external/paper-feed
python -m build
twine upload dist/*
git tag v1.0.0
git push --tags
```

**Step 2: 发布 zotero-core**
```bash
cd modules/zotero-core
python -m build
twine upload dist/*
git tag v1.0.0
git push --tags
```

**Step 3: 发布 paper-analyzer**
```bash
cd modules/paper-analyzer
python -m build
twine upload dist/*
git tag v1.0.0
git push --tags
```

**Step 4: 发布 zotero-mcp v3.0.0**
```bash
cd zotero-mcp
python -m build
twine upload dist/*
git tag v3.0.0
git push --tags
```

**Step 5: 创建 GitHub Release**
```bash
# 为每个仓库创建 GitHub Release
gh release create v1.0.0 --notes "Initial stable release"
```

---

## 总结

### 完成标准

✅ **paper-feed** 独立 PyPI 包
- 可独立安装使用
- 支持不依赖 Zotero 的场景
- ZoteroAdapter 作为可选功能

✅ **zotero-core** 核心数据访问
- CRUD 操作完整
- 混合搜索 (RRF)
- 元数据服务

✅ **paper-analyzer** PDF 分析
- PyMuPDF 提取
- 多 LLM 支持
- 检查点批处理

✅ **zotero-mcp** 轻量集成
- FastMCP 协议
- .env 配置
- 可选依赖管理

### 关键收益

1. **可维护性**: 每个模块 <5000 行代码
2. **可测试性**: 独立测试,测试覆盖率 >80%
3. **可复用性**: paper-feed 可被其他项目使用
4. **灵活性**: 用户按需安装模块

### 时间线

- **Week 0**: 准备阶段
- **Week 1-5**: paper-feed 独立化
- **Week 6-10**: zotero-core 提取
- **Week 11-15**: paper-analyzer 提取
- **Week 16-19**: zotero-mcp 重构
- **Week 20**: 文档和发布

**Total**: 20 weeks (5 months)

---

**Plan complete and saved to `docs/plans/2025-02-06-modular-refactor-implementation-plan.md`.**

**Execution Options:**

1. **Subagent-Driven (this session)** - I dispatch fresh subagent per task, review between tasks, fast iteration

2. **Parallel Session (separate)** - Open new session with executing-plans, batch execution with checkpoints

**Which approach?**

If Subagent-Driven chosen:
- REQUIRED SUB-SKILL: Use @superpowers:subagent-driven-development
- Stay in this session
- Fresh subagent per task + code review

If Parallel Session chosen:
- Guide you to open new session in worktree
- REQUIRED SUB-SKILL: New session uses @superpowers:executing-plans
