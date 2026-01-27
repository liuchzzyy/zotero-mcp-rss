"""
Workflow service for batch PDF analysis.

Provides core business logic for analyzing research papers in batch,
with checkpoint support for resuming interrupted workflows.
"""

from collections.abc import Callable
import logging
import time
from typing import Any, Literal

from zotero_mcp.clients.llm import get_llm_client
from zotero_mcp.models.workflow import (
    AnalysisItem,
    BatchAnalyzeResponse,
    ItemAnalysisResult,
    PrepareAnalysisResponse,
)
from zotero_mcp.services.checkpoint import get_checkpoint_manager
from zotero_mcp.services.data_access import get_data_service
from zotero_mcp.utils.markdown_html import markdown_to_html

logger = logging.getLogger(__name__)


# -------------------- Template Questions --------------------


TEMPLATE_QUESTIONS = [
    "这篇论文的主要研究问题是什么？",
    "引用的文献是否最新、全面？以往文献有什么不足？",
    "本研究聚焦的问题、逻辑思路、可行性和可靠性如何？",
    "作者选题角度是否新颖？有什么价值？",
    "提出了什么新的科学问题？",
    "在制备方法上有什么创新？",
    "研究思路有何独特之处？",
    "使用了什么新的研究工具或技术？",
    "在理论方面有何贡献？",
    "关键的制备方法和步骤是什么？",
    "使用了哪些表征方法？主要结果是什么？",
    "关键性能数据和指标有哪些？",
    "作者提出的机制解释是什么？",
    "理论基础和模型是什么？",
    "这篇论文有什么优点和不足？",
]


# -------------------- Workflow Service --------------------


class WorkflowService:
    """Service for batch PDF analysis workflows."""

    def __init__(self):
        self.data_service = get_data_service()
        self.checkpoint_manager = get_checkpoint_manager()

    async def prepare_analysis(
        self,
        source: str,
        collection_key: str | None = None,
        collection_name: str | None = None,
        days: int = 7,
        limit: int = 20,
        include_annotations: bool = True,
        skip_existing: bool = True,
    ) -> PrepareAnalysisResponse:
        """
        Prepare analysis data for external AI analysis (Mode A).

        Args:
            source: "collection" or "recent"
            collection_key: Collection key (takes precedence)
            collection_name: Collection name for fuzzy matching
            days: Days to look back (for recent mode)
            limit: Maximum items to prepare
            include_annotations: Whether to include PDF annotations
            skip_existing: Skip items that already have notes

        Returns:
            PrepareAnalysisResponse with prepared items
        """
        # Get items based on source
        items = await self._get_items(
            source, collection_key, collection_name, days, limit
        )

        if not items:
            return PrepareAnalysisResponse(
                total_items=0,
                prepared_items=0,
                items=[],
                template_structure={"questions": TEMPLATE_QUESTIONS},
            )

        prepared_items = []
        skipped_count = 0

        for item in items:
            try:
                # Check if already has notes
                if skip_existing:
                    notes = await self.data_service.get_notes(item.key)
                    if notes:
                        skipped_count += 1
                        continue

                # Get metadata
                item_data = await self.data_service.get_item(item.key)
                data = item_data.get("data", {})

                # Get full text
                fulltext = await self.data_service.get_fulltext(item.key)

                # Get annotations if requested
                annotations = []
                if include_annotations:
                    annotations = await self.data_service.get_annotations(item.key)

                # Build AnalysisItem
                analysis_item = AnalysisItem(
                    item_key=item.key,
                    title=item.title,
                    authors=item.authors,
                    date=item.date,
                    journal=data.get("publicationTitle"),
                    doi=item.doi,
                    pdf_content=fulltext or "PDF 内容不可用",
                    annotations=annotations,
                    metadata={
                        "item_type": item.item_type,
                        "abstract": item.abstract,
                        "tags": item.tags,
                    },
                    template_questions=TEMPLATE_QUESTIONS,
                )

                prepared_items.append(analysis_item)

            except Exception as e:
                logger.warning(f"Failed to prepare item {item.key}: {e}")
                continue

        return PrepareAnalysisResponse(
            total_items=len(items),
            prepared_items=len(prepared_items),
            skipped=skipped_count,
            items=prepared_items,
            template_structure={"questions": TEMPLATE_QUESTIONS},
        )

    async def batch_analyze(
        self,
        source: Literal["collection", "recent"],
        collection_key: str | None = None,
        collection_name: str | None = None,
        days: int = 7,
        limit: int = 20,
        resume_workflow_id: str | None = None,
        skip_existing: bool = True,
        include_annotations: bool = True,
        llm_provider: str = "auto",
        llm_model: str | None = None,
        template: str | None = None,
        dry_run: bool = False,
        progress_callback: Callable | None = None,
    ) -> BatchAnalyzeResponse:
        """
        Batch analyze PDFs with automatic LLM processing (Mode B).

        Args:
            source: "collection" or "recent"
            collection_key: Collection key
            collection_name: Collection name
            days: Days to look back
            limit: Maximum items to process
            resume_workflow_id: Workflow ID to resume
            skip_existing: Skip items with existing notes
            include_annotations: Include PDF annotations
            llm_provider: LLM provider to use
            llm_model: Model name (optional)
            template: Custom analysis template
            dry_run: Preview only, don't create notes
            progress_callback: Progress update callback

        Returns:
            BatchAnalyzeResponse with results
        """
        # Load or create workflow state
        workflow_state = None
        if resume_workflow_id:
            workflow_state = self.checkpoint_manager.load_state(resume_workflow_id)
            if not workflow_state:
                return BatchAnalyzeResponse(
                    success=False,
                    error=f"Workflow {resume_workflow_id} not found",
                    workflow_id=resume_workflow_id,
                    total_items=0,
                    processed=0,
                    failed=0,
                )

        # Get items
        items = await self._get_items(
            source, collection_key, collection_name, days, limit
        )

        if not items:
            return BatchAnalyzeResponse(
                workflow_id="",
                total_items=0,
                processed=0,
                skipped=0,
                failed=0,
                status="completed",
            )

        # Create workflow state if new
        if workflow_state is None:
            source_id = collection_key or collection_name or "recent"
            workflow_state = self.checkpoint_manager.create_workflow(
                source_type=source,
                source_identifier=source_id,
                total_items=len(items),
                metadata={
                    "llm_provider": llm_provider,
                    "llm_model": llm_model,
                    "include_annotations": include_annotations,
                },
            )

        # Get remaining items to process
        all_keys = [item.key for item in items]
        remaining_keys = workflow_state.get_remaining_items(all_keys)

        if not remaining_keys:
            workflow_state.status = "completed"
            self.checkpoint_manager.save_state(workflow_state)
            return BatchAnalyzeResponse(
                workflow_id=workflow_state.workflow_id,
                total_items=workflow_state.total_items,
                processed=len(workflow_state.processed_keys),
                skipped=len(workflow_state.skipped_keys),
                failed=len(workflow_state.failed_keys),
                status="completed",
                can_resume=False,
            )

        # Initialize LLM client
        try:
            llm_client = get_llm_client(provider=llm_provider, model=llm_model)
        except Exception as e:
            return BatchAnalyzeResponse(
                success=False,
                error=f"Failed to initialize LLM client: {str(e)}",
                workflow_id=workflow_state.workflow_id,
                total_items=workflow_state.total_items,
                processed=0,
                failed=0,
            )

        # Process items
        results = []
        processed_count = len(workflow_state.processed_keys)
        total_count = workflow_state.total_items

        for i, item_key in enumerate(remaining_keys):
            # Find item
            item = next((it for it in items if it.key == item_key), None)
            if not item:
                continue

            # Report progress
            current = processed_count + i + 1
            if progress_callback:
                await progress_callback(
                    current,
                    total_count,
                    f"正在分析 ({current}/{total_count}): {item.title[:40]}...",
                )

            # Analyze item
            result = await self._analyze_single_item(
                item=item,
                llm_client=llm_client,
                include_annotations=include_annotations,
                skip_existing=skip_existing,
                template=template,
                dry_run=dry_run,
            )

            results.append(result)

            # Update workflow state
            if result.success:
                workflow_state.mark_processed(item_key)
            elif result.skipped:
                workflow_state.mark_skipped(item_key)
            else:
                workflow_state.mark_failed(item_key, result.error or "Unknown error")

            # Save checkpoint after each item
            self.checkpoint_manager.save_state(workflow_state)

        # Final state update
        workflow_state.status = "completed"
        self.checkpoint_manager.save_state(workflow_state)

        # Build response
        total_processed = len(workflow_state.processed_keys)
        total_skipped = len(workflow_state.skipped_keys)
        total_failed = len(workflow_state.failed_keys)

        return BatchAnalyzeResponse(
            workflow_id=workflow_state.workflow_id,
            total_items=workflow_state.total_items,
            processed=total_processed,
            skipped=total_skipped,
            failed=total_failed,
            results=results,
            status="completed",
            can_resume=False,
        )

    async def _check_existing_notes(self, item_key: str) -> bool:
        """Check if item already has notes."""
        try:
            notes = await self.data_service.get_notes(item_key)
            return len(notes) > 0
        except Exception:
            return False

    async def _fetch_item_context(
        self, item_key: str, include_annotations: bool
    ) -> dict[str, Any]:
        """Fetch metadata, fulltext, and annotations for an item."""
        context = {
            "metadata": {},
            "fulltext": None,
            "annotations": [],
            "error": None,
        }

        try:
            # Get item metadata
            item_data = await self.data_service.get_item(item_key)
            context["metadata"] = item_data.get("data", {})

            # Get full text
            context["fulltext"] = await self.data_service.get_fulltext(item_key)

            # Get annotations
            if include_annotations:
                context["annotations"] = await self.data_service.get_annotations(
                    item_key
                )

        except Exception as e:
            context["error"] = str(e)

        return context

    async def _analyze_single_item(
        self,
        item: Any,
        llm_client: Any,
        include_annotations: bool,
        skip_existing: bool,
        template: str | None,
        dry_run: bool,
    ) -> ItemAnalysisResult:
        """Analyze a single item."""
        start_time = time.time()

        try:
            # 1. Check skip condition
            if skip_existing:
                has_notes = await self._check_existing_notes(item.key)
                if has_notes:
                    return ItemAnalysisResult(
                        item_key=item.key,
                        title=item.title,
                        success=True,
                        skipped=True,
                        skip_reason="已有分析笔记",
                        processing_time=time.time() - start_time,
                    )

            # 2. Fetch Context
            context = await self._fetch_item_context(item.key, include_annotations)
            if context.get("error"):
                return ItemAnalysisResult(
                    item_key=item.key,
                    title=item.title,
                    success=False,
                    error=f"数据获取失败: {context['error']}",
                    processing_time=time.time() - start_time,
                )

            fulltext = context.get("fulltext")
            if not fulltext:
                return ItemAnalysisResult(
                    item_key=item.key,
                    title=item.title,
                    success=False,
                    error="无法获取 PDF 全文内容",
                    processing_time=time.time() - start_time,
                )

            # 3. Call LLM
            metadata = context.get("metadata", {})
            markdown_note = await llm_client.analyze_paper(
                title=item.title,
                authors=item.authors,
                journal=metadata.get("publicationTitle"),
                date=item.date,
                doi=item.doi,
                fulltext=fulltext,
                annotations=context.get("annotations"),
                template=template,
            )

            if not markdown_note:
                return ItemAnalysisResult(
                    item_key=item.key,
                    title=item.title,
                    success=False,
                    error="LLM 未返回分析结果",
                    processing_time=time.time() - start_time,
                )

            # 4. Save Result
            note_key = None
            if not dry_run:
                html_note = markdown_to_html(markdown_note)
                result = await self.data_service.create_note(
                    parent_key=item.key,
                    content=html_note,
                    tags=["AI分析", "自动生成"],
                )

                # Extract note key
                if isinstance(result, dict):
                    success = result.get("successful", {})
                    if success:
                        note_data = list(success.values())[0] if success else {}
                        note_key = note_data.get("key", "unknown")

            return ItemAnalysisResult(
                item_key=item.key,
                title=item.title,
                success=True,
                note_key=note_key or "dry_run",
                processing_time=time.time() - start_time,
            )

        except Exception as e:
            logger.error(f"Failed to analyze item {item.key}: {e}")
            return ItemAnalysisResult(
                item_key=item.key,
                title=item.title,
                success=False,
                error=str(e),
                processing_time=time.time() - start_time,
            )

    async def _get_items(
        self,
        source: str,
        collection_key: str | None,
        collection_name: str | None,
        days: int,
        limit: int,
    ) -> list[Any]:
        """Get items based on source."""
        if source == "collection":
            # Find collection
            if collection_name and not collection_key:
                matches = await self.data_service.find_collection_by_name(
                    collection_name
                )
                if not matches:
                    logger.warning(f"Collection not found: {collection_name}")
                    return []
                # Use best match
                collection_key = matches[0].get("data", {}).get("key")

            if not collection_key:
                logger.warning("No collection key provided")
                return []

            # Get items in collection
            items = await self.data_service.get_collection_items(
                collection_key, limit=limit
            )
            return items

        elif source == "recent":
            # Get recent items
            items = await self.data_service.get_recent_items(limit=limit, days=days)
            return items

        else:
            logger.warning(f"Unknown source: {source}")
            return []


# -------------------- Singleton Instance --------------------


_workflow_service: WorkflowService | None = None


def get_workflow_service() -> WorkflowService:
    """Get singleton workflow service instance."""
    global _workflow_service
    if _workflow_service is None:
        _workflow_service = WorkflowService()
    return _workflow_service
