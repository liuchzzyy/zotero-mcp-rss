# Contributing to Zotero MCP

感谢您对 Zotero MCP 项目的关注！我们欢迎各种形式的贡献。

## 📋 目录

- [行为准则](#行为准则)
- [如何贡献](#如何贡献)
- [开发设置](#开发设置)
- [代码规范](#代码规范)
- [提交指南](#提交指南)
- [Pull Request 流程](#pull-request-流程)

---

## 行为准则

本项目遵循 [Contributor Covenant](https://www.contributor-covenant.org/) 行为准则。参与本项目即表示您同意遵守其条款。

---

## 如何贡献

### 报告 Bug

如果您发现了 bug，请：

1. **检查现有 Issues** - 确保问题尚未被报告
2. **创建详细的 Issue** - 包含以下信息：
   - 清晰的标题
   - 详细的问题描述
   - 重现步骤
   - 预期行为 vs 实际行为
   - 环境信息（Python 版本、操作系统等）
   - 相关日志或错误消息

**Issue 模板示例：**
```markdown
**Bug 描述**
简要描述问题

**重现步骤**
1. 调用工具 'zotero_search' with params {...}
2. 观察到错误 '...'

**预期行为**
应该返回 {...}

**实际行为**
返回了 {...}

**环境**
- Python 版本: 3.10
- Zotero MCP 版本: 2.0.0
- 操作系统: Windows 11
```

### 建议新功能

我们欢迎功能建议！请：

1. **检查现有 Issues 和 Discussions** - 避免重复
2. **创建 Feature Request** - 包含：
   - 功能描述
   - 使用场景
   - 可能的实现方案
   - 替代方案

### 改进文档

文档改进同样重要！您可以：

- 修正拼写或语法错误
- 添加示例代码
- 改进现有说明
- 翻译文档

---

## 开发设置

### 前置要求

- Python 3.10+
- Git
- uv

### 本地开发环境搭建

1. **Fork 仓库**
   ```bash
   # 在 GitHub 上 fork 项目
   ```

2. **克隆您的 Fork**
   ```bash
   git clone https://github.com/YOUR_USERNAME/zotero-mcp.git
   cd zotero-mcp
   ```

3. **添加上游仓库**
   ```bash
   git remote add upstream https://github.com/54yyyu/zotero-mcp.git
   ```

4. **安装开发依赖**
   ```bash
   uv sync --all-groups
   ```

5. **验证安装**
   ```bash
   # 运行测试
   uv run pytest

   # 启动服务器
   uv run zotero-mcp serve
   ```

---

## 代码规范

### Python 代码风格

我们遵循以下规范：

- **PEP 8** - Python 代码风格指南
- **Ruff** - 统一的代码格式化和检查（line-length 88）
- **Type Hints** - 所有函数使用类型注解

### 格式化代码

```bash
# 格式化代码
uv run ruff format src/
uv run ruff check --fix src/

# 检查格式
uv run ruff format --check src/
uv run ruff check src/
```

### 代码组织

```python
# 导入顺序（由 ruff 自动处理）
import asyncio  # 标准库
from typing import Any  # 标准库类型

from mcp.server import Server  # 第三方库
from pydantic import Field  # 第三方库

from zotero_mcp.models import SearchInput  # 本地导入
from zotero_mcp.services import get_data_service  # 本地导入
```

### 文档字符串

使用 Google-style docstrings：

```python
def example_function(param1: str, param2: int) -> bool:
    """
    One-line summary of the function.
    
    Detailed description of what the function does,
    including any important notes or caveats.
    
    Args:
        param1: Description of param1
        param2: Description of param2
    
    Returns:
        Description of return value
    
    Raises:
        ValueError: When param1 is empty
    
    Example:
        >>> example_function("test", 42)
        True
    """
```

### 类型注解

```python
# 使用现代 Python 3.10+ 语法
def process_items(items: list[dict[str, Any]]) -> str | None:
    ...

# 不使用旧式语法
def process_items(items: List[Dict[str, Any]]) -> Optional[str]:
    ...
```

---

## 提交指南

### Commit Message 格式

使用 [Conventional Commits](https://www.conventionalcommits.org/) 格式：

```
<type>(<scope>): <subject>

<body>

<footer>
```

**类型 (type):**
- `feat`: 新功能
- `fix`: Bug 修复
- `docs`: 文档更新
- `style`: 代码格式（不影响功能）
- `refactor`: 重构
- `test`: 测试相关
- `chore`: 构建/工具相关

**示例:**

```bash
# 好的 commit message
feat(search): add semantic search pagination support
fix(annotations): correct HTML cleaning in notes
docs(api): update structured output examples
refactor(tools): extract common error handling

# 不好的 commit message
update code
fix bug
changes
```

### Commit Message 最佳实践

1. **使用祈使句** - "Add feature" 而非 "Added feature"
2. **首字母小写** - 除非是专有名词
3. **不加句号** - 主题行不需要句号
4. **限制长度** - 主题行 ≤ 50 字符，正文 ≤ 72 字符
5. **解释原因** - 正文说明"为什么"而非"是什么"

---

## Pull Request 流程

### 1. 创建分支

```bash
# 从最新的 main 创建分支
git checkout main
git pull upstream main
git checkout -b feature/your-feature-name

# 或修复 bug
git checkout -b fix/bug-description
```

### 2. 进行更改

- 编写代码
- 添加测试（如果适用）
- 更新文档
- 运行 linter 和 formatter

### 3. 测试更改

```bash
# 运行测试
uv run pytest

# 运行 linters
uv run ruff check src/
uv run ruff format --check src/
```

### 4. 提交更改

```bash
git add .
git commit -m "feat(scope): description"
```

### 5. 推送到您的 Fork

```bash
git push origin feature/your-feature-name
```

### 6. 创建 Pull Request

1. 在 GitHub 上导航到您的 fork
2. 点击 "New Pull Request"
3. 选择您的分支
4. 填写 PR 描述

**PR 描述模板：**

```markdown
## 描述
简要描述此 PR 的更改

## 更改类型
- [ ] Bug 修复
- [ ] 新功能
- [ ] 文档更新
- [ ] 重构
- [ ] 其他（请说明）

## 相关 Issue
Closes #123

## 测试
- [ ] 已添加新测试
- [ ] 所有测试通过
- [ ] 手动测试通过

## 检查清单
- [ ] 代码遵循项目规范
- [ ] 已运行 linters
- [ ] 已更新相关文档
- [ ] Commit messages 遵循规范

## 截图（如适用）
```

### 7. 代码审查

- 响应审查意见
- 进行必要的更改
- 推送更新

```bash
# 修改后
git add .
git commit -m "refactor: address review comments"
git push origin feature/your-feature-name
```

---

## 开发工作流程

### 添加新工具

1. **定义输入模型** - 在 `src/zotero_mcp/models/` 中创建
2. **定义输出模型** - 在 `src/zotero_mcp/models/common.py` 中添加
3. **实现工具** - 在 `handlers/tools.py` 中实现调用逻辑，并在 `models/schemas.py` 中定义输入模型
4. **添加注释** - 使用 `ToolAnnotations`
5. **编写文档** - Google-style docstrings
6. **添加示例** - 在文档中添加使用示例
7. **测试** - 手动和自动化测试

### 修复 Bug

1. **重现问题** - 创建测试用例
2. **定位根因** - 使用调试工具
3. **实施修复** - 最小化更改范围
4. **验证修复** - 确保测试通过
5. **回归测试** - 确保没有引入新问题

### 更新文档

1. **识别需要更新的文档** - README, API 文档等
2. **进行更改** - 保持清晰和简洁
3. **检查链接** - 确保所有链接有效
4. **审查格式** - Markdown 格式正确

---

## 测试指南

### 运行测试

```bash
# 运行所有测试
uv run pytest

# 运行特定测试
uv run pytest tests/test_search.py

# 带覆盖率报告
uv run pytest --cov=src/zotero_mcp
```

### 编写测试

```python
import pytest
from zotero_mcp.tools.search import search_items

@pytest.mark.asyncio
async def test_search_returns_structured_response():
    """Test that search returns structured response."""
    result = await search_items(
        params=SearchItemsInput(query="test", limit=1)
    )
    
    assert "success" in result
    assert "results" in result
    assert isinstance(result["results"], list)
```

---

## 获取帮助

如有问题：

- **查看文档** - `docs/` 目录
- **搜索 Issues** - 可能已有答案
- **创建 Discussion** - 询问问题
- **加入社区** - （如有）

---

## 许可证

提交代码即表示您同意在与项目相同的 [MIT License](./LICENSE) 下发布您的贡献。

---

感谢您的贡献！🎉
