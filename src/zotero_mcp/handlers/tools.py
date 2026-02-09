"""MCP tool handlers (Logseq-style)."""

from __future__ import annotations

from collections.abc import Sequence
import re
from typing import Any

from mcp.types import TextContent, Tool

from zotero_mcp.models.common import (
    AnnotationItem,
    AnnotationsResponse,
    BaseResponse,
    BundleResponse,
    CollectionsResponse,
    DatabaseStatusResponse,
    DatabaseUpdateResponse,
    FulltextResponse,
    ItemDetailResponse,
    NoteCreationResponse,
    NotesResponse,
    SearchResponse,
    SearchResultItem,
)
from zotero_mcp.models.enums import ToolName
from zotero_mcp.models.responses import Formatters
from zotero_mcp.models.schemas import (
    AdvancedSearchInput,
    BatchAnalyzeInput,
    BatchGetMetadataInput,
    CreateCollectionInput,
    CreateNoteInput,
    DatabaseStatusInput,
    DeleteCollectionInput,
    EmptyInput,
    FindCollectionInput,
    GetAnnotationsInput,
    GetBundleInput,
    GetChildrenInput,
    GetCollectionsInput,
    GetFulltextInput,
    GetMetadataInput,
    GetNotesInput,
    GetRecentInput,
    MoveCollectionInput,
    PrepareAnalysisInput,
    RenameCollectionInput,
    ResumeWorkflowInput,
    SearchByTagInput,
    SearchItemsInput,
    SearchNotesInput,
    SemanticSearchInput,
    UpdateDatabaseInput,
)
from zotero_mcp.models.workflow import (
    BatchAnalyzeResponse,
    CollectionMatch,
    FindCollectionResponse,
    WorkflowInfo,
    WorkflowListResponse,
)
from zotero_mcp.models.workflow.batch import (
    BatchGetMetadataResponse,
    BatchItemResult,
)
from zotero_mcp.services.checkpoint import get_checkpoint_manager
from zotero_mcp.services.data_access import get_data_service
from zotero_mcp.services.workflow import get_workflow_service
from zotero_mcp.settings import settings
from zotero_mcp.utils.errors import format_error
from zotero_mcp.utils.formatting.helpers import format_creators


class ToolHandler:
    """Handler for MCP tool calls."""

    @staticmethod
    def get_tools() -> list[Tool]:
        """Get all tool definitions."""
        tools: list[Tool] = [
            # Search & discovery
            Tool(
                name=ToolName.SEARCH,
                description="Search Zotero items by keyword",
                inputSchema=SearchItemsInput.model_json_schema(),
            ),
            Tool(
                name=ToolName.SEARCH_BY_TAG,
                description="Search Zotero items by tag",
                inputSchema=SearchByTagInput.model_json_schema(),
            ),
            Tool(
                name=ToolName.ADVANCED_SEARCH,
                description="Advanced multi-field search",
                inputSchema=AdvancedSearchInput.model_json_schema(),
            ),
            Tool(
                name=ToolName.GET_RECENT,
                description="Get recently added items",
                inputSchema=GetRecentInput.model_json_schema(),
            ),
            # Content access
            Tool(
                name=ToolName.GET_METADATA,
                description="Get item metadata",
                inputSchema=GetMetadataInput.model_json_schema(),
            ),
            Tool(
                name=ToolName.GET_FULLTEXT,
                description="Get full text content",
                inputSchema=GetFulltextInput.model_json_schema(),
            ),
            Tool(
                name=ToolName.GET_CHILDREN,
                description="Get attachments and notes for an item",
                inputSchema=GetChildrenInput.model_json_schema(),
            ),
            Tool(
                name=ToolName.GET_COLLECTIONS,
                description="List collections or items in a collection",
                inputSchema=GetCollectionsInput.model_json_schema(),
            ),
            Tool(
                name=ToolName.GET_BUNDLE,
                description="Get comprehensive item bundle",
                inputSchema=GetBundleInput.model_json_schema(),
            ),
            # Annotations & notes
            Tool(
                name=ToolName.GET_ANNOTATIONS,
                description="Get PDF annotations",
                inputSchema=GetAnnotationsInput.model_json_schema(),
            ),
            Tool(
                name=ToolName.GET_NOTES,
                description="Get notes for an item",
                inputSchema=GetNotesInput.model_json_schema(),
            ),
            Tool(
                name=ToolName.SEARCH_NOTES,
                description="Search notes and annotations",
                inputSchema=SearchNotesInput.model_json_schema(),
            ),
            Tool(
                name=ToolName.CREATE_NOTE,
                description="Create a note attached to an item",
                inputSchema=CreateNoteInput.model_json_schema(),
            ),
            # Batch
            Tool(
                name=ToolName.BATCH_GET_METADATA,
                description="Get metadata for multiple items",
                inputSchema=BatchGetMetadataInput.model_json_schema(),
            ),
        ]

        if settings.enable_semantic_search:
            tools.append(
                Tool(
                    name=ToolName.SEMANTIC_SEARCH,
                    description="AI semantic similarity search",
                    inputSchema=SemanticSearchInput.model_json_schema(),
                )
            )

        if settings.enable_collection_tools:
            tools.extend(
                [
                    Tool(
                        name=ToolName.CREATE_COLLECTION,
                        description="Create a collection",
                        inputSchema=CreateCollectionInput.model_json_schema(),
                    ),
                    Tool(
                        name=ToolName.DELETE_COLLECTION,
                        description="Delete a collection",
                        inputSchema=DeleteCollectionInput.model_json_schema(),
                    ),
                    Tool(
                        name=ToolName.MOVE_COLLECTION,
                        description="Move a collection",
                        inputSchema=MoveCollectionInput.model_json_schema(),
                    ),
                    Tool(
                        name=ToolName.RENAME_COLLECTION,
                        description="Rename a collection",
                        inputSchema=RenameCollectionInput.model_json_schema(),
                    ),
                ]
            )

        if settings.enable_database_tools:
            tools.extend(
                [
                    Tool(
                        name=ToolName.UPDATE_DATABASE,
                        description="Update semantic search database",
                        inputSchema=UpdateDatabaseInput.model_json_schema(),
                    ),
                    Tool(
                        name=ToolName.DATABASE_STATUS,
                        description="Get semantic search database status",
                        inputSchema=DatabaseStatusInput.model_json_schema(),
                    ),
                ]
            )

        if settings.enable_workflows:
            tools.extend(
                [
                    Tool(
                        name=ToolName.PREPARE_ANALYSIS,
                        description="Prepare analysis data (Mode A)",
                        inputSchema=PrepareAnalysisInput.model_json_schema(),
                    ),
                    Tool(
                        name=ToolName.BATCH_ANALYZE_PDFS,
                        description="Batch analyze PDFs with LLM (Mode B)",
                        inputSchema=BatchAnalyzeInput.model_json_schema(),
                    ),
                    Tool(
                        name=ToolName.RESUME_WORKFLOW,
                        description="Resume an interrupted workflow",
                        inputSchema=ResumeWorkflowInput.model_json_schema(),
                    ),
                    Tool(
                        name=ToolName.LIST_WORKFLOWS,
                        description="List workflow states",
                        inputSchema=EmptyInput.model_json_schema(),
                    ),
                    Tool(
                        name=ToolName.FIND_COLLECTION,
                        description="Find collection by name",
                        inputSchema=FindCollectionInput.model_json_schema(),
                    ),
                ]
            )

        return tools

    async def handle_tool(
        self, name: str, arguments: dict[str, Any]
    ) -> Sequence[TextContent]:
        """Handle tool call."""
        try:
            args = arguments or {}
            data_service = get_data_service()

            match name:
                case ToolName.SEARCH:
                    params = SearchItemsInput(**args)
                    results = await data_service.search_items(
                        query=params.query,
                        limit=params.limit,
                        offset=params.offset,
                        qmode=params.qmode.value,
                    )
                    items = [
                        SearchResultItem(
                            key=r.key,
                            title=r.title,
                            authors=r.authors,
                            date=r.date,
                            item_type=r.item_type,
                            abstract=r.abstract,
                            doi=r.doi,
                            tags=r.tags or [],
                        )
                        for r in results
                    ]
                    if params.tags:
                        required = set(params.tags)
                        items = [
                            i for i in items if required.issubset(set(i.tags or []))
                        ]
                    response = SearchResponse(
                        query=params.query,
                        total=len(items),
                        count=len(items),
                        offset=params.offset,
                        limit=params.limit,
                        has_more=len(items) == params.limit,
                        next_offset=(
                            params.offset + len(items)
                            if len(items) == params.limit
                            else None
                        ),
                        items=items,
                    )
                    response_format = params.response_format

                case ToolName.SEARCH_BY_TAG:
                    params = SearchByTagInput(**args)
                    include_tags: list[str] = []
                    exclude_tags: list[str] = []
                    for tag in params.tags:
                        tag = tag.strip()
                        if not tag:
                            continue
                        if tag.startswith("-"):
                            exclude_tags.append(tag[1:].strip())
                        else:
                            include_tags.append(tag)
                    results = await data_service.search_by_tag(
                        tags=include_tags,
                        exclude_tags=exclude_tags,
                        limit=params.limit,
                    )
                    items = [
                        SearchResultItem(
                            key=r.key,
                            title=r.title,
                            authors=r.authors,
                            date=r.date,
                            item_type=r.item_type,
                            tags=r.tags or [],
                        )
                        for r in results
                    ]
                    response = SearchResponse(
                        query=f"tags={include_tags}",
                        total=len(items),
                        count=len(items),
                        offset=0,
                        limit=params.limit,
                        has_more=False,
                        items=items,
                    )
                    response_format = params.response_format

                case ToolName.ADVANCED_SEARCH:
                    params = AdvancedSearchInput(**args)
                    query_parts = []
                    for cond in params.conditions:
                        if cond.operation == "contains":
                            query_parts.append(f"{cond.value}")
                        elif cond.operation == "is":
                            query_parts.append(f'"{cond.value}"')
                    join_op = " AND " if params.join_mode == "all" else " OR "
                    query = join_op.join(query_parts) if query_parts else "*"
                    results = await data_service.search_items(
                        query=query,
                        limit=100,
                        qmode="everything",
                    )
                    start = params.offset
                    end = start + params.limit
                    filtered_page = results[start:end]
                    items = [
                        SearchResultItem(
                            key=r.key,
                            title=r.title,
                            authors=r.authors,
                            date=r.date,
                            item_type=r.item_type,
                            abstract=r.abstract,
                            tags=r.tags or [],
                        )
                        for r in filtered_page
                    ]
                    response = SearchResponse(
                        query=", ".join(
                            f"{c.field} {c.operation} '{c.value}'"
                            for c in params.conditions
                        ),
                        total=len(results),
                        count=len(items),
                        offset=0,
                        limit=params.limit,
                        has_more=end < len(results),
                        next_offset=end if end < len(results) else None,
                        items=items,
                    )
                    response_format = params.response_format

                case ToolName.SEMANTIC_SEARCH:
                    if not settings.enable_semantic_search:
                        raise ValueError("Semantic search is disabled by configuration")
                    params = SemanticSearchInput(**args)
                    from zotero_mcp.services.zotero.semantic_search import (
                        semantic_search,
                    )

                    results = await semantic_search(
                        query=params.query,
                        limit=params.limit,
                        filters=params.filters,
                    )
                    items = [
                        SearchResultItem(
                            key=r.get("key", ""),
                            title=r.get("title", "Untitled"),
                            authors=r.get("authors"),
                            date=r.get("date"),
                            item_type=r.get("item_type", "unknown"),
                            abstract=r.get("abstract"),
                            doi=r.get("doi"),
                            tags=r.get("tags", []),
                            similarity_score=r.get("similarity_score"),
                        )
                        for r in results
                    ]
                    response = SearchResponse(
                        query=f"semantic: {params.query}",
                        total=len(items),
                        count=len(items),
                        offset=0,
                        limit=params.limit,
                        has_more=False,
                        items=items,
                    )
                    response_format = params.response_format

                case ToolName.GET_RECENT:
                    params = GetRecentInput(**args)
                    results = await data_service.get_recent_items(
                        limit=params.limit,
                        days=params.days or 30,
                    )
                    items = [
                        SearchResultItem(
                            key=r.key,
                            title=r.title,
                            authors=r.authors,
                            date=r.date,
                            item_type=r.item_type,
                            tags=r.tags or [],
                        )
                        for r in results
                    ]
                    response = SearchResponse(
                        query=f"recent (last {params.days} days)",
                        total=len(items),
                        count=len(items),
                        offset=0,
                        limit=params.limit,
                        has_more=False,
                        items=items,
                    )
                    response_format = params.response_format
                case ToolName.GET_METADATA:
                    params = GetMetadataInput(**args)
                    item = await data_service.get_item(params.item_key.strip().upper())
                    data = item.get("data", {}) if isinstance(item, dict) else {}
                    tags = [
                        t.get("tag", "") for t in data.get("tags", []) if t.get("tag")
                    ]
                    response = ItemDetailResponse(
                        key=data.get("key", params.item_key),
                        title=data.get("title", "Untitled"),
                        item_type=data.get("itemType", "unknown"),
                        authors=format_creators(data.get("creators", [])),
                        date=data.get("date"),
                        publication=data.get("publicationTitle")
                        or data.get("journalAbbreviation"),
                        doi=data.get("DOI"),
                        url=data.get("url"),
                        abstract=data.get("abstractNote")
                        if params.include_abstract
                        else None,
                        tags=tags,
                        raw_data=item if params.output_format.value == "json" else None,
                    )
                    response_format = params.response_format

                case ToolName.GET_FULLTEXT:
                    params = GetFulltextInput(**args)
                    fulltext = await data_service.get_fulltext(
                        params.item_key.strip().upper()
                    )
                    if not fulltext:
                        response = FulltextResponse(
                            success=False,
                            error=(
                                f"No full-text content available for item {params.item_key}. "
                                "This may be because the item has no attachment, "
                                "or the content hasn't been indexed by Zotero."
                            ),
                            item_key=params.item_key,
                            fulltext=None,
                            length=0,
                            truncated=False,
                        )
                    else:
                        truncated = (
                            params.max_length is not None
                            and len(fulltext) > params.max_length
                        )
                        if truncated and params.max_length is not None:
                            fulltext = fulltext[: params.max_length]
                        response = FulltextResponse(
                            item_key=params.item_key,
                            fulltext=fulltext,
                            length=len(fulltext),
                            truncated=truncated,
                        )
                    response_format = params.response_format

                case ToolName.GET_CHILDREN:
                    params = GetChildrenInput(**args)
                    item_key = params.item_key.strip().upper()
                    type_filter = (
                        None if params.child_type == "all" else params.child_type
                    )
                    children = await data_service.get_item_children(
                        item_key, item_type=type_filter
                    )
                    response = {
                        "success": True,
                        "item_key": item_key,
                        "count": len(children),
                        "children": children,
                    }
                    response_format = params.response_format

                case ToolName.GET_COLLECTIONS:
                    params = GetCollectionsInput(**args)
                    if params.collection_key:
                        results = await data_service.get_collection_items(
                            params.collection_key.strip().upper(),
                            limit=params.limit,
                        )
                        items = [
                            SearchResultItem(
                                key=r.key,
                                title=r.title,
                                authors=r.authors,
                                date=r.date,
                                item_type=r.item_type,
                            )
                            for r in results
                        ]
                        response = SearchResponse(
                            query=f"collection:{params.collection_key}",
                            total=len(results),
                            count=len(items),
                            offset=0,
                            limit=params.limit,
                            has_more=False,
                            items=items,
                        )
                        response_format = params.response_format
                    else:
                        collections = await data_service.get_collections()
                        collection_items = []
                        for coll in collections:
                            data = coll.get("data", {})
                            parent_coll = data.get("parentCollection")
                            if parent_coll is False:
                                parent_coll = None
                            collection_items.append(
                                {
                                    "key": data.get("key", coll.get("key", "")),
                                    "name": data.get("name", "Unnamed"),
                                    "item_count": data.get("numItems"),
                                    "parent_key": parent_coll,
                                }
                            )
                        response = CollectionsResponse(
                            count=len(collection_items),
                            collections=collection_items,
                        )
                        response_format = params.response_format

                case ToolName.GET_BUNDLE:
                    params = GetBundleInput(**args)
                    bundle = await data_service.get_item_bundle(
                        params.item_key.strip().upper(),
                        include_fulltext=params.include_fulltext,
                        include_annotations=params.include_annotations,
                        include_notes=params.include_notes,
                    )
                    metadata_raw = bundle.get("metadata", {})
                    data = metadata_raw.get("data", {})
                    tags = [
                        t.get("tag", "") for t in data.get("tags", []) if t.get("tag")
                    ]
                    metadata = ItemDetailResponse(
                        key=data.get("key", params.item_key),
                        title=data.get("title", "Untitled"),
                        item_type=data.get("itemType", "unknown"),
                        authors=format_creators(data.get("creators", [])),
                        date=data.get("date"),
                        publication=data.get("publicationTitle")
                        or data.get("journalAbbreviation"),
                        doi=data.get("DOI"),
                        url=data.get("url"),
                        abstract=data.get("abstractNote"),
                        tags=tags,
                    )
                    annotations_raw = bundle.get("annotations", [])
                    annotations = [
                        AnnotationItem(
                            type=ann.get("type", ann.get("annotationType", "note")),
                            text=ann.get("text", ann.get("annotationText")),
                            comment=ann.get("comment", ann.get("annotationComment")),
                            page=ann.get("page", ann.get("annotationPageLabel")),
                            color=ann.get("color", ann.get("annotationColor")),
                        )
                        for ann in annotations_raw
                    ]
                    response = BundleResponse(
                        metadata=metadata,
                        attachments=bundle.get("attachments", []),
                        notes=bundle.get("notes", []),
                        annotations=annotations,
                        fulltext=bundle.get("fulltext"),
                    )
                    response_format = params.response_format
                case ToolName.GET_ANNOTATIONS:
                    params = GetAnnotationsInput(**args)
                    if not params.item_key:
                        response = AnnotationsResponse(
                            success=False,
                            error="item_key is required",
                            item_key="",
                            count=0,
                            annotations=[],
                        )
                    else:
                        item_key = params.item_key.strip().upper()
                        annotations = await data_service.get_annotations(item_key)
                        if params.annotation_type != "all":
                            annotations = [
                                a
                                for a in annotations
                                if a.get("type", a.get("annotationType", "")).lower()
                                == params.annotation_type
                            ]
                        annotation_items = [
                            AnnotationItem(
                                type=ann.get("type", ann.get("annotationType", "note")),
                                text=ann.get("text", ann.get("annotationText")),
                                comment=ann.get(
                                    "comment", ann.get("annotationComment")
                                ),
                                page=ann.get("page", ann.get("annotationPageLabel")),
                                color=ann.get("color", ann.get("annotationColor")),
                            )
                            for ann in annotations
                        ]
                        total_count = len(annotation_items)
                        start_idx = params.offset
                        end_idx = start_idx + params.limit
                        paginated_items = annotation_items[start_idx:end_idx]
                        has_more = end_idx < total_count
                        response = AnnotationsResponse(
                            item_key=item_key,
                            count=len(paginated_items),
                            total_count=total_count,
                            annotations=paginated_items,
                            has_more=has_more,
                            next_offset=end_idx if has_more else None,
                        )
                    response_format = params.response_format

                case ToolName.GET_NOTES:
                    params = GetNotesInput(**args)
                    if not params.item_key:
                        response = NotesResponse(
                            success=False,
                            error="item_key is required",
                            item_key="",
                            count=0,
                            notes=[],
                        )
                    else:
                        item_key = params.item_key.strip().upper()
                        notes = await data_service.get_notes(item_key)
                        processed_notes = []
                        for note in notes:
                            data = note.get("data", {})
                            note_key = data.get("key", "")
                            note_content = data.get("note", "")
                            clean_content = re.sub(r"<[^>]+>", "", note_content)
                            clean_content = clean_content.replace("&nbsp;", " ").strip()
                            display_content = clean_content[:2000]
                            if len(clean_content) > 2000:
                                display_content += "..."
                            processed_notes.append(
                                {
                                    "note_key": note_key,
                                    "content": display_content,
                                    "full_content": clean_content,
                                    "raw_html": note_content,
                                }
                            )
                        total_count = len(processed_notes)
                        start_idx = params.offset
                        end_idx = start_idx + params.limit
                        paginated_notes = processed_notes[start_idx:end_idx]
                        has_more = end_idx < total_count
                        response = NotesResponse(
                            item_key=item_key,
                            count=len(paginated_notes),
                            total_count=total_count,
                            notes=paginated_notes,
                            has_more=has_more,
                            next_offset=end_idx if has_more else None,
                        )
                    response_format = params.response_format

                case ToolName.SEARCH_NOTES:
                    params = SearchNotesInput(**args)
                    results = await data_service.search_items(
                        query=params.query,
                        limit=50,
                        qmode="everything",
                    )
                    matches = []
                    query_to_match = (
                        params.query if params.case_sensitive else params.query.lower()
                    )
                    for result in results:
                        try:
                            notes = await data_service.get_notes(result.key)
                            for note in notes:
                                data = note.get("data", {})
                                note_content = data.get("note", "")
                                clean = re.sub(r"<[^>]+>", "", note_content)
                                search_text = (
                                    clean if params.case_sensitive else clean.lower()
                                )
                                if query_to_match in search_text:
                                    idx = search_text.find(query_to_match)
                                    start = max(0, idx - 100)
                                    end = min(len(clean), idx + len(params.query) + 100)
                                    context = clean[start:end]
                                    matches.append(
                                        {
                                            "type": "note",
                                            "item_key": result.key,
                                            "item_title": result.title,
                                            "note_key": data.get("key", ""),
                                            "context": context,
                                        }
                                    )
                                    if len(matches) >= params.limit:
                                        break
                        except Exception:
                            continue
                        if len(matches) >= params.limit:
                            break
                    result_items = [
                        SearchResultItem(
                            key=match["item_key"],
                            title=match["item_title"],
                            creators=[],
                            year=None,
                            item_type="note",
                            date_added=None,
                            snippet=f"...{match['context']}...",
                            raw_data=match,
                        )
                        for match in matches
                    ]
                    total_count = len(result_items)
                    start_idx = params.offset
                    end_idx = start_idx + params.limit
                    paginated_results = result_items[start_idx:end_idx]
                    has_more = end_idx < total_count
                    response = SearchResponse(
                        query=params.query,
                        count=len(paginated_results),
                        total_count=total_count,
                        has_more=has_more,
                        next_offset=end_idx if has_more else None,
                        results=paginated_results,
                        total=total_count,
                        offset=params.offset,
                        limit=params.limit,
                        items=paginated_results,
                    )
                    response_format = params.response_format

                case ToolName.CREATE_NOTE:
                    params = CreateNoteInput(**args)
                    html_content = params.content
                    if not params.content.strip().startswith("<"):
                        html_content = f"<p>{params.content}</p>"
                        html_content = html_content.replace("\n\n", "</p><p>")
                        html_content = html_content.replace("\n", "<br/>")
                    item_key = params.item_key.strip().upper()
                    result = await data_service.create_note(
                        parent_key=item_key,
                        content=html_content,
                        tags=params.tags,
                    )
                    note_key = "unknown"
                    if isinstance(result, dict):
                        success = result.get("successful", {})
                        if success:
                            note_data = list(success.values())[0] if success else {}
                            note_key = note_data.get("key", "unknown")
                    response = NoteCreationResponse(
                        note_key=note_key if note_key else "unknown",
                        parent_key=item_key,
                        message=f"Note created successfully with key: {note_key}",
                    )
                    response_format = params.response_format
                case ToolName.CREATE_COLLECTION:
                    params = CreateCollectionInput(**args)
                    result = await data_service.create_collection(
                        name=params.name, parent_key=params.parent_key
                    )
                    if "successful" in result and result["successful"]:
                        data = list(result["successful"].values())[0]
                        response = {
                            "success": True,
                            "key": data["key"],
                            "name": data["data"]["name"],
                            "parent_key": data["data"].get("parentCollection"),
                        }
                    else:
                        response = BaseResponse(
                            success=False,
                            error=f"API response did not indicate success: {result}",
                        )
                    response_format = params.response_format

                case ToolName.DELETE_COLLECTION:
                    params = DeleteCollectionInput(**args)
                    await data_service.delete_collection(params.collection_key)
                    response = BaseResponse(success=True)
                    response_format = params.response_format

                case ToolName.MOVE_COLLECTION:
                    params = MoveCollectionInput(**args)
                    parent = params.parent_key
                    if parent in ["root", ""]:
                        parent = None
                    await data_service.update_collection(
                        collection_key=params.collection_key, parent_key=parent
                    )
                    response = BaseResponse(success=True)
                    response_format = params.response_format

                case ToolName.RENAME_COLLECTION:
                    params = RenameCollectionInput(**args)
                    await data_service.update_collection(
                        collection_key=params.collection_key, name=params.new_name
                    )
                    response = BaseResponse(success=True)
                    response_format = params.response_format

                case ToolName.UPDATE_DATABASE:
                    if not settings.enable_database_tools:
                        raise ValueError("Database tools are disabled by configuration")
                    params = UpdateDatabaseInput(**args)
                    from zotero_mcp.services.zotero.semantic_search import (
                        update_database,
                    )

                    result = await update_database(
                        force_rebuild=params.force_rebuild,
                        include_fulltext=params.extract_fulltext,
                        limit=params.limit,
                    )
                    if isinstance(result, dict):
                        items_processed = result.get(
                            "processed_items", result.get("items_processed", 0)
                        )
                        items_added = result.get(
                            "added_items", result.get("items_added", 0)
                        )
                        items_updated = result.get(
                            "updated_items", result.get("items_updated", 0)
                        )
                        duration_seconds = result.get("duration_seconds", 0)
                        response = DatabaseUpdateResponse(
                            items_processed=items_processed,
                            items_added=items_added,
                            items_updated=items_updated,
                            duration_seconds=duration_seconds,
                            message="Database update completed successfully",
                        )
                    else:
                        response = DatabaseUpdateResponse(
                            items_processed=0,
                            items_added=0,
                            items_updated=0,
                            duration_seconds=0,
                            message="Database update completed successfully",
                        )
                    response_format = params.response_format

                case ToolName.DATABASE_STATUS:
                    if not settings.enable_database_tools:
                        raise ValueError("Database tools are disabled by configuration")
                    params = DatabaseStatusInput(**args)
                    from zotero_mcp.services.zotero.semantic_search import (
                        get_database_status,
                    )

                    status = await get_database_status()
                    if not isinstance(status, dict):
                        status = {}
                    response = DatabaseStatusResponse(
                        exists=status.get("exists", False),
                        item_count=status.get("item_count", 0),
                        last_updated=status.get("last_updated", "Unknown"),
                        embedding_model=status.get("embedding_model", "default"),
                        model_name=status.get("model_name"),
                        fulltext_enabled=status.get("fulltext_enabled", False),
                        auto_update=status.get("update_config", {}).get(
                            "auto_update", False
                        ),
                        update_frequency=status.get("update_config", {}).get(
                            "update_frequency", "manual"
                        ),
                        message=status.get("message"),
                    )
                    response_format = params.response_format

                case ToolName.BATCH_GET_METADATA:
                    params = BatchGetMetadataInput(**args)
                    results = []
                    successful = 0
                    failed = 0
                    for item_key in params.item_keys:
                        try:
                            item = await data_service.get_item(item_key.strip().upper())
                            if item:
                                data = item.get("data", {})
                                tags = [
                                    t.get("tag", "")
                                    for t in data.get("tags", [])
                                    if t.get("tag")
                                ]
                                item_data = ItemDetailResponse(
                                    key=data.get("key", item_key),
                                    title=data.get("title", "Untitled"),
                                    item_type=data.get("itemType", "unknown"),
                                    authors=format_creators(data.get("creators", [])),
                                    date=data.get("date"),
                                    publication=data.get("publicationTitle")
                                    or data.get("journalAbbreviation"),
                                    doi=data.get("DOI"),
                                    url=data.get("url"),
                                    abstract=data.get("abstractNote"),
                                    tags=tags,
                                    raw_data=item
                                    if params.output_format == "json"
                                    else None,
                                )
                                results.append(
                                    BatchItemResult(
                                        item_key=item_key,
                                        success=True,
                                        data=item_data,
                                    )
                                )
                                successful += 1
                            else:
                                results.append(
                                    BatchItemResult(
                                        item_key=item_key,
                                        success=False,
                                        error="Item not found",
                                    )
                                )
                                failed += 1
                        except Exception as exc:
                            results.append(
                                BatchItemResult(
                                    item_key=item_key,
                                    success=False,
                                    error=str(exc),
                                )
                            )
                            failed += 1
                    response = BatchGetMetadataResponse(
                        total_requested=len(params.item_keys),
                        successful=successful,
                        failed=failed,
                        results=results,
                    )
                    response_format = params.response_format
                case ToolName.PREPARE_ANALYSIS:
                    if not settings.enable_workflows:
                        raise ValueError("Workflow tools are disabled by configuration")
                    params = PrepareAnalysisInput(**args)
                    workflow_service = get_workflow_service()
                    response = await workflow_service.prepare_analysis(
                        source=params.source,
                        collection_key=params.collection_key,
                        collection_name=params.collection_name,
                        days=params.days,
                        limit=params.limit,
                        include_annotations=params.include_annotations,
                        include_multimodal=params.include_multimodal,
                        skip_existing=params.skip_existing_notes,
                    )
                    response_format = params.response_format

                case ToolName.BATCH_ANALYZE_PDFS:
                    if not settings.enable_workflows:
                        raise ValueError("Workflow tools are disabled by configuration")
                    params = BatchAnalyzeInput(**args)
                    workflow_service = get_workflow_service()
                    response = await workflow_service.batch_analyze(
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
                    )
                    response_format = params.response_format

                case ToolName.RESUME_WORKFLOW:
                    if not settings.enable_workflows:
                        raise ValueError("Workflow tools are disabled by configuration")
                    params = ResumeWorkflowInput(**args)
                    checkpoint_manager = get_checkpoint_manager()
                    workflow_state = checkpoint_manager.load_state(params.workflow_id)
                    if not workflow_state:
                        response = BatchAnalyzeResponse(
                            success=False,
                            error=f"Workflow {params.workflow_id} not found",
                            workflow_id=params.workflow_id,
                            total_items=0,
                            processed=0,
                            failed=0,
                        )
                    else:
                        workflow_service = get_workflow_service()
                        metadata = workflow_state.metadata
                        response = await workflow_service.batch_analyze(
                            source=workflow_state.source_type,
                            collection_key=workflow_state.source_identifier,
                            days=7,
                            limit=workflow_state.total_items,
                            resume_workflow_id=params.workflow_id,
                            skip_existing=True,
                            include_annotations=metadata.get(
                                "include_annotations", True
                            ),
                            llm_provider=metadata.get("llm_provider", "auto"),
                            llm_model=metadata.get("llm_model"),
                            dry_run=False,
                        )
                    response_format = params.response_format

                case ToolName.LIST_WORKFLOWS:
                    params = EmptyInput(**args)
                    checkpoint_manager = get_checkpoint_manager()
                    workflows = checkpoint_manager.list_workflows(status_filter="all")
                    workflow_infos = [
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
                        for wf in workflows
                    ]
                    response = WorkflowListResponse(
                        count=len(workflow_infos),
                        workflows=workflow_infos,
                    )
                    response_format = params.response_format

                case ToolName.FIND_COLLECTION:
                    params = FindCollectionInput(**args)
                    matches = await data_service.find_collection_by_name(
                        name=params.name,
                        exact_match=params.exact_match,
                    )
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
                    response = FindCollectionResponse(
                        query=params.name,
                        count=len(collection_matches),
                        matches=collection_matches,
                    )
                    response_format = params.response_format

                case _:
                    raise ValueError(f"Unknown tool: {name}")

            text = Formatters.format_response(response, response_format)
            return [TextContent(type="text", text=text)]

        except Exception as exc:
            raise format_error(exc) from exc
