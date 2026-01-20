# Zotero MCP 完全重写计划

## 变更摘要

| 变更项 | 当前 | 重构后 |
|--------|------|--------|
| MCP 工具数 | 20 | 16 |
| 嵌入模型 | Default, OpenAI, Gemini | Default, OpenAI |
| MCP 客户端 | Claude Desktop | Claude Desktop + Opencode CLI |
| server.py 行数 | 2131 | <100 |

## 工具列表 (16个)

### 搜索 (5)
- zotero_search
- zotero_search_by_tag  
- zotero_advanced_search
- zotero_semantic_search
- zotero_get_recent

### 项目 (5)
- zotero_get_metadata
- zotero_get_fulltext
- zotero_get_children
- zotero_get_collections
- zotero_get_bundle (NEW)

### 注释 (4)
- zotero_get_annotations
- zotero_get_notes
- zotero_search_notes
- zotero_create_note

### 数据库 (2)
- zotero_update_database
- zotero_database_status

## 移除
- search, fetch (ChatGPT连接器)
- Gemini 嵌入模型
- zotero_get_tags (合并)
- zotero_batch_update_tags (暂时移除)

## 新增
- Opencode CLI 配置支持
- JSON 响应格式
- async/await
- Pydantic 模型
- Tool Annotations
