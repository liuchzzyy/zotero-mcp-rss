"""MCP prompt handler (placeholder for future prompts)."""

from __future__ import annotations

from typing import Any

import json

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
                        PromptArgument("query", "Search keywords", True),
                        PromptArgument("limit", "Maximum results (default: 20)", False),
                        PromptArgument("offset", "Pagination offset (default: 0)", False),
                        PromptArgument(
                            "qmode",
                            "Search mode: titleCreatorYear | everything",
                            False,
                        ),
                    ],
                ),
                Prompt(
                    name="zotero_search_by_tag",
                    description="Search Zotero items by tag",
                    arguments=[
                        PromptArgument(
                            "tags", "Tag list (use -tag to exclude)", True
                        ),
                        PromptArgument("limit", "Maximum results (default: 20)", False),
                    ],
                ),
                Prompt(
                    name="zotero_advanced_search",
                    description="Advanced multi-field search",
                    arguments=[
                        PromptArgument("conditions", "Search conditions list", True),
                        PromptArgument("join_mode", "all | any", False),
                        PromptArgument("limit", "Maximum results", False),
                        PromptArgument("offset", "Pagination offset", False),
                    ],
                ),
                Prompt(
                    name="zotero_semantic_search",
                    description="AI semantic similarity search",
                    arguments=[
                        PromptArgument("query", "Natural language query", True),
                        PromptArgument("limit", "Maximum results (default: 10)", False),
                    ],
                ),
                Prompt(
                    name="zotero_get_recent",
                    description="Get recently added items",
                    arguments=[
                        PromptArgument("days", "Look back window in days", False),
                        PromptArgument("limit", "Maximum results", False),
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
                        PromptArgument("item_key", "Zotero item key", True),
                        PromptArgument(
                            "include_abstract", "Include abstract (default: true)", False
                        ),
                        PromptArgument("output_format", "markdown | json", False),
                    ],
                ),
                Prompt(
                    name="zotero_get_fulltext",
                    description="Get full text content",
                    arguments=[
                        PromptArgument("item_key", "Zotero item key", True),
                        PromptArgument(
                            "max_length",
                            "Maximum characters to return",
                            False,
                        ),
                    ],
                ),
                Prompt(
                    name="zotero_get_children",
                    description="Get attachments/notes for an item",
                    arguments=[
                        PromptArgument("item_key", "Parent item key", True),
                        PromptArgument(
                            "child_type", "all | attachment | note", False
                        ),
                    ],
                ),
                Prompt(
                    name="zotero_get_collections",
                    description="List collections or items in a collection",
                    arguments=[
                        PromptArgument(
                            "collection_key",
                            "Collection key (omit to list all)",
                            False,
                        ),
                        PromptArgument("limit", "Maximum items when listing", False),
                    ],
                ),
                Prompt(
                    name="zotero_get_bundle",
                    description="Get comprehensive item bundle",
                    arguments=[
                        PromptArgument("item_key", "Zotero item key", True),
                        PromptArgument(
                            "include_fulltext", "Include full text (true/false)", False
                        ),
                        PromptArgument(
                            "include_annotations",
                            "Include PDF annotations (true/false)",
                            False,
                        ),
                        PromptArgument(
                            "include_notes", "Include notes (true/false)", False
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
                        PromptArgument("item_key", "Zotero item key", True),
                        PromptArgument(
                            "annotation_type",
                            "all | highlight | note | underline | image",
                            False,
                        ),
                        PromptArgument(
                            "use_pdf_extraction",
                            "Fallback to PDF extraction (true/false)",
                            False,
                        ),
                        PromptArgument("offset", "Pagination offset", False),
                        PromptArgument("limit", "Maximum results", False),
                    ],
                ),
                Prompt(
                    name="zotero_get_notes",
                    description="Get notes for an item",
                    arguments=[
                        PromptArgument("item_key", "Zotero item key", True),
                        PromptArgument(
                            "include_standalone",
                            "Include standalone notes (true/false)",
                            False,
                        ),
                        PromptArgument("offset", "Pagination offset", False),
                        PromptArgument("limit", "Maximum results", False),
                    ],
                ),
                Prompt(
                    name="zotero_search_notes",
                    description="Search notes and annotations",
                    arguments=[
                        PromptArgument("query", "Search query", True),
                        PromptArgument(
                            "include_annotations",
                            "Include annotations in search (true/false)",
                            False,
                        ),
                        PromptArgument(
                            "case_sensitive", "Case sensitive search (true/false)", False
                        ),
                        PromptArgument("offset", "Pagination offset", False),
                        PromptArgument("limit", "Maximum results", False),
                    ],
                ),
                Prompt(
                    name="zotero_create_note",
                    description="Create a note attached to an item",
                    arguments=[
                        PromptArgument("item_key", "Parent item key", True),
                        PromptArgument("content", "Note content (text or HTML)", True),
                        PromptArgument("tags", "Optional tags list", False),
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
                        PromptArgument("name", "Collection name", True),
                        PromptArgument("parent_key", "Parent collection key", False),
                    ],
                ),
                Prompt(
                    name="zotero_delete_collection",
                    description="Delete a collection",
                    arguments=[
                        PromptArgument("collection_key", "Collection key", True),
                    ],
                ),
                Prompt(
                    name="zotero_move_collection",
                    description="Move a collection",
                    arguments=[
                        PromptArgument("collection_key", "Collection key", True),
                        PromptArgument(
                            "parent_key",
                            "New parent key (or 'root')",
                            True,
                        ),
                    ],
                ),
                Prompt(
                    name="zotero_rename_collection",
                    description="Rename a collection",
                    arguments=[
                        PromptArgument("collection_key", "Collection key", True),
                        PromptArgument("new_name", "New collection name", True),
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
                            "force_rebuild",
                            "Rebuild from scratch (true/false)",
                            False,
                        ),
                        PromptArgument("limit", "Maximum items to process", False),
                        PromptArgument(
                            "extract_fulltext",
                            "Index full text (true/false)",
                            False,
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
                    PromptArgument("item_keys", "List of Zotero item keys", True),
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
                        PromptArgument("source", "collection | recent", True),
                        PromptArgument("collection_name", "Collection name", False),
                        PromptArgument("collection_key", "Collection key", False),
                        PromptArgument("days", "Recent days window", False),
                        PromptArgument("limit", "Maximum items", False),
                        PromptArgument(
                            "include_annotations", "Include annotations", False
                        ),
                        PromptArgument(
                            "include_multimodal", "Extract images/tables", False
                        ),
                        PromptArgument(
                            "skip_existing_notes", "Skip items with notes", False
                        ),
                    ],
                ),
                Prompt(
                    name="zotero_batch_analyze_pdfs",
                    description="Batch analyze PDFs (Mode B)",
                    arguments=[
                        PromptArgument("source", "collection | recent", True),
                        PromptArgument("collection_name", "Collection name", False),
                        PromptArgument("collection_key", "Collection key", False),
                        PromptArgument("days", "Recent days window", False),
                        PromptArgument("limit", "Maximum items", False),
                        PromptArgument("resume_workflow_id", "Resume workflow ID", False),
                        PromptArgument(
                            "skip_existing_notes", "Skip items with notes", False
                        ),
                        PromptArgument(
                            "include_annotations", "Include annotations", False
                        ),
                        PromptArgument(
                            "include_multimodal", "Extract images/tables", False
                        ),
                        PromptArgument("llm_provider", "deepseek | claude-cli | auto", False),
                        PromptArgument("llm_model", "Model name", False),
                        PromptArgument("template", "Template name", False),
                        PromptArgument("dry_run", "Preview only (true/false)", False),
                    ],
                ),
                Prompt(
                    name="zotero_resume_workflow",
                    description="Resume an interrupted workflow",
                    arguments=[
                        PromptArgument("workflow_id", "Workflow ID", True),
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
                        PromptArgument("name", "Collection name", True),
                        PromptArgument(
                            "exact_match", "Exact match only (true/false)", False
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
                        content=TextContent(type="text", text=f"Unknown prompt: {name}"),
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
            messages=[PromptMessage(role="user", content=TextContent(type="text", text=text))],
        )
