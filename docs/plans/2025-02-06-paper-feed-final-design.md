# paper-feed 完整设计文档

**日期**: 2025-02-06
**状态**: 最终设计
**版本**: 4.0 (集成 Gmail/EZGmail 支持)

## 概述

`paper-feed` 是一个独立的学术论文采集和过滤框架。支持从 **RSS feeds** 和 **Gmail 邮件提醒** 中获取论文，通过两级过滤管道筛选，并导出到多种目标。

## 支持的数据源

1. **RSS Feeds** - arXiv, bioRxiv, Nature, Science 等期刊
2. **Gmail 邮件** - Google Scholar 提醒、期刊 TOC 邮件

## 架构图

```
┌─────────────────────────────────────────────────────────────┐
│                         paper-feed                          │
└─────────────────────────────────────────────────────────────┘
                              │
        ┌─────────────────────┼─────────────────────┐
        │                     │                     │
        ▼                     ▼                     ▼
┌─────────────┐     ┌─────────────┐     ┌─────────────┐
│   Sources   │────▶│   Filters   │────▶│  Exporters  │
│             │     │             │     │             │
│ • RSS       │     │ 1. Keyword  │     │ • Zotero    │
│   feedparser│     │ 2. AI       │     │ • JSON      │
│ • Gmail     │     │             │     │             │
│   EZGmail   │     └─────────────┘     └─────────────┘
└─────────────┘                            │
                                            ▼
                                    ┌──────────────┐
                                    │ PaperItem    │
                                    │  (Universal) │
                                    └──────────────┘
```

## 核心数据模型

### PaperItem

```python
from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
from datetime import date

class PaperItem(BaseModel):
    """通用论文模型（不依赖 Zotero）"""

    # 基础元数据
    title: str = Field(..., description="论文标题")
    authors: List[str] = Field(default_factory=list, description="作者列表")
    abstract: str = Field(default="", description="摘要")

    # 发表信息
    published_date: Optional[date] = Field(None, description="发表日期")
    doi: Optional[str] = Field(None, description="DOI")
    url: str = Field(..., description="论文链接")
    pdf_url: Optional[str] = Field(None, description="PDF 链接")

    # 来源信息
    source: str = Field(..., description="来源名称（如 'arXiv', 'Google Scholar'）")
    source_id: Optional[str] = Field(None, description="来源 ID（RSS entry ID 或 Gmail message ID）")
    source_type: str = Field(..., description="来源类型: 'rss' 或 'email'")

    # 分类信息（仅作元数据，不用于过滤）
    categories: List[str] = Field(default_factory=list, description="主题分类")
    tags: List[str] = Field(default_factory=list, description="标签/关键词")

    # 扩展字段
    metadata: Dict[str, Any] = Field(
        default_factory=dict,
        description="额外的来源特定元数据"
    )

    class Config:
        json_encoders = {
            date: lambda v: v.isoformat() if v else None
        }
```

### FilterCriteria

```python
class FilterCriteria(BaseModel):
    """过滤条件配置"""

    # 关键词过滤（第1级：中等速度）
    keywords: List[str] = Field(
        default_factory=list,
        description="在标题/摘要中匹配的关键词"
    )
    keyword_mode: str = Field(
        default="any",
        description="匹配模式: 'any', 'all', 'weighted'"
    )
    exclude_keywords: List[str] = Field(
        default_factory=list,
        description="排除的关键词"
    )

    # AI 过滤（第2级：最慢但最精确）
    ai_interests: List[str] = Field(
        default_factory=list,
        description="研究兴趣，用于 AI 语义过滤"
    )
    min_relevance_score: float = Field(
        default=0.6,
        ge=0.0,
        le=1.0,
        description="最低相关性分数"
    )

    # 额外过滤条件
    date_range: Optional[tuple[date, date]] = Field(
        default=None,
        description="发表日期范围 (开始, 结束)"
    )
    has_pdf: bool = Field(
        default=False,
        description="是否必须有 PDF 链接"
    )
    min_authors: Optional[int] = Field(
        default=None,
        description="最少作者数量"
    )

    # 来源过滤
    allowed_sources: List[str] = Field(
        default_factory=list,
        description="仅包含这些来源（如 ['arXiv', 'Google Scholar']）"
    )
```

### FilterResult

```python
class FilterResult(BaseModel):
    """过滤执行结果"""

    papers: List[PaperItem] = Field(default_factory=list, description="过滤后的论文")
    reasons: List[str] = Field(default_factory=list, description="选中原因")

    total_evaluated: int = Field(default=0, description="总共评估的论文数")
    filtered_count: int = Field(default=0, description="被过滤掉的论文数")

    # 各阶段统计
    stage_stats: Dict[str, int] = Field(
        default_factory=dict,
        description="各阶段后剩余的论文数"
    )

    @property
    def pass_rate(self) -> float:
        """通过率 (0.0-1.0)"""
        if self.total_evaluated == 0:
            return 0.0
        return len(self.papers) / self.total_evaluated
```

## 数据源层

### 抽象基类

```python
from abc import ABC, abstractmethod
from typing import AsyncIterator, List

class PaperSource(ABC):
    """论文数据源抽象基类"""

    source_name: str = "base"
    source_type: str = "base"

    @abstractmethod
    async def fetch_papers(
        self,
        limit: Optional[int] = None,
        since: Optional[date] = None
    ) -> List[PaperItem]:
        """从该数据源获取论文"""
        pass

    @abstractmethod
    async def fetch_papers_stream(
        self,
        limit: Optional[int] = None,
        since: Optional[date] = None
    ) -> AsyncIterator[PaperItem]:
        """流式获取论文"""
        pass
```

### RSSSource（使用 feedparser）

```python
import feedparser
import httpx
from typing import Optional
from datetime import datetime, date

class RSSSource(PaperSource):
    """
    RSS feed 数据源（使用 feedparser）

    支持的来源：
    - arXiv RSS feeds
    - bioRxiv RSS feeds
    - Nature, Science 等期刊
    - 任何标准 RSS/Atom feed
    """

    source_name = "rss"
    source_type = "rss"

    def __init__(
        self,
        feed_url: str,
        source_name: Optional[str] = None,
        user_agent: str = "paper-feed/1.0",
        timeout: int = 30
    ):
        """
        Args:
            feed_url: RSS feed URL
            source_name: 覆盖自动检测的来源名称
            user_agent: HTTP 请求的 User-Agent
            timeout: 请求超时时间（秒）
        """
        self.feed_url = feed_url
        self.source_name = source_name or self._detect_source_name(feed_url)
        self.user_agent = user_agent
        self.timeout = timeout

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
        else:
            from urllib.parse import urlparse
            return urlparse(url).netloc

    async def fetch_papers(
        self,
        limit: Optional[int] = None,
        since: Optional[date] = None
    ) -> List[PaperItem]:
        """从 RSS feed 获取论文"""
        papers = []

        async for paper in self.fetch_papers_stream(limit, since):
            papers.append(paper)

        return papers

    async def fetch_papers_stream(
        self,
        limit: Optional[int] = None,
        since: Optional[date] = None
    ) -> AsyncIterator[PaperItem]:
        """流式获取论文"""
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
        feed = feedparser.parse(feed_content)

        # 处理 entries
        count = 0
        for entry in feed.entries:
            if limit and count >= limit:
                break

            try:
                paper = self._parse_entry(entry)

                # 日期过滤
                if since and paper.published_date:
                    if paper.published_date < since:
                        continue

                yield paper
                count += 1

            except Exception as e:
                print(f"Error parsing entry: {e}")
                continue

    def _parse_entry(self, entry) -> PaperItem:
        """将 feedparser entry 解析为 PaperItem"""
        from ..utils.rss_parser import RSSParser

        parser = RSSParser()
        return parser.parse(entry, self.source_name)
```

### GmailSource（使用 gmailparser）⭐ 推荐

```python
from paper_feed.utils.gmailparser import GmailClient
from typing import List, Optional
from datetime import date, timedelta
from bs4 import BeautifulSoup
import re

class GmailSource(PaperSource):
    """
    Gmail 邮件数据源（使用 gmailparser 封装 EZGmail）

    支持的来源：
    - Google Scholar alerts
    - 期刊 TOC 邮件
    - 任何包含论文信息的 HTML 邮件

    特点：
    - 使用 gmailparser 工具类（封装 EZGmail，简化 OAuth2 认证）
    - 自动解析 HTML 表格
    - 批量处理邮件
    """

    source_name = "gmail"
    source_type = "email"

    def __init__(
        self,
        query: str = "from:scholaralerts@google.com newer_than:7d",
        label: Optional[str] = None,
        max_results: int = 50
    ):
        """
        Args:
            query: Gmail 搜索查询（默认：最近7天的 Google Scholar alerts）
            label: Gmail 标签（仅处理该标签下的邮件）
            max_results: 最多获取的邮件数
        """
        self.query = query
        self.label = label
        self.max_results = max_results

        # GmailClient 封装了 EZGmail（首次运行会打开浏览器）
        try:
            self.client = GmailClient()
        except Exception as e:
            print(f"GmailClient 初始化失败: {e}")
            print("请确保已正确安装 EZGmail: pip install ezgmail")
            raise

    async def fetch_papers(
        self,
        limit: Optional[int] = None,
        since: Optional[date] = None
    ) -> List[PaperItem]:
        """从 Gmail 获取论文"""
        papers = []

        async for paper in self.fetch_papers_stream(limit, since):
            papers.append(paper)

        return papers

    async def fetch_papers_stream(
        self,
        limit: Optional[int] = None,
        since: Optional[date] = None
    ) -> AsyncIterator[PaperItem]:
        """流式获取论文"""
        # 构建查询
        query = self.query
        if since:
            days_ago = (date.today() - since).days
            query = f"{query} newer_than:{days_ago}d"

        if self.label:
            query = f"{query} label:{self.label}"

        # 搜索邮件（通过 GmailClient 封装 EZGmail）
        try:
            threads = self.client.search(query)
        except Exception as e:
            print(f"Gmail 搜索失败: {e}")
            return

        count = 0
        for thread in threads[:self.max_results]:
            if limit and count >= limit:
                break

            try:
                # 获取线程中的所有邮件
                for message in thread.messages:
                    # 解析邮件内容
                    email_items = self._parse_email_message(message)
                    # 解析邮件内容
                    email_items = self._parse_email_message(message)

                    # 转换为 PaperItem
                    for email_item in email_items:
                        yield email_item
                        count += 1
            except Exception as e:
                print(f"Error processing message: {e}")
                continue

    def _parse_email_message(self, message) -> List[PaperItem]:
        """解析 Gmail 邮件消息"""
        # 获取 HTML 内容
        html_body = message.html_body

        if not html_body:
            return []

        # 使用 BeautifulSoup 解析
        soup = BeautifulSoup(html_body, 'html.parser')
        items = []

        # 查找所有表格（Google Scholar 使用表格格式）
        for table in soup.find_all('table'):
            table_items = self._parse_paper_table(table, message)
            items.extend(table_items)

        return items

    def _parse_paper_table(
        self,
        table,
        message
    ) -> List[PaperItem]:
        """解析 HTML 表格中的论文信息"""
        rows = table.find_all('tr')

        # 跳过表头
        for row in rows[1:]:
            cells = row.find_all('td')
            if len(cells) < 2:
                continue

            try:
                # Google Scholar 格式：[复选框] [标题+作者] [链接/PDF]
                title_cell = cells[1]
                link_cell = cells[2] if len(cells) > 2 else None

                # 提取标题和链接
                title_link = title_cell.find('a')
                if title_link:
                    title = title_link.get_text(strip=True)
                    link = title_link.get('href', '')
                else:
                    title = title_cell.get_text(strip=True)
                    link = ''

                # 提取 PDF 链接
                pdf_url = None
                if link_cell:
                    pdf_anchor = link_cell.find('a')
                    if pdf_anchor and 'pdf' in pdf_anchor.get('href', '').lower():
                        pdf_url = pdf_anchor.get('href')

                # 提取作者（在 <br> 标签后）
                authors = []
                br_tag = title_cell.find('br')
                if br_tag:
                    author_text = br_tag.next_sibling
                    if author_text:
                        # 移除期刊信息（括号中的内容）
                        author_text = re.sub(r'\s*\([^)]*\)\s*$', '', str(author_text))
                        authors = self._parse_authors(author_text.strip())

                # 创建 PaperItem
                paper = PaperItem(
                    title=title,
                    authors=authors,
                    abstract="",  # 邮件通常没有摘要
                    published_date=None,
                    doi=None,
                    url=link,
                    pdf_url=pdf_url,
                    source="Google Scholar Alerts",
                    source_id=message.messageId,
                    source_type="email",
                    categories=[],
                    tags=[],
                    metadata={
                        "subject": message.subject,
                        "sender": message.sender
                    }
                )

                yield paper

            except Exception as e:
                print(f"Error parsing table row: {e}")
                continue

    def _parse_authors(self, authors_str: str) -> List[str]:
        """解析作者字符串"""
        if not authors_str:
            return []

        # 按常见分隔符分割
        for sep in [', ', '; ', ' and ']:
            if sep in authors_str:
                return [a.strip() for a in authors_str.split(sep)]

        return [authors_str.strip()]
```

## 过滤层

### FilterPipeline（两级过滤）

```python
from typing import List
from .keyword import KeywordFilterStage
from .ai_filter import AIFilterStage

class FilterPipeline:
    """
    两级过滤管道

    阶段：
    1. KeywordFilterStage - 关键词匹配（中等速度）
    2. AIFilterStage - AI 语义过滤（慢但精确）
    """

    def __init__(self, llm_client=None):
        """
        Args:
            llm_client: 可选的 LLM 客户端（用于 AI 过滤）
        """
        self.stages = [
            KeywordFilterStage(),
        ]

        if llm_client:
            self.stages.append(AIFilterStage(llm_client))

    async def filter(
        self,
        papers: List[PaperItem],
        criteria: FilterCriteria
    ) -> FilterResult:
        """应用两级过滤"""
        filtered = papers
        all_reasons = []
        stage_stats = {}

        for stage in self.stages:
            stage_name = stage.__class__.__name__

            # 跳过不适用的阶段
            if not stage.is_applicable(criteria):
                continue

            # 应用过滤
            filtered, stage_reasons = await stage.filter(filtered, criteria)

            # 记录统计
            stage_stats[stage_name] = len(filtered)
            all_reasons.extend(stage_reasons)

            # 早停
            if not filtered:
                break

        return FilterResult(
            papers=filtered,
            reasons=all_reasons,
            total_evaluated=len(papers),
            filtered_count=len(papers) - len(filtered),
            stage_stats=stage_stats
        )
```

### KeywordFilterStage（第1级）

```python
from typing import List, Tuple

class KeywordFilterStage:
    """关键词匹配过滤（中等速度）"""

    def is_applicable(self, criteria: FilterCriteria) -> bool:
        return len(criteria.keywords) > 0 or len(criteria.exclude_keywords) > 0

    async def filter(
        self,
        papers: List[PaperItem],
        criteria: FilterCriteria
    ) -> Tuple[List[PaperItem], List[str]]:
        """按关键词过滤"""
        filtered = []
        reasons = []

        for paper in papers:
            # 来源过滤
            if criteria.allowed_sources:
                if paper.source not in criteria.allowed_sources:
                    continue

            # 排除关键词
            if criteria.exclude_keywords:
                text = f"{paper.title} {paper.abstract}".lower()
                if any(kw.lower() in text for kw in criteria.exclude_keywords):
                    continue

            # 必需关键词
            if criteria.keywords:
                score = self._calculate_score(paper, criteria.keywords, criteria.keyword_mode)

                if criteria.keyword_mode == "weighted":
                    if score >= criteria.min_relevance_score:
                        filtered.append(paper)
                        reasons.append(f"Keyword score: {score:.2f}")
                elif criteria.keyword_mode == "any":
                    if score > 0:
                        filtered.append(paper)
                        reasons.append("Keyword matched")
                elif criteria.keyword_mode == "all":
                    if score == len(criteria.keywords):
                        filtered.append(paper)
                        reasons.append("All keywords matched")
            else:
                filtered.append(paper)

        return filtered, reasons

    def _calculate_score(
        self,
        paper: PaperItem,
        keywords: List[str],
        mode: str
    ) -> float:
        """计算关键词匹配分数"""
        title_text = paper.title.lower()
        abstract_text = paper.abstract.lower()

        if mode == "weighted":
            # 标题权重 > 摘要权重
            title_score = sum(2 for kw in keywords if kw.lower() in title_text)
            abstract_score = sum(1 for kw in keywords if kw.lower() in abstract_text)
            max_score = len(keywords) * 3
            return (title_score + abstract_score) / max_score if max_score > 0 else 0
        else:
            # 简单计数
            all_text = f"{title_text} {abstract_text}"
            return sum(1 for kw in keywords if kw.lower() in all_text)
```

### AIFilterStage（第2级）

```python
from typing import List, Tuple

class AIFilterStage:
    """AI 语义过滤（最慢但最精确）"""

    def __init__(self, llm_client):
        self.llm = llm_client

    def is_applicable(self, criteria: FilterCriteria) -> bool:
        return len(criteria.ai_interests) > 0

    async def filter(
        self,
        papers: List[PaperItem],
        criteria: FilterCriteria
    ) -> Tuple[List[PaperItem], List[str]]:
        """使用 AI 语义匹配过滤"""
        # 批量处理
        batch_size = 10
        all_filtered = []
        all_reasons = []

        for i in range(0, len(papers), batch_size):
            batch = papers[i:i + batch_size]
            filtered, reasons = await self._filter_batch(
                batch,
                criteria.ai_interests,
                criteria.min_relevance_score
            )
            all_filtered.extend(filtered)
            all_reasons.extend(reasons)

        return all_filtered, all_reasons

    async def _filter_batch(
        self,
        papers: List[PaperItem],
        interests: List[str],
        min_score: float
    ) -> Tuple[List[PaperItem], List[str]]:
        """批量过滤论文"""
        # 构建 prompt
        papers_info = "\n\n".join([
            f"Index: {i}\nTitle: {p.title}\nAbstract: {p.abstract[:300]}..."
            for i, p in enumerate(papers)
        ])

        prompt = f"""Research Interests: {', '.join(interests)}

Papers to Evaluate:
{papers_info}

Task: Return a JSON object with:
1. "relevant_indices": array of indices [0, 2, 4, ...] for papers highly relevant
2. "scores": object mapping each relevant index to a relevance score (0.0-1.0)
3. "reasons": object mapping each relevant index to a brief explanation

Response format:
{{
  "relevant_indices": [0, 2, 4],
  "scores": {{"0": 0.9, "2": 0.75}},
  "reasons": {{"0": "Direct relevance", "2": "Related methodology"}}
}}
"""

        response = await self.llm.analyze(prompt)
        result = self._parse_response(response)

        filtered = []
        reasons = []

        for idx_str, score in result["scores"].items():
            idx = int(idx_str)
            if score >= min_score:
                filtered.append(papers[idx])
                reason = result["reasons"].get(idx_str, "AI ranked relevant")
                reasons.append(f"AI score: {score:.2f} - {reason}")

        return filtered, reasons

    def _parse_response(self, response: str) -> dict:
        """解析 LLM 响应"""
        import json

        # 尝试直接解析
        try:
            return json.loads(response)
        except json.JSONDecodeError:
            pass

        # 提取 JSON 代码块
        if "```json" in response:
            start = response.find("```json") + 7
            end = response.find("```", start)
            return json.loads(response[start:end].strip())

        if "```" in response:
            start = response.find("```") + 3
            end = response.find("```", start)
            return json.loads(response[start:end].strip())

        raise ValueError(f"Cannot parse response: {response[:100]}")
```

## 导出层

### ExportAdapter 接口

```python
from abc import ABC, abstractmethod

class ExportAdapter(ABC):
    """导出适配器抽象基类"""

    @abstractmethod
    async def export(
        self,
        papers: List[PaperItem],
        **kwargs
    ) -> ExportResult:
        """导出论文到目标系统"""
        pass

class ExportResult(BaseModel):
    """导出结果"""
    success_count: int = 0
    failed_count: int = 0
    errors: List[str] = Field(default_factory=list)
```

### ZoteroAdapter

```python
class ZoteroAdapter(ExportAdapter):
    """导出到 Zotero（使用 zotero-core）"""

    def __init__(
        self,
        library_id: str,
        api_key: str,
        library_type: str = "user"
    ):
        self.library_id = library_id
        self.api_key = api_key
        self.library_type = library_type

    async def export(
        self,
        papers: List[PaperItem],
        collection_id: Optional[str] = None,
        tags: Optional[List[str]] = None
    ) -> ExportResult:
        """导出论文到 Zotero"""
        from zotero_core import ItemService

        service = ItemService(
            library_id=self.library_id,
            api_key=self.api_key,
            library_type=self.library_type
        )

        success_count = 0
        failed_count = 0
        errors = []

        for paper in papers:
            try:
                item_data = self._paper_to_zotero_item(paper, tags)
                await service.create_item(item_data, collection_id)
                success_count += 1
            except Exception as e:
                failed_count += 1
                errors.append(f"{paper.title}: {str(e)}")

        return ExportResult(
            success_count=success_count,
            failed_count=failed_count,
            errors=errors
        )

    def _paper_to_zotero_item(
        self,
        paper: PaperItem,
        additional_tags: Optional[List[str]] = None
    ) -> dict:
        """将 PaperItem 转换为 Zotero item 格式"""
        item = {
            "itemType": "journalArticle",
            "title": paper.title,
            "creators": [{"creatorType": "author", "name": name} for name in paper.authors],
            "abstractNote": paper.abstract,
            "url": paper.url,
            "accessDate": datetime.now().isoformat(),
            "tags": [{"tag": tag} for tag in paper.tags]
        }

        if paper.doi:
            item["DOI"] = paper.doi

        if paper.published_date:
            item["date"] = paper.published_date.isoformat()

        if paper.pdf_url:
            item["attachments"] = [{"path": paper.pdf_url, "title": "Full Text PDF"}]

        if additional_tags:
            item["tags"].extend([{"tag": tag} for tag in additional_tags])

        return item
```

### JSONAdapter

```python
class JSONAdapter(ExportAdapter):
    """导出到 JSON 文件"""

    async def export(
        self,
        papers: List[PaperItem],
        filepath: str,
        pretty: bool = True
    ) -> ExportResult:
        """导出论文到 JSON 文件"""
        import json
        from pathlib import Path

        try:
            data = [paper.model_dump() for paper in papers]
            Path(filepath).parent.mkdir(parents=True, exist_ok=True)

            with open(filepath, 'w', encoding='utf-8') as f:
                if pretty:
                    json.dump(data, f, indent=2, ensure_ascii=False)
                else:
                    json.dump(data, f, ensure_ascii=False)

            return ExportResult(success_count=len(papers))

        except Exception as e:
            return ExportResult(
                success_count=0,
                failed_count=len(papers),
                errors=[str(e)]
            )
```

## 高级 API

### fetch_and_filter（多源获取）

```python
async def fetch_and_filter(
    rss_feeds: List[str] = None,
    gmail_query: str = None,
    criteria: FilterCriteria = None,
    llm_client=None,
    limit_per_source: int = 100
) -> FilterResult:
    """
    高级 API：从多个数据源获取并过滤论文

    Args:
        rss_feeds: RSS feed URLs 列表
        gmail_query: Gmail 搜索查询
        criteria: 过滤条件
        llm_client: 可选的 LLM 客户端
        limit_per_source: 每个数据源的最大论文数

    Returns:
        FilterResult
    """
    all_papers = []

    # 从 RSS feeds 获取
    if rss_feeds:
        for url in rss_feeds:
            source = RSSSource(url)
            papers = await source.fetch_papers(limit=limit_per_source)
            all_papers.extend(papers)

    # 从 Gmail 获取
    if gmail_query:
        source = GmailSource(query=gmail_query)
        papers = await source.fetch_papers(limit=limit_per_source)
        all_papers.extend(papers)

    # 应用过滤
    pipeline = FilterPipeline(llm_client=llm_client)
    result = await pipeline.filter(all_papers, criteria)

    return result
```

## 使用示例

### 示例 1：仅使用 RSS

```python
from paper_feed import RSSSource, FilterPipeline, FilterCriteria, JSONAdapter

# 1. 从 arXiv 获取
source = RSSSource("https://arxiv.org/rss/cs.AI")
papers = await source.fetch_papers(limit=50)

# 2. 过滤
criteria = FilterCriteria(
    keywords=["machine learning", "deep learning"],
    keyword_mode="any"
)
pipeline = FilterPipeline()
result = await pipeline.filter(papers, criteria)

# 3. 导出
adapter = JSONAdapter()
await adapter.export(result.papers, "papers.json")
```

### 示例 2：仅使用 Gmail

```python
from paper_feed import GmailSource, FilterPipeline, FilterCriteria

# 1. 从 Gmail 获取（Google Scholar alerts）
source = GmailSource(
    query="from:scholaralerts@google.com newer_than:7d"
)
papers = await source.fetch_papers(limit=100)

# 2. 过滤
criteria = FilterCriteria(
    keywords=["neural network"],
    ai_interests=["deep learning"],
    min_relevance_score=0.7
)
pipeline = FilterPipeline(llm_client=deepseek_client)
result = await pipeline.filter(papers, criteria)

print(f"从 {result.total_evaluated} 篇论文中筛选出 {len(result.papers)} 篇")
```

### 示例 3：同时使用 RSS 和 Gmail

```python
from paper_feed import fetch_and_filter, FilterCriteria

result = await fetch_and_filter(
    rss_feeds=[
        "https://arxiv.org/rss/cs.AI",
        "https://arxiv.org/rss/cs.LG"
    ],
    gmail_query="from:scholaralerts@google.com newer_than:7d",
    criteria=FilterCriteria(
        keywords=["transformer"],
        ai_interests=["attention mechanism"]
    ),
    llm_client=deepseek_client
)

print(f"总计: {len(result.papers)} 篇论文")
print(f"按来源分布:")
from collections import Counter
source_counts = Counter(p.source for p in result.papers)
for source, count in source_counts.items():
    print(f"  - {source}: {count} 篇")
```

### 示例 4：导出到 Zotero

```python
from paper_feed import ZoteroAdapter

adapter = ZoteroAdapter(
    library_id="user_123",
    api_key="..."
)

export_result = await adapter.export(
    result.papers,
    collection_id="ABC123",
    tags=["Auto-imported"]
)

print(f"成功导出 {export_result.success_count} 篇到 Zotero")
if export_result.errors:
    print(f"失败: {export_result.failed_count} 篇")
    for error in export_result.errors:
        print(f"  - {error}")
```

## 目录结构

```
paper-feed/
├── src/paper_feed/
│   ├── __init__.py
│   ├── core/
│   │   ├── models.py          # PaperItem, FilterCriteria, FilterResult
│   │   └── base.py            # PaperSource ABC
│   ├── sources/
│   │   ├── __init__.py
│   │   ├── rss.py             # RSSSource (feedparser)
│   │   └── gmail.py           # GmailSource (gmailparser)
│   ├── filters/
│   │   ├── __init__.py
│   │   ├── pipeline.py        # FilterPipeline
│   │   ├── keyword.py         # KeywordFilterStage
│   │   └── ai_filter.py       # AIFilterStage
│   ├── exporters/
│   │   ├── __init__.py
│   │   ├── zotero.py          # ZoteroAdapter
│   │   ├── json.py            # JSONAdapter
│   │   └── base.py            # ExportAdapter ABC
│   ├── utils/
│   │   ├── __init__.py
│   │   ├── rss_parser.py      # RSS 解析工具
│   │   └── gmailparser.py     # Gmail 解析工具（封装 EZGmail）
│   └── cli.py                 # 命令行接口
├── tests/
│   ├── unit/
│   │   ├── test_models.py
│   │   ├── test_rss_source.py
│   │   ├── test_gmail_source.py
│   │   ├── test_filters.py
│   │   └── test_exporters.py
│   ├── integration/
│   │   ├── test_multi_source.py
│   │   └── test_e2e.py
│   └── fixtures/
│       ├── sample_rss.xml
│       └── sample_email.html
├── examples/
│   ├── rss_only.py
│   ├── gmail_only.py
│   └── multi_source.py
├── pyproject.toml
├── README.md
└── CHANGELOG.md
```

## 依赖配置

```toml
[project]
name = "paper-feed"
version = "1.0.0"
description = "Academic paper collection from RSS and Gmail alerts"
dependencies = [
    "feedparser>=6.0.0",
    "pydantic>=2.0.0",
    "httpx>=0.25.0",
    "python-dateutil>=2.8.0",
    "beautifulsoup4>=4.12.0",
]

[project.optional-dependencies]
gmail = [
    "ezgmail>=0.1.0",  # EZGmail 库
    "beautifulsoup4>=4.12.0",  # HTML 解析
]
llm = [
    "openai>=1.0.0",
]
zotero = [
    "zotero-core>=1.0.0",
]
all = ["paper-feed[gmail,llm,zotero]"]

[project.scripts]
paper-feed = "paper_feed.cli:main"
```

## 实施计划（5周）

### Week 1: 核心模型 + RSS 源
- [ ] 实现 PaperItem, FilterCriteria, FilterResult
- [ ] 实现 RSSSource（使用 feedparser）
- [ ] 实现 RSSParser 工具
- [ ] 单元测试（RSS 解析）

### Week 2: Gmail 源
- [ ] 实现 utils/gmailparser.py（封装 EZGmail）
- [ ] 实现 GmailSource（使用 gmailparser）
- [ ] 实现 HTML 邮件解析器（BeautifulSoup）
- [ ] 单元测试（Gmail 解析）

### Week 3: 过滤管道
- [ ] 实现 KeywordFilterStage
- [ ] 实现 FilterPipeline
- [ ] 实现来源过滤支持
- [ ] 集成测试

### Week 4: AI 过滤 + 导出器
- [ ] 实现 AIFilterStage
- [ ] 实现 JSONAdapter
- [ ] 实现 ZoteroAdapter
- [ ] 测试导出功能

### Week 5: CLI + 高级 API + 文档
- [ ] 实现 fetch_and_filter 高级 API
- [ ] 实现命令行接口
- [ ] 编写使用示例
- [ ] 编写 README 和 API 文档

## Gmail 认证指南

### 首次设置

```bash
# 1. 安装 EZGmail
pip install ezgmail

# 2. 运行 Python 脚本（首次会打开浏览器）
python -c "import ezgmail; ezgmail.init()"

# 3. 在浏览器中授权
# 4. Token 会自动保存到 ~/.ezgmail/credentials.json

# 5. GmailClient 会自动找到并使用这个 token
```

### utils/gmailparser.py 实现

```python
"""
Gmail utility wrapper for EZGmail.

This module provides a unified interface to EZGmail,
following paper-feed naming conventions.
"""

import ezgmail
from typing import List

class GmailClient:
    """
    Wrapper for EZGmail to provide unified interface.

    EZGmail automatically handles OAuth2 token at ~/.ezgmail/credentials.json
    """

    def __init__(self):
        """Initialize EZGmail (token auto-loaded)"""
        try:
            # EZGmail will automatically load token from ~/.ezgmail/credentials.json
            if not ezgmail.isToken():
                print("EZGmail token not found. Please run: import ezgmail; ezgmail.init()")
        except Exception as e:
            print(f"Failed to initialize EZGmail: {e}")
            raise

    def search(self, query: str) -> List:
        """
        Search Gmail messages.

        Args:
            query: Gmail search query (e.g., 'from:xxx newer_than:7d')

        Returns:
            List of EZGmail threads
        """
        return ezgmail.search(query)

    @staticmethod
    def setup():
        """
        Setup EZGmail OAuth2 (first-time only).

        This will open a browser for OAuth2 authorization.
        Token is automatically saved to ~/.ezgmail/credentials.json
        """
        import ezgmail
        ezgmail.init()
```

### 后续使用

```python
from paper_feed.utils.gmailparser import GmailClient

# 自动加载 EZGmail token
client = GmailClient()

# 搜索邮件
threads = client.search('from:scholaralerts@google.com newer_than:7d')
```

### GitHub Actions / CI

```bash
# 1. 导出 EZGmail token 为 base64
cat ~/.ezgmail/credentials.json | base64 -w 0 > ezgmail_token.b64

# 2. 在 GitHub Actions 中设置为 secret: EZGMAIL_TOKEN_JSON

# 3. 在 workflow 中恢复
mkdir -p ~/.ezgmail
echo "$EZGMAIL_TOKEN_JSON" | base64 -d > ~/.ezgmail/credentials.json
```

## 参考资料

### EZGmail（核心依赖）
- [asweigart/ezgmail](https://github.com/asweigart/ezgmail) - Pythonic Gmail API
- 最后更新：2024年12月 ✅
- 我们通过 `utils/gmailparser.py` 封装该库

### Google Scholar 邮件解析
- [Calmact/ScholarAlertGmail2Html](https://github.com/Calmact/ScholarAlertGmail2Html) - Scholar alerts HTML 解析参考
- [bzz/scholar-alert-digest](https://github.com/bzz/scholar-alert-digest) - 聚合 Scholar alerts 参考

---

**文档版本**: 5.0 (最终版 - 使用 gmailparser 封装 EZGmail)
**最后更新**: 2025-02-06
