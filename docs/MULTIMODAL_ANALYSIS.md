# 多模态PDF分析功能文档

Zotero MCP 提供了强大的多模态PDF分析功能，能够同时处理文本、图像和图表，提供比纯文本分析更深入的理解和总结。

## 功能概述

多模态PDF分析功能支持两种工作模式：

### 模式A：图像分析模式（默认）
- 直接处理PDF文件中的图像和图表
- 保留原始格式和布局信息
- 适合包含大量图表、公式的学术文献

### 模式B：OCR+文本分析模式
- 对PDF页面进行OCR识别
- 结合文本和图像信息进行综合分析
- 适合扫描版PDF或需要精确文本提取的场景

## 快速开始

### 基本用法

```bash
# 分析单个PDF文件
uv run zotero-mcp analyze-pdf "path/to/document.pdf"

# 指定LLM提供商
uv run zotero-mcp analyze-pdf "path/to/document.pdf" --llm-provider deepseek

# 使用OCR模式
uv run zotero-mcp analyze-pdf "path/to/document.pdf" --mode ocr

# 自定义分析主题
uv run zotero-mcp analyze-pdf "path/to/document.pdf" --topic "机器学习在医疗中的应用"

# 批量分析多个文件
uv run zotero-mcp analyze-pdf "doc1.pdf" "doc2.pdf" "doc3.pdf"
```

### 集成到Zotero工作流

```bash
# 批量分析Zotero库中的PDF
uv run zotero-mcp scan --scan-limit 50 --treated-limit 20

# 分析特定集合中的PDF
uv run zotero-mcp analyze-collection "机器学习" --llm-provider deepseek
```

## 详细配置

### LLM提供商选择

| 提供商 | 特点 | 优势 | 适用场景 |
|--------|------|------|----------|
| DeepSeek | 深度学习模型 | 中文理解优秀，成本较低 | 中文文献，学术研究 |
| OpenAI | GPT系列模型 | 多语言支持强，图像分析能力突出 | 英文文献，多模态任务 |
| Gemini | Google模型 | 多模态原生支持，推理能力强 | 复杂图表分析，跨模态任务 |
| Claude | Anthropic模型 | 安全性强，长文本处理优秀 | 大文档分析，需要高质量输出 |

### 环境变量配置

```bash
# 基础配置
ZOTERO_MCP_CLI_LLM_PROVIDER=deepseek
ZOTERO_MCP_CLI_LLM_MODEL=deepseek-chat
ZOTERO_MCP_CLI_LLM_API_KEY=your_api_key

# OCR配置（可选）
ZOTERO_MCP_CLI_LLM_OCR_ENABLED=true
ZOTERO_MCP_CLI_LLM_OCR_LANGUAGES=zh,en

# 分析配置
ZOTERO_MCP_CLI_LLM_MAX_PAGES=50
ZOTERO_MCP_CLI_LLM_MAX_IMAGES=20
ZOTERO_MCP_CLI_LLM_CHUNK_SIZE=2000
```

## 使用示例

### 示例1：学术论文分析

```bash
# 分析包含大量图表的论文
uv run zotero-mcp analyze-pdf "research_paper.pdf" \
  --llm-provider deepseek \
  --mode image \
  --topic "深度学习在计算机视觉中的应用" \
  --output-format markdown

# 结果将包含：
# - 文本总结
# - 图表描述
# - 关键发现
# - 方法论分析
```

### 示例2：技术文档分析

```bash
# 分析API文档
uv run zotero-mcp analyze-pdf "api_documentation.pdf" \
  --llm-provider openai \
  --mode ocr \
  --topic "RESTful API设计最佳实践" \
  --include-code-examples
```

### 示例3：批量报告分析

```bash
# 分析多个市场研究报告
for report in reports/*.pdf; do
  uv run zotero-mcp analyze-pdf "$report" \
    --llm-provider gemini \
    --mode hybrid \
    --topic "市场趋势分析" \
    --save-summary
done
```

## 输出格式

### Markdown格式

```markdown
# 文档标题

## 摘要
[生成的摘要内容]

## 主要发现
- 发现1
- 发现2
- 发现3

## 图表分析
### 图1：数据可视化
[图表描述和分析]

## 关键术语
- 术语1：定义
- 术语2：定义
```

### JSON格式

```json
{
  "title": "文档标题",
  "summary": "文档摘要",
  "key_findings": [
    "发现1",
    "发现2"
  ],
  "charts": [
    {
      "page": 5,
      "description": "图表描述",
      "analysis": "图表分析"
    }
  ],
  "keywords": {
    "术语1": "定义",
    "术语2": "定义"
  }
}
```

## 架构说明

```
┌─────────────────────────────────────────────────┐
│               多模态分析流程                    │
├─────────────────────────────────────────────────┤
│                                                 │
│  PDF输入 → 页面分割 → 图像提取 → OCR(可选) →    │
│                                                 │
│        ↓                    ↓                  │
│                                                 │
│    文本提取              图像分析               │
│                                                 │
│        ↓                    ↓                  │
│                                                 │
│     LLM处理 ←───────── 内容整合 ←─────────       │
│                                                 │
│        ↓                                       │
│                                                 │
│      输出生成                                  │
│                                                 │
└─────────────────────────────────────────────────┘
```

## 性能优化

### 1. 文档预处理

```bash
# 预处理大文档
uv run zotero-mcp analyze-pdf "large_document.pdf" \
  --max-pages 100 \
  --batch-size 10 \
  --parallel-processing
```

### 2. 缓存机制

- 分析结果自动缓存，避免重复处理
- 使用文档哈希值作为缓存键
- 缓存位置：`~/.cache/zotero-mcp/analyses/`

### 3. 并行处理

```bash
# 启用并行处理
uv run zotero-mcp analyze-pdf "document.pdf" \
  --parallel-processes 4 \
  --max-workers 2
```

## 故障排除

### 常见问题

#### 1. OCR识别失败

**症状**：OCR模式返回空结果或错误

**解决方案**：
- 检查PDF是否为扫描件
- 确认OCR语言配置正确
- 尝试不同的OCR引擎：

```bash
# 使用Tesseract OCR
ZOTERO_MCP_CLI_LLM_OCR_ENGINE=tesseract \
uv run zotero-mcp analyze-pdf "document.pdf" --mode ocr
```

#### 2. 图像提取失败

**症状**：无法提取PDF中的图像

**解决方案**：
- 确认PDF包含可提取的图像
- 检查PDF权限设置
- 尝试使用其他图像提取工具：

```bash
# 使用pdfimages提取图像
pdfimages -all document.pdf extracted_images
```

#### 3. LLM API限制

**症状**：API调用失败或超时

**解决方案**：
- 检查API配额和限制
- 增加重试次数：

```bash
# 配置重试参数
ZOTERO_MCP_CLI_LLM_MAX_RETRIES=5 \
ZOTERO_MCP_CLI_LLM_TIMEOUT=300 \
uv run zotero-mcp analyze-pdf "document.pdf"
```

#### 4. 内存不足

**症状**：处理大文档时程序崩溃

**解决方案**：
- 减少同时处理的页面数：
```bash
uv run zotero-mcp analyze-pdf "large_document.pdf" --max-pages 50
```

- 增加可用内存：
```bash
# 增加Python内存限制
uv run --python-memory-limit=8192 zotero-mcp analyze-pdf "document.pdf"
```

### 调试模式

```bash
# 启用详细日志
DEBUG=true uv run zotero-mcp analyze-pdf "document.pdf"

# 保存调试信息
uv run zotero-mcp analyze-pdf "document.pdf" --debug-output debug.log
```

## 高级功能

### 1. 自定义提示模板

创建自定义提示模板文件 `custom_prompt.txt`：

```
请分析以下PDF文档，重点关注：
1. 研究方法和实验设计
2. 主要发现和创新点
3. 实际应用价值
4. 未来研究方向

请用Markdown格式输出，包含代码示例和图表说明。
```

使用自定义模板：

```bash
uv run zotero-mcp analyze-pdf "document.pdf" --custom-prompt custom_prompt.txt
```

### 2. 批量处理流水线

```bash
# 创建批量处理脚本
#!/bin/bash

for pdf in *.pdf; do
  echo "Processing $pdf..."
  uv run zotero-mcp analyze-pdf "$pdf" \
    --llm-provider deepseek \
    --output-dir summaries \
    --save-summary
done

# 合并所有摘要
cat summaries/*.md > combined_summary.md
```

### 3. 自动化工作流

结合定时任务实现自动化分析：

```bash
# 添加到crontab
0 2 * * * cd /path/to/pdf && \
  uv run zotero-mcp scan --scan-limit 100 --treated-limit 10

# 每天凌晨2点自动分析新PDF
```

## 最佳实践

### 1. 文档准备

- 优化PDF文件大小（建议<50MB）
- 确保PDF文本可选中（非扫描件）
- 清理不必要的页面和内容

### 2. 分析策略

- 对于学术论文：使用图像模式，关注实验和数据
- 对于技术文档：使用OCR模式，准确提取代码和配置
- 对于报告文档：使用混合模式，平衡文本和图像分析

### 3. 资源管理

- 合理设置并行进程数
- 启用结果缓存避免重复分析
- 定期清理缓存文件

### 4. 质量控制

- 使用多个LLM提供商交叉验证
- 对重要文档进行人工复核
- 建立分析质量评估标准

## 更新日志

### v2.4.0
- 新增多模态PDF分析功能
- 支持DeepSeek、OpenAI、Gemini、Claude等多个LLM提供商
- 实现图像分析和OCR模式
- 添加批量处理和缓存机制

### v2.3.0
- 支持自定义输出格式
- 优化大文档处理性能
- 增强错误处理和恢复机制

## 贡献指南

欢迎提交问题和功能请求。在提交前请：

1. 检查是否已有相关问题
2. 提供详细的复现步骤
3. 提供错误日志和配置信息
4. 建议具体的改进方案

---

更多详细信息请参考：
- [主README](../README.md)
- [配置指南](../.env.example)
- [API文档](../docs/API.md)