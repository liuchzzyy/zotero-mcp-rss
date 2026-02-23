# Repository Guidelines

## 当前逻辑框架（2026-02）

### 1) 入口与调用链

#### CLI 入口（已重构）
- 打包脚本入口：`pyproject.toml` -> `zotero-mcp = "zotero_mcp.cli_app.main:main"`
- 运行链路：
  1. `src/zotero_mcp/cli_app/main.py`
  2. `src/zotero_mcp/cli_app/registry.py`（构建 parser + dispatch）
  3. `src/zotero_mcp/cli_app/commands/*.py`
  4. `src/zotero_mcp/services/*` / `src/zotero_mcp/services/zotero/*`
  5. `src/zotero_mcp/clients/*`

#### MCP 入口
- `zotero-mcp system serve` -> `src/zotero_mcp/server.py`
- `server.py` 内注册：
  - `ToolHandler`（`src/zotero_mcp/handlers/tools.py`）
  - `PromptHandler`（`src/zotero_mcp/handlers/prompts.py`）

### 2) 命令结构（当前实现）

> 统一命令形态：`zotero-mcp <command> <subcommand> [parameters]`

#### `system`
- `serve` / `setup` / `setup-info` / `version` / `update`
- 实现文件：`src/zotero_mcp/cli_app/commands/system.py`

#### `workflow`
- `item-analysis` -> `GlobalScanner.scan_and_process`
- `metadata-update` -> `MetadataUpdateService.update_item_metadata / update_all_items`
- `deduplicate` -> `DuplicateDetectionService.find_and_remove_duplicates`
- 实现文件：`src/zotero_mcp/cli_app/commands/workflow.py`

#### `semantic`
- `db-update` / `db-status` / `db-inspect`
- 实现文件：`src/zotero_mcp/cli_app/commands/semantic.py`
- 核心服务：`src/zotero_mcp/services/zotero/semantic_search.py`

#### `items`
- `get/list/children/fulltext/bundle/delete/update/create/add-tags/add-to-collection/remove-from-collection/delete-empty`
- 实现文件：`src/zotero_mcp/cli_app/commands/resources.py`

#### `notes`
- `list/create/search/delete`
- 实现文件：`src/zotero_mcp/cli_app/commands/resources.py`

#### `annotations`
- `list/add/search/delete`
- 实现文件：`src/zotero_mcp/cli_app/commands/resources.py`

#### `pdfs`
- `list/add/delete/search`
- 实现文件：`src/zotero_mcp/cli_app/commands/resources.py`

#### `collections`
- `list/find/create/rename/move/delete/delete-empty/items`
- 实现文件：`src/zotero_mcp/cli_app/commands/resources.py`

### 3) 语义搜索（当前实现细节）

#### 运行模式与入口
- 命令：`zotero-mcp semantic db-update`
- 默认本地模式（`--local` 默认启用）。
- 强制重建建议命令：
  - `uv run zotero-mcp semantic db-update --force-rebuild --treated-limit 0 --local --output json`

#### 当前索引策略
- 主条目（item）向量化保留。
- `note` 作为独立 fragment 向量化。
- `pdf` 作为独立 fragment 向量化。
- PDF 文本来源：本地 Zotero `storage` 直接读取附件并提取文本。
- 不通过 `get_fulltext()` 构建 PDF fragment。

#### fragment 结构
- 默认切片参数：`chunk_size=1800`，`overlap=200`。
- fragment metadata 字段：
  - `fragment_type`（`item` / `note` / `pdf`）
  - `item_key`（父条目 key）
  - `source_key`（note key / attachment key）
  - `source_label`（如 PDF 文件名）
  - `chunk_index` / `chunk_count`
- fragment 文档 ID：
  - `{item_key}::{fragment_type}::{source_key}::{chunk_index}`

#### 过滤与回填
- API 扫描路径排除：`attachment` / `note` / `annotation`。
- 命中 fragment 时，使用 metadata 中的 `item_key` 回查父条目。
- 返回中保留 `result_id` 标识具体命中片段。

#### 更新统计字段
- `total_items`: 主条目数量
- `total_fragments`: fragment 数量
- `total_documents`: 主条目 + fragment 总数
- 其余：`processed_items` / `added_items` / `updated_items` / `skipped_items` / `errors`

### 4) 统一数据访问门面（Facade）
- 文件：`src/zotero_mcp/services/data_access.py`
- 作用：统一封装读写入口，内部组合：
  - `ItemService`
  - `SearchService`
  - `MetadataService`
- 后端策略：
  - 读优先走本地 DB（若可用）
  - 写走 Zotero API

### 5) 批处理工作流实现
- `scanner.py`：两阶段扫描（优先源集合，再全库补足），筛选“有 PDF 且无 `AI分析` 标签”。
- `metadata_update_service.py`：先 DOI，再标题等补充路径，更新后打 `AI元数据` 标签。
- `duplicate_service.py`：按 `DOI > title > URL` 分组，保留信息最完整条目，删除其余重复条目。

### 6) CLI 输出与退出码
- 所有新命令支持 `--output text|json`。
- 主入口退出码（`cli_app/main.py`）：
  - `0` 成功
  - `1` 运行错误
  - `2` 参数错误（argparse）
  - `130` 用户中断

### 7) 当前项目结构
- 主代码：`src/zotero_mcp/`
- CLI：`src/zotero_mcp/cli_app/`
- MCP handlers：`src/zotero_mcp/handlers/`
- 业务服务：`src/zotero_mcp/services/`
- 外部客户端：`src/zotero_mcp/clients/`
- 数据模型：`src/zotero_mcp/models/`
- 测试：`tests/`
- 自动化：`.github/workflows/`

## Build, Test, and Development Commands
- `uv run zotero-mcp system serve`
- `uv run zotero-mcp workflow item-analysis --help`
- `uv run zotero-mcp semantic db-status --output json`
- `uv run pytest -q`
- `uv run pytest tests/test_cli.py -q`
- `uv run ruff check src/ tests/`

## Coding Style & Naming Conventions
- Python 3.12+, 4-space indentation, type hints required for new/changed code.
- Follow Ruff defaults configured in `pyproject.toml` (line length 88).
- Naming:
  - modules/functions: `snake_case`
  - classes: `PascalCase`
  - constants: `UPPER_SNAKE_CASE`
- Keep service entrypoints explicit: validate inputs via models, avoid implicit parameter behavior.

## Testing Guidelines
- Framework: `pytest` with `pytest-asyncio`.
- 为每个行为变更补测试，重点包括：
  - 参数边界
  - 工作流分支（dry-run、limit、skip）
  - 回归场景
- 测试文件命名 `test_*.py`，测试名应描述行为预期。

## Commit & Pull Request Guidelines
- Conventional Commit 例如：
  - `feat(cli): refactor command tree`
  - `fix(workflow): handle empty collection`
  - `ci(workflows): migrate command paths`
- PR 建议包含：
  - 问题/方案摘要
  - 影响路径
  - 测试证据（`pytest`/`ruff`）
  - 若改动 `.github/workflows/*`，说明 CI 行为变化

## Security & Configuration Tips
- 不要提交密钥，使用环境变量（`ZOTERO_API_KEY`、`OPENAI_API_KEY` 等）。
- 本地配置以 `.env.example` 为模板。
