# Tag System Final Plan (Zotero 落地版)

**Date:** 2026-03-02  
**Status:** Final  
**Based on:** `docs/plans/2025-02-16-tag-system-design.md`

## 1. 评审结论（对原方案的修正）

原方案的标签结构方向正确，但有 3 个落地差距：

1. 原文列出的 MCP 工具（如 `zotero_set_status` / `zotero_suggest_tags`）当前仓库未实现。  
2. `status/*` 的“互斥”规则需要流程/脚本保障，当前 `tags add` 不会自动清理旧状态。  
3. `focus/prep/*` 这种通配查询不是当前 CLI 的直接能力（`tags search` 需要明确标签名）。

因此最终版采用：**标签体系不变 + 先用现有 CLI 落地 + 必要处用轻量脚本补齐规则**。

## 2. 最终标签字典（保留）

### 2.1 状态标签（互斥）
- `status/new`
- `status/reading`
- `status/read`
- `status/todo`
- `status/cited`
- `status/skip`
- `status/archive`

### 2.2 用途标签（可多选）
- `use/intro`
- `use/related`
- `use/discuss`
- `use/reference`
- `use/compare`

### 2.3 焦点标签（可多选）
- `focus/prep/synth`, `focus/prep/coat`, `focus/prep/dope`, `focus/prep/nano`
- `focus/char/struct`, `focus/char/surf`, `focus/char/electro`, `focus/char/spec`
- `focus/perf/energy`, `focus/perf/power`, `focus/perf/cycle`, `focus/perf/rate`
- `focus/mech/react`, `focus/mech/decay`, `focus/mech/inter`
- `focus/theory/dft`, `focus/theory/md`, `focus/theory/ml`

### 2.4 现有标签兼容
- 保留：`AI分析`、`AI元数据`
- 不纳入互斥逻辑，不自动删除。

## 3. 规则（执行标准）

1. 每条文献 `status/*` 最多 1 个。  
2. `use/*` 与 `focus/*` 可并存多值。  
3. 推荐每条文献 `focus/*` 控制在 1–4 个，避免标签污染。  
4. 新导入文献默认打 `status/new`。

## 4. 实施路径（分阶段）

## Phase A: 基线盘点（1 天）

目标：确认当前库内已有标签和脏标签。

```bash
uv run zotero-mcp tags list --output json > tag_inventory.json
```

动作：
- 统计所有不在最终字典内的标签（拼写变体、中文旧标签、大小写混用）。
- 形成 `old_tag -> canonical_tag` 映射清单。

## Phase B: 规范化迁移（1–2 天）

目标：把旧标签归一到最终字典。

优先用内置命令：
```bash
uv run zotero-mcp tags rename --old-name "read" --new-name "status/read"
uv run zotero-mcp tags rename --old-name "to-read" --new-name "status/new"
uv run zotero-mcp tags rename --old-name "mechanism" --new-name "focus/mech/react"
```

注意：
- 先 `--dry-run` 再正式执行。  
- 高风险重命名分批执行（`--limit`）。

## Phase C: 状态互斥落地（核心）

目标：确保 `status/*` 严格互斥。

方案：新增轻量脚本 `scripts/tag_set_status.py`（建议），逻辑：
1. 读取 item 现有标签。
2. 删除全部 `status/*`。
3. 添加目标状态（如 `status/reading`）。

说明：
- 这一步不要求改 CLI 主命令；脚本基于现有 `DataAccessService` 即可。
- 后续若需要再升级为正式子命令（如 `tags set-status`）。

## Phase D: 工作流接入（持续）

建议流程：
1. 导入文献 -> `status/new`
2. 开始读 -> `status/reading`
3. 读完 -> `status/read`
4. 计划引用 -> `status/todo`
5. 已引用 -> `status/cited`

同时补 `use/*` 与 `focus/*`。

## 5. 查询与运营（当前能力下）

当前 `tags search` 是显式标签匹配，因此按“明确标签组合”查：

```bash
# 待引用 + 反应机理
uv run zotero-mcp tags search --tags status/todo focus/mech/react --output json

# 引言候选 + 合成方法
uv run zotero-mcp tags search --tags use/intro focus/prep/synth --output json
```

若要“某大类全部焦点”（如 `focus/prep/*`），建议后续补一个查询脚本做前缀匹配。

## 6. 验收标准（Definition of Done）

1. 100% 文献满足：`status/*` 数量 <= 1。  
2. 90%+ 核心文献具备至少 1 个 `focus/*`。  
3. 无高频脏标签（同义重复、大小写重复、错拼）。  
4. 查询场景可直接支持论文写作（intro/related/discuss + mech/perf/prep）。

## 7. 风险与回滚

- 风险：批量重命名误改。  
- 控制：所有批量操作先 `--dry-run`，再小批量正式执行。  
- 回滚：保留每次批处理前后的 JSON 快照（标签清单 + 受影响 item key 列表）。

## 8. 最终建议（执行优先级）

1. 先完成 Phase A + Phase B（立刻可做）。  
2. 紧接着做 Phase C（互斥规则脚本），这是体系稳定运行的关键。  
3. 之后再考虑 AI 自动推荐标签（放到增强迭代，不阻塞当前上线）。
