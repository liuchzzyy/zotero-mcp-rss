# Zotero MCP 规范化实施计划

## 📋 执行概述

**目标**: 将 Zotero MCP 服务器规范化为符合 MCP 最佳实践的高质量实现

**实施策略**: 
- ✅ 选项 A: 使用 Pydantic 输入模型
- ✅ 返回结构化 Pydantic 输出模型
- ✅ 不保持向后兼容性（可进行破坏性更改）
- ✅ 无需增加测试

**预计工期**: 5 天

---

## 🎯 核心改动汇总

| 改动项 | 当前状态 | 目标状态 |
|--------|---------|---------|
| **工具签名** | 原始参数 (`query: str, limit: int, ...`) | Pydantic 输入模型 (`params: SearchItemsInput`) |
| **返回类型** | `str` (格式化 Markdown/JSON 文本) | 结构化 Pydantic 模型 (`SearchResponse`) |
| **Tool Annotations** | ❌ 无 | ✅ 完整的 `ToolAnnotations` |
| **参数命名** | ❌ 不一致 (`output_format` vs `response_format`) | ✅ 统一使用 `response_format` |
| **Docstrings** | ⚠️ 基础 | ✅ 完整的 Google-style docstrings |
| **分页元数据** | ⚠️ 不完整 | ✅ 包含 `has_more`, `next_offset` |
| **错误处理** | ⚠️ 返回字符串 | ✅ 结构化错误响应 (`success=False, error="..."`) |

---

## 📁 Phase 1: 模型层重构 (Day 1)

### 文件: `src/zotero_mcp/models/common.py`

**新增结构化输出模型:**

```python
"""
Common Pydantic models and enums used across all tools.
"""

from enum import Enum
from typing import Any, Literal

from pydantic import BaseModel, Field, ConfigDict


# ===== Enums =====

class ResponseFormat(str, Enum):
    """Output format for tool responses."""
    MARKDOWN = "markdown"
    JSON = "json"


class OutputFormat(str, Enum):
    """Output format for metadata export."""
    MARKDOWN = "markdown"
    BIBTEX = "bibtex"
    JSON = "json"


class SearchMode(str, Enum):
    """Search mode for keyword search."""
    TITLE_CREATOR_YEAR = "titleCreatorYear"
    EVERYTHING = "everything"


# ===== Base Classes =====

class BaseInput(BaseModel):
    """Base class for all tool input models."""
    model_config = ConfigDict(
        str_strip_whitespace=True,
        validate_assignment=True,
        extra="forbid",
    )

    response_format: ResponseFormat = Field(
        default=ResponseFormat.MARKDOWN,
        description="Output format: 'markdown' for human-readable or 'json' for machine-readable"
    )


class PaginatedInput(BaseInput):
    """Base class for paginated tool inputs."""
    
    limit: int = Field(
        default=20,
        ge=1,
        le=100,
        description="Maximum number of results to return (1-100)"
    )
    offset: int = Field(
        default=0,
        ge=0,
        description="Number of results to skip for pagination"
    )


# ===== Response Models =====

class BaseResponse(BaseModel):
    """Base class for all tool responses."""
    model_config = ConfigDict(extra="allow")
    
    success: bool = Field(default=True, description="Whether the operation succeeded")
    error: str | None = Field(default=None, description="Error message if operation failed")


class PaginatedResponse(BaseResponse):
    """Standard paginated response structure."""
    total: int = Field(..., description="Total number of matching items")
    count: int = Field(..., description="Number of items in this response")
    offset: int = Field(default=0, description="Current offset")
    limit: int = Field(..., description="Requested limit")
    has_more: bool = Field(..., description="Whether more results are available")
    next_offset: int | None = Field(default=None, description="Offset for next page")


# ===== Search Result Models =====

class SearchResultItem(BaseModel):
    """Single search result item."""
    model_config = ConfigDict(extra="allow")
    
    key: str = Field(..., description="Zotero item key")
    title: str = Field(default="Untitled", description="Item title")
    authors: str | None = Field(default=None, description="Formatted author names")
    date: str | None = Field(default=None, description="Publication date")
    item_type: str = Field(default="unknown", description="Item type")
    abstract: str | None = Field(default=None, description="Abstract text")
    doi: str | None = Field(default=None, description="DOI if available")
    url: str | None = Field(default=None, description="URL if available")
    tags: list[str] = Field(default_factory=list, description="List of tags")
    similarity_score: float | None = Field(
        default=None,
        description="Similarity score for semantic search (0-1)"
    )


class SearchResponse(PaginatedResponse):
    """Response for search operations."""
    query: str = Field(..., description="Search query that was executed")
    items: list[SearchResultItem] = Field(default_factory=list, description="Search results")


# ===== Item Detail Models =====

class ItemDetailResponse(BaseResponse):
    """Response for single item details."""
    key: str = Field(..., description="Zotero item key")
    title: str = Field(default="Untitled", description="Item title")
    item_type: str = Field(default="unknown", description="Item type")
    authors: str | None = Field(default=None, description="Formatted author names")
    date: str | None = Field(default=None, description="Publication date")
    publication: str | None = Field(default=None, description="Publication title")
    doi: str | None = Field(default=None, description="DOI")
    url: str | None = Field(default=None, description="URL")
    abstract: str | None = Field(default=None, description="Abstract text")
    tags: list[str] = Field(default_factory=list, description="List of tags")
    raw_data: dict[str, Any] | None = Field(default=None, description="Raw Zotero item data")


class FulltextResponse(BaseResponse):
    """Response for fulltext retrieval."""
    item_key: str = Field(..., description="Item key")
    fulltext: str | None = Field(default=None, description="Full text content")
    length: int = Field(default=0, description="Character count")
    truncated: bool = Field(default=False, description="Whether content was truncated")


# ===== Annotation Models =====

class AnnotationItem(BaseModel):
    """Single annotation."""
    type: str = Field(..., description="Annotation type: highlight, note, underline")
    text: str | None = Field(default=None, description="Highlighted text")
    comment: str | None = Field(default=None, description="User comment")
    page: str | None = Field(default=None, description="Page number or label")
    color: str | None = Field(default=None, description="Highlight color")


class AnnotationsResponse(BaseResponse):
    """Response for annotations."""
    item_key: str = Field(..., description="Parent item key")
    count: int = Field(..., description="Number of annotations")
    annotations: list[AnnotationItem] = Field(default_factory=list, description="List of annotations")


class NotesResponse(BaseResponse):
    """Response for notes."""
    item_key: str = Field(..., description="Parent item key")
    count: int = Field(..., description="Number of notes")
    notes: list[dict[str, Any]] = Field(default_factory=list, description="List of notes")


# ===== Collection Models =====

class CollectionItem(BaseModel):
    """Single collection."""
    key: str = Field(..., description="Collection key")
    name: str = Field(..., description="Collection name")
    item_count: int | None = Field(default=None, description="Number of items in collection")
    parent_key: str | None = Field(default=None, description="Parent collection key")


class CollectionsResponse(BaseResponse):
    """Response for collections list."""
    count: int = Field(..., description="Number of collections")
    collections: list[CollectionItem] = Field(default_factory=list, description="List of collections")


# ===== Bundle Models =====

class BundleResponse(BaseResponse):
    """Comprehensive item bundle."""
    metadata: ItemDetailResponse = Field(..., description="Item metadata")
    attachments: list[dict[str, Any]] = Field(default_factory=list, description="Attachments")
    notes: list[dict[str, Any]] = Field(default_factory=list, description="Notes")
    annotations: list[AnnotationItem] = Field(default_factory=list, description="PDF annotations")
    fulltext: str | None = Field(default=None, description="Full text content")
    bibtex: str | None = Field(default=None, description="BibTeX citation")


# ===== Database Models =====

class DatabaseStatusResponse(BaseResponse):
    """Semantic search database status."""
    exists: bool = Field(..., description="Whether database exists")
    item_count: int = Field(default=0, description="Number of indexed items")
    last_updated: str | None = Field(default=None, description="Last update timestamp")
    embedding_model: str = Field(default="default", description="Embedding model used")
    model_name: str | None = Field(default=None, description="Specific model name")
    fulltext_enabled: bool = Field(default=False, description="Whether full-text indexing is enabled")
    auto_update: bool = Field(default=False, description="Whether auto-update is enabled")
    update_frequency: str = Field(default="manual", description="Update frequency setting")


class DatabaseUpdateResponse(BaseResponse):
    """Response for database update operation."""
    items_processed: int = Field(default=0, description="Number of items processed")
    items_added: int = Field(default=0, description="Number of items added")
    items_updated: int = Field(default=0, description="Number of items updated")
    duration_seconds: float = Field(default=0, description="Operation duration in seconds")
    force_rebuild: bool = Field(default=False, description="Whether database was rebuilt")
    fulltext_included: bool = Field(default=False, description="Whether full-text was indexed")


# ===== Note Creation Models =====

class NoteCreationResponse(BaseResponse):
    """Response for note creation."""
    note_key: str | None = Field(default=None, description="Created note key")
    parent_key: str = Field(..., description="Parent item key")
    message: str = Field(..., description="Status message")
```

### 文件: `src/zotero_mcp/models/search.py`

**确保所有输入模型正确定义:**

```python
"""
Pydantic models for search-related tools.
"""

from typing import Literal

from pydantic import Field, field_validator

from .common import BaseInput, PaginatedInput, ResponseFormat, SearchMode


class SearchItemsInput(PaginatedInput):
    """Input for zotero_search tool."""

    query: str = Field(
        ...,
        min_length=1,
        max_length=500,
        description="Search query string (e.g., 'machine learning', 'Smith 2023')"
    )
    search_mode: SearchMode = Field(
        default=SearchMode.TITLE_CREATOR_YEAR,
        description="Search mode: 'titleCreatorYear' searches title/author/year, 'everything' searches all fields"
    )

    @field_validator("query")
    @classmethod
    def validate_query(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("Query cannot be empty or whitespace only")
        return v.strip()


class TagSearchInput(PaginatedInput):
    """Input for zotero_search_by_tag tool."""

    tags: str = Field(
        ...,
        min_length=1,
        description="Comma-separated list of required tags (AND logic)"
    )
    exclude_tags: str = Field(
        default="",
        description="Comma-separated list of tags to exclude"
    )


class AdvancedSearchInput(PaginatedInput):
    """Input for zotero_advanced_search tool."""

    title: str = Field(default="", description="Title contains (partial match)")
    author: str = Field(default="", description="Author name contains")
    year_from: int | None = Field(default=None, ge=1000, le=9999, description="Published from year")
    year_to: int | None = Field(default=None, ge=1000, le=9999, description="Published to year")
    item_type: str = Field(default="", description="Filter by type (journalArticle, book, etc.)")
    tags: str = Field(default="", description="Comma-separated required tags")


class SemanticSearchInput(PaginatedInput):
    """Input for zotero_semantic_search tool."""

    query: str = Field(
        ...,
        min_length=2,
        max_length=1000,
        description=(
            "Natural language search query describing concepts or topics. "
            "Can be a phrase, question, or abstract snippet."
        )
    )

    @field_validator("query")
    @classmethod
    def validate_query(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("Query cannot be empty or whitespace only")
        return v.strip()


class RecentItemsInput(PaginatedInput):
    """Input for zotero_get_recent tool."""

    days: int = Field(
        default=30,
        ge=1,
        le=365,
        description="Look back this many days (1-365)"
    )
```

### 文件: `src/zotero_mcp/models/items.py`

**统一参数命名为 `response_format`:**

```python
"""
Pydantic models for item-related tools.
"""

from typing import Literal

from pydantic import Field

from .common import BaseInput, PaginatedInput, OutputFormat


class GetMetadataInput(BaseInput):
    """Input for zotero_get_metadata tool."""

    item_key: str = Field(
        ...,
        min_length=1,
        max_length=20,
        description="Zotero item key/ID (8-character alphanumeric string)"
    )
    include_abstract: bool = Field(
        default=True,
        description="Whether to include the abstract in the output"
    )
    # CHANGED: output_format → response_format for consistency
    # But we keep a separate "format" for BibTeX/Markdown/JSON distinction
    format: OutputFormat = Field(
        default=OutputFormat.MARKDOWN,
        description="Export format: 'markdown', 'bibtex', or 'json'"
    )


class GetFulltextInput(BaseInput):
    """Input for zotero_get_fulltext tool."""

    item_key: str = Field(
        ...,
        min_length=1,
        max_length=20,
        description="Zotero item key/ID"
    )
    max_length: int = Field(
        default=10000,
        ge=100,
        le=100000,
        description="Maximum characters to return"
    )


class GetChildrenInput(BaseInput):
    """Input for zotero_get_children tool."""

    item_key: str = Field(
        ...,
        min_length=1,
        max_length=20,
        description="Zotero item key/ID"
    )
    item_type: Literal["all", "attachment", "note"] = Field(
        default="all",
        description="Filter children by type"
    )


class GetCollectionsInput(BaseInput):
    """Input for zotero_get_collections tool."""

    collection_key: str = Field(
        default="",
        description="If provided, get items in this collection. Otherwise list all collections."
    )
    limit: int = Field(
        default=50,
        ge=1,
        le=100,
        description="Maximum items when retrieving collection contents"
    )


class GetBundleInput(BaseInput):
    """Input for zotero_get_bundle tool."""

    item_key: str = Field(
        ...,
        min_length=1,
        max_length=20,
        description="Zotero item key/ID"
    )
    include_fulltext: bool = Field(
        default=False,
        description="Include full-text content"
    )
    include_annotations: bool = Field(
        default=True,
        description="Include PDF annotations"
    )
    include_notes: bool = Field(
        default=True,
        description="Include notes"
    )
    include_bibtex: bool = Field(
        default=False,
        description="Include BibTeX citation"
    )
```

### 文件: `src/zotero_mcp/models/annotations.py`

```python
"""
Pydantic models for annotation-related tools.
"""

from typing import Literal

from pydantic import Field

from .common import BaseInput


class GetAnnotationsInput(BaseInput):
    """Input for zotero_get_annotations tool."""

    item_key: str = Field(
        ...,
        min_length=1,
        max_length=20,
        description="Zotero item key/ID"
    )
    annotation_type: Literal["all", "highlight", "note", "underline"] = Field(
        default="all",
        description="Filter by annotation type"
    )


class GetNotesInput(BaseInput):
    """Input for zotero_get_notes tool."""

    item_key: str = Field(
        ...,
        min_length=1,
        max_length=20,
        description="Zotero item key/ID"
    )


class SearchNotesInput(BaseInput):
    """Input for zotero_search_notes tool."""

    query: str = Field(
        ...,
        min_length=1,
        max_length=500,
        description="Search query for notes and annotations"
    )
    limit: int = Field(
        default=20,
        ge=1,
        le=100,
        description="Maximum results to return"
    )


class CreateNoteInput(BaseInput):
    """Input for zotero_create_note tool."""

    item_key: str = Field(
        ...,
        min_length=1,
        max_length=20,
        description="Parent item key"
    )
    content: str = Field(
        ...,
        min_length=1,
        description="Note content (plain text, will be converted to HTML)"
    )
    tags: str = Field(
        default="",
        description="Comma-separated tags for the note"
    )
```

### 文件: `src/zotero_mcp/models/database.py`

```python
"""
Pydantic models for database-related tools.
"""

from pydantic import Field

from .common import BaseInput


class UpdateDatabaseInput(BaseInput):
    """Input for zotero_update_database tool."""

    force_rebuild: bool = Field(
        default=False,
        description="Force complete rebuild (slower but fixes issues)"
    )
    include_fulltext: bool = Field(
        default=False,
        description="Include full-text from PDFs (slower but more comprehensive)"
    )
    limit: int | None = Field(
        default=None,
        ge=1,
        description="Limit number of items to process (useful for testing)"
    )


class DatabaseStatusInput(BaseInput):
    """Input for zotero_database_status tool."""
    # Inherits response_format from BaseInput
    pass
```

---

## 📁 Phase 2: 工具层 - Search Tools (Day 2)

### 文件: `src/zotero_mcp/tools/search.py`

**完整重构示例 (所有 5 个工具):**

```python
"""
Search tools for Zotero MCP.

Provides tools for searching the Zotero library:
- zotero_search: Basic keyword search
- zotero_search_by_tag: Tag-based search with include/exclude
- zotero_advanced_search: Multi-field search
- zotero_semantic_search: AI-powered semantic search
- zotero_get_recent: Recently added items
"""

from fastmcp import FastMCP, Context
from mcp.server.fastmcp import ToolAnnotations

from zotero_mcp.models.common import SearchResponse, SearchResultItem
from zotero_mcp.models.search import (
    SearchItemsInput,
    TagSearchInput,
    AdvancedSearchInput,
    SemanticSearchInput,
    RecentItemsInput,
)
from zotero_mcp.services import get_data_service


def register_search_tools(mcp: FastMCP) -> None:
    """Register all search tools with the MCP server."""

    @mcp.tool(
        name="zotero_search",
        annotations=ToolAnnotations(
            title="Search Zotero Library",
            readOnlyHint=True,
            destructiveHint=False,
            idempotentHint=True,
            openWorldHint=False,
        ),
    )
    async def zotero_search(params: SearchItemsInput, ctx: Context) -> SearchResponse:
        """
        Search for items in your Zotero library by keywords.
        
        Searches across titles, authors, and years by default. Use 'everything' 
        search mode for full-text search including abstracts and notes.
        
        Args:
            params: Validated search parameters containing:
                - query (str): Search keywords (e.g., 'machine learning', 'Smith 2023')
                - limit (int): Maximum results to return (1-100, default: 20)
                - offset (int): Pagination offset (default: 0)
                - search_mode: 'titleCreatorYear' (fast) or 'everything' (comprehensive)
                - response_format: 'markdown' or 'json' (legacy, returns structured data)
        
        Returns:
            SearchResponse: Structured search results with:
                - query: The search query executed
                - total: Total matching items
                - count: Items in this response
                - offset, limit: Pagination parameters
                - has_more: Whether more results are available
                - next_offset: Offset for next page (if has_more)
                - items: List of SearchResultItem objects
        
        Example:
            Use when: "Find papers about machine learning"
            Use when: "Search for Smith's 2023 publications"
            Use when: "What do I have on quantum computing?"
        """
        try:
            service = get_data_service()
            results = await service.search_items(
                query=params.query,
                limit=params.limit,
                offset=params.offset,
                qmode=params.search_mode.value,
            )

            items = [
                SearchResultItem(
                    key=r.key,
                    title=r.title,
                    authors=r.authors,
                    date=r.date,
                    item_type=r.item_type,
                    abstract=r.abstract,
                    doi=r.doi,
                    tags=r.tags or [],
                )
                for r in results
            ]

            return SearchResponse(
                query=params.query,
                total=len(results),  # Note: Actual total may come from API
                count=len(items),
                offset=params.offset,
                limit=params.limit,
                has_more=len(items) == params.limit,
                next_offset=params.offset + len(items) if len(items) == params.limit else None,
                items=items,
            )

        except Exception as e:
            await ctx.error(f"Search failed: {str(e)}")
            return SearchResponse(
                success=False,
                error=f"Search error: {str(e)}",
                query=params.query,
                total=0,
                count=0,
                offset=params.offset,
                limit=params.limit,
                has_more=False,
                items=[],
            )

    @mcp.tool(
        name="zotero_search_by_tag",
        annotations=ToolAnnotations(
            title="Search by Tags",
            readOnlyHint=True,
            destructiveHint=False,
            idempotentHint=True,
            openWorldHint=False,
        ),
    )
    async def zotero_search_by_tag(params: TagSearchInput, ctx: Context) -> SearchResponse:
        """
        Search items by tags with include/exclude logic.
        
        Args:
            params: Validated input containing:
                - tags (str): Comma-separated required tags (AND logic)
                - exclude_tags (str): Comma-separated tags to exclude
                - limit, offset: Pagination
        
        Returns:
            SearchResponse: Matching items with specified tags.
        
        Example:
            Use when: "Show me papers tagged 'machine learning'"
            Use when: "Find items with tag 'research' but not 'draft'"
        """
        try:
            # Parse tags
            include_tags = [t.strip() for t in params.tags.split(",") if t.strip()]
            exclude_list = (
                [t.strip() for t in params.exclude_tags.split(",") if t.strip()]
                if params.exclude_tags
                else None
            )

            if not include_tags:
                return SearchResponse(
                    success=False,
                    error="Please provide at least one tag to search for",
                    query=f"tags={params.tags}",
                    total=0,
                    count=0,
                    offset=0,
                    limit=params.limit,
                    has_more=False,
                    items=[],
                )

            service = get_data_service()
            results = await service.search_by_tag(
                tags=include_tags,
                exclude_tags=exclude_list,
                limit=params.limit,
            )

            items = [
                SearchResultItem(
                    key=r.key,
                    title=r.title,
                    authors=r.authors,
                    date=r.date,
                    item_type=r.item_type,
                    tags=r.tags or [],
                )
                for r in results
            ]

            tag_query = f"tags={params.tags}" + (
                f", exclude={params.exclude_tags}" if params.exclude_tags else ""
            )

            return SearchResponse(
                query=tag_query,
                total=len(items),
                count=len(items),
                offset=0,
                limit=params.limit,
                has_more=False,
                items=items,
            )

        except Exception as e:
            await ctx.error(f"Tag search failed: {str(e)}")
            return SearchResponse(
                success=False,
                error=f"Tag search error: {str(e)}",
                query=f"tags={params.tags}",
                total=0,
                count=0,
                offset=0,
                limit=params.limit,
                has_more=False,
                items=[],
            )

    @mcp.tool(
        name="zotero_advanced_search",
        annotations=ToolAnnotations(
            title="Advanced Multi-Field Search",
            readOnlyHint=True,
            destructiveHint=False,
            idempotentHint=True,
            openWorldHint=False,
        ),
    )
    async def zotero_advanced_search(params: AdvancedSearchInput, ctx: Context) -> SearchResponse:
        """
        Advanced search with multiple criteria: title, author, year range, item type, tags.
        
        Args:
            params: Advanced search parameters with multiple filters.
        
        Returns:
            SearchResponse: Items matching all specified criteria.
        
        Example:
            Use when: "Find journal articles by Smith from 2020-2023"
            Use when: "Search for books about AI published after 2018"
        """
        try:
            # Build query from criteria
            query_parts = []
            if params.title:
                query_parts.append(params.title)
            if params.author:
                query_parts.append(params.author)

            query = " ".join(query_parts) if query_parts else "*"

            service = get_data_service()

            # Get initial results
            results = await service.search_items(
                query=query,
                limit=100,  # Get more for filtering
                qmode="everything",
            )

            # Apply filters
            filtered = []
            for r in results:
                # Year filter
                if params.year_from or params.year_to:
                    if r.date:
                        try:
                            year = int(r.date[:4])
                            if params.year_from and year < params.year_from:
                                continue
                            if params.year_to and year > params.year_to:
                                continue
                        except (ValueError, IndexError):
                            continue
                    else:
                        continue

                # Item type filter
                if params.item_type and r.item_type != params.item_type:
                    continue

                # Tag filter
                if params.tags:
                    required_tags = [t.strip() for t in params.tags.split(",") if t.strip()]
                    item_tags = r.tags or []
                    if not all(t in item_tags for t in required_tags):
                        continue

                filtered.append(r)
                if len(filtered) >= params.limit:
                    break

            items = [
                SearchResultItem(
                    key=r.key,
                    title=r.title,
                    authors=r.authors,
                    date=r.date,
                    item_type=r.item_type,
                    abstract=r.abstract,
                    tags=r.tags or [],
                )
                for r in filtered
            ]

            # Build query description
            criteria = []
            if params.title:
                criteria.append(f"title='{params.title}'")
            if params.author:
                criteria.append(f"author='{params.author}'")
            if params.year_from:
                criteria.append(f"from={params.year_from}")
            if params.year_to:
                criteria.append(f"to={params.year_to}")
            if params.item_type:
                criteria.append(f"type={params.item_type}")
            if params.tags:
                criteria.append(f"tags={params.tags}")

            query_desc = ", ".join(criteria) if criteria else "all items"

            return SearchResponse(
                query=query_desc,
                total=len(filtered),
                count=len(items),
                offset=0,
                limit=params.limit,
                has_more=len(filtered) > params.limit,
                next_offset=params.limit if len(filtered) > params.limit else None,
                items=items,
            )

        except Exception as e:
            await ctx.error(f"Advanced search failed: {str(e)}")
            return SearchResponse(
                success=False,
                error=f"Advanced search error: {str(e)}",
                query="advanced search",
                total=0,
                count=0,
                offset=0,
                limit=params.limit,
                has_more=False,
                items=[],
            )

    @mcp.tool(
        name="zotero_semantic_search",
        annotations=ToolAnnotations(
            title="AI Semantic Search",
            readOnlyHint=True,
            destructiveHint=False,
            idempotentHint=True,
            openWorldHint=False,
        ),
    )
    async def zotero_semantic_search(params: SemanticSearchInput, ctx: Context) -> SearchResponse:
        """
        AI-powered semantic search using embeddings.
        
        Finds conceptually similar items using vector similarity rather than
        keyword matching. Great for finding papers related to a topic or
        similar to an abstract.
        
        Args:
            params: Semantic search parameters with natural language query.
        
        Returns:
            SearchResponse: Items ranked by semantic similarity with scores.
        
        Example:
            Use when: "Find papers conceptually similar to deep learning"
            Use when: "What do I have related to climate change impacts?"
            Use when: "Papers similar to this abstract: [paste abstract]"
        
        Note:
            Requires semantic search database to be initialized with
            'zotero-mcp update-db' command.
        """
        try:
            # Import semantic search module
            from zotero_mcp.services.semantic import semantic_search

            results = await semantic_search(
                query=params.query,
                limit=params.limit,
            )

            if not results:
                return SearchResponse(
                    success=False,
                    error="No results found. Make sure the semantic search database is initialized with 'zotero-mcp update-db'.",
                    query=params.query,
                    total=0,
                    count=0,
                    offset=0,
                    limit=params.limit,
                    has_more=False,
                    items=[],
                )

            items = [
                SearchResultItem(
                    key=r.get("key", ""),
                    title=r.get("title", "Untitled"),
                    authors=r.get("authors"),
                    date=r.get("date"),
                    item_type=r.get("item_type", "unknown"),
                    abstract=r.get("abstract"),
                    doi=r.get("doi"),
                    tags=r.get("tags", []),
                    similarity_score=r.get("similarity_score"),
                )
                for r in results
            ]

            return SearchResponse(
                query=f"semantic: {params.query}",
                total=len(items),
                count=len(items),
                offset=0,
                limit=params.limit,
                has_more=False,
                items=items,
            )

        except ImportError:
            return SearchResponse(
                success=False,
                error="Semantic search is not available. Run 'zotero-mcp update-db' to initialize.",
                query=params.query,
                total=0,
                count=0,
                offset=0,
                limit=params.limit,
                has_more=False,
                items=[],
            )
        except Exception as e:
            await ctx.error(f"Semantic search failed: {str(e)}")
            return SearchResponse(
                success=False,
                error=f"Semantic search error: {str(e)}",
                query=params.query,
                total=0,
                count=0,
                offset=0,
                limit=params.limit,
                has_more=False,
                items=[],
            )

    @mcp.tool(
        name="zotero_get_recent",
        annotations=ToolAnnotations(
            title="Get Recently Added Items",
            readOnlyHint=True,
            destructiveHint=False,
            idempotentHint=True,
            openWorldHint=False,
        ),
    )
    async def zotero_get_recent(params: RecentItemsInput, ctx: Context) -> SearchResponse:
        """
        Get recently added items from your Zotero library.
        
        Args:
            params: Parameters with days lookback and pagination.
        
        Returns:
            SearchResponse: Items added within the specified timeframe.
        
        Example:
            Use when: "What papers did I add recently?"
            Use when: "Show me items added in the last week"
        """
        try:
            service = get_data_service()
            results = await service.get_recent_items(
                limit=params.limit,
                days=params.days,
            )

            items = [
                SearchResultItem(
                    key=r.key,
                    title=r.title,
                    authors=r.authors,
                    date=r.date,
                    item_type=r.item_type,
                    tags=r.tags or [],
                )
                for r in results
            ]

            return SearchResponse(
                query=f"recent (last {params.days} days)",
                total=len(items),
                count=len(items),
                offset=0,
                limit=params.limit,
                has_more=False,
                items=items,
            )

        except Exception as e:
            await ctx.error(f"Failed to get recent items: {str(e)}")
            return SearchResponse(
                success=False,
                error=f"Error retrieving recent items: {str(e)}",
                query=f"recent ({params.days} days)",
                total=0,
                count=0,
                offset=0,
                limit=params.limit,
                has_more=False,
                items=[],
            )
```

---

## 📁 Phase 3: 工具层 - Item Tools (Day 3)

### 文件: `src/zotero_mcp/tools/items.py`

**核心改动:**
1. 所有工具使用 Pydantic 输入模型
2. 返回结构化 Pydantic 输出
3. 添加 ToolAnnotations
4. 完整的 docstrings

**工具清单:**
- `zotero_get_metadata` → 返回 `ItemDetailResponse`
- `zotero_get_fulltext` → 返回 `FulltextResponse`
- `zotero_get_children` → 返回自定义 `ChildrenResponse`
- `zotero_get_collections` → 返回 `CollectionsResponse`
- `zotero_get_bundle` → 返回 `BundleResponse`

**模板 (示例 - zotero_get_metadata):**

```python
@mcp.tool(
    name="zotero_get_metadata",
    annotations=ToolAnnotations(
        title="Get Item Metadata",
        readOnlyHint=True,
        destructiveHint=False,
        idempotentHint=True,
        openWorldHint=False,
    ),
)
async def zotero_get_metadata(params: GetMetadataInput, ctx: Context) -> ItemDetailResponse:
    """
    Get detailed metadata for a Zotero item.
    
    Retrieves comprehensive bibliographic information including title, authors,
    publication details, DOI, abstract, and tags.
    
    Args:
        params: Input parameters containing:
            - item_key (str): Zotero item key (8-character alphanumeric)
            - include_abstract (bool): Whether to include abstract (default: True)
            - format: Export format - 'markdown', 'bibtex', or 'json'
            - response_format: Legacy parameter (use structured output instead)
    
    Returns:
        ItemDetailResponse: Structured item metadata.
        
        For BibTeX format, returns special response with bibtex field populated.
    
    Example:
        Use when: "Get details for item ABC12345"
        Use when: "Show me metadata for this paper"
    """
    try:
        service = get_data_service()
        item = await service.get_item(params.item_key.strip().upper())
        
        # Special handling for BibTeX format
        if params.format == OutputFormat.BIBTEX:
            bibtex = await service.get_bibtex(params.item_key)
            if not bibtex:
                return ItemDetailResponse(
                    success=False,
                    error="Could not generate BibTeX for this item",
                    key=params.item_key,
                    title="Error",
                    item_type="unknown",
                )
            # Return as special response
            return ItemDetailResponse(
                key=params.item_key,
                title="BibTeX Citation",
                item_type="citation",
                raw_data={"bibtex": bibtex},
            )
        
        # Extract metadata
        data = item.get("data", {})
        tags = [t.get("tag", "") for t in data.get("tags", []) if t.get("tag")]
        
        return ItemDetailResponse(
            key=data.get("key", params.item_key),
            title=data.get("title", "Untitled"),
            item_type=data.get("itemType", "unknown"),
            authors=format_creators(data.get("creators", [])),
            date=data.get("date"),
            publication=data.get("publicationTitle") or data.get("journalAbbreviation"),
            doi=data.get("DOI"),
            url=data.get("url"),
            abstract=data.get("abstractNote") if params.include_abstract else None,
            tags=tags,
            raw_data=item if params.format == OutputFormat.JSON else None,
        )
        
    except Exception as e:
        await ctx.error(f"Failed to get metadata: {str(e)}")
        return ItemDetailResponse(
            success=False,
            error=f"Metadata retrieval error: {str(e)}",
            key=params.item_key,
            title="Error",
            item_type="unknown",
        )
```

---

## 📁 Phase 4: 工具层 - Annotations & Database (Day 4)

### 文件: `src/zotero_mcp/tools/annotations.py`

**工具清单:**
- `zotero_get_annotations` → 返回 `AnnotationsResponse`
- `zotero_get_notes` → 返回 `NotesResponse`
- `zotero_search_notes` → 返回 `SearchResponse` (复用)
- `zotero_create_note` → 返回 `NoteCreationResponse`

**特殊注意:**
- `zotero_create_note`: `readOnlyHint=False`, `destructiveHint=False`, `idempotentHint=False`

### 文件: `src/zotero_mcp/tools/database.py`

**工具清单:**
- `zotero_update_database` → 返回 `DatabaseUpdateResponse`
- `zotero_database_status` → 返回 `DatabaseStatusResponse`

**特殊注意:**
- `zotero_update_database`: `readOnlyHint=False`, `destructiveHint=False`, `idempotentHint=False`

---

## 📁 Phase 5: 清理和验证 (Day 5)

### 5.1 删除未使用的代码

**文件检查清单:**
- ❌ 删除: 工具内手动构建的 Markdown 字符串（现在由 Pydantic 模型处理）
- ❌ 删除: `tools/` 中未使用的 Formatter 导入
- ✅ 保留: Formatter 类（用于遗留系统或特殊格式需求）

### 5.2 更新 `handle_error` 工具

**文件: `src/zotero_mcp/utils/errors.py`**

当前 `handle_error` 返回字符串。考虑是否需要更新为返回结构化错误对象。

**建议**: 保持当前实现，因为工具内部已经使用 `success=False, error="..."` 模式。

### 5.3 验证清单

执行以下检查:

```bash
# 1. 检查所有工具都有 ToolAnnotations
grep -r "@mcp.tool" src/zotero_mcp/tools/ | wc -l  # 应该是 16

# 2. 检查所有工具使用 Pydantic 输入
grep -r "async def zotero_" src/zotero_mcp/tools/ | grep -v "params:" | wc -l  # 应该是 0

# 3. 检查所有工具返回 Pydantic 输出
grep -r "-> str:" src/zotero_mcp/tools/ | wc -l  # 应该是 0

# 4. 运行 LSP 诊断
# (手动检查类型错误)

# 5. 测试基本功能
# zotero-mcp serve
# 使用 MCP Inspector 测试工具调用
```

### 5.4 文档更新

**文件: `README.md`**

更新示例输出展示结构化响应:

```markdown
## Example Tool Response

```json
{
  "success": true,
  "query": "machine learning",
  "total": 42,
  "count": 20,
  "offset": 0,
  "limit": 20,
  "has_more": true,
  "next_offset": 20,
  "items": [
    {
      "key": "ABC12345",
      "title": "Deep Learning for Computer Vision",
      "authors": "Smith, J.; Doe, A.",
      "date": "2023",
      "item_type": "journalArticle",
      "doi": "10.1234/example",
      "tags": ["machine-learning", "computer-vision"]
    },
    ...
  ]
}
```
```

**文件: `AGENTS.md`**

更新工具使用示例:

```markdown
### Using Tools

All tools now return structured Pydantic models:

```python
from zotero_mcp.models.search import SearchItemsInput
from zotero_mcp.models.common import SearchResponse

# Input validation
params = SearchItemsInput(
    query="machine learning",
    limit=10,
    search_mode="everything"
)

# Structured output
response: SearchResponse = await zotero_search(params, ctx)
for item in response.items:
    print(f"{item.title} by {item.authors}")
```
```

---

## 🔍 验证检查表

完成后，确保所有项都打勾:

### 模型层
- [ ] `models/common.py` 包含所有输出模型
- [ ] `models/search.py` 所有输入模型正确定义
- [ ] `models/items.py` 参数统一为 `response_format`
- [ ] `models/annotations.py` 完整定义
- [ ] `models/database.py` 完整定义

### 工具层 - Search
- [ ] `zotero_search` 使用 `SearchItemsInput` 和 `SearchResponse`
- [ ] `zotero_search_by_tag` 使用 `TagSearchInput` 和 `SearchResponse`
- [ ] `zotero_advanced_search` 使用 `AdvancedSearchInput` 和 `SearchResponse`
- [ ] `zotero_semantic_search` 使用 `SemanticSearchInput` 和 `SearchResponse`
- [ ] `zotero_get_recent` 使用 `RecentItemsInput` 和 `SearchResponse`
- [ ] 所有 5 个工具都有 `ToolAnnotations`

### 工具层 - Items
- [ ] `zotero_get_metadata` 返回 `ItemDetailResponse`
- [ ] `zotero_get_fulltext` 返回 `FulltextResponse`
- [ ] `zotero_get_children` 返回结构化响应
- [ ] `zotero_get_collections` 返回 `CollectionsResponse`
- [ ] `zotero_get_bundle` 返回 `BundleResponse`
- [ ] 所有 5 个工具都有 `ToolAnnotations`

### 工具层 - Annotations
- [ ] `zotero_get_annotations` 返回 `AnnotationsResponse`
- [ ] `zotero_get_notes` 返回 `NotesResponse`
- [ ] `zotero_search_notes` 返回 `SearchResponse`
- [ ] `zotero_create_note` 返回 `NoteCreationResponse`
- [ ] 所有 4 个工具都有 `ToolAnnotations`

### 工具层 - Database
- [ ] `zotero_update_database` 返回 `DatabaseUpdateResponse`
- [ ] `zotero_database_status` 返回 `DatabaseStatusResponse`
- [ ] 所有 2 个工具都有 `ToolAnnotations`

### Docstrings
- [ ] 所有 16 个工具都有完整的 Google-style docstrings
- [ ] 所有 docstrings 包含 Args, Returns, Example 部分
- [ ] 所有输入参数都有清晰的类型说明

### 一致性
- [ ] 参数命名 100% 一致（统一使用 `response_format`）
- [ ] 分页响应都包含 `has_more`, `next_offset`
- [ ] 错误响应都使用 `success=False` + `error` 字段
- [ ] Tool Annotations 正确反映工具行为

### 清理
- [ ] 删除工具内手动构建的 Markdown 代码
- [ ] 删除未使用的导入
- [ ] LSP 诊断无错误

---

## 📊 工具注解参考表

| 工具名 | readOnlyHint | destructiveHint | idempotentHint | openWorldHint |
|--------|--------------|-----------------|----------------|---------------|
| `zotero_search` | ✅ True | ❌ False | ✅ True | ❌ False |
| `zotero_search_by_tag` | ✅ True | ❌ False | ✅ True | ❌ False |
| `zotero_advanced_search` | ✅ True | ❌ False | ✅ True | ❌ False |
| `zotero_semantic_search` | ✅ True | ❌ False | ✅ True | ❌ False |
| `zotero_get_recent` | ✅ True | ❌ False | ✅ True | ❌ False |
| `zotero_get_metadata` | ✅ True | ❌ False | ✅ True | ❌ False |
| `zotero_get_fulltext` | ✅ True | ❌ False | ✅ True | ❌ False |
| `zotero_get_children` | ✅ True | ❌ False | ✅ True | ❌ False |
| `zotero_get_collections` | ✅ True | ❌ False | ✅ True | ❌ False |
| `zotero_get_bundle` | ✅ True | ❌ False | ✅ True | ❌ False |
| `zotero_get_annotations` | ✅ True | ❌ False | ✅ True | ❌ False |
| `zotero_get_notes` | ✅ True | ❌ False | ✅ True | ❌ False |
| `zotero_search_notes` | ✅ True | ❌ False | ✅ True | ❌ False |
| `zotero_create_note` | ❌ False | ❌ False | ❌ False | ❌ False |
| `zotero_update_database` | ❌ False | ❌ False | ❌ False | ❌ False |
| `zotero_database_status` | ✅ True | ❌ False | ✅ True | ❌ False |

---

## 🎓 MCP 最佳实践遵循

本计划确保遵循以下 MCP 最佳实践:

### ✅ 服务器命名
- **格式**: `{service}_mcp` (Python)
- **实际**: `zotero_mcp` ✅

### ✅ 工具命名
- **格式**: `{service}_{action}_{resource}`
- **示例**: `zotero_search_items`, `zotero_get_metadata` ✅

### ✅ 输入验证
- **使用 Pydantic**: 所有输入模型继承自 `BaseModel`
- **Field 约束**: `min_length`, `max_length`, `ge`, `le`
- **自定义验证器**: `@field_validator`

### ✅ 结构化输出
- **Pydantic 模型**: 所有工具返回 Pydantic 模型
- **一致的 schema**: FastMCP 自动生成 JSON Schema
- **类型安全**: 完整的类型注解

### ✅ Tool Annotations
- **readOnlyHint**: 标记只读操作
- **destructiveHint**: 标记删除/覆盖操作
- **idempotentHint**: 标记幂等操作
- **openWorldHint**: 标记与外部世界交互

### ✅ 错误处理
- **统一模式**: `success=False` + `error` 字段
- **用户友好**: 清晰的错误消息
- **可操作**: 提供解决建议

### ✅ 分页
- **完整元数据**: `total`, `count`, `offset`, `limit`
- **导航信息**: `has_more`, `next_offset`
- **一致性**: 所有分页工具使用相同模式

### ✅ 文档
- **Google-style docstrings**: 完整的 Args, Returns, Example
- **类型信息**: 明确的输入输出类型
- **使用示例**: "Use when" 指导

---

## 📝 实施注意事项

### 破坏性更改
以下更改会破坏现有客户端:
1. **工具签名**: 从多个参数改为单个 `params` 对象
2. **返回类型**: 从 `str` 改为 Pydantic 模型
3. **参数名**: `output_format` → `response_format`

### 向后兼容建议
如果需要保持兼容:
1. **保留旧工具**: 创建 `_legacy` 版本
2. **别名**: 使用 FastMCP 的工具别名功能
3. **版本控制**: 在工具名中添加版本号 (`v2`)

### 性能考虑
1. **Pydantic 验证**: 有轻微性能开销，但可接受
2. **结构化输出**: JSON 序列化比字符串拼接稍慢
3. **总体影响**: 对于 I/O 密集型操作（API 调用）影响可忽略

---

## 🚀 执行指令

**当计划被批准后，实施者应该:**

1. **按阶段执行**: 严格按照 Phase 1-5 的顺序
2. **每阶段验证**: 完成一个阶段后验证该阶段的检查表
3. **提交策略**: 
   - Phase 1: 单独提交（模型层基础）
   - Phase 2-4: 每个工具文件一个提交
   - Phase 5: 清理和文档作为最后提交
4. **测试频率**: 每完成一个工具文件后手动测试
5. **文档更新**: 与代码更改同步更新

---

**计划创建日期**: 2026-01-20
**预计完成时间**: 5 个工作日
**复杂度**: 中等（重构现有代码，无新功能）
**风险等级**: 低（已有清晰模式，主要是机械式重构）
