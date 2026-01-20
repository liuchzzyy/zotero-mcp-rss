"""
Annotation tools for Zotero MCP.

Provides tools for working with annotations and notes:
- zotero_get_annotations: Get PDF annotations
- zotero_get_notes: Get notes
- zotero_search_notes: Search in notes and annotations
- zotero_create_note: Create a new note
"""

import re

from fastmcp import FastMCP, Context
from mcp.types import ToolAnnotations

from zotero_mcp.models.annotations import (
    CreateNoteInput,
    GetAnnotationsInput,
    GetNotesInput,
    SearchNotesInput,
)
from zotero_mcp.models.common import (
    AnnotationItem,
    AnnotationsResponse,
    NoteCreationResponse,
    NotesResponse,
    SearchResponse,
    SearchResultItem,
)
from zotero_mcp.services import get_data_service


def register_annotation_tools(mcp: FastMCP) -> None:
    """Register all annotation tools with the MCP server."""

    @mcp.tool(
        name="zotero_get_annotations",
        annotations=ToolAnnotations(
            title="Get PDF Annotations",
            readOnlyHint=True,
            destructiveHint=False,
            idempotentHint=True,
            openWorldHint=False,
        ),
    )
    async def zotero_get_annotations(
        params: GetAnnotationsInput, ctx: Context
    ) -> AnnotationsResponse:
        """
        Get PDF annotations (highlights, notes, comments) for a Zotero item.

        Requires Better BibTeX plugin for best results. Supports direct PDF
        extraction as fallback when Better BibTeX is unavailable.

        Args:
            params: Input containing:
                - item_key (str | None): Zotero item key to filter by. None for all annotations
                - annotation_type (str): Filter by annotation type ("all", "highlight", "note", "underline", "image")
                - use_pdf_extraction (bool): Whether to attempt direct PDF extraction as fallback
                - response_format (str): Output format preference (inherited from BaseInput)
                - offset (int): Pagination offset (inherited from PaginatedInput)
                - limit (int): Maximum results (inherited from PaginatedInput)

        Returns:
            AnnotationsResponse: Structured annotations with metadata.

        Example:
            Use when: "Get all highlights from this paper"
            Use when: "Show me annotations on page 5"
            Use when: "Extract comments and notes from the PDF"
        """
        try:
            service = get_data_service()

            # Get annotations for item
            if not params.item_key:
                await ctx.error("item_key is required for get_annotations")
                return AnnotationsResponse(
                    success=False,
                    error="item_key is required",
                    item_key="",
                    count=0,
                    annotations=[],
                )

            item_key_normalized = params.item_key.strip().upper()
            annotations = await service.get_annotations(item_key_normalized)

            if not annotations:
                return AnnotationsResponse(
                    item_key=item_key_normalized,
                    count=0,
                    annotations=[],
                )

            # Filter by type if specified
            if params.annotation_type != "all":
                annotations = [
                    a
                    for a in annotations
                    if a.get("type", a.get("annotationType", "")).lower()
                    == params.annotation_type
                ]

            # Convert to AnnotationItem models
            annotation_items = [
                AnnotationItem(
                    type=ann.get("type", ann.get("annotationType", "note")),
                    text=ann.get("text", ann.get("annotationText")),
                    comment=ann.get("comment", ann.get("annotationComment")),
                    page=ann.get("page", ann.get("annotationPageLabel")),
                    color=ann.get("color", ann.get("annotationColor")),
                )
                for ann in annotations
            ]

            # Apply pagination
            total_count = len(annotation_items)
            start_idx = params.offset
            end_idx = start_idx + params.limit
            paginated_items = annotation_items[start_idx:end_idx]
            has_more = end_idx < total_count

            return AnnotationsResponse(
                item_key=item_key_normalized,
                count=len(paginated_items),
                total_count=total_count,
                annotations=paginated_items,
                has_more=has_more,
                next_offset=end_idx if has_more else None,
            )

        except Exception as e:
            await ctx.error(f"Failed to get annotations: {str(e)}")
            return AnnotationsResponse(
                success=False,
                error=f"Annotations retrieval error: {str(e)}",
                item_key=params.item_key or "",
                count=0,
                annotations=[],
            )

    @mcp.tool(
        name="zotero_get_notes",
        annotations=ToolAnnotations(
            title="Get Notes",
            readOnlyHint=True,
            destructiveHint=False,
            idempotentHint=True,
            openWorldHint=False,
        ),
    )
    async def zotero_get_notes(params: GetNotesInput, ctx: Context) -> NotesResponse:
        """
        Get notes attached to a Zotero item.

        Retrieves notes with HTML content, automatically cleaning for display.
        Supports filtering by parent item or retrieving all notes.

        Args:
            params: Input containing:
                - item_key (str | None): Zotero item key to filter by. None for all notes
                - include_standalone (bool): Whether to include standalone notes (not attached to items)
                - response_format (str): Output format preference (inherited from BaseInput)
                - offset (int): Pagination offset (inherited from PaginatedInput)
                - limit (int): Maximum results (inherited from PaginatedInput)

        Returns:
            NotesResponse: Structured notes with cleaned content.

        Example:
            Use when: "Show me all notes for this paper"
            Use when: "Get standalone notes"
            Use when: "What notes did I write about this article?"
        """
        try:
            service = get_data_service()

            if not params.item_key:
                await ctx.error("item_key is required for get_notes")
                return NotesResponse(
                    success=False,
                    error="item_key is required",
                    item_key="",
                    count=0,
                    notes=[],
                )

            item_key_normalized = params.item_key.strip().upper()
            notes = await service.get_notes(item_key_normalized)

            if not notes:
                return NotesResponse(
                    item_key=item_key_normalized,
                    count=0,
                    notes=[],
                )

            # Process notes - clean HTML and extract content
            processed_notes = []
            for note in notes:
                data = note.get("data", {})
                note_key = data.get("key", "")
                note_content = data.get("note", "")

                # Clean HTML from note content
                clean_content = re.sub(r"<[^>]+>", "", note_content)
                clean_content = clean_content.replace("&nbsp;", " ").strip()

                # Truncate if too long (max 2000 chars per note in list)
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

            # Apply pagination
            total_count = len(processed_notes)
            start_idx = params.offset
            end_idx = start_idx + params.limit
            paginated_notes = processed_notes[start_idx:end_idx]
            has_more = end_idx < total_count

            return NotesResponse(
                item_key=item_key_normalized,
                count=len(paginated_notes),
                total_count=total_count,
                notes=paginated_notes,
                has_more=has_more,
                next_offset=end_idx if has_more else None,
            )

        except Exception as e:
            await ctx.error(f"Failed to get notes: {str(e)}")
            return NotesResponse(
                success=False,
                error=f"Notes retrieval error: {str(e)}",
                item_key=params.item_key or "",
                count=0,
                notes=[],
            )

    @mcp.tool(
        name="zotero_search_notes",
        annotations=ToolAnnotations(
            title="Search Notes and Annotations",
            readOnlyHint=True,
            destructiveHint=False,
            idempotentHint=True,
            openWorldHint=False,
        ),
    )
    async def zotero_search_notes(
        params: SearchNotesInput, ctx: Context
    ) -> SearchResponse:
        """
        Search through notes and annotations in your Zotero library.

        Performs full-text search across note content, with context extraction
        around matching text. Optionally includes annotations in search.

        Args:
            params: Input containing:
                - query (str): Search query to find in notes and annotations
                - include_annotations (bool): Whether to also search in PDF annotations
                - case_sensitive (bool): Whether the search should be case-sensitive
                - response_format (str): Output format preference (inherited from BaseInput)
                - offset (int): Pagination offset (inherited from PaginatedInput)
                - limit (int): Maximum results (inherited from PaginatedInput)

        Returns:
            SearchResponse: Search results with contextual excerpts.

        Example:
            Use when: "Search my notes for mentions of 'neural networks'"
            Use when: "Find notes containing the word 'methodology'"
            Use when: "Search annotations for 'important finding'"
        """
        try:
            service = get_data_service()

            # Search for items (broad search first)
            results = await service.search_items(
                query=params.query,
                limit=50,  # Get more to filter
                qmode="everything",
            )

            matches = []
            query_to_match = (
                params.query if params.case_sensitive else params.query.lower()
            )

            for result in results:
                # Get notes for this item
                try:
                    notes = await service.get_notes(result.key)
                    for note in notes:
                        data = note.get("data", {})
                        note_content = data.get("note", "")

                        # Clean HTML
                        clean = re.sub(r"<[^>]+>", "", note_content)
                        search_text = clean if params.case_sensitive else clean.lower()

                        if query_to_match in search_text:
                            # Extract matching context (200 chars around match)
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
                    # Skip items that error
                    continue

                if len(matches) >= params.limit:
                    break

            # Convert to SearchResultItem models
            result_items = [
                SearchResultItem(
                    key=match["item_key"],
                    title=match["item_title"],
                    creators=[],  # Not available in note search context
                    year=None,
                    item_type="note",
                    date_added=None,
                    snippet=f"...{match['context']}...",
                    raw_data=match,
                )
                for match in matches
            ]

            # Apply pagination
            total_count = len(result_items)
            start_idx = params.offset
            end_idx = start_idx + params.limit
            paginated_results = result_items[start_idx:end_idx]
            has_more = end_idx < total_count

            return SearchResponse(
                query=params.query,
                count=len(paginated_results),
                total_count=total_count,
                results=paginated_results,
                has_more=has_more,
                next_offset=end_idx if has_more else None,
            )

        except Exception as e:
            await ctx.error(f"Failed to search notes: {str(e)}")
            return SearchResponse(
                success=False,
                error=f"Note search error: {str(e)}",
                query=params.query,
                total=0,
                count=0,
                offset=0,
                limit=params.limit,
                has_more=False,
                results=[],
            )

    @mcp.tool(
        name="zotero_create_note",
        annotations=ToolAnnotations(
            title="Create Note",
            readOnlyHint=False,
            destructiveHint=False,
            idempotentHint=False,
            openWorldHint=False,
        ),
    )
    async def zotero_create_note(
        params: CreateNoteInput, ctx: Context
    ) -> NoteCreationResponse:
        """
        Create a new note attached to a Zotero item.

        Creates a note with HTML formatting, automatically converting plain text
        to HTML. Supports optional tags for organization.

        Args:
            params: Input containing:
                - item_key (str): Parent item key to attach the note to
                - content (str): Note content in HTML or plain text format
                - tags (list[str] | None): Optional tags to add to the note
                - response_format (str): Output format preference (inherited from BaseInput)

        Returns:
            NoteCreationResponse: Confirmation with created note key.

        Example:
            Use when: "Create a note on this paper about the methodology"
            Use when: "Add a note with my thoughts on this article"
            Use when: "Create a summary note for this item"

        Note:
            This feature requires Web API access (ZOTERO_API_KEY).
            It is NOT supported when using the Local API only.
        """
        try:
            service = get_data_service()

            # Convert plain text to basic HTML if not already HTML
            html_content = params.content
            if not params.content.strip().startswith("<"):
                html_content = f"<p>{params.content}</p>"
                html_content = html_content.replace("\n\n", "</p><p>")
                html_content = html_content.replace("\n", "<br/>")

            item_key_normalized = params.item_key.strip().upper()

            result = await service.create_note(
                parent_key=item_key_normalized,
                content=html_content,
                tags=params.tags,
            )

            if result:
                # Extract note key from result
                if isinstance(result, dict):
                    success = result.get("successful", {})
                    if success:
                        note_data = list(success.values())[0] if success else {}
                        note_key = note_data.get("key", "unknown")
                        return NoteCreationResponse(
                            note_key=note_key,
                            parent_key=item_key_normalized,
                            message=f"Note created successfully with key: {note_key}",
                        )

                return NoteCreationResponse(
                    note_key="unknown",
                    parent_key=item_key_normalized,
                    message="Note created successfully (key not returned)",
                )

            # Creation failed
            await ctx.error("Failed to create note: No result returned")
            return NoteCreationResponse(
                success=False,
                error="Failed to create note. Please check the item key and try again.",
                note_key="",
                parent_key=item_key_normalized,
            )

        except Exception as e:
            await ctx.error(f"Failed to create note: {str(e)}")
            return NoteCreationResponse(
                success=False,
                error=f"Note creation error: {str(e)}",
                note_key="",
                parent_key=params.item_key,
            )
