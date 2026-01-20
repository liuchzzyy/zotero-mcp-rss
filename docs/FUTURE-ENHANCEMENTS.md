# Future Enhancements

**文档**: 未来增强和改进建议  
**状态**: 计划中  
**最后更新**: 2026-01-20

---

## 概述

本文档列出了 Zotero MCP 项目的潜在增强和改进方向。这些是可选的改进，不影响当前版本的功能。

---

## 🔄 1. 响应格式转换层（兼容性）

### 目标
为需要向后兼容的客户端提供可选的格式转换层。

### 实现方案

创建一个转换器模块，可以将新的结构化响应转换为旧的字符串格式：

```python
# src/zotero_mcp/utils/response_converter.py

from typing import Any
import json
from zotero_mcp.models.common import (
    SearchResponse,
    ItemDetailResponse,
    AnnotationsResponse,
    BaseResponse
)


class ResponseConverter:
    """Convert structured Pydantic responses to legacy string formats."""
    
    @staticmethod
    def to_legacy_format(
        response: BaseResponse,
        format_type: str = "json"
    ) -> str:
        """
        Convert structured response to legacy string format.
        
        Args:
            response: Structured Pydantic response
            format_type: Output format ("json" or "markdown")
        
        Returns:
            Formatted string in legacy format
        """
        if not response.success:
            return f"❌ Error: {response.error}"
        
        if format_type == "json":
            return ResponseConverter._to_json_string(response)
        else:
            return ResponseConverter._to_markdown_string(response)
    
    @staticmethod
    def _to_json_string(response: BaseResponse) -> str:
        """Convert to JSON string (legacy format)."""
        if isinstance(response, SearchResponse):
            # Convert to legacy format: {"items": [...], "count": N}
            legacy_format = {
                "items": [item.model_dump() for item in response.results],
                "count": response.count,
                "total": response.total_count
            }
            return json.dumps(legacy_format, indent=2, default=str)
        
        elif isinstance(response, ItemDetailResponse):
            # Convert creators list to authors
            data = response.model_dump()
            if "creators" in data:
                data["authors"] = data.pop("creators")
            return json.dumps(data, indent=2, default=str)
        
        # Default: return full model as JSON
        return response.model_dump_json(indent=2)
    
    @staticmethod
    def _to_markdown_string(response: BaseResponse) -> str:
        """Convert to Markdown string (legacy format)."""
        if isinstance(response, SearchResponse):
            lines = [
                f"# Search Results: '{response.query}'",
                "",
                f"Found {response.total_count} results (showing {response.count})",
                ""
            ]
            
            for i, item in enumerate(response.results, 1):
                lines.extend([
                    f"## {i}. {item.title}",
                    f"**Authors:** {', '.join(item.creators)}",
                    f"**Year:** {item.year or 'N/A'}",
                    f"**Type:** {item.item_type}",
                    f"**Key:** `{item.key}`",
                    ""
                ])
            
            if response.has_more:
                lines.append(f"*More results available (offset: {response.next_offset})*")
            
            return "\n".join(lines)
        
        elif isinstance(response, AnnotationsResponse):
            lines = [
                f"# Annotations for {response.item_key}",
                "",
                f"Found {response.count} annotation(s)",
                ""
            ]
            
            for ann in response.annotations:
                lines.extend([
                    f"### {ann.type.title()}" + (f" (Page {ann.page})" if ann.page else ""),
                    f"*Color: {ann.color}*" if ann.color else "",
                    f"> {ann.text}" if ann.text else "",
                    f"\n**Comment:** {ann.comment}" if ann.comment else "",
                    ""
                ])
            
            return "\n".join(filter(None, lines))
        
        # Default: return message field or JSON
        return response.message or response.model_dump_json(indent=2)


# Usage Example
def convert_response_for_legacy_client(response: BaseResponse) -> str:
    """Helper function for legacy clients."""
    converter = ResponseConverter()
    return converter.to_legacy_format(response, format_type="markdown")
```

### 使用示例

```python
from zotero_mcp.tools.search import search_items
from zotero_mcp.utils.response_converter import ResponseConverter

# Get structured response
response = await search_items(params=SearchItemsInput(query="AI", limit=10))

# Convert to legacy format for old clients
legacy_string = ResponseConverter.to_legacy_format(response, format_type="markdown")
print(legacy_string)  # Old-style markdown string
```

---

## 💾 2. 响应缓存层

### 目标
缓存频繁访问的响应，减少 Zotero API 调用，提升性能。

### 实现方案

```python
# src/zotero_mcp/utils/cache.py

from typing import Any, Optional
from datetime import datetime, timedelta
import hashlib
import json
from functools import wraps


class ResponseCache:
    """Simple in-memory cache for tool responses."""
    
    def __init__(self, ttl_seconds: int = 300):
        """
        Initialize cache.
        
        Args:
            ttl_seconds: Time-to-live for cache entries (default: 5 minutes)
        """
        self._cache: dict[str, tuple[Any, datetime]] = {}
        self._ttl = timedelta(seconds=ttl_seconds)
    
    def _make_key(self, tool_name: str, params: dict) -> str:
        """Generate cache key from tool name and parameters."""
        # Sort params for consistent hashing
        param_str = json.dumps(params, sort_keys=True, default=str)
        key_str = f"{tool_name}:{param_str}"
        return hashlib.md5(key_str.encode()).hexdigest()
    
    def get(self, tool_name: str, params: dict) -> Optional[Any]:
        """Get cached response if available and not expired."""
        key = self._make_key(tool_name, params)
        
        if key in self._cache:
            response, timestamp = self._cache[key]
            
            # Check if expired
            if datetime.now() - timestamp < self._ttl:
                return response
            else:
                # Remove expired entry
                del self._cache[key]
        
        return None
    
    def set(self, tool_name: str, params: dict, response: Any) -> None:
        """Cache a response."""
        key = self._make_key(tool_name, params)
        self._cache[key] = (response, datetime.now())
    
    def clear(self) -> None:
        """Clear all cached entries."""
        self._cache.clear()
    
    def invalidate(self, tool_name: str, params: dict) -> None:
        """Invalidate specific cache entry."""
        key = self._make_key(tool_name, params)
        if key in self._cache:
            del self._cache[key]


# Global cache instance
_global_cache = ResponseCache(ttl_seconds=300)


def cached_tool(ttl_seconds: Optional[int] = None):
    """
    Decorator to cache tool responses.
    
    Args:
        ttl_seconds: Override default TTL for this tool
    
    Example:
        @cached_tool(ttl_seconds=600)
        async def zotero_search(params: SearchItemsInput, ctx: Context):
            ...
    """
    def decorator(func):
        @wraps(func)
        async def wrapper(params, ctx, **kwargs):
            # Only cache read-only operations
            tool_name = func.__name__
            cache = _global_cache if ttl_seconds is None else ResponseCache(ttl_seconds)
            
            # Try to get from cache
            cached_response = cache.get(tool_name, params.model_dump())
            if cached_response is not None:
                await ctx.info(f"Cache hit for {tool_name}")
                return cached_response
            
            # Call actual function
            response = await func(params, ctx, **kwargs)
            
            # Cache successful responses
            if response.success:
                cache.set(tool_name, params.model_dump(), response)
            
            return response
        
        return wrapper
    return decorator
```

### 使用示例

```python
from zotero_mcp.utils.cache import cached_tool

@mcp.tool(name="zotero_search", ...)
@cached_tool(ttl_seconds=600)  # Cache for 10 minutes
async def zotero_search(params: SearchItemsInput, ctx: Context) -> SearchResponse:
    """Search with caching enabled."""
    # ... implementation
```

---

## 🔢 3. 批量操作支持

### 目标
允许一次调用处理多个项目，减少往返次数。

### 实现方案

```python
# src/zotero_mcp/models/batch.py

from pydantic import Field
from zotero_mcp.models.common import BaseInput, BaseResponse


class BatchGetMetadataInput(BaseInput):
    """Input for batch metadata retrieval."""
    
    item_keys: list[str] = Field(
        ...,
        min_length=1,
        max_length=50,  # Limit batch size
        description="List of item keys to retrieve"
    )
    format: str = Field(default="json", description="Output format")


class BatchItemResult(BaseModel):
    """Single item result in batch operation."""
    
    item_key: str = Field(..., description="Item key")
    success: bool = Field(..., description="Whether retrieval succeeded")
    data: ItemDetailResponse | None = Field(
        default=None,
        description="Item data if successful"
    )
    error: str | None = Field(
        default=None,
        description="Error message if failed"
    )


class BatchGetMetadataResponse(BaseResponse):
    """Response for batch metadata retrieval."""
    
    total_requested: int = Field(..., description="Total items requested")
    successful: int = Field(..., description="Successfully retrieved items")
    failed: int = Field(..., description="Failed items")
    results: list[BatchItemResult] = Field(
        default_factory=list,
        description="Individual item results"
    )
```

### 工具实现

```python
# src/zotero_mcp/tools/batch.py

from fastmcp import Context, FastMCP
from fastmcp.tools.base import ToolAnnotations

from zotero_mcp.models.batch import (
    BatchGetMetadataInput,
    BatchGetMetadataResponse,
    BatchItemResult
)
from zotero_mcp.services import get_data_service


def register_batch_tools(mcp: FastMCP) -> None:
    """Register batch operation tools."""
    
    @mcp.tool(
        name="zotero_batch_get_metadata",
        annotations=ToolAnnotations(
            title="Batch Get Metadata",
            readOnlyHint=True,
            destructiveHint=False,
            idempotentHint=True,
            openWorldHint=False,
        ),
    )
    async def batch_get_metadata(
        params: BatchGetMetadataInput,
        ctx: Context
    ) -> BatchGetMetadataResponse:
        """
        Get metadata for multiple items in a single call.
        
        More efficient than calling get_metadata multiple times.
        
        Args:
            params: Batch input with list of item keys
        
        Returns:
            BatchGetMetadataResponse with results for each item
        
        Example:
            Use when: "Get metadata for items ABC123, DEF456, GHI789"
        """
        service = get_data_service()
        results = []
        successful = 0
        failed = 0
        
        for item_key in params.item_keys:
            try:
                # Get metadata for single item
                item_data = await service.get_item(item_key)
                
                if item_data:
                    results.append(BatchItemResult(
                        item_key=item_key,
                        success=True,
                        data=ItemDetailResponse.from_dict(item_data)
                    ))
                    successful += 1
                else:
                    results.append(BatchItemResult(
                        item_key=item_key,
                        success=False,
                        error="Item not found"
                    ))
                    failed += 1
            
            except Exception as e:
                results.append(BatchItemResult(
                    item_key=item_key,
                    success=False,
                    error=str(e)
                ))
                failed += 1
        
        return BatchGetMetadataResponse(
            total_requested=len(params.item_keys),
            successful=successful,
            failed=failed,
            results=results
        )
```

### 使用示例

```python
# Batch get metadata for multiple items
result = await call_tool(
    "zotero_batch_get_metadata",
    params={
        "item_keys": ["ABC123", "DEF456", "GHI789"],
        "format": "json"
    }
)

# Process results
for item_result in result["results"]:
    if item_result["success"]:
        print(f"✓ {item_result['item_key']}: {item_result['data']['title']}")
    else:
        print(f"✗ {item_result['item_key']}: {item_result['error']}")
```

---

## 🌊 4. 流式响应支持

### 目标
对于大型结果集，支持流式返回，避免内存问题。

### 实现方案

```python
# src/zotero_mcp/utils/streaming.py

from typing import AsyncIterator, TypeVar
from zotero_mcp.models.common import SearchResultItem

T = TypeVar('T')


async def stream_search_results(
    service: Any,
    query: str,
    batch_size: int = 50
) -> AsyncIterator[list[SearchResultItem]]:
    """
    Stream search results in batches.
    
    Args:
        service: Data access service
        query: Search query
        batch_size: Number of items per batch
    
    Yields:
        Batches of search results
    """
    offset = 0
    
    while True:
        # Fetch batch
        results = await service.search_items(
            query=query,
            limit=batch_size,
            offset=offset
        )
        
        if not results:
            break
        
        # Yield batch
        yield results
        
        # Check if more results available
        if len(results) < batch_size:
            break
        
        offset += batch_size


# Usage example
async def process_all_results(query: str):
    """Process large result set with streaming."""
    service = get_data_service()
    total_processed = 0
    
    async for batch in stream_search_results(service, query):
        # Process each batch
        for item in batch:
            # Do something with item
            process_item(item)
            total_processed += 1
        
        print(f"Processed {total_processed} items...")
```

---

## 📊 5. 性能监控和指标

### 目标
添加性能监控，跟踪工具调用时间和频率。

### 实现方案

```python
# src/zotero_mcp/utils/metrics.py

from typing import Any
from functools import wraps
import time
from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class ToolMetrics:
    """Metrics for a single tool."""
    
    total_calls: int = 0
    successful_calls: int = 0
    failed_calls: int = 0
    total_duration_ms: float = 0
    min_duration_ms: float = float('inf')
    max_duration_ms: float = 0
    last_called: datetime | None = None


class MetricsCollector:
    """Collect and report tool usage metrics."""
    
    def __init__(self):
        self._metrics: dict[str, ToolMetrics] = {}
    
    def record_call(
        self,
        tool_name: str,
        duration_ms: float,
        success: bool
    ) -> None:
        """Record a tool call."""
        if tool_name not in self._metrics:
            self._metrics[tool_name] = ToolMetrics()
        
        metrics = self._metrics[tool_name]
        metrics.total_calls += 1
        
        if success:
            metrics.successful_calls += 1
        else:
            metrics.failed_calls += 1
        
        metrics.total_duration_ms += duration_ms
        metrics.min_duration_ms = min(metrics.min_duration_ms, duration_ms)
        metrics.max_duration_ms = max(metrics.max_duration_ms, duration_ms)
        metrics.last_called = datetime.now()
    
    def get_report(self) -> dict[str, Any]:
        """Generate metrics report."""
        report = {}
        
        for tool_name, metrics in self._metrics.items():
            avg_duration = (
                metrics.total_duration_ms / metrics.total_calls
                if metrics.total_calls > 0
                else 0
            )
            
            report[tool_name] = {
                "total_calls": metrics.total_calls,
                "successful": metrics.successful_calls,
                "failed": metrics.failed_calls,
                "success_rate": (
                    metrics.successful_calls / metrics.total_calls * 100
                    if metrics.total_calls > 0
                    else 0
                ),
                "avg_duration_ms": round(avg_duration, 2),
                "min_duration_ms": round(metrics.min_duration_ms, 2),
                "max_duration_ms": round(metrics.max_duration_ms, 2),
                "last_called": metrics.last_called.isoformat() if metrics.last_called else None
            }
        
        return report


# Global metrics collector
_metrics_collector = MetricsCollector()


def monitored_tool(func):
    """Decorator to monitor tool performance."""
    @wraps(func)
    async def wrapper(*args, **kwargs):
        start_time = time.time()
        success = False
        
        try:
            result = await func(*args, **kwargs)
            success = getattr(result, 'success', True)
            return result
        finally:
            duration_ms = (time.time() - start_time) * 1000
            _metrics_collector.record_call(
                func.__name__,
                duration_ms,
                success
            )
    
    return wrapper


# Example: Get metrics report
def get_metrics_report() -> dict:
    """Get current metrics report."""
    return _metrics_collector.get_report()
```

---

## 🎯 实施优先级

### 高优先级
1. **响应格式转换层** - 帮助现有用户迁移
2. **批量操作支持** - 显著提升性能

### 中优先级
3. **响应缓存层** - 减少 API 调用
4. **性能监控** - 了解使用模式

### 低优先级
5. **流式响应** - 仅在处理超大结果集时需要

---

## 📝 贡献

欢迎为这些增强功能贡献代码！请参阅项目的贡献指南。

---

**最后更新**: 2026-01-20  
**状态**: 规划阶段
