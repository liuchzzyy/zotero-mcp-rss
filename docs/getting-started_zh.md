# Zotero MCP 使用指南

欢迎使用 **Zotero MCP**！这是一个强大的 Model Context Protocol (MCP) 服务器，它能让 AI 助手（如 Claude Desktop, Opencode 等）直接访问、搜索和分析您的 Zotero 文献库。

本文档将指导您完成安装、配置和日常使用。

---

## 📋 前置要求

1.  **Zotero Desktop**: 需要安装并运行 Zotero 桌面端（推荐）。
2.  **Python 3.10+**: 运行环境。
3.  **Better BibTeX (可选但推荐)**: Zotero 插件，用于生成稳定的引用键 (Citation Keys) 和提取 PDF 注释。
4.  **MCP 客户端**: 如 Claude Desktop App, 或 Opencode CLI。
5.  **uv**: 现代 Python 包管理工具。

---

## 🚀 安装

我们推荐使用 `uv` 安装 `zotero-mcp`，以确保环境隔离和依赖管理的稳定性。

```bash
# 安装为全局工具
uv tool install zotero-mcp

# 验证安装
zotero-mcp version
```

---

## ⚙️ 配置与连接

Zotero MCP 提供了一个方便的交互式设置向导。

### 1. 运行设置向导

在终端中运行：

```bash
zotero-mcp setup
```

该向导会自动执行以下操作：

1.  **检测安装**: 找到 `zotero-mcp` 可执行文件的位置。
2.  **配置 Claude Desktop/Opencode CLI**: 自动检测并更新 Claude 的配置文件
    (`claude_desktop_config.json`, `opencode_config.json`)。
3.  **模式选择**:
    - **本地模式 (Local)**: 直接读取本地 SQLite 数据库（速度极快，支持全文搜索）和本地 API。需要 Zotero 运行时保持开启。
    - **Web 模式**: 通过 Zotero Web API 访问（需要 API Key 和 Library ID）。适用于无法运行 Zotero 桌面端的环境。
4.  **配置语义搜索**: 设置用于 AI 向量搜索的嵌入模型（OpenAI, Gemini 或 本地模型）。

### 2. 手动配置 (如果是 Web 模式)

如果您选择 Web 模式，需要提供：

- **API Key**: 在 Zotero 官网设置中生成。
- **Library ID**: 您的用户 ID。

```bash
zotero-mcp setup --no-local --api-key YOUR_KEY --library-id YOUR_ID
```

---

## 🧠 启用语义搜索 (Semantic Search)

这是 Zotero MCP 最强大的功能之一。它允许您使用自然语言（例如："关于气候变化对农业影响的论文"）来搜索文献，而不仅仅是关键词匹配。

### 1. 初始化/更新数据库

在使用语义搜索之前，必须先建立索引：

```bash
# 基础索引（仅元数据，速度快）
zotero-mcp update-db

# [推荐] 包含全文索引（读取 PDF 内容，速度较慢但更精准）
zotero-mcp update-db --fulltext
```

### 2. 自动更新策略

在 `setup` 过程中，您可以配置数据库的更新频率（启动时、每天、或每 N 天）。您也可以随时手动运行上述命令来更新。

### 3. 查看状态

```bash
zotero-mcp db-status
```

---

## 💡 在 AI 助手中的使用

配置完成后，重启您的 MCP 客户端（如 Claude Desktop/Opencode CLI）。您现在可以用自然语言与您的文献库交互。

### 常用指令示例

#### 🔎 搜索文献

- "帮我找一下关于 **[主题]** 的论文。"
- "搜索 2023 年以后关于 **[关键词]** 的文章。"
- "查找作者是 **[名字]** 的所有著作。"
- （语义搜索）"有哪些论文讨论了与这个概念类似的想法？"

#### 📄 阅读与分析

- "请读取 **[论文标题/Key]** 的全文，并总结核心观点。"
- "这篇论文的结论是什么？"
- "获取 **[论文]** 的所有 PDF 注释和高亮。"

#### 📝 写作辅助

- "为 **[论文]** 生成 BibTeX 引用格式。"
- "根据这几篇论文的内容，写一段文献综述。"
- "查看我最近添加了哪些文献？"

---

## 🛠️ 命令行工具参考

`zotero-mcp` 提供了丰富的 CLI 命令：

| 命令                    | 说明                                   |
| ----------------------- | -------------------------------------- |
| `zotero-mcp setup`      | 运行交互式配置向导                     |
| `zotero-mcp serve`      | 启动 MCP 服务器 (通常由客户端自动调用) |
| `zotero-mcp update-db`  | 更新语义搜索向量数据库                 |
| `zotero-mcp db-status`  | 查看数据库状态和统计信息               |
| `zotero-mcp db-inspect` | 检查数据库中的具体内容                 |
| `zotero-mcp setup-info` | 显示当前的安装路径和配置信息（调试用） |
| `zotero-mcp update`     | 自我更新到最新版本                     |

---

## ❓ 常见问题 (FAQ)

**Q: 找不到 Zotero 数据库？**
A: 请确保您至少运行过一次 Zotero。如果您的数据库在自定义位置，请在 `setup` 过程中指定路径，或使用 `zotero-mcp update-db --db-path /path/to/zotero.sqlite`。

**Q: 全文提取失败？**
A: 请确保 PDF 文件已下载到本地。Zotero MCP 需要直接访问 `storage` 目录下的附件文件。

**Q: 语义搜索报错？**
A: 确保您已运行 `update-db`。如果您使用的是 OpenAI/Gemini 模型，请检查环境变量或配置文件中的 API Key 是否正确。

**Q: 如何卸载？**
A: 使用 `uv tool uninstall zotero-mcp`。配置文件夹位于 `~/.config/zotero-mcp`，可以手动删除。
