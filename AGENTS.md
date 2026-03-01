# Repository Guidelines

## 协作约定（重要）
- 每次回复用户时，固定称呼：`干饭小伙子`。
- 每次完成修订后，需将修改文件保存到 git（`git add` 并创建 commit）。
- 重要：执行任务时，必须持续显示任务完成进度，格式形如 `[1/10]`。

## 当前逻辑框架（2026-03-01）

### 1) 入口与调用链

#### CLI 入口
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

统一命令形态：`zotero-mcp <command> <subcommand> [parameters]`

#### `system`
- `serve` / `setup` / `setup-info` / `version` / `update`
- 实现文件：`src/zotero_mcp/cli_app/commands/system.py`

#### `workflow`
- `item-analysis` -> `GlobalScanner.scan_and_process`
- `metadata-update` -> `MetadataUpdateService.update_item_metadata / update_all_items`
- `deduplicate` -> `DuplicateDetectionService.find_and_remove_duplicates`
- 实现文件：`src/zotero_mcp/cli_app/commands/workflow.py`
- 参数约定（重要）：
  - `--treated-limit` 必须 `>=1`
  - 需要全库处理时使用 `--all`（而不是 `--treated-limit=0`）
  - `item-analysis --llm-provider` 取值：`auto | deepseek`
  - `item-analysis --template` 取值：`research | review | book | auto`
  - `item-analysis --template auto` 判定优先级：
    1. `itemType` 属于 `book/bookSection/encyclopediaArticle/dictionaryEntry` -> `book`
    2. 否则优先基于 PDF 文本分类：`review | si | ms`（其中 `ms=manuscript`）
    3. `si/ms` 均映射为 `research` 模板，`review` 映射为 `review` 模板
    4. 若无可用全文则回退到标题/摘要元数据分类

#### `semantic`
- `db-update` / `db-status` / `db-inspect`
- 实现文件：`src/zotero_mcp/cli_app/commands/semantic.py`
- 核心服务：`src/zotero_mcp/services/zotero/semantic_search.py`
- `db-update` 支持 `--all`，并在更新失败时返回非 0 退出码

#### `tags`
- `list` / `add` / `search` / `delete` / `purge` / `rename`
- 实现文件：`src/zotero_mcp/cli_app/commands/tags.py`

#### 资源命令组（`src/zotero_mcp/cli_app/commands/resources.py`）
- `items`:
  `get/list/children/fulltext/bundle/delete/update/create/add-tags/add-to-collection/remove-from-collection/delete-empty`
- `notes`:
  `list/create/search/delete`
- `annotations`:
  `list/add/search/delete`
- `pdfs`:
  `list/add/search/delete`
- `collections`:
  `list/find/create/rename/move/delete/delete-empty/items`

### 3) 关键服务与约定

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
- `scanner.py`：两阶段扫描（Stage 1 默认优先 `00_INBOXS_BB`；Stage 2 按顺序扫描但排除所有 `00_INBOXS_*` 集合），仅处理父条目（过滤 `note/attachment/annotation` 与有 `parentItem` 的子条目），筛选“有 PDF 且无 `AI分析` 标签”。
- `metadata_update_service.py`：先 DOI，再标题等补充路径，更新后打 `AI元数据` 标签；支持 `include_unfiled`。
- `duplicate_service.py`：
  - 仅处理父条目（过滤 `note/attachment/annotation` 及有 `parentItem` 的子条目）
  - 匹配优先级：`DOI > title > URL+title`
  - URL 去重要求“同 URL 且同规范化标题”，避免通用出版商落地页误判
  - 同标题但 DOI 冲突不合并
  - `groups` 返回结构化明细（包含 `primary_item`/`duplicate_items` 的 `key + title + item_type`）

#### CLI 输出与退出码
- 所有新命令支持 `--output text|json`。
- `--output json` 默认输出到 stdout；如需落盘请使用 shell 重定向（例如 `> dedup_run.json`）。
- 主入口退出码（`cli_app/main.py`）：
  - `0` 成功
  - `1` 运行错误
  - `2` 参数错误（argparse）
  - `130` 用户中断

### 4) 开发命令
- `uv run zotero-mcp system serve`
- `uv run zotero-mcp workflow item-analysis --help`
- `uv run zotero-mcp semantic db-status --output json`
- `uv run pytest -q`
- `uv run pytest tests/test_cli.py -q`
- `uv run ruff check .`
- `uv run ty check .`
- `uv run ty check tests`

### 5) 代码风格与命名
- Python 3.12+，4 空格缩进。
- 新增/修改代码要求类型标注。
- 遵循 `pyproject.toml` 中 Ruff 配置（line length 88）。
- 静态检查范围约定：
  - `ruff` 默认排除 `scripts/`
  - `ty` 默认排除 `scripts/`
- 命名约定：
  - modules/functions：`snake_case`
  - classes：`PascalCase`
  - constants：`UPPER_SNAKE_CASE`

### 6) 测试要求
- 测试框架：`pytest` + `pytest-asyncio`。
- 每个行为变更补测试，重点覆盖：
  - 参数边界
  - 工作流分支（dry-run、limit、skip）
  - 回归场景
- 文件命名 `test_*.py`，函数名描述行为预期。

### 7) 提交与 PR
- 建议使用 Conventional Commit：
  - `feat(cli): ...`
  - `fix(workflow): ...`
  - `docs(readme): ...`
- PR 建议包含：
  - 问题/方案摘要
  - 影响路径
  - 测试证据（`pytest`/`ruff`）
  - 若改动 `.github/workflows/*`，说明 CI 变化

### 8) 安全与配置
- 不提交任何密钥，统一使用环境变量（如 `ZOTERO_API_KEY`、`OPENAI_API_KEY`）。
- 本地配置以 `.env.example` 为模板。
