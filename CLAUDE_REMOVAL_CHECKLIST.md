# 移除 Claude Desktop 相关代码 - 修改清单

## 已完成的修改

### 1. ✅ src/zotero_mcp/utils/config.py
- 移除 `find_claude_config()` 函数
- 移除 `load_claude_config()` 函数
- 移除 `is_claude_configured()` 函数
- 更新 `load_config()` 优先级：只保留 Opencode 和 Standalone 配置

### 2. ✅ src/zotero_mcp/utils/setup.py
- 移除 `update_claude_config()` 函数
- 移除所有 Claude Desktop 相关的命令行参数（`--no-claude`, `--config-path`）
- 简化为只支持 Opencode CLI 和 standalone 配置
- 更新 `main()` 函数，只使用 `write_standalone_config()`

## 待完成的修改

### 3. ⏳ src/zotero_mcp/cli.py
移除以下参数：
```python
# 行 117-118
"--no-claude", action="store_true", help="Skip Claude Desktop config"
"--config-path", help="Path to Claude Desktop config file"
```

### 4. ⏳ src/zotero_mcp/utils/updater.py  
移除 Claude Desktop 配置备份和恢复逻辑：
- 行 153-182: Claude Desktop configs 备份逻辑
- 行 220-232: Claude Desktop config 恢复逻辑

### 5. ⏳ src/zotero_mcp/utils/__init__.py
移除 `find_claude_config` 导出：
```python
# 移除导入
from zotero_mcp.utils.config import (
    find_claude_config,  # <- 移除这行
    ...
)

# 移除导出
__all__ = [
    "find_claude_config",  # <- 移除这行
    ...
]
```

### 6. ⏳ README.md
移除以下章节：
- "For Claude Desktop (example MCP client)" 章节
- "Installing via Smithery" 章节（Smithery 主要用于 Claude Desktop）
- 所有提到 Claude Desktop 的示例和配置说明

保留：
- Opencode CLI 相关内容
- Cherry Studio 等其他 MCP 客户端的说明

### 7. ⏳ 说明.md
移除以下内容：
- 所有 Claude Desktop 配置示例
- "Claude Desktop 配置" 章节
- 测试指南中提到 Claude Desktop 的部分

更新为：
- 只保留 Opencode CLI 的配置示例
- 只保留 Opencode CLI 的测试说明

### 8. ⏳ AGENTS.md
移除所有 Claude Desktop 相关提及，替换为 Opencode CLI 说明

## 快速执行脚本

由于修改较多，建议你执行以下操作：

```bash
# 1. 手动编辑 cli.py，移除第 117-120 行的 Claude 相关参数

# 2. 手动编辑 updater.py，移除第 153-182 行和 220-232 行

# 3. 手动编辑 utils/__init__.py，移除 find_claude_config 导入和导出

# 4. 更新文档（README.md, 说明.md, AGENTS.md）
```

## 测试验证

完成所有修改后，执行以下测试：

```bash
# 1. 检查 import 错误
python -m zotero_mcp.cli --help

# 2. 运行设置
zotero-mcp setup

# 3. 检查配置文件
cat ~/.config/zotero-mcp/config.json

# 4. 测试启动
zotero-mcp serve --transport stdio
```

## 注意事项

1. **不要删除 Opencode 相关代码**
   - `find_opencode_config()`
   - `load_opencode_config()`
   - `is_opencode_configured()`

2. **保留 standalone 配置支持**
   - `write_standalone_config()`
   - `~/.config/zotero-mcp/config.json`

3. **文档更新重点**
   - 将所有 "Claude Desktop" 替换为 "Opencode CLI" 或 "MCP 客户端"
   - 更新配置示例为 Opencode 格式
   - 移除 Claude Desktop 特定的安装说明（Smithery 等）

## 预期结果

完成后，项目将：
- ✅ 只支持 Opencode CLI 配置
- ✅ 只支持 standalone 配置文件
- ✅ 移除所有 Claude Desktop 特定功能
- ✅ 保持与其他 MCP 客户端的兼容性
