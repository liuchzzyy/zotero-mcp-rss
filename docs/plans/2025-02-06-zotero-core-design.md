# zotero-core 完整设计文档

**日期**: 2025-02-06
**状态**: 最终设计
**版本**: 1.0

## 概述

`zotero-core` 是一个专注于 Zotero 数据操作的独立 Python 库。提供完整的 Zotero API 访问、CRUD 服务、高级搜索和元数据管理功能。

## 设计目标

1. **独立可用**: 可以独立安装和使用,不依赖 zotero-mcp
2. **API 完整**: 覆盖 Zotero Web API 的核心功能
3. **搜索增强**: 提供混合搜索(Hybrid Search)和高级查询构建
4. **元数据丰富**: 集成 Crossref/OpenAlex 进行 DOI 查询
5. **易于扩展**: 清晰的服务层和客户端层分离

## 架构图

```
┌─────────────────────────────────────────────────────────┐
│                      zotero-core                         │
└─────────────────────────────────────────────────────────┘
                            │
        ┌───────────────────┼───────────────────┐
        │                   │                   │
        ▼                   ▼                   ▼
┌──────────────┐  ┌──────────────┐  ┌──────────────┐
│   Services   │  │   Clients    │  │    Models    │
│              │  │              │  │              │
│ • ItemService│  │ • ZoteroAPI  │  │ • Item       │
│ • Collection │  │ • Crossref   │  │ • Collection │
│ • TagService │  │ • OpenAlex   │  │ • SearchQuery│
│ • Metadata   │  │              │  │              │
│ • Search     │  │              │  │              │
│ • Hybrid     │  │              │  │              │
│ • Duplicate  │  │              │  │              │
└──────────────┘  └──────────────┘  └──────────────┘
        │                   │                   │
        └───────────────────┼───────────────────┘
                            ▼
                    ┌──────────────┐
                    │  Utilities   │
                    │              │
                    │ • Retry      │
                    │ • Formatting │
                    │ • Config     │
                    └──────────────┘
```

## 核心数据模型

### Item (条目)

```python
from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
from datetime import datetime

class Creator(BaseModel):
    """作者/创建者"""
    creator_type: str = Field(..., description="类型: author, editor, etc.")
    name: str = Field(..., description="姓名")

class Item(BaseModel):
    """Zotero 条目模型"""

    # 基础信息
    key: str = Field(..., description="Zotero 唯一标识符")
    item_type: str = Field(..., description="条目类型: journalArticle, book, etc.")
    title: str = Field(..., description="标题")

    # 作者信息
    creators: List[Creator] = Field(default_factory=list, description="创建者列表")

    # 元数据
    abstract_note: Optional[str] = Field(None, description="摘要")
    doi: Optional[str] = Field(None, description="DOI")
    url: Optional[str] = Field(None, description="URL")
    date: Optional[str] = Field(None, description="发表日期")
    publication_title: Optional[str] = Field(None, description="期刊/会议名称")
    volume: Optional[str] = Field(None, description="卷")
    issue: Optional[str] = Field(None, description="期")
    pages: Optional[str] = Field(None, description="页码")
    publisher: Optional[str] = Field(None, description="出版社")

    # Zotero 特定字段
    parent_item: Optional[str] = Field(None, description="父条目 key (附件/笔记)")
    collection_ids: List[str] = Field(default_factory=list, description="所属集合 ID 列表")
    tags: List[str] = Field(default_factory=list, description="标签列表")

    # 时间戳
    date_added: Optional[datetime] = Field(None, description="添加时间")
    date_modified: Optional[datetime] = Field(None, description="修改时间")

    # 扩展数据
    data: Dict[str, Any] = Field(
        default_factory=dict,
        description="额外的自定义字段"
    )

    @property
    def has_attachment(self) -> bool:
        """是否有附件"""
        return any(
            item.get("itemType") == "attachment"
            for item in self.data.get("attachments", [])
        )

    @property
    def pdf_url(self) -> Optional[str]:
        """获取 PDF 附件 URL"""
        attachments = self.data.get("attachments", [])
        for att in attachments:
            if att.get("itemType") == "attachment" and "pdf" in att.get("title", "").lower():
                return att.get("url")
        return None
```

### Collection (集合)

```python
class Collection(BaseModel):
    """Zotero 集合模型"""

    key: str = Field(..., description="集合唯一标识符")
    name: str = Field(..., description="集合名称")
    parent_collection: Optional[str] = Field(None, description="父集合 key")

    # 统计信息
    num_items: int = Field(default=0, description="包含的条目数量")

    # 时间戳
    date_added: Optional[datetime] = Field(None, description="添加时间")
    date_modified: Optional[datetime] = Field(None, description="修改时间")
```

### SearchQuery (搜索查询)

```python
class SearchQuery(BaseModel):
    """高级搜索查询"""

    # 基础查询
    q: Optional[str] = Field(None, description="全文搜索关键词")

    # 字段过滤
    title: Optional[str] = Field(None, description="标题关键词")
    author: Optional[str] = Field(None, description="作者名")
    year: Optional[str] = Field(None, description="年份")
    tag: Optional[str] = Field(None, description="标签")
    notes: Optional[str] = Field(None, description="笔记内容")

    # 范围限制
    collection_key: Optional[str] = Field(None, description="限定集合")
    item_type: Optional[str] = Field(None, description="条目类型")

    # 布尔逻辑
    condition: str = Field(default="and", description="组合逻辑: and / or / not")

    # 排序
    sort: str = Field(default="date", description="排序字段: date / title / creator")
    order: str = Field(default="desc", description="排序方向: asc / desc")

    # 分页
    limit: int = Field(default=25, ge=1, le=100, description="每页数量")
    start: int = Field(default=0, ge=0, description="起始位置")
```

### SearchResult (搜索结果)

```python
class SearchResult(BaseModel):
    """搜索结果"""

    items: List[Item] = Field(default_factory=list, description="匹配的条目")
    total: int = Field(default=0, description="总结果数")
    query: SearchQuery = Field(..., description="原始查询")

    # 可用性
    found: int = Field(default=0, description="实际找到的结果数")
    start: int = Field(default=0, description="起始位置")

    @property
    def has_more(self) -> bool:
        """是否有更多结果"""
        return self.start + self.found < self.total
```

## 客户端层

### ZoteroAPIClient (Zotero API 客户端)

```python
import httpx
from typing import List, Optional, Dict, Any
from ..models import Item, Collection
from ..utils.retry import async_retry

class ZoteroAPIClient:
    """
    Zotero Web API 客户端

    基于 pyzotero,提供更 Pythonic 的接口
    """

    def __init__(
        self,
        library_id: str,
        api_key: str,
        library_type: str = "user",
        timeout: int = 45,
        retry_attempts: int = 3
    ):
        """
        Args:
            library_id: Zotero library ID (user 或 group ID)
            api_key: Zotero API key
            library_type: "user" 或 "group"
            timeout: 请求超时时间(秒)
            retry_attempts: 重试次数
        """
        self.library_id = library_id
        self.api_key = api_key
        self.library_type = library_type
        self.timeout = timeout
        self.retry_attempts = retry_attempts

        # 初始化 pyzotero
        from pyzotero import zotero
        self._zot = zotero.Zotero(
            library_id,
            library_type,
            api_key,
            timeout=timeout
        )

    @async_retry(max_attempts=3, backoff_base=2.0)
    async def get_items(
        self,
        limit: int = 25,
        start: int = 0,
        collection_key: Optional[str] = None,
        tag: Optional[str] = None,
        q: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        获取条目列表

        Args:
            limit: 返回数量
            start: 起始位置
            collection_key: 限定集合
            tag: 限定标签
            q: 全文搜索

        Returns:
            原始条目数据列表
        """
        kwargs = {
            "limit": limit,
            "start": start
        }

        if collection_key:
            kwargs["collection"] = collection_key
        if tag:
            kwargs["tag"] = tag
        if q:
            kwargs["q"] = q

        # pyzotero 调用
        result = self._zot.everything(**kwargs)
        return result

    @async_retry(max_attempts=3, backoff_base=2.0)
    async def get_item(self, item_key: str) -> Dict[str, Any]:
        """获取单个条目"""
        return self._zot.get(item_key)

    @async_retry(max_attempts=3, backoff_base=2.0)
    async def create_item(self, item_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        创建新条目

        Args:
            item_data: 条目数据字典

        Returns:
            创建的条目数据(包含 key)
        """
        result = self._zot.create_items([item_data])
        if "successful" not in result or not result["successful"]:
            raise ValueError(f"Failed to create item: {result}")

        # 返回创建的条目
        created_key = result["successful"]["0"]["key"]
        return await self.get_item(created_key)

    @async_retry(max_attempts=3, backoff_base=2.0)
    async def update_item(
        self,
        item_key: str,
        item_data: Dict[str, Any],
        version: int
    ) -> Dict[str, Any]:
        """
        更新条目

        Args:
            item_key: 条目 key
            item_data: 更新的数据
            version: 当前版本号(用于乐观锁)

        Returns:
            更新后的条目数据
        """
        # 添加 key 和 version
        item_data["key"] = item_key
        item_data["version"] = version

        result = self._zot.update_item(item_data)
        if not result.get("successful"):
            raise ValueError(f"Failed to update item: {result}")

        return await self.get_item(item_key)

    @async_retry(max_attempts=3, backoff_base=2.0)
    async def delete_item(self, item_key: str) -> bool:
        """删除条目"""
        result = self._zot.delete_item(item_key)
        return result.get("successful", False)

    @async_retry(max_attempts=3, backoff_base=2.0)
    async def get_collections(
        self,
        top_level: bool = False
    ) -> List[Dict[str, Any]]:
        """
        获取集合列表

        Args:
            top_level: 仅返回顶级集合

        Returns:
            集合数据列表
        """
        return self._zot.collections(top=top_level)

    @async_retry(max_attempts=3, backoff_base=2.0)
    async def create_collection(
        self,
        name: str,
        parent_collection: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        创建集合

        Args:
            name: 集合名称
            parent_collection: 父集合 key (可选)

        Returns:
            创建的集合数据
        """
        collection_data = {
            "name": name,
            "collections": [] if not parent_collection else [parent_collection]
        }

        result = self._zot.create_collection(collection_data)
        if not result.get("successful"):
            raise ValueError(f"Failed to create collection: {result}")

        return result

    @async_retry(max_attempts=3, backoff_base=2.0)
    async def update_collection(
        self,
        collection_key: str,
        collection_data: Dict[str, Any],
        version: int
    ) -> Dict[str, Any]:
        """更新集合"""
        collection_data["key"] = collection_key
        collection_data["version"] = version

        result = self._zot.update_collection(collection_data)
        if not result.get("successful"):
            raise ValueError(f"Failed to update collection: {result}")

        return result

    @async_retry(max_attempts=3, backoff_base=2.0)
    async def delete_collection(self, collection_key: str) -> bool:
        """删除集合"""
        result = self._zot.delete_collection(collection_key)
        return result.get("successful", False)

    @async_retry(max_attempts=3, backoff_base=2.0)
    async def add_to_collection(
        self,
        collection_key: str,
        item_keys: List[str]
    ) -> bool:
        """
        将条目添加到集合

        Args:
            collection_key: 集合 key
            item_keys: 条目 key 列表

        Returns:
            是否成功
        """
        result = self._zot.collection_items(collection_key)

        # 获取当前集合中的条目
        current_items = [item["key"] for item in result]

        # 添加新条目
        new_items = current_items + item_keys

        # 更新集合
        collection = await self.get_collections()
        collection_data = next(
            (c for c in collection if c["key"] == collection_key),
            None
        )

        if not collection_data:
            raise ValueError(f"Collection {collection_key} not found")

        version = collection_data["version"]
        collection_data["items"] = new_items

        result = await self.update_collection(collection_key, collection_data, version)
        return result.get("successful", False)

    @async_retry(max_attempts=3, backoff_base=2.0)
    async def get_tags(self) -> List[Dict[str, Any]]:
        """获取所有标签"""
        return self._zot.all_tags()

    @async_retry(max_attempts=3, backoff_base=2.0)
    async def get_item_tags(self, item_key: str) -> List[str]:
        """获取条目的标签"""
        item = await self.get_item(item_key)
        return [tag["tag"] for tag in item.get("data", {}).get("tags", [])]

    @async_retry(max_attempts=3, backoff_base=2.0)
    async def add_tags(
        self,
        item_key: str,
        tags: List[str]
    ) -> bool:
        """
        为条目添加标签

        Args:
            item_key: 条目 key
            tags: 标签列表

        Returns:
            是否成功
        """
        item = await self.get_item(item_key)
        item_data = item["data"]
        version = item["version"]

        # 合并标签(去重)
        existing_tags = [
            tag["tag"]
            for tag in item_data.get("tags", [])
        ]
        new_tags = list(set(existing_tags + tags))

        item_data["tags"] = [{"tag": tag} for tag in new_tags]

        result = await self.update_item(item_key, item_data, version)
        return result.get("successful", False)

    @async_retry(max_attempts=3, backoff_base=2.0)
    async def remove_tags(
        self,
        item_key: str,
        tags: List[str]
    ) -> bool:
        """移除条目标签"""
        item = await self.get_item(item_key)
        item_data = item["data"]
        version = item["version"]

        # 过滤标签
        existing_tags = [
            tag["tag"]
            for tag in item_data.get("tags", [])
            if tag["tag"] not in tags
        ]

        item_data["tags"] = [{"tag": tag} for tag in existing_tags]

        result = await self.update_item(item_key, item_data, version)
        return result.get("successful", False)
```

### MetadataAPIClient (元数据 API 客户端)

```python
import httpx
from typing import Optional, Dict, Any

class CrossrefClient:
    """Crossref API 客户端 (DOI 查询)"""

    BASE_URL = "https://api.crossref.org/works"

    def __init__(self, timeout: int = 10, email: Optional[str] = None):
        """
        Args:
            timeout: 请求超时(秒)
            email: 提供 email 以获得更友好的速率限制
        """
        self.timeout = timeout
        self.email = email

    async def fetch_by_doi(self, doi: str) -> Optional[Dict[str, Any]]:
        """
        通过 DOI 获取元数据

        Args:
            doi: DOI 标识符(如 "10.1038/nature12373")

        Returns:
            元数据字典,未找到返回 None
        """
        url = f"{self.BASE_URL}/{doi}"
        headers = {}

        if self.email:
            headers["User-Agent"] = f"zotero-core/1.0 (mailto:{self.email})"

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            try:
                response = await client.get(url, headers=headers)
                response.raise_for_status()
                data = response.json()

                if data["status"] == "ok":
                    return data["message"]
                else:
                    return None

            except httpx.HTTPError:
                return None

    def _crossref_to_zotero(self, crossref_data: Dict[str, Any]) -> Dict[str, Any]:
        """将 Crossref 数据转换为 Zotero 格式"""
        # 提取作者
        creators = []
        for author in crossref_data.get("author", []):
            given = author.get("given", "")
            family = author.get("family", "")
            if given and family:
                creators.append({
                    "creatorType": "author",
                    "name": f"{family}, {given}"
                })

        # 提取期刊信息
        title = crossref_data.get("title", [""])[0]
        container_title = crossref_data.get("container-title", [""])[0]
        volume = crossref_data.get("volume", "")
        issue = crossref_data.get("issue", "")
        page = crossref_data.get("page", "")
        published = crossref_data.get("published-print", {})
        year = published.get("date-parts", [[""]])[0][0] if published else ""

        return {
            "itemType": "journalArticle",
            "title": title,
            "creators": creators,
            "publicationTitle": container_title,
            "volume": volume,
            "issue": issue,
            "pages": page,
            "date": year,
            "DOI": crossref_data.get("DOI"),
            "url": crossref_data.get("URL"),
        }


class OpenAlexClient:
    """OpenAlex API 客户端 (更丰富的元数据)"""

    BASE_URL = "https://api.openalex.org/works"

    def __init__(self, timeout: int = 10, email: Optional[str] = None):
        self.timeout = timeout
        self.email = email

    async def fetch_by_doi(self, doi: str) -> Optional[Dict[str, Any]]:
        """通过 DOI 获取元数据"""
        # 使用 filter 查询
        filter_param = f"doi:{doi}"
        url = f"{self.BASE_URL}?filter={filter_param}"

        params = {}
        if self.email:
            params["mailto"] = self.email

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            try:
                response = await client.get(url, params=params)
                response.raise_for_status()
                data = response.json()

                if data["meta"]["count"] > 0:
                    return data["results"][0]
                else:
                    return None

            except httpx.HTTPError:
                return None

    def _openalex_to_zotero(self, openalex_data: Dict[str, Any]) -> Dict[str, Any]:
        """将 OpenAlex 数据转换为 Zotero 格式"""
        # 提取作者
        creators = []
        for authorship in openalex_data.get("authorships", []):
            author = authorship.get("author", {})
            display_name = author.get("display_name", "")
            if display_name:
                creators.append({
                    "creatorType": "author",
                    "name": display_name
                })

        # 提取期刊信息
        title = openalex_data.get("title", "")
        source = openalex_data.get("primary_location", {})
        source_name = source.get("source", {}).get("display_name", "")
        volume = source.get("volume", "")
        issue = source.get("issue", "")
        pages = source.get("pages", "")
        year = openalex_data.get("publication_year", "")

        return {
            "itemType": "journalArticle",
            "title": title,
            "creators": creators,
            "publicationTitle": source_name,
            "volume": volume,
            "issue": issue,
            "pages": pages,
            "date": str(year),
            "DOI": openalex_data.get("doi"),
            "url": openalex_data.get("id"),
        }
```

## 服务层

### ItemService (条目服务)

```python
from typing import List, Optional
from .clients.zotero_api import ZoteroAPIClient
from .models import Item, Creator

class ItemService:
    """条目 CRUD 服务"""

    def __init__(
        self,
        library_id: str,
        api_key: str,
        library_type: str = "user",
        timeout: int = 45
    ):
        """
        Args:
            library_id: Zotero library ID
            api_key: Zotero API key
            library_type: "user" 或 "group"
            timeout: 请求超时(秒)
        """
        self.client = ZoteroAPIClient(
            library_id=library_id,
            api_key=api_key,
            library_type=library_type,
            timeout=timeout
        )

    async def get_items(
        self,
        limit: int = 25,
        start: int = 0,
        collection_key: Optional[str] = None,
        tag: Optional[str] = None,
        q: Optional[str] = None
    ) -> List[Item]:
        """
        获取条目列表

        Args:
            limit: 返回数量
            start: 起始位置
            collection_key: 限定集合
            tag: 限定标签
            q: 全文搜索关键词

        Returns:
            Item 对象列表
        """
        raw_items = await self.client.get_items(
            limit=limit,
            start=start,
            collection_key=collection_key,
            tag=tag,
            q=q
        )

        return [self._parse_item(item) for item in raw_items]

    async def get_item(self, item_key: str) -> Item:
        """获取单个条目"""
        raw_item = await self.client.get_item(item_key)
        return self._parse_item(raw_item)

    async def create_item(
        self,
        item_data: dict,
        collection_keys: Optional[List[str]] = None
    ) -> Item:
        """
        创建新条目

        Args:
            item_data: 条目数据(符合 Zotero schema)
            collection_keys: 要添加到的集合列表

        Returns:
            创建的 Item 对象
        """
        # 创建条目
        created_item = await self.client.create_item(item_data)

        # 添加到集合
        if collection_keys:
            item_key = created_item["key"]
            for collection_key in collection_keys:
                await self.client.add_to_collection(collection_key, [item_key])

        return self._parse_item(created_item)

    async def update_item(
        self,
        item_key: str,
        updates: dict
    ) -> Item:
        """
        更新条目

        Args:
            item_key: 条目 key
            updates: 要更新的字段

        Returns:
            更新后的 Item 对象
        """
        # 获取当前条目
        current = await self.client.get_item(item_key)
        version = current["version"]
        data = current["data"]

        # 合并更新
        data.update(updates)

        # 提交更新
        updated_item = await self.client.update_item(item_key, data, version)
        return self._parse_item(updated_item)

    async def delete_item(self, item_key: str) -> bool:
        """删除条目"""
        return await self.client.delete_item(item_key)

    async def trash_item(self, item_key: str) -> Item:
        """将条目移至回收站(软删除)"""
        return await self.update_item(item_key, {"deleted": 1})

    async def restore_item(self, item_key: str) -> Item:
        """从回收站恢复条目"""
        return await self.update_item(item_key, {"deleted": 0})

    def _parse_item(self, raw_item: dict) -> Item:
        """将原始 API 响应解析为 Item 模型"""
        data = raw_item.get("data", {})
        meta = raw_item.get("meta", {})

        # 解析作者
        creators = [
            Creator(
                creator_type=c.get("creatorType", "author"),
                name=c.get("name", "")
            )
            for c in data.get("creators", [])
        ]

        # 解析标签
        tags = [tag["tag"] for tag in data.get("tags", [])]

        # 解析集合
        collection_ids = data.get("collections", [])

        return Item(
            key=data.get("key", ""),
            item_type=data.get("itemType", ""),
            title=data.get("title", ""),
            creators=creators,
            abstract_note=data.get("abstractNote"),
            doi=data.get("DOI"),
            url=data.get("url"),
            date=data.get("date"),
            publication_title=data.get("publicationTitle"),
            volume=data.get("volume"),
            issue=data.get("issue"),
            pages=data.get("pages"),
            publisher=data.get("publisher"),
            parent_item=data.get("parentItem"),
            collection_ids=collection_ids,
            tags=tags,
            date_added=meta.get("dateAdded"),
            date_modified=meta.get("dateModified"),
            data=raw_item
        )
```

### CollectionService (集合服务)

```python
from typing import List, Optional
from .clients.zotero_api import ZoteroAPIClient
from .models import Collection

class CollectionService:
    """集合管理服务"""

    def __init__(
        self,
        library_id: str,
        api_key: str,
        library_type: str = "user"
    ):
        self.client = ZoteroAPIClient(
            library_id=library_id,
            api_key=api_key,
            library_type=library_type
        )

    async def get_collections(
        self,
        top_level: bool = False
    ) -> List[Collection]:
        """
        获取集合列表

        Args:
            top_level: 仅返回顶级集合

        Returns:
            Collection 对象列表
        """
        raw_collections = await self.client.get_collections(top_level=top_level)

        return [
            self._parse_collection(c)
            for c in raw_collections
        ]

    async def get_collection(self, collection_key: str) -> Collection:
        """获取单个集合"""
        collections = await self.get_collections()
        return next(
            (c for c in collections if c.key == collection_key),
            None
        )

    async def create_collection(
        self,
        name: str,
        parent_collection: Optional[str] = None
    ) -> Collection:
        """
        创建集合

        Args:
            name: 集合名称
            parent_collection: 父集合 key (可选)

        Returns:
            创建的 Collection 对象
        """
        raw_collection = await self.client.create_collection(
            name=name,
            parent_collection=parent_collection
        )
        return self._parse_collection(raw_collection)

    async def update_collection(
        self,
        collection_key: str,
        name: Optional[str] = None,
        parent_collection: Optional[str] = None
    ) -> Collection:
        """更新集合"""
        collection = await self.get_collection(collection_key)
        raw_data = collection.data

        updates = {}
        if name is not None:
            updates["name"] = name
        if parent_collection is not None:
            updates["collections"] = [] if not parent_collection else [parent_collection]

        version = raw_data.get("version", 0)
        raw_collection = await self.client.update_collection(
            collection_key,
            {**raw_data, **updates},
            version
        )
        return self._parse_collection(raw_collection)

    async def delete_collection(self, collection_key: str) -> bool:
        """删除集合"""
        return await self.client.delete_collection(collection_key)

    async def add_items(
        self,
        collection_key: str,
        item_keys: List[str]
    ) -> bool:
        """将条目添加到集合"""
        return await self.client.add_to_collection(collection_key, item_keys)

    def _parse_collection(self, raw_collection: dict) -> Collection:
        """解析原始集合数据"""
        data = raw_collection.get("data", raw_collection)
        meta = raw_collection.get("meta", {})

        return Collection(
            key=data.get("key", ""),
            name=data.get("name", ""),
            parent_collection=data.get("parentCollection"),
            num_items=meta.get("numItems", 0),
            date_added=meta.get("dateAdded"),
            date_modified=meta.get("dateModified")
        )
```

### TagService (标签服务)

```python
from typing import List, Dict, Counter
from collections import Counter
from .clients.zotero_api import ZoteroAPIClient

class TagService:
    """标签管理服务"""

    def __init__(
        self,
        library_id: str,
        api_key: str,
        library_type: str = "user"
    ):
        self.client = ZoteroAPIClient(
            library_id=library_id,
            api_key=api_key,
            library_type=library_type
        )

    async def get_all_tags(self) -> List[Dict[str, Any]]:
        """
        获取所有标签及其使用次数

        Returns:
            标签列表,格式: [{"tag": "name", "count": 5}, ...]
        """
        return await self.client.get_tags()

    async def get_item_tags(self, item_key: str) -> List[str]:
        """获取条目的标签"""
        return await self.client.get_item_tags(item_key)

    async def add_tags(
        self,
        item_key: str,
        tags: List[str]
    ) -> bool:
        """为条目添加标签"""
        return await self.client.add_tags(item_key, tags)

    async def remove_tags(
        self,
        item_key: str,
        tags: List[str]
    ) -> bool:
        """移除条目标签"""
        return await self.client.remove_tags(item_key, tags)

    async def replace_tags(
        self,
        item_key: str,
        new_tags: List[str]
    ) -> bool:
        """替换条目的所有标签"""
        # 获取现有标签
        existing_tags = await self.get_item_tags(item_key)

        # 先移除所有标签
        if existing_tags:
            await self.remove_tags(item_key, existing_tags)

        # 添加新标签
        if new_tags:
            return await self.add_tags(item_key, new_tags)

        return True

    async def get_tag_colors(self) -> Dict[str, str]:
        """
        获取标签颜色配置(Zotero 客户端功能)

        Returns:
            标签到颜色的映射
        """
        # 这个功能需要访问本地配置,暂不实现
        return {}

    async def rename_tag(
        self,
        old_name: str,
        new_name: str
    ) -> int:
        """
        重命名全局标签

        Args:
            old_name: 旧标签名
            new_name: 新标签名

        Returns:
            更新的条目数量
        """
        # 这是一个批量操作,需要遍历所有带该标签的条目
        # 暂不实现,可能需要 Zotero 5.0+ 的 API 支持
        raise NotImplementedError("Tag renaming requires Zotero 5.0+ API")
```

### MetadataService (元数据服务)

```python
from typing import Optional, Dict, Any
from .clients.metadata import CrossrefClient, OpenAlexClient

class MetadataService:
    """
    元数据查询和补全服务

    集成 Crossref 和 OpenAlex,提供 DOI 查询
    """

    def __init__(
        self,
        timeout: int = 10,
        email: Optional[str] = None,
        preferred_source: str = "crossref"
    ):
        """
        Args:
            timeout: API 请求超时(秒)
            email: 提供 email 以获得更友好的速率限制
            preferred_source: 首选数据源 ("crossref" 或 "openalex")
        """
        self.crossref = CrossrefClient(timeout=timeout, email=email)
        self.openalex = OpenAlexClient(timeout=timeout, email=email)
        self.preferred_source = preferred_source

    async def fetch_by_doi(
        self,
        doi: str,
        source: Optional[str] = None
    ) -> Optional[Dict[str, Any]]:
        """
        通过 DOI 获取元数据

        Args:
            doi: DOI 标识符
            source: 数据源 ("crossref", "openalex", 或 None 使用默认)

        Returns:
            Zotero 格式的元数据字典,未找到返回 None
        """
        # 清理 DOI
        doi = self._clean_doi(doi)

        # 选择数据源
        source = source or self.preferred_source

        if source == "openalex":
            data = await self.openalex.fetch_by_doi(doi)
            if data:
                return self.openalex._openalex_to_zotero(data)

        # 默认使用 Crossref
        data = await self.crossref.fetch_by_doi(doi)
        if data:
            return self.crossref._crossref_to_zotero(data)

        return None

    async def complete_metadata(
        self,
        item_data: Dict[str, Any],
        fetch_abstract: bool = False
    ) -> Dict[str, Any]:
        """
        补全条目元数据

        Args:
            item_data: 部分元数据
            fetch_abstract: 是否尝试获取摘要

        Returns:
            补全后的元数据
        """
        # 检查是否有 DOI
        doi = item_data.get("DOI")
        if not doi:
            return item_data

        # 从 DOI 获取完整元数据
        complete_data = await self.fetch_by_doi(doi)
        if not complete_data:
            return item_data

        # 合并数据(优先保留用户提供的字段)
        merged = {**complete_data, **item_data}

        return merged

    def _clean_doi(self, doi: str) -> str:
        """清理 DOI 格式"""
        # 移除 URL 前缀
        if doi.startswith("http"):
            doi = doi.split("doi.org/")[-1]
        elif doi.startswith("doi:"):
            doi = doi[4:]

        # 移除前后空格
        doi = doi.strip()

        return doi
```

### SearchService (基础搜索服务)

```python
from typing import List, Optional
from .clients.zotero_api import ZoteroAPIClient
from .models import SearchQuery, SearchResult, Item

class SearchService:
    """
    基础搜索服务

    基于 Zotero API 的关键词搜索功能
    """

    def __init__(
        self,
        library_id: str,
        api_key: str,
        library_type: str = "user"
    ):
        self.client = ZoteroAPIClient(
            library_id=library_id,
            api_key=api_key,
            library_type=library_type
        )

    async def search(self, query: SearchQuery) -> SearchResult:
        """
        执行搜索

        Args:
            query: 搜索查询对象

        Returns:
            搜索结果对象
        """
        # 构建查询参数
        params = {
            "limit": query.limit,
            "start": query.start
        }

        # 添加过滤条件
        if query.collection_key:
            params["collection"] = query.collection_key

        if query.tag:
            params["tag"] = query.tag

        # 关键词搜索
        if query.q:
            params["q"] = query.q
        elif query.title:
            params["q"] = f"title:{query.title}"
        elif query.author:
            params["q"] = f"author:{query.author}"
        elif query.year:
            params["q"] = f"date:{query.year}"

        # 执行搜索
        raw_results = await self.client.get_items(**params)

        # 解析结果
        items = [self._parse_item(r) for r in raw_results]

        return SearchResult(
            items=items,
            total=len(items),  # Zotero API 不返回总数,这里简化处理
            query=query,
            found=len(items),
            start=query.start
        )

    async def quick_search(
        self,
        keyword: str,
        limit: int = 25
    ) -> List[Item]:
        """
        快速搜索(便捷方法)

        Args:
            keyword: 搜索关键词
            limit: 返回数量

        Returns:
            匹配的 Item 列表
        """
        query = SearchQuery(q=keyword, limit=limit)
        result = await self.search(query)
        return result.items

    def _parse_item(self, raw_item: dict) -> Item:
        """解析条目数据"""
        # 重用 ItemService 的解析逻辑
        from .item_service import ItemService
        # 这里简化处理,实际实现中可以提取为共享工具
        data = raw_item.get("data", {})
        return Item(
            key=data.get("key", ""),
            item_type=data.get("itemType", ""),
            title=data.get("title", ""),
            creators=[],  # 简化
            abstract_note=data.get("abstractNote"),
            doi=data.get("DOI"),
            url=data.get("url"),
            date=data.get("date"),
            publication_title=data.get("publicationTitle"),
            tags=[tag["tag"] for tag in data.get("tags", [])],
            collection_ids=data.get("collections", []),
            data=raw_item
        )
```

### HybridSearchService (混合搜索 - RRF 算法)

```python
from typing import List, Optional, Dict, Tuple
from .models import SearchQuery, SearchResult, Item
from .search_service import SearchService

class HybridSearchService:
    """
    混合搜索服务 (Reciprocal Rank Fusion)

    融合关键词搜索和语义搜索结果,提供更准确的检索
    参考: ZotSeek (https://github.com/introfini/ZotSeek)
    """

    def __init__(
        self,
        library_id: str,
        api_key: str,
        library_type: str = "user",
        semantic_search_client=None
    ):
        """
        Args:
            library_id: Zotero library ID
            api_key: Zotero API key
            library_type: "user" 或 "group"
            semantic_search_client: 可选的语义搜索客户端
                                   (来自独立的 semantic-search 模块)
        """
        self.keyword_search = SearchService(
            library_id=library_id,
            api_key=api_key,
            library_type=library_type
        )
        self.semantic_search = semantic_search_client

    async def search(
        self,
        query: str,
        search_mode: str = "hybrid",
        top_k: int = 10,
        collection_key: Optional[str] = None
    ) -> SearchResult:
        """
        执行混合搜索

        Args:
            query: 搜索查询
            search_mode: 搜索模式
                - "keyword": 仅关键词搜索
                - "semantic": 仅语义搜索 (需要 semantic_search_client)
                - "hybrid": 混合搜索 (RRF 融合)
            top_k: 返回前 K 个结果
            collection_key: 限定集合

        Returns:
            搜索结果对象
        """
        if search_mode == "keyword":
            return await self._keyword_search(query, top_k, collection_key)

        elif search_mode == "semantic":
            if not self.semantic_search:
                raise ValueError("Semantic search requires semantic_search_client")
            return await self._semantic_search(query, top_k, collection_key)

        else:  # hybrid
            return await self._hybrid_search_rrf(query, top_k, collection_key)

    async def _keyword_search(
        self,
        query: str,
        top_k: int,
        collection_key: Optional[str]
    ) -> SearchResult:
        """纯关键词搜索"""
        search_query = SearchQuery(
            q=query,
            limit=top_k,
            collection_key=collection_key
        )
        return await self.keyword_search.search(search_query)

    async def _semantic_search(
        self,
        query: str,
        top_k: int,
        collection_key: Optional[str]
    ) -> SearchResult:
        """纯语义搜索"""
        if not self.semantic_search:
            return SearchResult(items=[], total=0, query=SearchQuery())

        # 调用语义搜索客户端
        results = await self.semantic_search.search(
            query=query,
            top_k=top_k,
            collection_key=collection_key
        )

        return results

    async def _hybrid_search_rrf(
        self,
        query: str,
        top_k: int,
        collection_key: Optional[str],
        k: int = 60
    ) -> SearchResult:
        """
        混合搜索 (RRF 融合)

        RRF (Reciprocal Rank Fusion) 算法:
        score(item) = Σ(1 / (k + rank_i))

        其中:
        - k: 平滑常数 (默认 60)
        - rank_i: 该条目在第 i 个搜索结果中的排名

        Args:
            query: 搜索查询
            top_k: 返回前 K 个结果
            collection_key: 限定集合
            k: RRF 平滑常数
        """
        # 1. 关键词搜索 (获取更多结果用于融合)
        keyword_results = await self._keyword_search(
            query,
            top_k * 2,
            collection_key
        )

        # 2. 语义搜索 (如果有)
        if self.semantic_search:
            semantic_results = await self._semantic_search(
                query,
                top_k * 2,
                collection_key
            )
        else:
            semantic_results = SearchResult(items=[], total=0, query=SearchQuery())

        # 3. RRF 融合
        fused_scores = self._rrf_fusion(
            keyword_results.items,
            semantic_results.items,
            k=k
        )

        # 4. 排序并返回 top_k
        sorted_items = sorted(
            fused_scores.items(),
            key=lambda x: x[1],
            reverse=True
        )[:top_k]

        final_items = [item for item, score in sorted_items]

        return SearchResult(
            items=final_items,
            total=len(final_items),
            query=SearchQuery(q=query),
            found=len(final_items),
            start=0
        )

    def _rrf_fusion(
        self,
        keyword_results: List[Item],
        semantic_results: List[Item],
        k: int = 60
    ) -> Dict[Item, float]:
        """
        RRF 融合算法

        Args:
            keyword_results: 关键词搜索结果
            semantic_results: 语义搜索结果
            k: 平滑常数

        Returns:
            条目到融合分数的映射
        """
        scores: Dict[Item, float] = {}

        # 贡献 1: 关键词搜索排名
        for rank, item in enumerate(keyword_results, 1):
            scores[item] = scores.get(item, 0) + 1 / (k + rank)

        # 贡献 2: 语义搜索排名
        for rank, item in enumerate(semantic_results, 1):
            scores[item] = scores.get(item, 0) + 1 / (k + rank)

        return scores
```

**RRF 算法说明**:

```
RRF (Reciprocal Rank Fusion) 是一种简单但有效的多列表融合算法:

1. 对于每个条目,计算其在每个搜索结果中的排名
2. RRF 分数 = Σ(1 / (k + rank_i))
   - k 是平滑常数 (通常 60-80)
   - rank_i 是该条目在第 i 个结果列表中的排名
3. 按 RRF 分数排序

优势:
- 不需要归一化分数
- 对排名顺序敏感,而非绝对分数
- 简单高效,易于实现
- 在信息检索任务中表现优异

示例:
    关键词搜索: [A, B, C, D, E]
    语义搜索:   [C, A, D, F, B]

    RRF 分数 (k=60):
    A: 1/(60+1) + 1/(60+2) = 0.0325
    B: 1/(60+2) + 1/(60+5) = 0.0317
    C: 1/(60+3) + 1/(60+1) = 0.0322
    D: 1/(60+4) + 1/(60+3) = 0.0319
    E: 1/(60+5) = 0.0159
    F: 1/(60+1) = 0.0164

    最终排序: [A, C, B, D, F, E]
```

### DuplicateService (重复检测服务)

```python
from typing import List, Dict, Tuple, Set
from .models import Item
from .item_service import ItemService

class DuplicateService:
    """
    重复检测服务

    基于多种策略检测重复条目:
    1. DOI 匹配 (最可靠)
    2. 标题 + 作者匹配
    3. URL 匹配
    """

    def __init__(self, item_service: ItemService):
        """
        Args:
            item_service: ItemService 实例
        """
        self.item_service = item_service

    async def find_duplicates(
        self,
        collection_key: Optional[str] = None,
        strategies: List[str] = None
    ) -> List[List[Item]]:
        """
        查找重复条目

        Args:
            collection_key: 限定集合 (None 则全库扫描)
            strategies: 检测策略列表 ("doi", "title_author", "url")
                       默认使用所有策略

        Returns:
            重复组列表,每组是重复的条目
        """
        if strategies is None:
            strategies = ["doi", "title_author", "url"]

        # 获取所有条目
        items = await self.item_service.get_items(
            limit=999999,  # 大批量获取
            collection_key=collection_key
        )

        duplicates = []

        if "doi" in strategies:
            duplicates.extend(await self._find_by_doi(items))

        if "title_author" in strategies:
            duplicates.extend(await self._find_by_title_author(items))

        if "url" in strategies:
            duplicates.extend(await self._find_by_url(items))

        return duplicates

    async def _find_by_doi(self, items: List[Item]) -> List[List[Item]]:
        """基于 DOI 查找重复"""
        doi_groups: Dict[str, List[Item]] = {}

        for item in items:
            doi = item.doi
            if not doi:
                continue

            # 标准化 DOI
            normalized_doi = self._normalize_doi(doi)

            if normalized_doi not in doi_groups:
                doi_groups[normalized_doi] = []
            doi_groups[normalized_doi].append(item)

        # 仅返回有重复的组
        return [
            group for group in doi_groups.values()
            if len(group) > 1
        ]

    async def _find_by_title_author(
        self,
        items: List[Item]
    ) -> List[List[Item]]:
        """基于标题 + 作者查找重复"""
        title_author_groups: Dict[Tuple[str, str], List[Item]] = {}

        for item in items:
            # 标准化标题
            normalized_title = self._normalize_title(item.title)

            # 提取第一作者
            first_author = ""
            if item.creators:
                first_author = item.creators[0].name.lower()

            key = (normalized_title, first_author)

            if key not in title_author_groups:
                title_author_groups[key] = []
            title_author_groups[key].append(item)

        # 仅返回有重复的组
        return [
            group for group in title_author_groups.values()
            if len(group) > 1
        ]

    async def _find_by_url(self, items: List[Item]) -> List[List[Item]]:
        """基于 URL 查找重复"""
        url_groups: Dict[str, List[Item]] = {}

        for item in items:
            url = item.url
            if not url:
                continue

            # 标准化 URL
            normalized_url = self._normalize_url(url)

            if normalized_url not in url_groups:
                url_groups[normalized_url] = []
            url_groups[normalized_url].append(item)

        # 仅返回有重复的组
        return [
            group for group in url_groups.values()
            if len(group) > 1
        ]

    def _normalize_doi(self, doi: str) -> str:
        """标准化 DOI"""
        # 移除 URL 前缀
        if doi.startswith("http"):
            doi = doi.split("doi.org/")[-1]
        elif doi.startswith("doi:"):
            doi = doi[4:]

        # 转小写,去空格
        return doi.lower().strip()

    def _normalize_title(self, title: str) -> str:
        """标准化标题"""
        # 转小写
        title = title.lower()

        # 移除常见后缀
        for suffix in [": a review", ": a study", ": review", ": study"]:
            if title.endswith(suffix):
                title = title[:-len(suffix)]

        # 移除标点和空格
        import re
        title = re.sub(r'[^\w\s]', '', title)
        title = re.sub(r'\s+', ' ', title)

        return title.strip()

    def _normalize_url(self, url: str) -> str:
        """标准化 URL"""
        # 移除查询参数和片段
        from urllib.parse import urlparse
        parsed = urlparse(url)
        normalized = f"{parsed.scheme}://{parsed.netloc}{parsed.path}"
        return normalized.lower()

    async def merge_duplicates(
        self,
        duplicate_group: List[Item],
        keep: Item = None,
        delete_others: bool = False
    ) -> Item:
        """
        合并重复条目

        Args:
            duplicate_group: 重复条目组
            keep: 保留的条目 (None 则选择最新的)
            delete_others: 是否删除其他条目 (默认不删除)

        Returns:
            合并后的条目
        """
        if not duplicate_group:
            raise ValueError("Empty duplicate group")

        # 选择保留的条目
        if keep is None:
            # 选择最近修改的
            keep = max(
                duplicate_group,
                key=lambda item: item.date_modified or item.date_added
            )

        # 合并其他条目的数据
        for item in duplicate_group:
            if item.key == keep.key:
                continue

            # 合并标签
            if item.tags:
                await self.item_service.client.add_tags(
                    keep.key,
                    item.tags
                )

            # 合并集合
            if item.collection_ids:
                for collection_id in item.collection_ids:
                    if collection_id not in keep.collection_ids:
                        await self.item_service.client.add_to_collection(
                            collection_id,
                            [keep.key]
                        )

            # 可选: 删除其他条目
            if delete_others:
                await self.item_service.delete_item(item.key)

        return keep
```

## CLI 工具

### 命令行接口设计

```python
import click
from .item_service import ItemService
from .collection_service import CollectionService
from .hybrid_search import HybridSearchService

@click.group()
@click.option('--library-id', envvar='ZOTERO_LIBRARY_ID', required=True)
@click.option('--api-key', envvar='ZOTERO_API_KEY', required=True)
@click.option('--library-type', default='user', type=click.Choice(['user', 'group']))
@click.pass_context
def cli(ctx, library_id, api_key, library_type):
    """zotero-core CLI"""
    ctx.ensure_object(dict)
    ctx.obj['library_id'] = library_id
    ctx.obj['api_key'] = api_key
    ctx.obj['library_type'] = library_type

@cli.command()
@click.option('--collection', '-c', help='Collection key')
@click.option('--limit', '-l', default=25, help='Number of items')
@click.pass_context
def list_items(ctx, collection, limit):
    """List items"""
    service = ItemService(
        library_id=ctx.obj['library_id'],
        api_key=ctx.obj['api_key'],
        library_type=ctx.obj['library_type']
    )

    items = service.get_items(
        limit=limit,
        collection_key=collection
    )

    for item in items:
        click.echo(f"{item.key}: {item.title}")

@cli.command()
@click.argument('query')
@click.option('--mode', type=click.Choice(['keyword', 'semantic', 'hybrid']), default='hybrid')
@click.option('--top-k', default=10)
@click.pass_context
def search(ctx, query, mode, top_k):
    """Search items"""
    service = HybridSearchService(
        library_id=ctx.obj['library_id'],
        api_key=ctx.obj['api_key'],
        library_type=ctx.obj['library_type']
    )

    result = service.search(
        query=query,
        search_mode=mode,
        top_k=top_k
    )

    click.echo(f"Found {result.found} items:")
    for item in result.items:
        click.echo(f"  - {item.title}")

@cli.command()
@click.pass_context
def find_duplicates(ctx):
    """Find duplicate items"""
    item_service = ItemService(
        library_id=ctx.obj['library_id'],
        api_key=ctx.obj['api_key'],
        library_type=ctx.obj['library_type']
    )

    dup_service = DuplicateService(item_service)
    duplicates = dup_service.find_duplicates()

    click.echo(f"Found {len(duplicates)} duplicate groups:")
    for group in duplicates:
        click.echo(f"  Group ({len(group)} items):")
        for item in group:
            click.echo(f"    - {item.title} (DOI: {item.doi})")

def main():
    cli(obj={})

if __name__ == '__main__':
    main()
```

## 测试策略

### 单元测试

```python
import pytest
from zotero_core import ItemService, SearchService

@pytest.mark.asyncio
async def test_item_service_create():
    """测试创建条目"""
    service = ItemService(
        library_id="test",
        api_key="test"
    )

    # 使用 mock client
    # ...

@pytest.mark.asyncio
async def test_search_service():
    """测试搜索服务"""
    service = SearchService(
        library_id="test",
        api_key="test"
    )

    query = SearchQuery(q="machine learning")
    result = await service.search(query)

    assert result.items is not None
```

### 集成测试

```python
@pytest.mark.integration
@pytest.mark.asyncio
async def test_hybrid_search_real_api():
    """使用真实 API 测试混合搜索"""
    service = HybridSearchService(
        library_id=os.getenv("ZOTERO_LIBRARY_ID"),
        api_key=os.getenv("ZOTERO_API_KEY")
    )

    result = await service.search(
        query="deep learning",
        search_mode="hybrid",
        top_k=10
    )

    assert len(result.items) > 0
```

## 使用示例

### 基础使用

```python
from zotero_core import ItemService, SearchService

# 初始化服务
item_service = ItemService(
    library_id="user_123",
    api_key="your_api_key"
)

# 获取条目
items = await item_service.get_items(limit=10)
for item in items:
    print(f"{item.title} - {item.authors}")

# 创建条目
new_item = await item_service.create_item(
    item_data={
        "itemType": "journalArticle",
        "title": "Test Paper",
        "creators": [{"creatorType": "author", "name": "John Doe"}],
        "date": "2024"
    },
    collection_keys=["ABC123"]
)
```

### 混合搜索

```python
from zotero_core import HybridSearchService

search_service = HybridSearchService(
    library_id="user_123",
    api_key="your_api_key"
)

# 混合搜索
result = await search_service.search(
    query="neural network interpretability",
    search_mode="hybrid",
    top_k=10
)

print(f"Found {result.found} items")
for item in result.items:
    print(f"  - {item.title}")
```

### 重复检测

```python
from zotero_core import ItemService, DuplicateService

item_service = ItemService(...)
dup_service = DuplicateService(item_service)

# 查找重复
duplicates = await dup_service.find_duplicates()

for group in duplicates:
    print(f"Duplicate group: {len(group)} items")
    for item in group:
        print(f"  - {item.title} (DOI: {item.doi})")

# 合并重复
if duplicates:
    merged = await dup_service.merge_duplicates(
        duplicate_group=duplicates[0],
        delete_others=False  # 不删除,仅合并标签和集合
    )
    print(f"Merged into: {merged.title}")
```

## 依赖配置

```toml
[project]
name = "zotero-core"
version = "1.0.0"
description = "Zotero data access library"
dependencies = [
    "pyzotero>=1.8.0",
    "pydantic>=2.0.0",
    "httpx>=0.25.0",
    "click>=8.0.0",
]

[project.optional-dependencies]
semantic = [
    "chromadb>=0.4.0",  # For semantic search (optional)
]
all = ["zotero-core[semantic]"]

[project.scripts]
zotero-core = "zotero_core.cli:main"
```

## 实施计划(6周)

### Week 1: 核心模型 + 客户端
- [ ] 实现 Item, Collection, SearchQuery, SearchResult 模型
- [ ] 实现 ZoteroAPIClient (pyzotero 封装)
- [ ] 实现 CrossrefClient, OpenAlexClient
- [ ] 单元测试

### Week 2: CRUD 服务
- [ ] 实现 ItemService
- [ ] 实现 CollectionService
- [ ] 实现 TagService
- [ ] 集成测试

### Week 3: 搜索服务
- [ ] 实现 SearchService
- [ ] 实现 SmartQueryBuilder
- [ ] 测试搜索功能

### Week 4: 混合搜索
- [ ] 实现 HybridSearchService
- [ ] 实现 RRF 融合算法
- [ ] 测试混合搜索准确度

### Week 5: 高级功能
- [ ] 实现 MetadataService
- [ ] 实现 DuplicateService
- [ ] 测试元数据补全和重复检测

### Week 6: CLI + 文档
- [ ] 实现命令行接口
- [ ] 编写使用示例
- [ ] 编写 README 和 API 文档
- [ ] 性能优化和测试覆盖率 > 80%

---

**文档版本**: 1.0 (最终版)
**最后更新**: 2025-02-06
