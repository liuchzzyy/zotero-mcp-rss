"""
Workflow tools for Zotero MCP.

Provides MCP tools for batch PDF analysis workflows.
"""

from fastmcp import Context, FastMCP
from mcp.types import ToolAnnotations

from zotero_mcp.models.workflow import (
    BatchAnalyzeInput,
    BatchAnalyzeResponse,
    CollectionMatch,
    FindCollectionInput,
    FindCollectionResponse,
    PrepareAnalysisInput,
    PrepareAnalysisResponse,
    ResumeWorkflowInput,
    WorkflowInfo,
    WorkflowListResponse,
)
from zotero_mcp.services.checkpoint import get_checkpoint_manager
from zotero_mcp.services.data_access import get_data_service
from zotero_mcp.services.workflow import get_workflow_service


def register_workflow_tools(mcp: FastMCP) -> None:
    """Register all workflow tools with the MCP server."""

    @mcp.tool(
        name="zotero_prepare_analysis",
        annotations=ToolAnnotations(
            title="Prepare PDF Analysis Data (Mode A)",
            readOnlyHint=True,
            destructiveHint=False,
            idempotentHint=True,
            openWorldHint=False,
        ),
    )
    async def prepare_analysis(
        params: PrepareAnalysisInput, ctx: Context
    ) -> PrepareAnalysisResponse:
        """
        准备论文分析数据，返回给 AI 客户端进行分析（模式 A）。

        此工具收集所有必要的数据（元数据、PDF 全文、批注）并返回给 AI 客户端。
        AI 客户端可以逐个审核并生成分析内容，然后手动调用 zotero_create_note 保存。

        Args:
            params: 包含:
                - source: "collection" | "recent" - 数据来源
                - collection_name: 收藏集名称（支持模糊匹配）
                - collection_key: 收藏集 key（优先于 name）
                - days: 最近天数（source="recent" 时）
                - limit: 最大准备数量
                - include_annotations: 是否包含 PDF 批注
                - include_multimodal: 是否提取 PDF 图像/表格
                - skip_existing_notes: 跳过已有笔记的条目

        Returns:
            PrepareAnalysisResponse: 包含准备好的分析数据

        Example:
            Use when: "准备分析 '催化剂研究' 收藏集中的论文"
            Use when: "获取最近添加的 10 篇论文的分析数据"
        """
        try:
            workflow_service = get_workflow_service()

            result = await workflow_service.prepare_analysis(
                source=params.source,
                collection_key=params.collection_key,
                collection_name=params.collection_name,
                days=params.days,
                limit=params.limit,
                include_annotations=params.include_annotations,
                include_multimodal=params.include_multimodal,
                skip_existing=params.skip_existing_notes,
            )

            await ctx.info(
                f"已准备 {result.prepared_items}/{result.total_items} 个条目的分析数据"
            )

            return result

        except Exception as e:
            await ctx.error(f"准备分析数据失败: {str(e)}")
            return PrepareAnalysisResponse(
                success=False,
                error=f"准备分析失败: {str(e)}",
                total_items=0,
                prepared_items=0,
                items=[],
            )

    @mcp.tool(
        name="zotero_batch_analyze_pdfs",
        task=True,  # Enable background task mode
        annotations=ToolAnnotations(
            title="Batch Analyze PDFs with LLM (Mode B)",
            readOnlyHint=False,
            destructiveHint=False,
            idempotentHint=False,
            openWorldHint=False,
        ),
    )
    async def batch_analyze_pdfs(
        params: BatchAnalyzeInput, ctx: Context
    ) -> BatchAnalyzeResponse:
        """
        批量自动分析 PDF 并生成结构化笔记（模式 B）。

        使用内置 LLM（DeepSeek 或 Claude CLI）自动分析每篇论文，
        按照预定义模板生成 Markdown 格式笔记并保存到 Zotero。

        支持断点续传：如果中途中断，可以使用返回的 workflow_id 继续处理。

        Args:
            params: 包含:
                - source: "collection" | "recent" - 数据来源
                - collection_name: 收藏集名称
                - collection_key: 收藏集 key
                - days: 最近天数
                - limit: 最大处理数量（默认 20）
                - resume_workflow_id: 断点续传的工作流 ID
                - skip_existing_notes: 跳过已有笔记的条目
                - include_annotations: 包含 PDF 批注
                - include_multimodal: 提取 PDF 图像/表格
                - llm_provider: "deepseek" | "claude-cli" | "auto"
                - llm_model: 模型名称（可选）
                - dry_run: 仅预览，不创建笔记

        Returns:
            BatchAnalyzeResponse: 包含工作流 ID 和处理结果

        Example:
            Use when: "自动分析 '催化剂研究' 收藏集中的论文"
            Use when: "使用 DeepSeek 分析最近 20 篇论文"

        Note:
            - 需要配置 LLM API Key（DEEPSEEK_API_KEY）或 Claude CLI
            - 需要 Web API 访问权限以创建笔记
            - 处理时间较长，建议使用后台任务模式
        """
        try:
            workflow_service = get_workflow_service()

            # Progress callback
            async def progress_callback(current: int, total: int, message: str):
                await ctx.report_progress(current, total, message)

            await ctx.info("开始批量分析...")

            result = await workflow_service.batch_analyze(
                source=params.source,
                collection_key=params.collection_key,
                collection_name=params.collection_name,
                days=params.days,
                limit=params.limit,
                resume_workflow_id=params.resume_workflow_id,
                skip_existing=params.skip_existing_notes,
                include_annotations=params.include_annotations,
                include_multimodal=params.include_multimodal,
                llm_provider=params.llm_provider,
                llm_model=params.llm_model,
                template=params.template,
                dry_run=params.dry_run,
                progress_callback=progress_callback,
            )

            # Report final status
            if result.success:
                await ctx.info(
                    f"批量分析完成: 成功 {result.processed}, "
                    f"跳过 {result.skipped}, 失败 {result.failed}"
                )
            else:
                await ctx.error(f"批量分析失败: {result.error}")

            return result

        except Exception as e:
            await ctx.error(f"批量分析异常: {str(e)}")
            return BatchAnalyzeResponse(
                success=False,
                error=f"批量分析异常: {str(e)}",
                workflow_id="",
                total_items=0,
                processed=0,
                failed=0,
            )

    @mcp.tool(
        name="zotero_resume_workflow",
        task=True,
        annotations=ToolAnnotations(
            title="Resume Interrupted Workflow",
            readOnlyHint=False,
            destructiveHint=False,
            idempotentHint=False,
            openWorldHint=False,
        ),
    )
    async def resume_workflow(
        params: ResumeWorkflowInput, ctx: Context
    ) -> BatchAnalyzeResponse:
        """
        继续之前中断的批量分析工作流。

        从保存的检查点恢复工作流状态，继续处理未完成的条目。

        Args:
            params: 包含:
                - workflow_id: 要继续的工作流 ID

        Returns:
            BatchAnalyzeResponse: 处理结果

        Example:
            Use when: "继续工作流 wf_abc123"
            Use when: "恢复之前中断的分析任务"
        """
        try:
            checkpoint_manager = get_checkpoint_manager()

            # Load workflow state
            workflow_state = checkpoint_manager.load_state(params.workflow_id)
            if not workflow_state:
                return BatchAnalyzeResponse(
                    success=False,
                    error=f"工作流 {params.workflow_id} 不存在",
                    workflow_id=params.workflow_id,
                    total_items=0,
                    processed=0,
                    failed=0,
                )

            await ctx.info(
                f"恢复工作流 {params.workflow_id}: "
                f"已完成 {len(workflow_state.processed_keys)}/{workflow_state.total_items}"
            )

            # Resume using batch_analyze
            workflow_service = get_workflow_service()

            async def progress_callback(current: int, total: int, message: str):
                await ctx.report_progress(current, total, message)

            # Get metadata from workflow state
            metadata = workflow_state.metadata
            llm_provider = metadata.get("llm_provider", "auto")
            llm_model = metadata.get("llm_model")
            include_annotations = metadata.get("include_annotations", True)

            result = await workflow_service.batch_analyze(
                source=workflow_state.source_type,
                collection_key=workflow_state.source_identifier,
                days=7,  # Default, will be ignored for collection source
                limit=workflow_state.total_items,
                resume_workflow_id=params.workflow_id,
                skip_existing=True,
                include_annotations=include_annotations,
                llm_provider=llm_provider,
                llm_model=llm_model,
                dry_run=False,
                progress_callback=progress_callback,
            )

            if result.success:
                await ctx.info(f"工作流恢复完成: {params.workflow_id}")

            return result

        except Exception as e:
            await ctx.error(f"恢复工作流失败: {str(e)}")
            return BatchAnalyzeResponse(
                success=False,
                error=f"恢复失败: {str(e)}",
                workflow_id=params.workflow_id,
                total_items=0,
                processed=0,
                failed=0,
            )

    @mcp.tool(
        name="zotero_list_workflows",
        annotations=ToolAnnotations(
            title="List Batch Analysis Workflows",
            readOnlyHint=True,
            destructiveHint=False,
            idempotentHint=True,
            openWorldHint=False,
        ),
    )
    async def list_workflows(ctx: Context) -> WorkflowListResponse:
        """
        列出所有批量分析工作流及其状态。

        显示所有保存的工作流，包括进度、状态等信息。

        Returns:
            WorkflowListResponse: 工作流列表

        Example:
            Use when: "显示所有分析工作流"
            Use when: "查看批量分析任务状态"
        """
        try:
            checkpoint_manager = get_checkpoint_manager()

            # Get all workflows
            workflows = checkpoint_manager.list_workflows(status_filter="all")

            # Convert to WorkflowInfo
            workflow_infos = []
            for wf in workflows:
                workflow_infos.append(
                    WorkflowInfo(
                        workflow_id=wf.workflow_id,
                        source_type=wf.source_type,
                        source_identifier=wf.source_identifier,
                        total_items=wf.total_items,
                        processed=len(wf.processed_keys),
                        failed=len(wf.failed_keys),
                        status=wf.status,
                        created_at=wf.created_at,
                        updated_at=wf.updated_at,
                    )
                )

            return WorkflowListResponse(
                count=len(workflow_infos),
                workflows=workflow_infos,
            )

        except Exception as e:
            await ctx.error(f"获取工作流列表失败: {str(e)}")
            return WorkflowListResponse(
                success=False,
                error=f"获取列表失败: {str(e)}",
                count=0,
                workflows=[],
            )

    @mcp.tool(
        name="zotero_find_collection",
        annotations=ToolAnnotations(
            title="Find Collection by Name",
            readOnlyHint=True,
            destructiveHint=False,
            idempotentHint=True,
            openWorldHint=False,
        ),
    )
    async def find_collection(
        params: FindCollectionInput, ctx: Context
    ) -> FindCollectionResponse:
        """
        按名称查找收藏集。

        支持模糊匹配，返回匹配的收藏集及其匹配分数。

        Args:
            params: 包含:
                - name: 收藏集名称
                - exact_match: 是否要求精确匹配

        Returns:
            FindCollectionResponse: 匹配的收藏集列表

        Example:
            Use when: "查找名为 '催化剂' 的收藏集"
            Use when: "搜索收藏集 'research'"
        """
        try:
            data_service = get_data_service()

            matches = await data_service.find_collection_by_name(
                name=params.name,
                exact_match=params.exact_match,
            )

            # Convert to CollectionMatch
            collection_matches = []
            for match in matches:
                data = match.get("data", {})
                collection_matches.append(
                    CollectionMatch(
                        key=data.get("key", ""),
                        name=data.get("name", ""),
                        item_count=data.get("numItems"),
                        parent_key=(
                            data.get("parentCollection")
                            if data.get("parentCollection") is not False
                            else None
                        ),
                        match_score=match.get("match_score", 1.0),
                    )
                )

            if collection_matches:
                await ctx.info(f"找到 {len(collection_matches)} 个匹配的收藏集")
            else:
                await ctx.info(f"未找到匹配 '{params.name}' 的收藏集")

            return FindCollectionResponse(
                query=params.name,
                count=len(collection_matches),
                matches=collection_matches,
            )

        except Exception as e:
            await ctx.error(f"查找收藏集失败: {str(e)}")
            return FindCollectionResponse(
                success=False,
                error=f"查找失败: {str(e)}",
                query=params.name,
                count=0,
                matches=[],
            )
