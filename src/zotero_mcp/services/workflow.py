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
from zotero_mcp.utils.batch_loader import BatchLoader
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
        # BatchLoader will be initialized with item_service from data_service
        # We access item_service via property to ensure it's initialized
        self.batch_loader = BatchLoader(self.data_service.item_service)

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

        # Optimization: Fetch bundles in batches
        chunk_size = 5

        # We need to map keys to Item objects for metadata not in bundle (like item.title vs bundle.title)
        # Actually bundle['metadata'] has everything.

        for i in range(0, len(items), chunk_size):
            chunk_items = items[i : i + chunk_size]

            # 1. Filter existing notes first (fast check)
            # We can't batch check notes easily without fetching children, which BatchLoader does.
            # But legacy logic checked notes first to avoid heavy fetch.
            # Let's verify existing notes first if skip_existing is True.

            keys_to_fetch = []
            for item in chunk_items:
                if skip_existing:
                    notes = await self.data_service.get_notes(item.key)
                    if notes:
                        skipped_count += 1
                        continue
                keys_to_fetch.append(item.key)

            if not keys_to_fetch:
                continue

            # 2. Parallel Fetch
            bundles = await self.batch_loader.fetch_many_bundles(
                keys_to_fetch,
                include_fulltext=True,
                include_annotations=include_annotations,
                include_bibtex=False,
            )

            # Map bundles by key
            bundle_map = {b["metadata"]["key"]: b for b in bundles}

            for item_key in keys_to_fetch:
                if item_key not in bundle_map:
                    logger.warning(f"Failed to fetch bundle for {item_key}")
                    continue

                bundle = bundle_map[item_key]
                metadata = bundle["metadata"]
                data = metadata.get("data", {})

                # Build AnalysisItem
                try:
                    analysis_item = AnalysisItem(
                        item_key=metadata.get("key"),
                        title=data.get("title", "Unknown"),
                        authors=data.get(
                            "creators", []
                        ),  # Note: this might be raw list, SearchResultItem handles formatting
                        # Wait, AnalysisItem expects formatted strings?
                        # models/workflow.py says: authors: str | None
                        # data_access.get_item returns raw Zotero JSON.
                        # We need to format creators.
                        # Let's use the helper from item service if possible or helper util.
                        # DataAccessService had _api_item_to_result which formatted it.
                        # Here we deal with raw dicts.
                        # Let's try to be robust.
                        date=data.get("date"),
                        journal=data.get("publicationTitle"),
                        doi=data.get("DOI"),
                        pdf_content=bundle.get("fulltext") or "PDF 内容不可用",
                        annotations=bundle.get("annotations", []),
                        metadata={
                            "item_type": data.get("itemType"),
                            "abstract": data.get("abstractNote"),
                            "tags": data.get("tags"),
                        },
                        template_questions=TEMPLATE_QUESTIONS,
                    )

                    # Fix authors format
                    # We need to format the creators list to string
                    from zotero_mcp.utils.helpers import format_creators

                    analysis_item.authors = format_creators(data.get("creators", []))

                    prepared_items.append(analysis_item)
                except Exception as e:
                    logger.warning(f"Failed to build analysis item {item_key}: {e}")

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

        # Process items in batches to balance parallelism and rate limits
        results = []
        processed_count = len(workflow_state.processed_keys)
        total_count = workflow_state.total_items

        chunk_size = 5

        for i in range(0, len(remaining_keys), chunk_size):
            chunk_keys = remaining_keys[i : i + chunk_size]

            # 1. Fetch Bundles Parallel (BatchLoader)
            # We map keys to bundles.
            bundles = await self.batch_loader.fetch_many_bundles(
                chunk_keys,
                include_fulltext=True,
                include_annotations=include_annotations,
                include_bibtex=False,
            )
            bundle_map = {b["metadata"]["key"]: b for b in bundles}

            # 2. Analyze Sequential (LLM)
            for item_key in chunk_keys:
                # Find original item object for progress reporting
                item = next((it for it in items if it.key == item_key), None)
                if not item:
                    continue

                # Report progress
                current = processed_count + len(results) + 1
                if progress_callback:
                    await progress_callback(
                        current,
                        total_count,
                        f"正在分析 ({current}/{total_count}): {item.title[:40]}...",
                    )

                # Check if fetch failed
                if item_key not in bundle_map:
                    # Mark as failed
                    workflow_state.mark_failed(item_key, "Failed to fetch item data")
                    results.append(
                        ItemAnalysisResult(
                            item_key=item.key,
                            title=item.title,
                            success=False,
                            error="Failed to fetch item data",
                        )
                    )
                    continue

                # Analyze using fetched bundle
                result = await self._analyze_single_item(
                    item=item,
                    bundle=bundle_map[item_key],
                    llm_client=llm_client,
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
                    workflow_state.mark_failed(
                        item_key, result.error or "Unknown error"
                    )

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

    async def _analyze_single_item(
        self,
        item: Any,
        bundle: dict[str, Any],
        llm_client: Any,
        skip_existing: bool,
        template: str | None,
        dry_run: bool,
    ) -> ItemAnalysisResult:
        """Analyze a single item using pre-fetched bundle."""
        start_time = time.time()

        try:
            # 1. Check skip condition (using notes from bundle if available, or fetch)
            # Actually bundle has notes if requested.
            # But skip logic might want to verify fresh state?
            # BatchLoader fetches notes if include_notes=True.

            if skip_existing:
                # If bundle has notes, skip
                if bundle.get("notes"):
                    return ItemAnalysisResult(
                        item_key=item.key,
                        title=item.title,
                        success=True,
                        skipped=True,
                        skip_reason="已有分析笔记",
                        processing_time=time.time() - start_time,
                    )

            # 2. Extract Context from Bundle
            metadata = bundle.get("metadata", {})
            # Note: item object (SearchResultItem) has formatted creators, but metadata dict has raw list
            # We can use item.authors or format from metadata

            fulltext = bundle.get("fulltext")
            if not fulltext:
                return ItemAnalysisResult(
                    item_key=item.key,
                    title=item.title,
                    success=False,
                    error="无法获取 PDF 全文内容",
                    processing_time=time.time() - start_time,
                )

            annotations = bundle.get("annotations", [])

            # 3. Call LLM
            markdown_note = await llm_client.analyze_paper(
                title=item.title,
                authors=item.authors,
                journal=metadata.get("data", {}).get("publicationTitle"),
                date=item.date,
                doi=item.doi,
                fulltext=fulltext,
                annotations=annotations,
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
