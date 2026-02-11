"""MCP prompt handler (placeholder for future prompts)."""

from __future__ import annotations

import json
from typing import Any

from mcp.types import (
    GetPromptResult,
    Prompt,
    PromptArgument,
    PromptMessage,
    TextContent,
)


class PromptHandler:
    """Handler for MCP prompts."""

    @staticmethod
    def get_prompts() -> list[Prompt]:
        """Return available prompts."""
        prompts: list[Prompt] = []

        # Aliases (kept for convenience)
        prompts.extend(
            [
                Prompt(
                    name="zotero_search_items",
                    description="Search Zotero items by keyword (alias of zotero_search)",
                    arguments=[
                        PromptArgument(
                            name="query", description="Search keywords", required=True
                        ),
                        PromptArgument(
                            name="limit",
                            description="Maximum results (default: 25)",
                            required=False,
                        ),
                    ],
                ),
                Prompt(
                    name="zotero_get_item",
                    description="Fetch a single Zotero item by key (alias of zotero_get_metadata)",
                    arguments=[
                        PromptArgument(
                            name="item_key",
                            description="Zotero item key (8-character alphanumeric)",
                            required=True,
                        ),
                    ],
                ),
                Prompt(
                    name="zotero_analyze_paper",
                    description="Analyze a local PDF (alias of zotero_batch_analyze_pdfs / workflow)",
                    arguments=[
                        PromptArgument(
                            name="file_path",
                            description="Path to the PDF file",
                            required=True,
                        ),
                        PromptArgument(
                            name="template",
                            description="Template name (default/multimodal/structured)",
                            required=False,
                        ),
                        PromptArgument(
                            name="extract_images",
                            description="Extract images for multimodal analysis (true/false)",
                            required=False,
                        ),
                    ],
                ),
            ]
        )

        # Search tools
        prompts.extend(
            [
                Prompt(
                    name="zotero_search",
                    description="Search Zotero items by keyword",
                    arguments=[
                        PromptArgument(
                            name="query", description="Search keywords", required=True
                        ),
                        PromptArgument(
                            name="limit",
                            description="Maximum results (default: 20)",
                            required=False,
                        ),
                        PromptArgument(
                            name="offset",
                            description="Pagination offset (default: 0)",
                            required=False,
                        ),
                        PromptArgument(
                            name="qmode",
                            description="Search mode: titleCreatorYear | everything",
                            required=False,
                        ),
                    ],
                ),
                Prompt(
                    name="zotero_search_by_tag",
                    description="Search Zotero items by tag",
                    arguments=[
                        PromptArgument(
                            name="tags",
                            description="Tag list (use -tag to exclude)",
                            required=True,
                        ),
                        PromptArgument(
                            name="limit",
                            description="Maximum results (default: 20)",
                            required=False,
                        ),
                    ],
                ),
                Prompt(
                    name="zotero_advanced_search",
                    description="Advanced multi-field search",
                    arguments=[
                        PromptArgument(
                            name="conditions",
                            description="Search conditions list",
                            required=True,
                        ),
                        PromptArgument(
                            name="join_mode", description="all | any", required=False
                        ),
                        PromptArgument(
                            name="limit", description="Maximum results", required=False
                        ),
                        PromptArgument(
                            name="offset",
                            description="Pagination offset",
                            required=False,
                        ),
                    ],
                ),
                Prompt(
                    name="zotero_semantic_search",
                    description="AI semantic similarity search",
                    arguments=[
                        PromptArgument(
                            name="query",
                            description="Natural language query",
                            required=True,
                        ),
                        PromptArgument(
                            name="limit",
                            description="Maximum results (default: 10)",
                            required=False,
                        ),
                    ],
                ),
                Prompt(
                    name="zotero_get_recent",
                    description="Get recently added items",
                    arguments=[
                        PromptArgument(
                            name="days",
                            description="Look back window in days",
                            required=False,
                        ),
                        PromptArgument(
                            name="limit", description="Maximum results", required=False
                        ),
                    ],
                ),
            ]
        )

        # Item tools
        prompts.extend(
            [
                Prompt(
                    name="zotero_get_metadata",
                    description="Get item metadata",
                    arguments=[
                        PromptArgument(
                            name="item_key",
                            description="Zotero item key",
                            required=True,
                        ),
                        PromptArgument(
                            name="include_abstract",
                            description="Include abstract (default: true)",
                            required=False,
                        ),
                        PromptArgument(
                            name="output_format",
                            description="markdown | json",
                            required=False,
                        ),
                    ],
                ),
                Prompt(
                    name="zotero_get_fulltext",
                    description="Get full text content",
                    arguments=[
                        PromptArgument(
                            name="item_key",
                            description="Zotero item key",
                            required=True,
                        ),
                        PromptArgument(
                            name="max_length",
                            description="Maximum characters to return",
                            required=False,
                        ),
                    ],
                ),
                Prompt(
                    name="zotero_get_children",
                    description="Get attachments/notes for an item",
                    arguments=[
                        PromptArgument(
                            name="item_key",
                            description="Parent item key",
                            required=True,
                        ),
                        PromptArgument(
                            name="child_type",
                            description="all | attachment | note",
                            required=False,
                        ),
                    ],
                ),
                Prompt(
                    name="zotero_get_collections",
                    description="List collections or items in a collection",
                    arguments=[
                        PromptArgument(
                            name="collection_key",
                            description="Collection key (omit to list all)",
                            required=False,
                        ),
                        PromptArgument(
                            name="limit",
                            description="Maximum items when listing",
                            required=False,
                        ),
                    ],
                ),
                Prompt(
                    name="zotero_get_bundle",
                    description="Get comprehensive item bundle",
                    arguments=[
                        PromptArgument(
                            name="item_key",
                            description="Zotero item key",
                            required=True,
                        ),
                        PromptArgument(
                            name="include_fulltext",
                            description="Include full text (true/false)",
                            required=False,
                        ),
                        PromptArgument(
                            name="include_annotations",
                            description="Include PDF annotations (true/false)",
                            required=False,
                        ),
                        PromptArgument(
                            name="include_notes",
                            description="Include notes (true/false)",
                            required=False,
                        ),
                    ],
                ),
            ]
        )

        # Annotation tools
        prompts.extend(
            [
                Prompt(
                    name="zotero_get_annotations",
                    description="Get PDF annotations for an item",
                    arguments=[
                        PromptArgument(
                            name="item_key",
                            description="Zotero item key",
                            required=True,
                        ),
                        PromptArgument(
                            name="annotation_type",
                            description="all | highlight | note | underline | image",
                            required=False,
                        ),
                        PromptArgument(
                            name="use_pdf_extraction",
                            description="Fallback to PDF extraction (true/false)",
                            required=False,
                        ),
                        PromptArgument(
                            name="offset",
                            description="Pagination offset",
                            required=False,
                        ),
                        PromptArgument(
                            name="limit", description="Maximum results", required=False
                        ),
                    ],
                ),
                Prompt(
                    name="zotero_get_notes",
                    description="Get notes for an item",
                    arguments=[
                        PromptArgument(
                            name="item_key",
                            description="Zotero item key",
                            required=True,
                        ),
                        PromptArgument(
                            name="include_standalone",
                            description="Include standalone notes (true/false)",
                            required=False,
                        ),
                        PromptArgument(
                            name="offset",
                            description="Pagination offset",
                            required=False,
                        ),
                        PromptArgument(
                            name="limit", description="Maximum results", required=False
                        ),
                    ],
                ),
                Prompt(
                    name="zotero_search_notes",
                    description="Search notes and annotations",
                    arguments=[
                        PromptArgument(
                            name="query", description="Search query", required=True
                        ),
                        PromptArgument(
                            name="include_annotations",
                            description="Include annotations in search (true/false)",
                            required=False,
                        ),
                        PromptArgument(
                            name="case_sensitive",
                            description="Case sensitive search (true/false)",
                            required=False,
                        ),
                        PromptArgument(
                            name="offset",
                            description="Pagination offset",
                            required=False,
                        ),
                        PromptArgument(
                            name="limit", description="Maximum results", required=False
                        ),
                    ],
                ),
                Prompt(
                    name="zotero_create_note",
                    description="Create a note attached to an item",
                    arguments=[
                        PromptArgument(
                            name="item_key",
                            description="Parent item key",
                            required=True,
                        ),
                        PromptArgument(
                            name="content",
                            description="Note content (text or HTML)",
                            required=True,
                        ),
                        PromptArgument(
                            name="tags",
                            description="Optional tags list",
                            required=False,
                        ),
                    ],
                ),
            ]
        )

        # Collection management tools
        prompts.extend(
            [
                Prompt(
                    name="zotero_create_collection",
                    description="Create a collection",
                    arguments=[
                        PromptArgument(
                            name="name", description="Collection name", required=True
                        ),
                        PromptArgument(
                            name="parent_key",
                            description="Parent collection key",
                            required=False,
                        ),
                    ],
                ),
                Prompt(
                    name="zotero_delete_collection",
                    description="Delete a collection",
                    arguments=[
                        PromptArgument(
                            name="collection_key",
                            description="Collection key",
                            required=True,
                        ),
                    ],
                ),
                Prompt(
                    name="zotero_move_collection",
                    description="Move a collection",
                    arguments=[
                        PromptArgument(
                            name="collection_key",
                            description="Collection key",
                            required=True,
                        ),
                        PromptArgument(
                            name="parent_key",
                            description="New parent key (or 'root')",
                            required=True,
                        ),
                    ],
                ),
                Prompt(
                    name="zotero_rename_collection",
                    description="Rename a collection",
                    arguments=[
                        PromptArgument(
                            name="collection_key",
                            description="Collection key",
                            required=True,
                        ),
                        PromptArgument(
                            name="new_name",
                            description="New collection name",
                            required=True,
                        ),
                    ],
                ),
            ]
        )

        # Database tools
        prompts.extend(
            [
                Prompt(
                    name="zotero_update_database",
                    description="Update semantic search database",
                    arguments=[
                        PromptArgument(
                            name="force_rebuild",
                            description="Rebuild from scratch (true/false)",
                            required=False,
                        ),
                        PromptArgument(
                            name="limit",
                            description="Maximum items to process",
                            required=False,
                        ),
                        PromptArgument(
                            name="extract_fulltext",
                            description="Index full text (true/false)",
                            required=False,
                        ),
                    ],
                ),
                Prompt(
                    name="zotero_database_status",
                    description="Get semantic search database status",
                    arguments=[],
                ),
            ]
        )

        # Batch tools
        prompts.append(
            Prompt(
                name="zotero_batch_get_metadata",
                description="Get metadata for multiple items",
                arguments=[
                    PromptArgument(
                        name="item_keys",
                        description="List of Zotero item keys",
                        required=True,
                    ),
                ],
            )
        )

        # Workflow tools
        prompts.extend(
            [
                Prompt(
                    name="zotero_prepare_analysis",
                    description="Prepare analysis data (Mode A)",
                    arguments=[
                        PromptArgument(
                            name="source",
                            description="collection | recent",
                            required=True,
                        ),
                        PromptArgument(
                            name="collection_name",
                            description="Collection name",
                            required=False,
                        ),
                        PromptArgument(
                            name="collection_key",
                            description="Collection key",
                            required=False,
                        ),
                        PromptArgument(
                            name="days",
                            description="Recent days window",
                            required=False,
                        ),
                        PromptArgument(
                            name="limit", description="Maximum items", required=False
                        ),
                        PromptArgument(
                            name="include_annotations",
                            description="Include annotations",
                            required=False,
                        ),
                        PromptArgument(
                            name="include_multimodal",
                            description="Extract images/tables",
                            required=False,
                        ),
                        PromptArgument(
                            name="skip_existing_notes",
                            description="Skip items with notes",
                            required=False,
                        ),
                    ],
                ),
                Prompt(
                    name="zotero_batch_analyze_pdfs",
                    description="Batch analyze PDFs (Mode B)",
                    arguments=[
                        PromptArgument(
                            name="source",
                            description="collection | recent",
                            required=True,
                        ),
                        PromptArgument(
                            name="collection_name",
                            description="Collection name",
                            required=False,
                        ),
                        PromptArgument(
                            name="collection_key",
                            description="Collection key",
                            required=False,
                        ),
                        PromptArgument(
                            name="days",
                            description="Recent days window",
                            required=False,
                        ),
                        PromptArgument(
                            name="limit", description="Maximum items", required=False
                        ),
                        PromptArgument(
                            name="resume_workflow_id",
                            description="Resume workflow ID",
                            required=False,
                        ),
                        PromptArgument(
                            name="skip_existing_notes",
                            description="Skip items with notes",
                            required=False,
                        ),
                        PromptArgument(
                            name="include_annotations",
                            description="Include annotations",
                            required=False,
                        ),
                        PromptArgument(
                            name="include_multimodal",
                            description="Extract images/tables",
                            required=False,
                        ),
                        PromptArgument(
                            name="llm_provider",
                            description="deepseek | claude-cli | auto",
                            required=False,
                        ),
                        PromptArgument(
                            name="llm_model", description="Model name", required=False
                        ),
                        PromptArgument(
                            name="template", description="Template name", required=False
                        ),
                        PromptArgument(
                            name="dry_run",
                            description="Preview only (true/false)",
                            required=False,
                        ),
                    ],
                ),
                Prompt(
                    name="zotero_resume_workflow",
                    description="Resume an interrupted workflow",
                    arguments=[
                        PromptArgument(
                            name="workflow_id", description="Workflow ID", required=True
                        ),
                    ],
                ),
                Prompt(
                    name="zotero_list_workflows",
                    description="List workflows and status",
                    arguments=[],
                ),
                Prompt(
                    name="zotero_find_collection",
                    description="Find collection by name",
                    arguments=[
                        PromptArgument(
                            name="name", description="Collection name", required=True
                        ),
                        PromptArgument(
                            name="exact_match",
                            description="Exact match only (true/false)",
                            required=False,
                        ),
                    ],
                ),
            ]
        )

        return prompts

    async def handle_prompt(
        self, name: str, arguments: dict[str, Any] | None
    ) -> GetPromptResult:
        """Build a prompt message for common Zotero workflows."""
        arguments = arguments or {}

        alias_to_tool = {
            "zotero_search_items": "zotero_search",
            "zotero_get_item": "zotero_get_metadata",
            "zotero_analyze_paper": "zotero_batch_analyze_pdfs",
        }

        tool_name = alias_to_tool.get(name, name)

        if not tool_name.startswith("zotero_"):
            return GetPromptResult(
                description=f"Unknown prompt: {name}",
                messages=[
                    PromptMessage(
                        role="user",
                        content=TextContent(
                            type="text", text=f"Unknown prompt: {name}"
                        ),
                    )
                ],
            )

        payload = json.dumps(arguments, ensure_ascii=False, indent=2)
        text = (
            f"Please call tool `{tool_name}` with the following arguments:\n{payload}"
        )
        description = f"Call tool: {tool_name}"

        return GetPromptResult(
            description=description,
            messages=[
                PromptMessage(role="user", content=TextContent(type="text", text=text))
            ],
        )
