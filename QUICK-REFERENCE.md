# Zotero MCP v2.0 快速参考

## 🚀 快速开始

### 重要变更
- ✅ 所有工具现在返回**结构化 Pydantic 模型**而非字符串
- ✅ 参数使用单个 `params` 对象而非多个独立参数
- ✅ 一致的错误处理：`{success: false, error: "..."}`
- ✅ 内置分页：`{has_more: true, next_offset: 10}`

### 迁移示例

**旧方式 (v1.x):**
```python
result = await call_tool(
    "zotero_search",
    query="AI",
    limit=10,
    response_format="json"
)
# 返回: '{"items": [...]}'  (字符串)
```

**新方式 (v2.0):**
```python
result = await call_tool(
    "zotero_search",
    params={
        "query": "AI",
        "limit": 10,
        "response_format": "json"
    }
)
# 返回: {success: true, results: [...]}  (结构化对象)
```

---

## 📚 核心响应格式

### 搜索响应
```json
{
  "success": true,
  "query": "machine learning",
  "count": 10,
  "total_count": 45,
  "has_more": true,
  "next_offset": 10,
  "results": [
    {
      "key": "ABC123",
      "title": "Paper Title",
      "creators": ["Author A", "Author B"],
      "year": 2023
    }
  ]
}
```

### 项目详情响应
```json
{
  "success": true,
  "item_key": "ABC123",
  "title": "Paper Title",
  "creators": ["Author A"],
  "year": 2023,
  "doi": "10.xxx/xxx",
  "tags": ["AI", "ML"]
}
```

### 错误响应
```json
{
  "success": false,
  "error": "Item not found: INVALID_KEY",
  "query": "...",
  "count": 0,
  "results": []
}
```

---

## 🔧 所有工具概览

### 搜索工具 (5)
| 工具 | 输入 | 输出 |
|------|------|------|
| `zotero_search` | `{query, limit, offset}` | `SearchResponse` |
| `zotero_search_by_tag` | `{include_tags, exclude_tags}` | `SearchResponse` |
| `zotero_advanced_search` | `{title, creator, year}` | `SearchResponse` |
| `zotero_semantic_search` | `{query, threshold}` | `SearchResponse` |
| `zotero_get_recent` | `{limit, days}` | `SearchResponse` |

### 项目工具 (5)
| 工具 | 输入 | 输出 |
|------|------|------|
| `zotero_get_metadata` | `{item_key, format}` | `ItemDetailResponse` |
| `zotero_get_fulltext` | `{item_key}` | `FulltextResponse` |
| `zotero_get_children` | `{item_key}` | `dict` (structured) |
| `zotero_get_collections` | `{item_key}` | `CollectionsResponse` |
| `zotero_get_bundle` | `{item_key, ...}` | `BundleResponse` |

### 注释工具 (4)
| 工具 | 输入 | 输出 |
|------|------|------|
| `zotero_get_annotations` | `{item_key, type}` | `AnnotationsResponse` |
| `zotero_get_notes` | `{item_key}` | `NotesResponse` |
| `zotero_search_notes` | `{query}` | `SearchResponse` |
| `zotero_create_note` | `{item_key, content}` | `NoteCreationResponse` |

### 数据库工具 (2)
| 工具 | 输入 | 输出 |
|------|------|------|
| `zotero_update_database` | `{force_rebuild, ...}` | `DatabaseUpdateResponse` |
| `zotero_database_status` | `{}` | `DatabaseStatusResponse` |

---

## 📖 完整文档

- **结构化输出示例**: [`docs/STRUCTURED-OUTPUT-EXAMPLES.md`](./docs/STRUCTURED-OUTPUT-EXAMPLES.md)
- **迁移指南**: [`docs/MIGRATION-GUIDE.md`](./docs/MIGRATION-GUIDE.md)
- **完整报告**: [`.sisyphus/plans/REFACTORING-COMPLETE.md`](./.sisyphus/plans/REFACTORING-COMPLETE.md)

---

## ✅ 常见模式

### 1. 检查成功
```python
result = await call_tool("zotero_search", params={...})
if not result.get("success", True):
    print(f"Error: {result['error']}")
    return
# 继续处理
```

### 2. 处理分页
```python
offset = 0
while True:
    result = await call_tool(
        "zotero_search",
        params={"query": "AI", "limit": 10, "offset": offset}
    )
    if not result["success"]:
        break
    
    process(result["results"])
    
    if not result["has_more"]:
        break
    offset = result["next_offset"]
```

### 3. 提取字段
```python
result = await call_tool("zotero_search", params={...})
if result["success"]:
    titles = [item["title"] for item in result["results"]]
```

---

## 🆘 故障排除

| 问题 | 解决方案 |
|------|----------|
| `KeyError: 'items'` | 使用 `result["results"]` 而非 `result["items"]` |
| `KeyError: 'authors'` | 使用 `result["creators"]` 而非 `result["authors"]` |
| 参数错误 | 将所有参数包装在 `params={}` 对象中 |
| 字符串解析 | 不需要！响应已经是结构化对象 |

---

**快速参考 - Zotero MCP v2.0**  
**更新**: 2026-01-20
