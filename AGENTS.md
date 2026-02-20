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

> 旧扁平命令（如 `zotero-mcp scan` / `zotero-mcp deduplicate`）已移除。
> 当前统一为：`zotero-mcp <command> <subcommand> [parameters]`

#### `system`
- `serve` / `setup` / `setup-info` / `version` / `update`
- 实现文件：`src/zotero_mcp/cli_app/commands/system.py`

#### `workflow`
- `scan` -> `GlobalScanner.scan_and_process`
- `metadata-update` -> `MetadataUpdateService.update_item_metadata / update_all_items`
- `deduplicate` -> `DuplicateDetectionService.find_and_remove_duplicates`
- `clean-empty` -> 基于 `DataAccessService` 扫描并删除空父条目
- `clean-tags` -> 扫描并按前缀保留 tags
- 实现文件：`src/zotero_mcp/cli_app/commands/workflow.py`

#### `semantic`
- `db-update` / `db-status` / `db-inspect`
- 实现文件：`src/zotero_mcp/cli_app/commands/semantic.py`
- 核心服务：`src/zotero_mcp/services/zotero/semantic_search.py`

#### 资源命令组
- `items`: `get/list/children/fulltext/bundle/delete/update/create/add-tags/add-to-collection/remove-from-collection`
- `notes`: `list/create/search`
- `annotations`: `list`
- `pdfs`: `upload`
- `collections`: `list/find/create/rename/move/delete/items`
- 实现文件：`src/zotero_mcp/cli_app/commands/resources.py`

### 3) 关键实现细节

#### 统一数据访问门面（Facade）
- 文件：`src/zotero_mcp/services/data_access.py`
- 作用：统一封装读写入口，内部组合：
  - `ItemService`
  - `SearchService`
  - `MetadataService`
- 后端策略：
  - 读优先走本地 DB（若可用）
  - 写走 Zotero API

#### 批处理工作流实现
- `scanner.py`：两阶段扫描（优先源集合，再全库补足），筛选规则“有 PDF 且无 `AI分析` 标签”。
- `metadata_update_service.py`：先 DOI，再标题等补充路径，更新后打 `AI元数据` 标签。
- `duplicate_service.py`：按 `DOI > title > URL` 分组，保留信息最完整条目，删除其余重复条目。

#### CLI 输出与退出码
- 所有新命令支持 `--output text|json`。
- 主入口退出码约定（`cli_app/main.py`）：
  - `0` 成功
  - `1` 运行错误
  - `2` 参数错误（argparse）
  - `130` 用户中断

### 4) 当前项目结构（与实现对应）
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
  Run the MCP server locally over stdio.
- `uv run zotero-mcp workflow scan --help`  
  Show workflow scan CLI usage.
- `uv run zotero-mcp semantic db-status --output json`  
  Check semantic DB status.
- `uv run pytest -q`  
  Run full test suite.
- `uv run pytest tests/test_cli.py -q`  
  Run CLI-focused tests.
- `uv run ruff check src/ tests/`  
  Run lint checks.

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
- Add tests for each behavior change, especially:
  - parameter validation boundaries
  - workflow branch behavior (dry-run, limits, skip paths)
  - regression cases for fixed bugs.
- Test files should be named `test_*.py`; test functions should describe expected behavior.

## Commit & Pull Request Guidelines
- Use Conventional Commit style, e.g.:
  - `feat(cli): refactor command tree`
  - `fix(workflow): handle empty collection`
  - `ci(workflows): migrate command paths`
- PRs should include:
  - concise problem/solution summary
  - impacted paths
  - test evidence (`pytest`/`ruff` output)
  - workflow impact if `.github/workflows/*` changed.

## Security & Configuration Tips
- Never commit secrets. Use environment variables (`ZOTERO_API_KEY`, `OPENAI_API_KEY`, etc.).
- Use `.env.example` as the template for local configuration.
