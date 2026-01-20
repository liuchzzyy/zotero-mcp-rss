# Zotero MCP Workflow 实现指南

本文档说明如何完成批量 PDF 分析工作流的剩余实现。

## 📁 已完成的文件

✅ `src/zotero_mcp/models/workflow.py` - Pydantic 模型定义
✅ `src/zotero_mcp/utils/markdown_html.py` - Markdown/HTML 转换器
✅ `src/zotero_mcp/clients/llm.py` - LLM 客户端 (DeepSeek/OpenAI/Gemini)
✅ `src/zotero_mcp/services/checkpoint.py` - 断点续传状态管理
✅ `src/zotero_mcp/services/data_access.py` - 添加了 `find_collection_by_name` 方法

## 📝 待实现的文件

### 1. `src/zotero_mcp/services/workflow.py` - 核心工作流服务

```python
"""
Workflow service for batch PDF analysis.
"""

import logging
import time
from typing import Callable

from zotero_mcp.clients.llm import get_llm_client
from zotero_mcp.models.workflow import (
    AnalysisItem,
    ItemAnalysisResult,
    BatchAnalyzeResponse,
    PrepareAnalysisResponse,
)
from zotero_mcp.services.checkpoint import get_checkpoint_manager, WorkflowState
from zotero_mcp.services.data_access import get_data_service
from zotero_mcp.utils.markdown_html import markdown_to_html

logger = logging.getLogger(__name__)


class WorkflowService:
    """Service for batch PDF analysis workflows."""

    def __init__(self):
        self.data_service = get_data_service()
        self.checkpoint_manager = get_checkpoint_manager()

    async def prepare_analysis(
        self,
        source: str,  # "collection" or "recent"
        collection_key: str | None = None,
        collection_name: str | None = None,
        days: int = 7,
        limit: int = 20,
        include_annotations: bool = True,
        skip_existing: bool = True,
    ) -> PrepareAnalysisResponse:
        """
        准备分析数据（模式 A）- 返回数据给 AI 客户端分析
        
        实现步骤:
        1. 根据 source 获取条目列表
        2. 对每个条目:
           - 获取元数据
           - 获取 PDF 全文 (get_fulltext)
           - 获取 PDF 批注 (get_annotations) 如果 include_annotations=True
           - 检查是否已有笔记 (如果 skip_existing=True)
        3. 组装 AnalysisItem 列表
        4. 返回 PrepareAnalysisResponse
        """
        # TODO: 实现此方法
        pass

    async def batch_analyze(
        self,
        source: str,
        collection_key: str | None = None,
        collection_name: str | None = None,
        days: int = 7,
        limit: int = 20,
        resume_workflow_id: str | None = None,
        skip_existing: bool = True,
        include_annotations: bool = True,
        llm_provider: str = "auto",
        llm_model: str | None = None,
        dry_run: bool = False,
        progress_callback: Callable | None = None,
    ) -> BatchAnalyzeResponse:
        """
        批量分析 PDF（模式 B）- 全自动 LLM 分析
        
        实现步骤:
        1. 如果提供 resume_workflow_id，加载工作流状态；否则创建新的
        2. 获取条目列表
        3. 过滤掉已处理的条目 (使用 workflow_state.get_remaining_items)
        4. 初始化 LLM 客户端
        5. 对每个条目:
           a. 更新进度 (progress_callback)
           b. 获取元数据、全文、批注
           c. 调用 LLM 分析 (llm_client.analyze_paper)
           d. 转换 Markdown → HTML (markdown_to_html)
           e. 创建笔记 (data_service.create_note) 如果不是 dry_run
           f. 更新检查点状态 (workflow_state.mark_processed/mark_failed)
           g. 保存检查点 (checkpoint_manager.save_state)
        6. 返回 BatchAnalyzeResponse
        """
        # TODO: 实现此方法
        pass

    async def _analyze_single_item(
        self,
        item_key: str,
        llm_client,
        include_annotations: bool,
        dry_run: bool,
    ) -> ItemAnalysisResult:
        """分析单个条目的辅助方法"""
        # TODO: 实现此方法
        pass
```

### 2. `src/zotero_mcp/tools/workflow.py` - MCP 工具定义

```python
"""
Workflow tools for Zotero MCP.
"""

from fastmcp import FastMCP, Context
from mcp.types import ToolAnnotations

from zotero_mcp.models.workflow import (
    PrepareAnalysisInput,
    BatchAnalyzeInput,
    ResumeWorkflowInput,
    FindCollectionInput,
    PrepareAnalysisResponse,
    BatchAnalyzeResponse,
    WorkflowListResponse,
    FindCollectionResponse,
)
from zotero_mcp.services.workflow import WorkflowService
from zotero_mcp.services.checkpoint import get_checkpoint_manager
from zotero_mcp.services.data_access import get_data_service


def register_workflow_tools(mcp: FastMCP) -> None:
    """Register workflow tools."""

    workflow_service = WorkflowService()
    checkpoint_manager = get_checkpoint_manager()
    data_service = get_data_service()

    @mcp.tool(
        name="zotero_prepare_analysis",
        annotations=ToolAnnotations(
            title="Prepare PDF Analysis (Mode A)",
            readOnlyHint=True,
        ),
    )
    async def prepare_analysis(
        params: PrepareAnalysisInput, ctx: Context
    ) -> PrepareAnalysisResponse:
        """
        准备论文分析数据，返回给 AI 客户端进行分析。
        
        此工具不执行自动分析，而是收集所有必要的数据（元数据、PDF 全文、批注）
        并返回给 AI 客户端（如 Claude）。AI 客户端可以逐个审核并生成分析。
        """
        try:
            result = await workflow_service.prepare_analysis(
                source=params.source,
                collection_key=params.collection_key,
                collection_name=params.collection_name,
                days=params.days,
                limit=params.limit,
                include_annotations=params.include_annotations,
                skip_existing=params.skip_existing_notes,
            )
            return result
        except Exception as e:
            await ctx.error(f"准备分析失败: {str(e)}")
            return PrepareAnalysisResponse(
                success=False,
                error=str(e),
                total_items=0,
                prepared_items=0,
                items=[],
            )

    @mcp.tool(
        name="zotero_batch_analyze_pdfs",
        task=True,  # 启用后台任务模式
        annotations=ToolAnnotations(
            title="Batch Analyze PDFs (Mode B)",
            readOnlyHint=False,
        ),
    )
    async def batch_analyze_pdfs(
        params: BatchAnalyzeInput, ctx: Context
    ) -> BatchAnalyzeResponse:
        """
        批量自动分析 PDF 并生成结构化笔记。
        
        使用内置 LLM（DeepSeek/OpenAI/Gemini）自动分析每篇论文，
        生成 Markdown 格式笔记并保存到 Zotero。
        
        支持断点续传：如果中途中断，可以使用 resume_workflow_id 继续。
        """
        try:
            # 定义进度回调
            async def progress_callback(current: int, total: int, message: str):
                progress = int((current / total) * 100)
                await ctx.report_progress(progress, 100, message)

            result = await workflow_service.batch_analyze(
                source=params.source,
                collection_key=params.collection_key,
                collection_name=params.collection_name,
                days=params.days,
                limit=params.limit,
                resume_workflow_id=params.resume_workflow_id,
                skip_existing=params.skip_existing_notes,
                include_annotations=params.include_annotations,
                llm_provider=params.llm_provider,
                llm_model=params.llm_model,
                dry_run=params.dry_run,
                progress_callback=progress_callback,
            )
            return result
        except Exception as e:
            await ctx.error(f"批量分析失败: {str(e)}")
            return BatchAnalyzeResponse(
                success=False,
                error=str(e),
                workflow_id="",
                total_items=0,
                processed=0,
                failed=0,
            )

    @mcp.tool(name="zotero_resume_workflow")
    async def resume_workflow(
        params: ResumeWorkflowInput, ctx: Context
    ) -> BatchAnalyzeResponse:
        """继续之前中断的批量分析工作流。"""
        # 调用 batch_analyze_pdfs，传入 resume_workflow_id
        # TODO: 实现

    @mcp.tool(name="zotero_list_workflows")
    async def list_workflows(ctx: Context) -> WorkflowListResponse:
        """列出所有批量分析工作流及其状态。"""
        # TODO: 实现

    @mcp.tool(name="zotero_find_collection")
    async def find_collection(
        params: FindCollectionInput, ctx: Context
    ) -> FindCollectionResponse:
        """按名称查找收藏集。"""
        # TODO: 实现
```

### 3. 注册新工具到 `src/zotero_mcp/tools/__init__.py`

在 `register_all_tools` 函数中添加:

```python
from zotero_mcp.tools.workflow import register_workflow_tools

def register_all_tools(mcp: FastMCP) -> None:
    """Register all MCP tools."""
    register_search_tools(mcp)
    register_item_tools(mcp)
    register_annotation_tools(mcp)
    register_database_tools(mcp)
    register_batch_tools(mcp)
    register_workflow_tools(mcp)  # 新增
```

### 4. 更新配置支持 LLM API Key

在 `src/zotero_mcp/utils/config.py` 中添加 LLM 配置加载。

### 5. 更新依赖 `pyproject.toml`

添加新依赖:

```toml
dependencies = [
    # ... 现有依赖 ...
    "openai>=1.0.0",  # DeepSeek 和 OpenAI 都用这个
    "google-generativeai>=0.3.0",  # Gemini
]
```

## 🚀 使用示例

安装完成后，在 Claude Desktop 中使用:

```
用户: 帮我分析 "催化剂研究" 收藏集中的论文

# 模式 A: AI 客户端分析
Claude 调用: zotero_prepare_analysis(
    source="collection",
    collection_name="催化剂研究",
    limit=5
)

返回: {
    items: [
        {
            key: "ABC123",
            title: "...",
            pdf_content: "...",
            annotations: [...],
            template_questions: [...]
        },
        ...
    ]
}

Claude: (根据每个 item 生成分析，然后逐个调用 zotero_create_note)

---

# 模式 B: 全自动分析
Claude 调用: zotero_batch_analyze_pdfs(
    source="collection",
    collection_name="催化剂研究",
    limit=20,
    llm_provider="deepseek"
)

返回: {
    workflow_id: "wf_abc123",
    processed: 18,
    failed: 2,
    ...
}
```

## 📊 实现优先级

1. **高优先级** (核心功能):
   - ✅ 模型定义
   - ✅ LLM 客户端
   - ✅ 断点续传管理
   - ⏸️ Workflow 服务层（需完成 prepare_analysis 和 batch_analyze）
   - ⏸️ Workflow 工具层（需完成 5 个工具）

2. **中优先级** (辅助功能):
   - 配置系统更新
   - 错误处理增强
   - 单元测试

3. **低优先级** (文档):
   - README 更新
   - 使用示例文档

## ⚠️ 注意事项

1. **API 成本**: 20 篇论文预计消耗 200k-500k tokens，使用 DeepSeek 成本最低
2. **超时处理**: 批量分析使用 `task=True` 后台模式，避免超时
3. **错误恢复**: 单篇失败不影响整体，使用 try/except 包裹每个分析
4. **进度报告**: 使用 `ctx.report_progress` 实时更新进度

## 🔧 调试建议

1. 先测试单个条目分析
2. 使用 `dry_run=True` 测试流程不创建笔记
3. 使用小的 `limit` 值（如 2-3）测试
4. 检查 `~/.config/zotero-mcp/workflows/` 中的状态文件

---

**下一步**: 根据此指南完成 workflow.py 服务层和工具层的详细实现。
