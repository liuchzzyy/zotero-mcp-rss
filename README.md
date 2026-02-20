# Zotero MCP

连接 AI 助手与 Zotero 研究库的 Model Context Protocol 服务器。

## 业务逻辑框架

```
┌───────────────────────────────────────────────────────────
│                   Entry Layer                             
│  ├── server.py (MCP stdio server)                         
│  └── cli.py (CLI)                                         
├───────────────────────────────────────────────────────────
│                   Handlers Layer                          
│  ├── annotations.py  (PDF 注释工具)                        
│  ├── batch.py        (批量操作工具)                        
│  ├── collections.py  (集合管理工具)                        
│  ├── database.py     (语义搜索工具)                        
│  ├── items.py        (条目 CRUD 工具)                      
│  ├── search.py       (搜索工具)                            
│  └── workflow.py     (批量分析工作流工具)                   
├───────────────────────────────────────────────────────────
│                  Services Layer                           
│  ├── zotero/                                              
│  │   ├── ItemService         (CRUD 操作)                  
│  │   ├── SearchService        (关键词/语义搜索)            
│  │   ├── MetadataService      (DOI/元数据补全)             
│  │   ├── MetadataUpdateService (条目元数据更新)            
│  │   ├── SemanticSearch       (ChromaDB 向量搜索)          
│  │   └── DuplicateService      (去重)                     
│  ├── workflow.py      (批量分析 + 检查点)                 
│  └── data_access.py  (本地 DB / Zotero API 门面)           
├──────────────────────────────────────────────────────────
│                  Clients Layer                        
│  ├── zotero/          (Zotero API + 本地 DB)                      
│  ├── database/        (ChromaDB 向量数据库)                     
│  ├── metadata/        (Crossref + OpenAlex APIs)                 
│  └── llm/            (DeepSeek/OpenAI/Gemini/Claude CLI)        
└──────────────────────────────────────────────────────────
```

## 核心服务

### 1. Scanner Service (`scanner.py`)
- 入口: `GlobalScanner.scan_and_process()`
- 目标: 扫描需要 AI 分析的条目并触发分析
- 逻辑阶段:
1. 扫描 `source_collection`（默认 `00_INBOXS`）
2. 候选不足时按集合顺序继续扫描
3. 过滤规则: 必须有 PDF 且未带 `AI分析` 标签
4. 执行分析并可移动到 `target_collection`

### 2. Metadata Update Service (`metadata_update_service.py`)
- 入口: `MetadataUpdateService.update_all_items()`
- 目标: 使用 Crossref/OpenAlex 增强条目元数据
- 逻辑要点:
1. 先按 DOI 查，DOI 路径不再降级 title/url
2. 清洗 HTML 标题后再做 title 查询
3. 将扩展信息安全写入 `extra`

### 3. Duplicate Detection Service (`duplicate_service.py`)
- 入口: `DuplicateDetectionService.find_and_remove_duplicates()`
- 目标: 检测并删除重复条目（永久删除，不移动回收站）
- 分组优先级: `DOI > title > URL`
- 保留策略: 按完整度评分保留主条目

### 4. Workflow Service (`workflow.py`)
- 入口: `WorkflowService.prepare_analysis()` / `WorkflowService.batch_analyze()`
- 目标: 批量 PDF 分析、生成结构化笔记、支持检查点恢复

### 5. Semantic Search (`semantic_search.py`)
- 入口: `ZoteroSemanticSearch.search()` / `update_database()`
- 目标: ChromaDB 向量检索与索引更新
- 当前行为:
1. `limit <= 0` 直接返回空结果
2. 兼容空嵌套列表结果结构
3. 连接拒绝抛出 `RuntimeError`

## 统一参数与返回约定

### 参数模型
跨服务的批处理入口统一由显式参数模型约束:
- `src/zotero_mcp/models/operations.py`
  - `ScannerRunParams`
  - `MetadataUpdateBatchParams`
  - `DuplicateScanParams`

这三个模型统一了:
- 默认值
- 数值边界（如 `scan_limit >= 1`）
- 禁止隐式额外字段（`extra="forbid"`）

### 运行结果结构
批处理服务统一返回 envelope（并保留兼容字段）:
- `src/zotero_mcp/services/common/operation_result.py`
  - `operation_success(...)`
  - `operation_error(...)`

统一字段:
- `success`
- `operation`
- `status`
- `metrics`
- `message` / `error` / `details`

### 分页扫描 helper
重复的 `offset + limit` 循环已统一:
- `src/zotero_mcp/services/common/pagination.py`
  - `iter_offset_batches(...)`

已接入:
- `scanner.py`
- `metadata_update_service.py`
- `duplicate_service.py`

## CLI 命令

### 基本格式

```bash
zotero-mcp <command> <subcommand> [parameters]
```

### 顶层命令组

| command | 说明 |
|------|------|
| `system` | 系统与运行命令 |
| `workflow` | 批处理工作流命令 |
| `semantic` | 语义数据库命令 |
| `items` | 条目操作 |
| `notes` | 笔记操作 |
| `annotations` | 注释操作 |
| `pdfs` | PDF 附件操作 |
| `collections` | 集合操作 |

### `system` 子命令
- `zotero-mcp system serve`
- `zotero-mcp system setup`
- `zotero-mcp system setup-info`
- `zotero-mcp system version`
- `zotero-mcp system update [--check-only --force --method pip|uv|conda|pipx]`

### `workflow` 子命令
- `zotero-mcp workflow item-analysis`
- `zotero-mcp workflow metadata-update`
- `zotero-mcp workflow deduplicate`

#### `workflow item-analysis` 常用参数
| 参数 | 默认值 | 说明 |
|------|--------|------|
| `--scan-limit` | `100` | 每批抓取条目数 |
| `--treated-limit` | `20` | 最多处理条目数 |
| `--target-collection` | 必填 | 分析后移动目标集合 |
| `--dry-run` | `False` | 预览模式 |
| `--llm-provider` | `auto` | `auto/claude-cli/deepseek/openai/gemini` |
| `--source-collection` | `00_INBOXS` | 优先扫描集合 |
| `--multimodal` / `--no-multimodal` | `True` | 是否启用多模态 |
| `--output` | `text` | 输出格式：`text/json` |

### `semantic` 子命令
- `zotero-mcp semantic db-update`
- `zotero-mcp semantic db-status`
- `zotero-mcp semantic db-inspect`

#### `semantic db-update` 常用参数
| 参数 | 默认值 | 说明 |
|------|--------|------|
| `--force-rebuild` | `False` | 强制重建向量库 |
| `--scan-limit` | `500` | 每批抓取条目数 |
| `--treated-limit` | `100` | 最大处理条目数 |
| `--no-fulltext` | `False` | 禁用全文提取 |
| `--config-path` | `None` | 指定语义配置路径 |
| `--db-path` | `None` | 指定 Zotero DB 路径 |
| `--output` | `text` | 输出格式：`text/json` |

### 资源命令组

| command | subcommand |
|------|------|
| `items` | `get/list/children/fulltext/bundle/delete/update/create/add-tags/add-to-collection/remove-from-collection/delete-empty` |
| `notes` | `list/create/search/delete` |
| `annotations` | `list/add/search/delete` |
| `pdfs` | `list/add/search/delete` |
| `collections` | `list/find/create/rename/move/delete/delete-empty/items` |
| `tags` | `list/add/search/delete/rename` |

### 示例

```bash
# 扫描并分析
zotero-mcp workflow item-analysis --target-collection 01_SHORTTERMS --output json

# 更新元数据
zotero-mcp workflow metadata-update --scan-limit 200 --treated-limit 100

# 查看语义数据库状态
zotero-mcp semantic db-status --output json

# 获取条目详情
zotero-mcp items get --item-key ABCD1234 --output json

# 创建笔记
zotero-mcp notes create --item-key ABCD1234 --content "My note"

# 上传 PDF 附件
zotero-mcp pdfs add --item-key ABCD1234 --file ./paper.pdf
```

## 环境变量

### Zotero 连接
| 变量 | 默认值 | 说明 |
|------|---------|------|
| `ZOTERO_LOCAL` | `true` | 使用本地 API |
| `ZOTERO_API_KEY` | - | Web API 密钥 |
| `ZOTERO_LIBRARY_ID` | - | Web API 库 ID |
| `ZOTERO_LIBRARY_TYPE` | `user` | 库类型 |

### 语义搜索
| 变量 | 默认值 | 说明 |
|------|---------|------|
| `ZOTERO_EMBEDDING_MODEL` | `default` | 嵌入模型 |
| `OPENAI_API_KEY` | - | OpenAI 密钥 |
| `OPENAI_EMBEDDING_MODEL` | `text-embedding-3-small` | OpenAI 模型 |
| `GEMINI_API_KEY` | - | Gemini 密钥 |
| `GEMINI_EMBEDDING_MODEL` | `models/text-embedding-004` | Gemini 模型 |

### 批量分析
| 变量 | 默认值 | 说明 |
|------|---------|------|
| `DEEPSEEK_API_KEY` | - | DeepSeek 密钥 |
| `DEEPSEEK_MODEL` | `deepseek-chat` | DeepSeek 模型 |
| `DEEPSEEK_BASE_URL` | `https://api.deepseek.com` | API endpoint |

### 多模态分析
| 变量 | 默认值 | 说明 |
|------|---------|------|
| `ZOTERO_MCP_CLI_LLM_PROVIDER` | `deepseek` | LLM 提供商 |
| `ZOTERO_MCP_CLI_LLM_OCR_ENABLED` | `true` | 启用 OCR |
| `ZOTERO_MCP_CLI_LLM_MAX_PAGES` | `50` | 最大处理页数 |
| `ZOTERO_MCP_CLI_LLM_MAX_IMAGES` | `20` | 最大提取图片数 |

## MCP 工具

### 搜索工具
- `zotero_semantic_search` - 语义搜索
- `zotero_search` - 关键词搜索
- `zotero_advanced_search` - 高级搜索
- `zotero_search_by_tag` - 标签搜索
- `zotero_get_recent` - 最近条目

### 内容访问
- `zotero_get_metadata` - 条目元数据
- `zotero_get_fulltext` - 全文内容
- `zotero_get_bundle` - 完整条目数据
- `zotero_get_children` - 附件和笔记

### 集合和标签
- `zotero_get_collections` - 列出集合
- `zotero_find_collection` - 按名称查找（模糊匹配）
- `zotero_get_tags` - 列出所有标签

### 注释和笔记
- `zotero_get_annotations` - PDF 注释
- `zotero_get_notes` - 获取笔记
- `zotero_search_notes` - 搜索笔记/注释
- `zotero_create_note` - 创建笔记

### 批量工作流
- `zotero_prepare_analysis` - 收集 PDF 内容
- `zotero_batch_analyze_pdfs` - 批量 AI 分析
- `zotero_resume_workflow` - 恢复中断的工作流
- `zotero_list_workflows` - 查看工作流状态
