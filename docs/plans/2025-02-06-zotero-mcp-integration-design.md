# zotero-mcp 集成层设计文档

**日期**: 2025-02-06
**状态**: 最终设计
**版本**: 3.0

## 概述

`zotero-mcp` 是轻量级的 MCP (Model Context Protocol) 集成层。作为 zotero-core、paper-analyzer 和 semantic-search 的粘合层,向 AI 助手暴露统一的 MCP 工具接口。

## 设计目标

1. **轻量级**: 最小化代码,专注于集成和协议转换
2. **统一接口**: 将多个模块的能力整合为 MCP 工具
3. **配置简单**: 使用 .env 文件管理所有 API keys
4. **易于安装**: 所有依赖内置,无需可选安装
5. **向后兼容**: 保持与现有 zotero-mcp v2.x 的兼容性

## 架构图

```
┌─────────────────────────────────────────────────────────┐
│                    zotero-mcp (集成层)                    │
│                       (FastMCP)                          │
└─────────────────────────────────────────────────────────┘
                            │
        ┌───────────────────┼───────────────────┐
        │                   │                   │
        ▼                   ▼                   ▼
┌─────────────┐    ┌─────────────┐    ┌──────────────┐
│ zotero-core │    │paper-analyzer│   │semantic-search│
│  (API)      │    │  (分析)      │   │  (ChromaDB)   │
└─────────────┘    └─────────────┘    └──────────────┘
        │                   │                   │
        └───────────────────┼───────────────────┘
                            ▼
                    ┌──────────────┐
                    │ MCP Tools    │
                    │              │
                    │ • Items      │
                    │ • Collections│
                    │ • Search     │
                    │ • Analysis   │
                    │ • Semantic   │
                    └──────────────┘
```

## 目录结构

```
zotero-mcp/
├── src/zotero_mcp/
│   ├── __init__.py
│   ├── server.py              # FastMCP 服务器入口
│   ├── cli.py                 # 命令行接口
│   ├── config.py              # 配置管理
│   ├── integration/           # 集成层
│   │   ├── __init__.py
│   │   ├── mcp_tools.py       # MCP 工具包装器
│   │   ├── zotero_integration.py  # Zotero 集成
│   │   ├── analyzer_integration.py # 分析器集成
│   │   └── semantic_integration.py # 语义搜索集成
│   └── utils/
│       ├── __init__.py
│       ├── env_loader.py      # .env 加载器
│       └── logging.py         # 日志配置
├── tests/
│   └── integration/
│       ├── test_mcp_tools.py
│       └── test_end_to_end.py
├── pyproject.toml
├── README.md
├── CLAUDE.md
└── .env.example               # 配置模板
```

## 配置管理

### .env 文件格式

```bash
# Zotero 配置
ZOTERO_LIBRARY_ID=user_123
ZOTERO_API_KEY=your_zotero_api_key
ZOTERO_LIBRARY_TYPE=user

# LLM 配置 (用于 paper-analyzer)
LLM_PROVIDER=deepseek  # deepseek, openai, gemini
LLM_API_KEY=your_llm_api_key
LLM_BASE_URL=https://api.deepseek.com/v1  # 可选
LLM_MODEL=deepseek-chat  # 可选

# 语义搜索配置 (ChromaDB)
CHROMADB_PERSIST_DIR=./chromadb_data  # 可选
EMBEDDING_PROVIDER=openai  # openai, huggingface
EMBEDDING_API_KEY=your_embedding_api_key  # 可选
EMBEDDING_MODEL=text-embedding-3-small  # 可选

# 日志配置
LOG_LEVEL=INFO  # DEBUG, INFO, WARNING, ERROR
DEBUG=false  # 启用调试模式
```

### config.py 实现

```python
import os
from pathlib import Path
from dotenv import load_dotenv
from pydantic import BaseModel, Field

class Config(BaseModel):
    """应用配置"""

    # Zotero 配置
    zotero_library_id: str = Field(..., env="ZOTERO_LIBRARY_ID")
    zotero_api_key: str = Field(..., env="ZOTERO_API_KEY")
    zotero_library_type: str = Field(default="user", env="ZOTERO_LIBRARY_TYPE")

    # LLM 配置
    llm_provider: str = Field(default="deepseek", env="LLM_PROVIDER")
    llm_api_key: str = Field(default="", env="LLM_API_KEY")
    llm_base_url: str = Field(default="", env="LLM_BASE_URL")
    llm_model: str = Field(default="deepseek-chat", env="LLM_MODEL")

    # 语义搜索配置
    chromadb_persist_dir: str = Field(default="./chromadb_data", env="CHROMADB_PERSIST_DIR")
    embedding_provider: str = Field(default="openai", env="EMBEDDING_PROVIDER")
    embedding_api_key: str = Field(default="", env="EMBEDDING_API_KEY")
    embedding_model: str = Field(default="text-embedding-3-small", env="EMBEDDING_MODEL")

    # 日志配置
    log_level: str = Field(default="INFO", env="LOG_LEVEL")
    debug: bool = Field(default=False, env="DEBUG")

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        extra = "ignore"  # 忽略额外的环境变量

    @classmethod
    def load(cls, env_file: str = ".env") -> "Config":
        """从 .env 文件加载配置"""
        # 加载 .env 文件
        load_dotenv(env_file)

        # 创建配置对象
        return cls()

def get_config() -> Config:
    """获取全局配置实例"""
    return Config.load()
```

## MCP 工具层

### mcp_tools.py (MCP 工具包装器)

```python
from fastmcp import FastMCP
from typing import List, Optional
from .zotero_integration import ZoteroIntegration
from .analyzer_integration import AnalyzerIntegration
from .semantic_integration import SemanticIntegration

class MCPTools:
    """
    MCP 工具包装器

    职责:
    1. 将底层模块的功能包装为 MCP 工具
    2. 处理输入/输出转换
    3. 统一错误处理
    """

    def __init__(
        self,
        zotero: ZoteroIntegration,
        analyzer: Optional[AnalyzerIntegration] = None,
        semantic: Optional[SemanticIntegration] = None
    ):
        """
        Args:
            zotero: Zotero 集成
            analyzer: 分析器集成 (可选)
            semantic: 语义搜索集成 (可选)
        """
        self.zotero = zotero
        self.analyzer = analyzer
        self.semantic = semantic

    def register_tools(self, mcp: FastMCP) -> None:
        """注册所有 MCP 工具"""

        # ========== Zotero 核心工具 ==========

        @mcp.tool()
        async def get_items(
            limit: int = 25,
            collection_key: Optional[str] = None,
            tag: Optional[str] = None
        ) -> str:
            """
            获取 Zotero 条目列表

            Args:
                limit: 返回数量
                collection_key: 集合 key (可选)
                tag: 标签过滤 (可选)

            Returns:
                Markdown 格式的条目列表
            """
            items = await self.zotero.get_items(
                limit=limit,
                collection_key=collection_key,
                tag=tag
            )

            return self.zotero.format_items(items)

        @mcp.tool()
        async def get_item(item_key: str) -> str:
            """
            获取单个 Zotero 条目详情

            Args:
                item_key: 条目 key

            Returns:
                Markdown 格式的条目详情
            """
            item = await self.zotero.get_item(item_key)
            return self.zotero.format_item(item)

        @mcp.tool()
        async def create_item(
            item_type: str,
            title: str,
            creators: Optional[List[str]] = None,
            abstract: Optional[str] = None,
            doi: Optional[str] = None,
            url: Optional[str] = None,
            collection_keys: Optional[List[str]] = None
        ) -> str:
            """
            创建新的 Zotero 条目

            Args:
                item_type: 条目类型 (journalArticle, book, etc.)
                title: 标题
                creators: 作者列表 ["Author Name", ...]
                abstract: 摘要
                doi: DOI
                url: URL
                collection_keys: 要添加到的集合 key 列表

            Returns:
                创建的条目信息
            """
            item = await self.zotero.create_item(
                item_type=item_type,
                title=title,
                creators=creators,
                abstract=abstract,
                doi=doi,
                url=url,
                collection_keys=collection_keys
            )

            return f"Created item: {item.key} - {item.title}"

        @mcp.tool()
        async def search_items(
            query: str,
            limit: int = 25
        ) -> str:
            """
            搜索 Zotero 条目

            Args:
                query: 搜索关键词
                limit: 返回数量

            Returns:
                Markdown 格式的搜索结果
            """
            results = await self.zotero.search(query, limit)
            return self.zotero.format_search_results(results)

        # ========== 集合管理工具 ==========

        @mcp.tool()
        async def get_collections() -> str:
            """
            获取所有 Zotero 集合

            Returns:
                Markdown 格式的集合列表
            """
            collections = await self.zotero.get_collections()
            return self.zotero.format_collections(collections)

        @mcp.tool()
        async def create_collection(
            name: str,
            parent_collection_key: Optional[str] = None
        ) -> str:
            """
            创建 Zotero 集合

            Args:
                name: 集合名称
                parent_collection_key: 父集合 key (可选)

            Returns:
                创建的集合信息
            """
            collection = await self.zotero.create_collection(
                name=name,
                parent_collection_key=parent_collection_key
            )

            return f"Created collection: {collection.key} - {collection.name}"

        # ========== PDF 分析工具 ==========

        @mcp.tool()
        async def analyze_paper(
            item_key: str,
            template_name: str = "default",
            extract_images: bool = False
        ) -> str:
            """
            分析 PDF 论文

            Args:
                item_key: 条目 key
                template_name: 分析模板名称 (default, multimodal, structured)
                extract_images: 是否提取图像

            Returns:
                分析结果 (摘要、关键点等)
            """
            if not self.analyzer:
                return "Error: Analyzer not configured. Please set LLM_API_KEY."

            result = await self.analyzer.analyze_item(
                item_key=item_key,
                template_name=template_name,
                extract_images=extract_images
            )

            return self.analyzer.format_result(result)

        @mcp.tool()
        async def batch_analyze(
            collection_key: str,
            template_name: str = "default",
            limit: int = 10
        ) -> str:
            """
            批量分析集合中的 PDF 论文

            Args:
                collection_key: 集合 key
                template_name: 分析模板名称
                limit: 最大处理数量

            Returns:
                批量分析结果摘要
            """
            if not self.analyzer:
                return "Error: Analyzer not configured. Please set LLM_API_KEY."

            results = await self.analyzer.analyze_collection(
                collection_key=collection_key,
                template_name=template_name,
                limit=limit
            )

            return self.analyzer.format_batch_results(results)

        # ========== 语义搜索工具 ==========

        @mcp.tool()
        async def semantic_search(
            query: str,
            top_k: int = 10,
            collection_key: Optional[str] = None
        ) -> str:
            """
            语义搜索 Zotero 条目

            Args:
                query: 自然语言查询
                top_k: 返回结果数量
                collection_key: 限定集合 (可选)

            Returns:
                Markdown 格式的搜索结果
            """
            if not self.semantic:
                return "Error: Semantic search not configured. Please set CHROMADB_PERSIST_DIR."

            results = await self.semantic.search(
                query=query,
                top_k=top_k,
                collection_key=collection_key
            )

            return self.semantic.format_results(results)

        @mcp.tool()
        async def update_semantic_index(
            mode: str = "metadata",
            force: bool = False
        ) -> str:
            """
            更新语义搜索索引

            Args:
                mode: 更新模式 ("metadata" 快速 / "fulltext" 完整)
                force: 强制重新索引

            Returns:
                索引更新结果
            """
            if not self.semantic:
                return "Error: Semantic search not configured."

            result = await self.semantic.update_index(mode=mode, force=force)
            return f"Index updated: {result['indexed']} items indexed"
```

## 集成层实现

### zotero_integration.py (Zotero 集成)

```python
from typing import List, Optional
from zotero_core import ItemService, SearchService, CollectionService
from ..config import get_config

class ZoteroIntegration:
    """Zotero 模块集成"""

    def __init__(self):
        config = get_config()

        # 初始化 zotero-core 服务
        self.item_service = ItemService(
            library_id=config.zotero_library_id,
            api_key=config.zotero_api_key,
            library_type=config.zotero_library_type
        )

        self.search_service = SearchService(
            library_id=config.zotero_library_id,
            api_key=config.zotero_api_key,
            library_type=config.zotero_library_type
        )

        self.collection_service = CollectionService(
            library_id=config.zotero_library_id,
            api_key=config.zotero_api_key,
            library_type=config.zotero_library_type
        )

    async def get_items(
        self,
        limit: int = 25,
        collection_key: Optional[str] = None,
        tag: Optional[str] = None
    ) -> List:
        """获取条目列表"""
        return await self.item_service.get_items(
            limit=limit,
            collection_key=collection_key,
            tag=tag
        )

    async def get_item(self, item_key: str):
        """获取单个条目"""
        return await self.item_service.get_item(item_key)

    async def create_item(
        self,
        item_type: str,
        title: str,
        creators: Optional[List[str]] = None,
        **kwargs
    ):
        """创建条目"""
        # 构建条目数据
        item_data = {
            "itemType": item_type,
            "title": title,
        }

        if creators:
            item_data["creators"] = [
                {"creatorType": "author", "name": name}
                for name in creators
            ]

        # 添加其他字段
        for key, value in kwargs.items():
            if value is not None:
                item_data[key] = value

        return await self.item_service.create_item(item_data)

    async def search(self, query: str, limit: int = 25):
        """搜索条目"""
        from zotero_core import SearchQuery
        search_query = SearchQuery(q=query, limit=limit)
        return await self.search_service.search(search_query)

    async def get_collections(self):
        """获取集合列表"""
        return await self.collection_service.get_collections()

    async def create_collection(self, name: str, parent_collection_key: Optional[str] = None):
        """创建集合"""
        return await self.collection_service.create_collection(
            name=name,
            parent_collection=parent_collection_key
        )

    def format_items(self, items) -> str:
        """格式化条目列表为 Markdown"""
        lines = [f"## Found {len(items)} items\n"]

        for item in items:
            authors = ", ".join([c.name for c in item.creators[:3]])
            lines.append(f"### {item.title}")
            lines.append(f"- **Key**: {item.key}")
            lines.append(f"- **Authors**: {authors}")
            lines.append(f"- **Date**: {item.date or 'N/A'}")
            lines.append(f"- **DOI**: {item.doi or 'N/A'}")
            lines.append("")

        return "\n".join(lines)

    def format_item(self, item) -> str:
        """格式化单个条目为 Markdown"""
        authors = ", ".join([c.name for c in item.creators])
        lines = [
            f"## {item.title}",
            f"",
            f"**Key**: {item.key}",
            f"**Type**: {item.item_type}",
            f"**Authors**: {authors}",
            f"**Date**: {item.date or 'N/A'}",
            f"**DOI**: {item.doi or 'N/A'}",
            f"**URL**: {item.url or 'N/A'}",
            f"",
            f"### Abstract",
            item.abstract_note or "No abstract available",
            f"",
            f"### Tags",
            ", ".join(item.tags) if item.tags else "No tags"
        ]

        return "\n".join(lines)

    def format_search_results(self, results) -> str:
        """格式化搜索结果"""
        return self.format_items(results.items)
```

### analyzer_integration.py (分析器集成)

```python
from typing import List, Optional
from pathlib import Path
from paper_analyzer import PDFAnalyzer, TemplateManager
from paper_analyzer.clients.openai import OpenAIClient
from paper_analyzer.clients.deepseek import DeepSeekClient
from ..config import get_config

class AnalyzerIntegration:
    """Paper Analyzer 模块集成"""

    def __init__(self):
        config = get_config()

        # 初始化 LLM 客户端
        if config.llm_provider == "openai":
            self.llm_client = OpenAIClient(
                api_key=config.llm_api_key,
                base_url=config.llm_base_url or "https://api.openai.com/v1",
                model=config.llm_model
            )
        else:  # deepseek
            self.llm_client = DeepSeekClient(
                api_key=config.llm_api_key,
                model=config.llm_model,
                base_url=config.llm_base_url or "https://api.deepseek.com/v1"
            )

        # 初始化分析器
        self.template_manager = TemplateManager()
        self.analyzer = PDFAnalyzer(
            llm_client=self.llm_client,
            template_manager=self.template_manager
        )

        # 关联 Zotero (用于获取 PDF 路径)
        from .zotero_integration import ZoteroIntegration
        self.zotero = ZoteroIntegration()

    async def analyze_item(
        self,
        item_key: str,
        template_name: str = "default",
        extract_images: bool = False
    ):
        """分析单个条目的 PDF"""
        # 1. 获取条目
        item = await self.zotero.get_item(item_key)

        # 2. 查找 PDF 附件
        pdf_path = self._find_pdf_path(item)
        if not pdf_path:
            raise ValueError(f"No PDF attachment found for item {item_key}")

        # 3. 分析
        result = await self.analyzer.analyze(
            file_path=pdf_path,
            template_name=template_name,
            extract_images=extract_images
        )

        return result

    async def analyze_collection(
        self,
        collection_key: str,
        template_name: str = "default",
        limit: int = 10
    ) -> List:
        """批量分析集合中的条目"""
        # 获取集合中的条目
        items = await self.zotero.item_service.get_items(
            limit=limit,
            collection_key=collection_key
        )

        results = []
        for item in items:
            try:
                result = await self.analyze_item(
                    item_key=item.key,
                    template_name=template_name
                )
                results.append(result)
            except Exception as e:
                print(f"Failed to analyze {item.key}: {e}")

        return results

    def _find_pdf_path(self, item) -> Optional[str]:
        """查找条目的 PDF 路径"""
        # 从 Zotero 本地存储查找
        # 这里需要访问 Zotero 的本地文件路径
        # 简化实现: 使用 item.data 中的路径信息

        # 实际实现需要:
        # 1. 获取 Zotero 数据目录路径
        # 2. 根据 item.key 构建文件路径
        # 3. 检查 PDF 是否存在

        # 简化: 假设环境变量 ZOTERO_DATA_DIR 已设置
        import os
        zotero_data_dir = os.getenv("ZOTERO_DATA_DIR")
        if not zotero_data_dir:
            return None

        pdf_path = Path(zotero_data_dir) / item.key / f"{item.key}.pdf"

        if pdf_path.exists():
            return str(pdf_path)

        return None

    def format_result(self, result) -> str:
        """格式化分析结果为 Markdown"""
        lines = [
            f"# Analysis Result: {Path(result.file_path).name}",
            f"",
            f"**Template**: {result.template_name}",
            f"**Model**: {result.model}",
            f"**Processing Time**: {result.processing_time:.2f}s",
            f"",
            f"## Summary",
            result.summary,
            f"",
            f"## Key Points",
        ]

        for i, point in enumerate(result.key_points, 1):
            lines.append(f"{i}. {point}")

        lines.extend([
            f"",
            f"## Methodology",
            result.methodology or "N/A",
            f"",
            f"## Conclusions",
            result.conclusions or "N/A"
        ])

        return "\n".join(lines)

    def format_batch_results(self, results: List) -> str:
        """格式化批量分析结果"""
        lines = [f"# Batch Analysis Results ({len(results)} papers)\n"]

        for i, result in enumerate(results, 1):
            lines.append(f"## {i}. {Path(result.file_path).name}")
            lines.append(result.summary)
            lines.append("")

        return "\n".join(lines)
```

### semantic_integration.py (语义搜索集成)

```python
from typing import List, Optional
from semantic_search import ChromaEmbedder, HybridSearchService
from ..config import get_config

class SemanticIntegration:
    """Semantic Search 模块集成"""

    def __init__(self):
        config = get_config()

        # 初始化 ChromaDB
        self.embedder = ChromaEmbedder(
            persist_dir=config.chromadb_persist_dir,
            provider=config.embedding_provider,
            api_key=config.embedding_api_key,
            model=config.embedding_model
        )

        # 关联 Zotero
        from .zotero_integration import ZoteroIntegration
        self.zotero = ZoteroIntegration()

    async def search(
        self,
        query: str,
        top_k: int = 10,
        collection_key: Optional[str] = None
    ):
        """语义搜索"""
        # 1. 嵌入查询
        query_embedding = await self.embedder.embed_query(query)

        # 2. 搜索 ChromaDB
        results = await self.embedder.search(
            query_embedding=query_embedding,
            top_k=top_k
        )

        # 3. 获取完整条目信息
        items = []
        for result in results:
            item = await self.zotero.get_item(result["id"])
            items.append({
                "item": item,
                "score": result["score"]
            })

        return items

    async def update_index(self, mode: str = "metadata", force: bool = False):
        """更新语义搜索索引"""
        # 获取所有条目
        items = await self.zotero.item_service.get_items(limit=999999)

        indexed_count = 0

        for item in items:
            # 准备文档内容
            if mode == "fulltext":
                # 需要提取 PDF 全文
                text = await self._extract_fulltext(item)
            else:
                # 仅使用元数据
                text = f"{item.title}\n{item.abstract_note}"

            # 嵌入并存储
            await self.embedder.add_document(
                doc_id=item.key,
                text=text,
                metadata={
                    "title": item.title,
                    "authors": [c.name for c in item.creators],
                    "date": item.date,
                    "doi": item.doi
                }
            )

            indexed_count += 1

        return {"indexed": indexed_count}

    async def _extract_fulltext(self, item) -> str:
        """提取 PDF 全文"""
        # 使用 paper-analyzer 的 PDFExtractor
        from paper_analyzer.extractors.pdf_extractor import PDFExtractor

        pdf_path = self.zotero._find_pdf_path(item)
        if not pdf_path:
            return f"{item.title}\n{item.abstract_note}"

        extractor = PDFExtractor(extract_images=False, extract_tables=False)
        content = await extractor.extract_text_only(pdf_path)
        return content

    def format_results(self, results) -> str:
        """格式化语义搜索结果"""
        lines = [f"## Semantic Search Results ({len(results)} items)\n"]

        for i, result in enumerate(results, 1):
            item = result["item"]
            score = result["score"]
            authors = ", ".join([c.name for c in item.creators[:3]])

            lines.append(f"### {i}. {item.title}")
            lines.append(f"**Relevance**: {score:.3f}")
            lines.append(f"**Authors**: {authors}")
            lines.append(f"**Key**: {item.key}")
            lines.append("")

        return "\n".join(lines)
```

## 服务器入口

### server.py (FastMCP 服务器)

```python
from fastmcp import FastMCP
from .config import get_config
from .integration import MCPTools
from .integration.zotero_integration import ZoteroIntegration
from .integration.analyzer_integration import AnalyzerIntegration
from .integration.semantic_integration import SemanticIntegration

def create_server() -> FastMCP:
    """创建 FastMCP 服务器"""
    config = get_config()

    # 创建 FastMCP 服务器
    mcp = FastMCP(
        name="zotero-mcp",
        version="3.0.0"
    )

    # 初始化集成层
    zotero = ZoteroIntegration()

    # 可选集成
    analyzer = None
    semantic = None

    try:
        if config.llm_api_key:
            analyzer = AnalyzerIntegration()
    except Exception as e:
        print(f"Warning: Analyzer integration failed: {e}")

    try:
        if config.chromadb_persist_dir:
            semantic = SemanticIntegration()
    except Exception as e:
        print(f"Warning: Semantic search integration failed: {e}")

    # 注册工具
    tools = MCPTools(zotero=zotero, analyzer=analyzer, semantic=semantic)
    tools.register_tools(mcp)

    return mcp

def main():
    """启动 MCP 服务器"""
    import sys

    # 加载配置
    config = get_config()

    # 配置日志
    import logging
    log_level = getattr(logging, config.log_level.upper())
    logging.basicConfig(level=log_level)

    # 创建服务器
    mcp = create_server()

    # 运行服务器
    if config.debug:
        mcp.run(transport="stdio")
    else:
        mcp.run(transport="stdio")

if __name__ == "__main__":
    main()
```

## CLI 入口

### cli.py (命令行接口)

```python
import click
from .server import create_server
from .config import Config, get_config

@click.group()
def cli():
    """zotero-mcp CLI"""
    pass

@cli.command()
@click.option('--env-file', default='.env', type=click.Path(exists=True))
def serve(env_file):
    """启动 MCP 服务器"""
    # 加载配置
    config = Config.load(env_file)

    # 启动服务器
    mcp = create_server()
    mcp.run(transport="stdio")

@cli.command()
@click.option('--output', '-o', type=click.Path(), default='.env')
def init(output):
    """初始化配置文件"""
    from .utils.env_loader import create_default_env
    create_default_env(output)
    click.echo(f"Created configuration file: {output}")

@cli.command()
def config():
    """显示当前配置"""
    config = get_config()

    click.echo("Current Configuration:")
    click.echo(f"  Zotero Library ID: {config.zotero_library_id}")
    click.echo(f"  Zotero Library Type: {config.zotero_library_type}")
    click.echo(f"  LLM Provider: {config.llm_provider}")
    click.echo(f"  LLM Model: {config.llm_model}")
    click.echo(f"  Embedding Provider: {config.embedding_provider}")
    click.echo(f"  Log Level: {config.log_level}")

@cli.command()
@click.argument('query')
@click.option('--top-k', default=10, type=int)
@click.option('--collection', '-c', type=str)
def search(query, top_k, collection):
    """测试语义搜索"""
    import asyncio
    from .integration.semantic_integration import SemanticIntegration

    async def _search():
        semantic = SemanticIntegration()
        results = await semantic.search(query, top_k, collection)
        click.echo(semantic.format_results(results))

    asyncio.run(_search())

def main():
    cli(prog_name="zotero-mcp")

if __name__ == "__main__":
    main()
```

## 依赖配置

```toml
[project]
name = "zotero-mcp"
version = "3.0.0"
description = "MCP server for Zotero research management"
dependencies = [
    # 核心框架
    "fastmcp>=2.14.0",
    "pydantic>=2.0.0",
    "python-dotenv>=1.0.0",

    # zotero-core 依赖
    "pyzotero>=1.8.0",
    "httpx>=0.25.0",

    # paper-analyzer 依赖
    "PyMuPDF>=1.23.0",
    "openai>=1.0.0",

    # semantic-search 依赖
    "chromadb>=0.4.0",

    # 工具
    "click>=8.0.0",
]

[project.scripts]
zotero-mcp = "zotero_mcp.cli:main"

[project.optional-dependencies]
# 所有依赖内置,无需可选依赖
dev = [
    "pytest>=7.0.0",
    "pytest-asyncio>=0.21.0",
    "ruff>=0.1.0",
]
```

## 使用示例

### 安装和配置

```bash
# 1. 安装
pip install zotero-mcp

# 2. 初始化配置
zotero-mcp init

# 3. 编辑 .env 文件,填写 API keys
# ZOTERO_LIBRARY_ID=user_123
# ZOTERO_API_KEY=your_key
# LLM_API_KEY=your_llm_key

# 4. 启动 MCP 服务器
zotero-mcp serve
```

### Claude Desktop 配置

```json
{
  "mcpServers": {
    "zotero": {
      "command": "zotero-mcp",
      "args": ["serve"],
      "env": {
        "ZOTERO_LIBRARY_ID": "user_123",
        "ZOTERO_API_KEY": "your_api_key",
        "LLM_API_KEY": "your_llm_key"
      }
    }
  }
}
```

### 在 Claude 中使用

```
用户: 搜索我关于机器学习的论文

Claude: [使用 semantic_search 工具]
找到 15 篇相关论文...

用户: 分析第一篇论文的 PDF

Claude: [使用 analyze_paper 工具]
以下是该论文的分析...
- 摘要: ...
- 关键点: 1. ..., 2. ..., 3. ...
```

## 测试策略

### 集成测试

```python
import pytest
from zotero_mcp.server import create_server

@pytest.mark.asyncio
async def test_mcp_tools():
    """测试 MCP 工具注册"""
    mcp = create_server()

    # 验证工具已注册
    tools = mcp._tools_manager.list_tools()
    assert "get_items" in tools
    assert "analyze_paper" in tools
    assert "semantic_search" in tools

@pytest.mark.integration
async def test_end_to_end_analysis():
    """端到端分析测试"""
    # 需要:
    # 1. 真实的 Zotero API keys
    # 2. LLM API key
    # 3. 测试 PDF 文件

    pass
```

## 实施计划(4周)

### Week 1: 配置和服务器框架
- [ ] 实现 config.py (.env 加载)
- [ ] 实现 server.py (FastMCP 入口)
- [ ] 实现 cli.py 基础命令
- [ ] 测试服务器启动

### Week 2: Zotero 集成
- [ ] 实现 zotero_integration.py
- [ ] 实现 MCP 工具包装 (Zotero 部分)
- [ ] 测试 CRUD 操作
- [ ] 测试搜索功能

### Week 3: 分析器和语义搜索集成
- [ ] 实现 analyzer_integration.py
- [ ] 实现 semantic_integration.py
- [ ] 实现 MCP 工具包装 (分析器/语义搜索)
- [ ] 测试多模态分析
- [ ] 测试语义搜索

### Week 4: 文档和优化
- [ ] 编写 README
- [ ] 编写配置指南
- [ ] 编写 Claude Desktop 配置示例
- [ ] 性能优化
- [ ] 端到端测试

---

**文档版本**: 3.0 (最终版)
**最后更新**: 2025-02-06
