# Obsidian Vault Restructure Design

**Date**: 2026-02-28
**Vault**: `F:\ChengL1u\ChengL1u`
**Scheme**: 方案 B — Inbox 优先 + 科研专区（两层结构 + YAML 属性）

## Use Case

Daily note as inbox → AI cleans/enriches → categorized storage + research notes + project tracking.

## Target Folder Structure

```
ChengL1u/ (vault root)
├── 00 - Daily/                    ← 每日笔记 inbox
├── 01 - Research/                 ← 科研专区
│   ├── Experiments/               ← 实验记录
│   ├── Literature/                ← 文献阅读笔记
│   └── Thesis/                    ← 论文写作笔记
├── 02 - Knowledge/                ← AI提炼后的知识卡片
├── 03 - Projects/                 ← 任务/项目跟踪
├── 04 - References/               ← 工具参考 + 剪藏
│   ├── Tools/                     ← 工具参考
│   └── Clippings/                 ← 网页剪藏
└── 99 - Meta/                     ← 模板
```

## Migration Mapping

| 原文件夹 | 新位置 |
|---------|--------|
| `科研实验/*.md` | `01 - Research/Experiments/` |
| `学术与思想/*.md` | `02 - Knowledge/` |
| `职业发展/*.md` | `03 - Projects/` |
| `工具与参考/*.md` | `04 - References/Tools/` |
| `Clippings/*.md` | `04 - References/Clippings/` |

## YAML Frontmatter Schema

```yaml
---
tags:
  - type/<note|experiment|literature|daily|project|reference|clipping>
  - theme/<topic>
  - status/<active|done|archive>
date: YYYY-MM-DD
source: <来源>
---
```

- Existing tags preserved and supplemented with `type/` and `status/` if missing
- All existing `date` and `source` fields kept as-is
