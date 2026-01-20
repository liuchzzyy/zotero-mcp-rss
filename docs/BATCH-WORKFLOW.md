# Batch PDF Analysis Workflow

A powerful batch workflow system for analyzing research papers in your Zotero library using AI (DeepSeek, OpenAI, or Gemini).

## Overview

The workflow system provides two modes for analyzing PDFs:

- **Mode A (Prepare)**: Collect PDF content and annotations, return to AI client for manual review
- **Mode B (Auto-analyze)**: Fully automatic analysis with built-in LLM, creates Markdown notes in Zotero

### Key Features

✅ **Batch Processing**: Analyze multiple papers at once (recommended ~20 papers per batch)  
✅ **Checkpoint/Resume**: Automatically saves progress, resume interrupted workflows  
✅ **Multi-provider LLM**: Supports DeepSeek (recommended), OpenAI, Gemini  
✅ **Chinese Academic Template**: Structured note format for research analysis  
✅ **Full-text + Annotations**: Extracts both PDF content and your highlights/comments  
✅ **Markdown → HTML**: Converts generated notes to Zotero-compatible HTML  

## Quick Start

### 1. Setup API Keys

Set at least one LLM provider API key:

```bash
# DeepSeek (Recommended - lowest cost, ~¥0.1 per paper)
export DEEPSEEK_API_KEY=sk-...

# OR OpenAI
export OPENAI_API_KEY=sk-...

# OR Gemini
export GEMINI_API_KEY=...
```

Add these to your MCP client config (e.g., Claude Desktop config) or standalone config.

### 2. Usage Examples

#### Mode A: Prepare Analysis (Manual Review)

Use this when you want to review PDF content before analysis:

```
User: "准备分析 '催化剂研究' 收藏集中的最近 5 篇论文"

Claude calls: zotero_prepare_analysis(
    source="collection",
    collection_name="催化剂研究",
    limit=5
)

Returns: {
    "success": true,
    "count": 5,
    "items": [
        {
            "key": "ABC123",
            "title": "Paper Title",
            "fulltext": "Full PDF content...",
            "annotations": [...],
            "metadata": {...}
        }
    ]
}
```

You can then ask Claude to analyze this content using its built-in models.

#### Mode B: Automatic Batch Analysis

Fully automated workflow with checkpoint/resume:

```
User: "批量分析最近 10 篇论文，使用 DeepSeek"

Claude calls: zotero_batch_analyze_pdfs(
    source="recent",
    limit=10,
    llm_provider="deepseek"
)

Returns: {
    "success": true,
    "workflow_id": "wf_20260120_214530_abc",
    "processed": 10,
    "failed": 0,
    "status": "completed",
    "notes_created": [
        {"item_key": "ABC123", "note_key": "NOTE1"},
        ...
    ]
}
```

Each paper gets a **structured Markdown note** saved to Zotero, following the Chinese academic template.

### 3. Checkpoint/Resume

If the workflow is interrupted (network error, rate limit, etc.), resume from where it stopped:

```
# List all workflows and their status
Claude calls: zotero_list_workflows()

# Resume a specific workflow
Claude calls: zotero_resume_workflow(
    workflow_id="wf_20260120_214530_abc",
    llm_provider="deepseek"
)
```

Workflow state is saved in `~/.config/zotero-mcp/workflows/`.

## Analysis Template Structure

The generated notes follow this Chinese academic structure:

```markdown
# 论文标题

**作者**: Author1, Author2  
**年份**: 2024  
**来源**: Zotero Item Key

---

## 一、粗读筛选

**相关性评估**: [高度相关/中等相关/低度相关]  
**阅读建议**: [精读/泛读/略过]

## 二、前言及文献综述

- **研究背景**: [背景描述]
- **研究现状**: [现有研究总结]
- **研究不足**: [现有问题]

## 三、创新点

### 科学问题
- [提出的科学问题]

### 制备方法
- [新的制备方法]

### 研究思路
- [独特的研究思路]

### 工具
- [新工具或技术]

### 理论
- [理论创新]

## 四、笔记原子化

### 制备
- [制备方法详细笔记]

### 表征
- [表征技术和结果]

### 性能
- [性能测试和数据]

### 机制
- [机理分析]

### 理论
- [理论计算/模拟]

## 五、思考

### 优点
- [论文优点]

### 缺点
- [论文不足]

### 疑问
- [待解决的疑问]

### 启发
- [对自己研究的启发]
```

## Available Tools

### Core Workflow Tools

#### `zotero_prepare_analysis`

Prepare papers for analysis (Mode A).

**Parameters**:
- `source`: "collection" or "recent"
- `collection_name`: Collection name (if source=collection)
- `limit`: Number of items (default: 10)

**Returns**: List of items with full-text, annotations, metadata

---

#### `zotero_batch_analyze_pdfs`

Automatic batch analysis with LLM (Mode B).

**Parameters**:
- `source`: "collection" or "recent"
- `collection_name`: Collection name (if source=collection)
- `limit`: Number of items (default: 20)
- `llm_provider`: "deepseek", "openai", or "gemini"

**Returns**: Workflow result with status and created note keys

---

#### `zotero_resume_workflow`

Resume interrupted workflow.

**Parameters**:
- `workflow_id`: Workflow ID from previous batch_analyze call
- `llm_provider`: LLM provider to use

**Returns**: Resume result with processed/failed counts

---

#### `zotero_list_workflows`

List all workflows and their status.

**Returns**: List of workflows with completion status

---

#### `zotero_find_collection`

Find collections by name (fuzzy matching).

**Parameters**:
- `query`: Collection name to search
- `limit`: Max results (default: 5)

**Returns**: Matching collections with scores

## Configuration

### Environment Variables

```bash
# LLM Provider API Keys (set at least one)
DEEPSEEK_API_KEY=sk-...
OPENAI_API_KEY=sk-...
GEMINI_API_KEY=...

# Optional: Override default models
DEEPSEEK_MODEL=deepseek-chat          # Default
OPENAI_MODEL=gpt-4o-mini              # Default
GEMINI_MODEL=gemini-2.0-flash-exp     # Default

# Zotero credentials (required for note creation)
ZOTERO_API_KEY=...
ZOTERO_LIBRARY_ID=...
```

### Claude Desktop Config Example

```json
{
  "mcpServers": {
    "zotero": {
      "command": "zotero-mcp",
      "env": {
        "ZOTERO_LOCAL": "true",
        "ZOTERO_API_KEY": "your_api_key",
        "ZOTERO_LIBRARY_ID": "your_library_id",
        "DEEPSEEK_API_KEY": "sk-..."
      }
    }
  }
}
```

## Cost Estimation

Approximate costs per paper (based on ~10k tokens per paper):

| Provider | Model | Cost per Paper | 100 Papers |
|----------|-------|----------------|------------|
| **DeepSeek** | deepseek-chat | ~¥0.10 | ~¥10 |
| OpenAI | gpt-4o-mini | ~$0.015 | ~$1.50 |
| Gemini | gemini-2.0-flash | ~$0.02 | ~$2.00 |

**Recommendation**: Use DeepSeek for best cost-performance ratio.

## Workflow State Files

Workflow checkpoints are stored in:

```
~/.config/zotero-mcp/workflows/
├── wf_20260120_214530_abc.json
├── wf_20260121_103045_def.json
└── ...
```

Each file contains:
- Item keys (total, processed, failed, remaining)
- Metadata (collection name, LLM provider)
- Created note keys
- Timestamps

Automatically cleaned up after 30 days.

## Troubleshooting

### "No LLM provider API key found"

**Solution**: Set at least one of `DEEPSEEK_API_KEY`, `OPENAI_API_KEY`, or `GEMINI_API_KEY`.

### "Failed to create note"

**Solution**: Ensure `ZOTERO_API_KEY` and `ZOTERO_LIBRARY_ID` are set, and you have write permissions.

### Analysis quality is poor

**Solution**: 
1. Use `--fulltext` when running `zotero-mcp update-db` to index full PDF content
2. Try a more powerful model: `DEEPSEEK_MODEL=deepseek-reasoner` or `OPENAI_MODEL=gpt-4o`

### Workflow stuck/interrupted

**Solution**: Use `zotero_list_workflows()` to find the workflow ID, then `zotero_resume_workflow(workflow_id=...)`.

### Rate limit errors

**Solution**: The workflow automatically retries with exponential backoff. If persistent, check your API provider's rate limits.

## Architecture

```
User Request
    ↓
MCP Tools (workflow.py)
    ├─→ zotero_prepare_analysis
    ├─→ zotero_batch_analyze_pdfs
    ├─→ zotero_resume_workflow
    └─→ zotero_list_workflows
    ↓
WorkflowService (services/workflow.py)
    ├─→ CheckpointManager - State persistence
    ├─→ LLMClient - DeepSeek/OpenAI/Gemini
    ├─→ DataAccessService - Zotero API
    └─→ markdown_to_html - Format conversion
    ↓
Zotero API (create_note)
```

## Development

### Running Tests

```bash
# Install test dependencies
pip install -e ".[dev]"

# Run workflow tests
pytest tests/test_workflow.py -v

# Run all tests
pytest -v
```

### Adding Custom Templates

Edit `src/zotero_mcp/clients/llm.py` and modify `ANALYSIS_TEMPLATE` to customize the note structure.

## Related Documentation

- [Main README](../README.md)
- [Structured Output Examples](./STRUCTURED-OUTPUT-EXAMPLES.md)
- [Implementation Guide](../IMPLEMENTATION_GUIDE.md) - Developer details
