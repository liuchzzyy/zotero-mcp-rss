"""
Workflow service for batch PDF analysis.

Provides core business logic for analyzing research papers in batch,
with checkpoint support for resuming interrupted workflows.
"""

from collections.abc import Callable
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
from zotero_mcp.services.note_parser import get_structured_note_parser
from zotero_mcp.services.note_renderer import get_structured_note_renderer
from zotero_mcp.utils.async_helpers.batch_loader import BatchLoader
from zotero_mcp.utils.config.logging import (
    get_logger,
    log_task_end,
    log_task_start,
)
from zotero_mcp.utils.data.templates import (
    DEFAULT_ANALYSIS_TEMPLATE_JSON,
    get_analysis_questions,
)
from zotero_mcp.utils.formatting.beautify import beautify_ai_note
from zotero_mcp.utils.formatting.helpers import format_creators
from zotero_mcp.utils.formatting.markdown import markdown_to_html

logger = get_logger(__name__)


# -------------------- Workflow Service --------------------


class WorkflowService:
    """Service for batch PDF analysis workflows."""

    BATCH_CHUNK_SIZE = 5

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
        include_multimodal: bool = True,
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
                template_structure={"questions": get_analysis_questions()},
            )

        prepared_items = []
        skipped_count = 0

        # Optimization: Fetch bundles in batches
        chunk_size = self.BATCH_CHUNK_SIZE

        # We need to map keys to Item objects for metadata not in bundle (like item.title vs bundle.title)
        # Actually bundle['metadata'] has everything.

        for i in range(0, len(items), chunk_size):
            chunk_items = items[i : i + chunk_size]

            # 1. Filter existing notes first (fast check)
            keys_to_fetch: list[str] = []
            if skip_existing:
                note_bundles = await self.batch_loader.fetch_many_bundles(
                    [item.key for item in chunk_items],
                    include_fulltext=False,
                    include_annotations=False,
                    include_notes=True,
                    include_multimodal=False,
                )
                note_map = {b["metadata"]["key"]: b for b in note_bundles}
                for item in chunk_items:
                    bundle = note_map.get(item.key)
                    if bundle is None:
                        logger.warning(
                            f"Failed to fetch notes bundle for {item.key}, "
                            "defaulting to fetch full bundle"
                        )
                        keys_to_fetch.append(item.key)
                        continue
                    notes = bundle.get("notes", []) if bundle else []
                    if notes:
                        skipped_count += 1
                        continue
                    keys_to_fetch.append(item.key)
            else:
                keys_to_fetch = [item.key for item in chunk_items]

            if not keys_to_fetch:
                continue

            # 2. Parallel Fetch
            bundles = await self.batch_loader.fetch_many_bundles(
                keys_to_fetch,
                include_fulltext=True,
                include_annotations=include_annotations,
                include_notes=False,
                include_multimodal=include_multimodal,
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

                # Extract multi-modal content (only if include_multimodal is True)
                multimodal = bundle.get("multimodal", {}) if include_multimodal else {}

                # Build AnalysisItem
                try:
                    analysis_item = AnalysisItem(
                        item_key=metadata.get("key"),
                        title=data.get("title", "Unknown"),
                        authors=format_creators(data.get("creators", [])),
                        date=data.get("date"),
                        journal=data.get("publicationTitle"),
                        doi=data.get("DOI"),
                        pdf_content=bundle.get("fulltext") or "PDF 内容不可用",
                        annotations=bundle.get("annotations", []),
                        images=multimodal.get("images", []),
                        tables=multimodal.get("tables", []),
                        metadata={
                            "item_type": data.get("itemType"),
                            "abstract": data.get("abstractNote"),
                            "tags": data.get("tags"),
                        },
                        template_questions=get_analysis_questions(),
                    )

                    prepared_items.append(analysis_item)
                except Exception as e:
                    logger.warning(f"Failed to build analysis item {item_key}: {e}")

        return PrepareAnalysisResponse(
            total_items=len(items),
            prepared_items=len(prepared_items),
            skipped=skipped_count,
            items=prepared_items,
            template_structure={"questions": get_analysis_questions()},
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
        include_multimodal: bool = True,
        llm_provider: str = "auto",
        llm_model: str | None = None,
        template: str | None = None,
        dry_run: bool = False,
        progress_callback: Callable | None = None,
        delete_old_notes: bool = False,
        move_to_collection: str | None = None,
    ) -> BatchAnalyzeResponse:
        """
        Batch analyze PDFs with automatic LLM processing (Mode B).

        Args:
            source: "collection" or "recent"
            collection_key: Collection key
            collection_name: Collection name (alternative to key)
            days: Days to look back
            limit: Maximum results
            resume_workflow_id: Workflow ID to resume
            skip_existing: Skip items with existing notes
            include_annotations: Include PDF annotations
            include_multimodal: Include PDF images/tables
            llm_provider: LLM provider to use
            llm_model: Model name (optional)
            template: Custom analysis template
            dry_run: Preview only, no changes
            progress_callback: Progress update callback
            delete_old_notes: Delete existing notes before creating new ones
            move_to_collection: Collection name to move items to after analysis

        Returns:
            BatchAnalyzeResponse with results
        """
        # Log task start
        task_name = f"Batch Analysis ({source})"
        log_task_start(
            logger,
            task_name,
            source=source,
            collection=collection_key or collection_name or "N/A",
            days=days,
            limit=limit,
            dry_run=dry_run,
        )

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
                    "include_multimodal": include_multimodal,
                },
            )

        # Get remaining items to process
        item_map = {item.key: item for item in items}
        all_keys = list(item_map.keys())
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

        # Auto-select LLM provider if needed
        if llm_provider == "auto":
            # Fetch a sample bundle to check for images
            # Only fetch if include_multimodal is True
            if include_multimodal and remaining_keys:
                sample_keys = remaining_keys[:3]
                try:
                    sample_bundles = await self.batch_loader.fetch_many_bundles(
                        sample_keys,
                        include_fulltext=False,
                        include_annotations=False,
                        include_multimodal=True,
                    )
                    has_images = False
                    for bundle in sample_bundles:
                        sample_multimodal = bundle.get("multimodal", {})
                        if sample_multimodal.get("images"):
                            has_images = True
                            break
                        # Auto-select: prefer multi-modal if images available
                        llm_provider = "claude-cli" if has_images else "deepseek"
                        logger.info(
                            f"Auto-selected LLM provider: {llm_provider} "
                            f"(has_images={has_images})"
                        )
                except Exception as e:
                    logger.warning(
                        f"Failed to check for images during auto-select: {e}"
                    )
                    # Fall back to default
                    llm_provider = "deepseek"
            else:
                # No multi-modal or no items, use text-only LLM
                llm_provider = "deepseek"
                logger.info(f"Auto-selected LLM provider: {llm_provider} (text-only)")

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

        chunk_size = self.BATCH_CHUNK_SIZE

        for i in range(0, len(remaining_keys), chunk_size):
            chunk_keys = remaining_keys[i : i + chunk_size]

            # 1. Fetch Bundles Parallel (BatchLoader)
            # We map keys to bundles.
            bundles = await self.batch_loader.fetch_many_bundles(
                chunk_keys,
                include_fulltext=True,
                include_annotations=include_annotations,
                include_multimodal=include_multimodal,
            )
            bundle_map = {b["metadata"]["key"]: b for b in bundles}

            # 2. Analyze Sequential (LLM)
            for item_key in chunk_keys:
                # Find original item object for progress reporting
                item = item_map.get(item_key)
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
                    delete_old_notes=delete_old_notes,
                    move_to_collection=move_to_collection,
                    include_multimodal=include_multimodal,
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

        # Collect errors
        errors = [
            f"{r.item_key}: {r.error}"
            for r in results
            if not r.success and not r.skipped
        ]

        # Log task end
        log_task_end(
            logger,
            f"Batch Analysis ({source})",
            items_processed=total_processed,
            errors=errors if errors else None,
            skipped=total_skipped,
            failed=total_failed,
        )

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
        delete_old_notes: bool = False,
        move_to_collection: str | None = None,
        use_structured: bool = True,
        include_multimodal: bool = True,
    ) -> ItemAnalysisResult:
        """Analyze a single item using pre-fetched bundle.

        Args:
            item: Item object with key, title, etc.
            bundle: Pre-fetched data bundle from BatchLoader.
            llm_client: LLM client for analysis.
            skip_existing: Skip items with existing notes.
            template: Custom analysis template.
            dry_run: Preview only, no changes.
            delete_old_notes: Delete all existing notes before creating new one.
            move_to_collection: Collection name to move item to after analysis.
            include_multimodal: Whether to include multi-modal content (images/tables).
        """
        start_time = time.time()

        try:
            # 1. Check if should skip
            existing_notes = bundle.get("notes", [])
            if skip_result := self._should_skip_item(
                item, existing_notes, skip_existing, delete_old_notes, start_time
            ):
                return skip_result

            # 2. Extract context
            context = self._extract_bundle_context(bundle, include_multimodal)
            if error_result := self._validate_context(item, context, start_time):
                return error_result

            # 3. Prepare images based on LLM capability
            from zotero_mcp.clients.llm.capabilities import get_provider_capability

            capability = get_provider_capability(llm_client.provider)
            images_to_send = None
            if capability.can_handle_images() and context.get("images"):
                images_to_send = context["images"]

            # 4. Call LLM
            if use_structured and template is None:
                template = DEFAULT_ANALYSIS_TEMPLATE_JSON
            elif template is None:
                template = ""
            analysis_content = await self._call_llm_analysis(
                item=item,
                llm_client=llm_client,
                metadata=bundle.get("metadata", {}),
                fulltext=context["fulltext"],
                annotations=context["annotations"],
                template=template,
                images=images_to_send,
            )
            if not analysis_content:
                logger.warning(
                    "LLM returned empty analysis content",
                    extra={
                        "item_key": item.key,
                        "provider": getattr(llm_client, "provider", None),
                        "model": getattr(llm_client, "model", None),
                    },
                )
                return ItemAnalysisResult(
                    item_key=item.key,
                    title=item.title,
                    success=False,
                    error="LLM 未返回分析结果",
                    processing_time=time.time() - start_time,
                )

            # 5. Save note (if not dry run)
            note_key = None
            if not dry_run:
                if delete_old_notes:
                    delete_errors = await self._delete_old_notes(
                        item.key, existing_notes
                    )
                    if delete_errors:
                        return ItemAnalysisResult(
                            item_key=item.key,
                            title=item.title,
                            success=False,
                            error="Failed to delete existing notes",
                            processing_time=time.time() - start_time,
                        )

                html_note = self._generate_html_note(
                    item=item,
                    metadata=bundle.get("metadata", {}),
                    analysis_content=analysis_content,
                    use_structured=use_structured,
                )
                note_key = await self._save_note(
                    item=item,
                    html_note=html_note,
                    llm_client=llm_client,
                )
                if move_to_collection and note_key:
                    await self._move_to_collection(item, move_to_collection)

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

    def _should_skip_item(
        self,
        item: Any,
        existing_notes: list,
        skip_existing: bool,
        delete_old_notes: bool,
        start_time: float,
    ) -> ItemAnalysisResult | None:
        """Check if item should be skipped. Returns skip result or None."""
        if skip_existing and not delete_old_notes and existing_notes:
            return ItemAnalysisResult(
                item_key=item.key,
                title=item.title,
                success=True,
                skipped=True,
                skip_reason="已有分析笔记",
                processing_time=time.time() - start_time,
            )
        return None

    def _extract_bundle_context(
        self,
        bundle: dict[str, Any],
        include_multimodal: bool = True,
    ) -> dict[str, Any]:
        """Extract relevant context from bundle."""
        context = {
            "fulltext": bundle.get("fulltext"),
            "annotations": bundle.get("annotations", []),
        }

        # Add multi-modal content if requested
        if include_multimodal:
            multimodal = bundle.get("multimodal", {})
            context["images"] = multimodal.get("images", [])
            context["tables"] = multimodal.get("tables", [])
        else:
            context["images"] = []
            context["tables"] = []

        return context

    def _validate_context(
        self, item: Any, context: dict[str, Any], start_time: float
    ) -> ItemAnalysisResult | None:
        """Validate extracted context. Returns error result if invalid."""
        if not context["fulltext"]:
            return ItemAnalysisResult(
                item_key=item.key,
                title=item.title,
                success=False,
                error="无法获取 PDF 全文内容",
                processing_time=time.time() - start_time,
            )
        return None

    async def _call_llm_analysis(
        self,
        item: Any,
        llm_client: Any,
        metadata: dict,
        fulltext: str,
        annotations: list,
        template: str,
        images: list | None = None,
    ) -> str | None:
        """Call LLM to analyze paper."""
        return await llm_client.analyze_paper(
            title=item.title,
            authors=item.authors,
            journal=metadata.get("data", {}).get("publicationTitle"),
            date=item.date,
            doi=item.doi,
            fulltext=fulltext,
            annotations=annotations,
            images=images,
            template=template,
        )

    async def _delete_old_notes(
        self, item_key: str, notes: list
    ) -> list[str]:
        """Delete existing notes for an item."""
        errors: list[str] = []
        for note in notes:
            note_key = note.get("key") or note.get("data", {}).get("key")
            if note_key:
                try:
                    await self.data_service.delete_item(note_key)
                    logger.debug(f"Deleted old note {note_key} from {item_key}")
                except Exception as e:
                    errors.append(str(e))
                    logger.warning(f"Failed to delete old note {note_key}: {e}")
        return errors

    def _generate_html_note(
        self, item: Any, metadata: dict, analysis_content: str, use_structured: bool
    ) -> str:
        """Generate HTML note from analysis content."""
        # Try structured parsing
        if use_structured:
            try:
                parser = get_structured_note_parser()
                renderer = get_structured_note_renderer()
                blocks = parser.parse(analysis_content)
                html_note = renderer.render(blocks, title=item.title)
                logger.info(f"Generated structured note with {len(blocks)} blocks")
                return html_note
            except Exception as e:
                logger.warning(
                    f"Structured parsing failed: {e}, falling back to Markdown"
                )

        # Fallback to markdown
        journal = metadata.get("data", {}).get("publicationTitle") or "未知"
        basic_info = (
            f"# AI分析 - {item.title}\n\n"
            f"## 论文基本信息\n\n"
            f"- **标题**: {item.title}\n"
            f"- **作者**: {item.authors or '未知'}\n"
            f"- **期刊**: {journal}\n"
            f"- **发表日期**: {item.date or '未知'}\n"
            f"- **DOI**: {item.doi or '未知'}\n\n"
            f"---\n\n"
            f"{analysis_content}\n"
        )
        return beautify_ai_note(markdown_to_html(basic_info))

    async def _save_note(
        self, item: Any, html_note: str, llm_client: Any
    ) -> str | None:
        """Save note to item and return note key."""
        # Generate tags: AI分析 + LLM provider name
        provider_map = {
            "deepseek": "DeepSeek",
            "claude-cli": "Claude",
            "claude": "Claude",
        }
        provider_name = provider_map.get(
            llm_client.provider,
            "Claude"
            if llm_client.provider == "claude-cli"
            else llm_client.provider.capitalize(),
        )
        note_tags = ["AI分析", provider_name]

        result = await self.data_service.create_note(
            parent_key=item.key,
            content=html_note,
            tags=note_tags,
        )

        # Extract note key
        if isinstance(result, dict):
            success = result.get("successful", {})
            if success:
                note_data = list(success.values())[0] if success else {}
                return note_data.get("key", "unknown")
        return None

    async def _move_to_collection(self, item: Any, target_collection_name: str) -> None:
        """Move item to target collection (add to target, remove from source).

        Args:
            item: Item object with key and collection info.
            target_collection_name: Name of the collection to move item to.
        """
        try:
            # Find target collection by name
            matches = await self.data_service.find_collection_by_name(
                target_collection_name
            )
            if not matches:
                logger.warning(
                    f"Target collection '{target_collection_name}' not found, "
                    f"skipping move for {item.key}"
                )
                return

            target_key = matches[0].get("data", {}).get("key")
            if not target_key:
                return

            # Add to target collection
            await self.data_service.add_item_to_collection(target_key, item.key)
            logger.debug(f"Added {item.key} to collection {target_collection_name}")

            # Remove from source collections
            # Get current item data to find its collections
            item_data = await self.data_service.get_item(item.key)
            if item_data:
                data = item_data.get("data", {})
                current_collections = data.get("collections", [])
                for col_key in current_collections:
                    if col_key != target_key:
                        try:
                            await self.data_service.remove_item_from_collection(
                                col_key, item.key
                            )
                            logger.debug(
                                f"Removed {item.key} from collection {col_key}"
                            )
                        except Exception as e:
                            logger.warning(
                                f"Failed to remove {item.key} from {col_key}: {e}"
                            )

        except Exception as e:
            logger.warning(f"Failed to move item {item.key}: {e}")

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
