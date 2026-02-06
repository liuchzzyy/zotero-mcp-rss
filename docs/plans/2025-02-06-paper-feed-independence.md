# paper-feed 独立化架构调整说明

**日期**: 2025-02-06
**状态**: 架构调整
**版本**: 2.0

## 概述

将 **paper-feed** 从 zotero-mcp 项目中独立出来，作为一个通用的学术论文采集框架发布。

## 调整后的架构

### 仓库组织

```
GitHub 仓库布局:

yourname/
└── paper-feed/                    # 独立仓库 ✅
    ├── src/paper_feed/
    ├── pyproject.toml
    └── README.md

zotero-mcp/                        # 主组织
├── zotero-core/                   # 保留在组织内
│   ├── src/zotero_core/
│   └── pyproject.toml
├── paper-analyzer/                # 保留在组织内
│   ├── src/paper_analyzer/
│   └── pyproject.toml
├── zotero-mcp/                    # 集成层
│   ├── src/zotero_mcp/
│   └── pyproject.toml
└── semantic-search/               # 归档功能
    └── src/semantic_search/
```

### 依赖关系图

```
┌─────────────────────────────────────────────────────┐
│                    paper-feed                        │
│                 (独立仓库/PyPI 包)                   │
│                                                      │
│  • RSS feeds (arXiv, bioRxiv, Nature, etc.)        │
│  • Gmail alerts (Google Scholar, journal TOCs)      │
│  • 多级过滤管道                                       │
│  • 可配置模板                                         │
└─────────────────────────────────────────────────────┘
                         │
                         │ (适配器模式)
                         │ 可选依赖
                         ▼
              ┌─────────────────────┐
              │    zotero-core       │
              │  (zotero-mcp/core)   │
              │                     │
              │ • Zotero API Client │
              │ • CRUD Services     │
              │ • 搜索服务          │
              └─────────────────────┘
                         │
                         ▲
                         │
        ┌────────────────┴────────────────┐
        │                                 │
┌───────────────┐              ┌──────────────┐
│ paper-analyzer│              │  zotero-mcp  │
│ (分析引擎)     │              │  (集成层)     │
└───────────────┘              └──────────────┘
```

### 关键变化

#### 1. paper-feed 独立性

**之前**: paper-feed 是 zotero-mcp 的一部分
```python
# 在 zotero-mcp 单体仓库中
from zotero_mcp.services.rss import RSSService
from zotero_mcp.services.gmail import GmailService
```

**之后**: paper-feed 作为独立包
```bash
# 安装
pip install paper-feed

# 使用
from paper_feed import RSSSource, GmailSource, FilterPipeline
```

#### 2. ZoteroAdapter 依赖调整

**之前**: 内部依赖
```python
# paper-feed/src/adapters/zotero.py
from ..services.zotero_service import ZoteroService  # 内部导入
```

**之后**: 外部依赖
```python
# paper-feed/src/adapters/zotero.py
from zotero_core import ItemService  # 外部依赖

class ZoteroAdapter(ExportAdapter):
    def __init__(self, library_id: str, api_key: str):
        self.item_service = ItemService(
            library_id=library_id,
            api_key=api_key
        )
```

**依赖配置**:
```toml
# paper-feed/pyproject.toml
[project]
dependencies = [
    "feedparser>=6.0.0",
    "pydantic>=2.0.0",
    "httpx>=0.25.0",
    "beautifulsoup4>=4.12.0",
]

[project.optional-dependencies]
zotero = [
    "zotero-core>=1.0.0",  # 可选依赖
]
all = ["paper-feed[zotero]"]
```

#### 3. 用户安装选项

**方案 1: 仅使用 paper-feed**
```bash
# 采集论文,导出为 JSON
pip install paper-feed

python -c "
from paper_feed import RSSSource, FilterPipeline, JSONAdapter

source = RSSSource('https://arxiv.org/rss/cs.AI')
papers = await source.fetch_papers()

filtered = await FilterPipeline().filter(papers, criteria)
await JSONAdapter().export(filtered.papers, 'papers.json')
"
```

**方案 2: paper-feed + Zotero 导出**
```bash
# 采集论文,导出到 Zotero
pip install paper-feed[zotero]

python -c "
from paper_feed import RSSSource, FilterPipeline, ZoteroAdapter

source = RSSSource('https://arxiv.org/rss/cs.AI')
papers = await source.fetch_papers()

filtered = await FilterPipeline().filter(papers, criteria)
adapter = ZoteroAdapter(library_id='user_123', api_key='...')
await adapter.export(filtered.papers)
"
```

**方案 3: 通过 zotero-mcp 使用**
```bash
# 完整的 Zotero MCP 体验
pip install zotero-mcp[full]  # 包含 paper-feed

# zotero-mcp 依赖 paper-feed 作为可选依赖
# pip install paper-feed 会自动安装
```

## 迁移步骤

### Phase 1: 创建 paper-feed 独立仓库 (Week 1-2)

```bash
# 1. 创建新仓库
mkdir paper-feed
cd paper-feed
git init

# 2. 复制代码结构
cp -r ../zotero-mcp/src/services/rss/* src/paper_feed/sources/
cp -r ../zotero-mcp/src/services/gmail/* src/paper_feed/sources/
cp -r ../zotero-mcp/src/services/common/ai_filter.py src/paper_feed/filters/

# 3. 创建独立的 pyproject.toml
# 4. 编写独立的 README.md
# 5. 发布到 PyPI: pip install paper-feed
```

### Phase 2: 调整 zotero-mcp 依赖 (Week 3)

**zotero-mcp/pyproject.toml**:
```toml
[project]
name = "zotero-mcp"
version = "3.0.0"
dependencies = [
    "fastmcp>=2.14.0",
    "pydantic>=2.0.0",
    "zotero-core>=1.0.0",  # 核心依赖
    "paper-analyzer>=1.0.0",  # 核心依赖
]

[project.optional-dependencies]
ingestion = [
    "paper-feed>=1.0.0",  # 可选: 论文采集功能
]
full = ["zotero-mcp[ingestion]"]
```

**zotero-mcp 集成调整**:
```python
# zotero-mcp/src/integration/feed_integration.py
from typing import Optional

class FeedIntegration:
    """RSS/Gmail 采集集成"""

    def __init__(self):
        try:
            from paper_feed import RSSSource, GmailSource, FilterPipeline
            self.available = True
        except ImportError:
            self.available = False
            print("Warning: paper-feed not installed. Install with: pip install zotero-mcp[ingestion]")

    async def fetch_from_rss(self, feed_url: str):
        if not self.available:
            raise RuntimeError("paper-feed is required for RSS fetching")

        from paper_feed import RSSSource, ZoteroAdapter
        # ... 实现
```

### Phase 3: 更新文档 (Week 4)

1. **paper-feed README**
   - 独立使用指南
   - 不依赖 Zotero 的示例
   - Zotero 导出作为可选功能

2. **zotero-mcp README**
   - 标注 paper-feed 为可选依赖
   - 提供无 paper-feed 的使用场景

3. **交叉引用文档**
   - paper-feed 如何配合 zotero-core 使用
   - zotero-mcp 如何集成 paper-feed

## 收益分析

### ✅ 优势

1. **更广泛的适用性**
   - paper-feed 可以被任何项目使用
   - 不局限于 Zotero 生态

2. **更清晰的职责边界**
   - paper-feed: 学术论文采集
   - zotero-core: Zotero 数据操作
   - paper-analyzer: PDF 分析
   - zotero-mcp: MCP 集成层

3. **更灵活的依赖管理**
   - 用户可以选择仅安装需要的模块
   - 减少不必要的依赖

4. **更快的开发迭代**
   - paper-feed 可以独立发版
   - 不受 zotero-mcp 发布周期限制

### ⚠️ 挑战

1. **额外的维护成本**
   - 需要维护独立的仓库
   - 需要同步版本兼容性

2. **用户困惑**
   - 需要清晰的文档说明各模块关系
   - 需要提供多种安装方案

3. **依赖兼容性**
   - paper-feed 的 ZoteroAdapter 需要 zotero-core
   - 需要保证版本兼容性

## 推荐的实施顺序

### Step 1: 准备 paper-feed 独立仓库 ✅ 优先级最高

```bash
# 创建仓库
gh repo create paper-feed --public --description="Academic paper collection framework (RSS/Gmail)"

# 复制代码
git clone https://github.com/yourname/zotero-mcp.git
cd zotero-mcp
git worktree add ../paper-feed-independent main

# 重构代码为独立包
cd ../paper-feed-independent
# 重构目录结构,创建 pyproject.toml
```

### Step 2: 发布 paper-feed v1.0.0

```bash
cd paper-feed
uv publish  # 或 twine upload
```

### Step 3: 更新 zotero-mcp 依赖

```bash
cd zotero-mcp
# 修改 pyproject.toml
# 将 paper-feed 改为外部依赖
# 发布 zotero-mcp v3.0.0
```

### Step 4: 文档和示例更新

- 创建 paper-feed 独立使用示例
- 更新 zotero-mcp 文档说明可选依赖
- 创建多模块集成示例

## 版本兼容性策略

### Semantic Versioning

```
paper-feed:     1.0.0  →  1.1.0  →  2.0.0
zotero-core:    1.0.0  →  1.0.0  →  2.0.0
zotero-mcp:     3.0.0  →  3.1.0  →  4.0.0

兼容性规则:
- paper-feed 1.x 兼容 zotero-core 1.x
- 破坏性变更同步升级主版本号
```

### 依赖约束

```toml
# paper-feed/pyproject.toml
[project.dependencies]
# 无硬依赖

[project.optional-dependencies]
zotero = [
    "zotero-core>=1.0.0,<2.0.0",  # 明确版本约束
]
```

## 检查清单

### paper-feed 独立化清单

- [ ] 创建独立的 GitHub 仓库
- [ ] 设置独立的 PyPI 包名: `paper-feed`
- [ ] 重构代码结构,移除 zotero-mcp 内部依赖
- [ ] 调整 ZoteroAdapter 为外部依赖
- [ ] 编写独立的 README.md
- [ ] 创建独立的使用示例
- [ ] 设置 CI/CD (GitHub Actions)
- [ ] 发布 v1.0.0 到 PyPI

### zotero-mcp 调整清单

- [ ] 移除 paper-feed 相关代码
- [ ] 更新 pyproject.toml 依赖
- [ ] 实现 FeedIntegration (可选依赖检查)
- [ ] 更新文档说明 paper-feed 为可选
- [ ] 更新 CHANGELOG.md
- [ ] 发布 v3.0.0

## 需要调整的文档

1. ✅ **本文档** - paper-feed 独立化说明
2. ⏳ **paper-feed README** - 独立使用指南
3. ⏳ **zotero-mcp README** - 可选依赖说明
4. ⏳ **modular-refactor-design.md** - 更新架构图
5. ⏳ **创建 PAPER_FEED_INTEGRATION.md** - 集成指南

---

**文档版本**: 2.0 (独立化调整)
**最后更新**: 2025-02-06
