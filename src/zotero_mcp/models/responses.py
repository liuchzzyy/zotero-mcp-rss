"""Response formatting utilities (Logseq-style)."""

from __future__ import annotations

import json
from typing import Any

from zotero_mcp.formatters import JSONFormatter, MarkdownFormatter
from zotero_mcp.models.common import ResponseFormat
from zotero_mcp.models.common.responses import (
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
)
from zotero_mcp.models.workflow.analysis import (
    BatchAnalyzeResponse,
    FindCollectionResponse,
    PrepareAnalysisResponse,
    WorkflowListResponse,
)
from zotero_mcp.models.workflow.batch import BatchGetMetadataResponse


class Formatters:
    """Format response models into text outputs."""

    _json = JSONFormatter()
    _md = MarkdownFormatter()
    _max_inline_json_chars = 20000

    @classmethod
    def _truncate_json(cls, text: str) -> str:
        if len(text) <= cls._max_inline_json_chars:
            return text
        return (
            text[: cls._max_inline_json_chars]
            + "\n... (truncated)\n"
        )

    @classmethod
    def format_response(cls, response: Any, response_format: ResponseFormat) -> str:
        """Format a response model into text."""
        if response_format == ResponseFormat.JSON:
            return cls._format_json(response)
        return cls._format_markdown(response)

    @classmethod
    def _format_json(cls, response: Any) -> str:
        if hasattr(response, "model_dump"):
            return json.dumps(response.model_dump(), indent=2, ensure_ascii=False)
        return json.dumps(response, indent=2, ensure_ascii=False)

    @classmethod
    def _format_markdown(cls, response: Any) -> str:
        if isinstance(response, SearchResponse):
            items = [item.model_dump() for item in response.items]
            total_value = (
                response.total_count
                if response.total_count is not None
                else response.total
            )
            return cls._md.format_search_results(
                items=items,
                query=response.query,
                total=total_value,
                offset=response.offset,
                limit=response.limit,
            )

        if isinstance(response, ItemDetailResponse):
            lines = [
                f"# {response.title}",
                "",
                f"**Key:** `{response.key}`",
                f"**Type:** {response.item_type}",
            ]
            if response.authors:
                lines.append(f"**Authors:** {response.authors}")
            if response.date:
                lines.append(f"**Date:** {response.date}")
            if response.publication:
                lines.append(f"**Publication:** {response.publication}")
            if response.doi:
                lines.append(f"**DOI:** {response.doi}")
            if response.url:
                lines.append(f"**URL:** {response.url}")
            if response.tags:
                lines.append(f"**Tags:** {', '.join(response.tags)}")
            if response.abstract:
                lines.extend(["", "## Abstract", "", response.abstract])
            return "\n".join(lines)

        if isinstance(response, FulltextResponse):
            if not response.fulltext:
                return (
                    f"# Full Text for `{response.item_key}`\n\n"
                    f"❌ {response.error or 'No full text available.'}"
                )
            return (
                f"# Full Text for `{response.item_key}`\n\n"
                f"Length: {response.length}\n\n"
                f"{response.fulltext}"
            )

        if isinstance(response, CollectionsResponse):
            collections = [c.model_dump() for c in response.collections]
            return cls._md.format_collections(collections)

        if isinstance(response, AnnotationsResponse):
            annotations = [a.model_dump() for a in response.annotations]
            title = f"Annotations for `{response.item_key}`"
            return cls._md.format_annotations(annotations, item_title=title)

        if isinstance(response, NotesResponse):
            if not response.notes:
                return f"# Notes for `{response.item_key}`\n\nNo notes found."
            lines = [
                f"# Notes for `{response.item_key}`",
                "",
                f"Found {response.count} note(s).",
                "",
            ]
            for note in response.notes:
                data = note.get("data", note)
                title = data.get("title") or data.get("note", "")[:80]
                key = data.get("key", note.get("key", "unknown"))
                snippet = data.get("content") or data.get("note") or ""
                snippet = snippet[:200] + ("..." if len(snippet) > 200 else "")
                lines.append(f"- **{title}** (`{key}`) {snippet}")
            return "\n".join(lines)

        if isinstance(response, BundleResponse):
            lines = [
                f"# Bundle for `{response.metadata.key}`",
                "",
                f"**Title:** {response.metadata.title}",
                f"**Type:** {response.metadata.item_type}",
                f"**Attachments:** {len(response.attachments)}",
                f"**Notes:** {len(response.notes)}",
                f"**Annotations:** {len(response.annotations)}",
            ]
            if response.metadata.authors:
                lines.insert(3, f"**Authors:** {response.metadata.authors}")
            if response.metadata.date:
                lines.insert(4, f"**Date:** {response.metadata.date}")
            if response.fulltext:
                lines.extend(
                    ["", "## Fulltext (excerpt)", "", response.fulltext[:2000]]
                )
            return "\n".join(lines)

        if isinstance(response, DatabaseStatusResponse):
            lines = [
                "# Semantic Search Database Status",
                "",
                f"**Exists:** {response.exists}",
                f"**Items:** {response.item_count}",
                f"**Embedding Model:** {response.embedding_model}",
            ]
            if response.last_updated:
                lines.append(f"**Last Updated:** {response.last_updated}")
            if response.message:
                lines.append(f"**Message:** {response.message}")
            return "\n".join(lines)

        if isinstance(response, DatabaseUpdateResponse):
            lines = [
                "# Semantic Search Database Update",
                "",
                f"**Items Processed:** {response.items_processed}",
                f"**Items Added:** {response.items_added}",
                f"**Items Updated:** {response.items_updated}",
                f"**Duration (s):** {response.duration_seconds}",
                f"**Force Rebuild:** {response.force_rebuild}",
                f"**Fulltext Included:** {response.fulltext_included}",
            ]
            if response.message:
                lines.append(f"**Message:** {response.message}")
            return "\n".join(lines)

        if isinstance(response, NoteCreationResponse):
            if not response.success:
                return f"❌ {response.error or 'Failed to create note.'}"
            return (
                f"# Note Created\n\n"
                f"**Parent:** `{response.parent_key}`\n"
                f"**Note Key:** `{response.note_key}`\n"
                f"**Message:** {response.message}"
            )

        if isinstance(response, PrepareAnalysisResponse):
            lines = [
                "# Prepare Analysis",
                "",
                f"**Total Items:** {response.total_items}",
                f"**Prepared:** {response.prepared_items}",
                f"**Skipped:** {response.skipped}",
            ]
            if response.items:
                lines.append("")
                lines.append("## Items")
                for item in response.items:
                    author = f" - {item.authors}" if item.authors else ""
                    lines.append(f"- **{item.title}** (`{item.item_key}`){author}")
            return "\n".join(lines)

        if isinstance(response, BatchAnalyzeResponse):
            lines = [
                "# Batch Analyze PDFs",
                "",
                f"**Workflow ID:** {response.workflow_id}",
                f"**Total Items:** {response.total_items}",
                f"**Processed:** {response.processed}",
                f"**Skipped:** {response.skipped}",
                f"**Failed:** {response.failed}",
                f"**Status:** {response.status}",
            ]
            if response.results:
                lines.append("")
                lines.append("## Results")
                for result in response.results[:50]:
                    status = (
                        "skipped"
                        if result.skipped
                        else ("ok" if result.success else "failed")
                    )
                    extra = f" - {result.error}" if result.error else ""
                    lines.append(
                        f"- {result.title} (`{result.item_key}`): {status}{extra}"
                    )
            return "\n".join(lines)

        if isinstance(response, WorkflowListResponse):
            lines = ["# Workflows", "", f"Found {response.count} workflow(s).", ""]
            for wf in response.workflows:
                lines.append(
                    f"- `{wf.workflow_id}` ({wf.status}) {wf.processed}/{wf.total_items} source={wf.source_type}"
                )
            return "\n".join(lines)

        if isinstance(response, FindCollectionResponse):
            lines = [
                f"# Collection Search: {response.query}",
                "",
                f"Found {response.count} match(es).",
                "",
            ]
            for match in response.matches:
                lines.append(
                    f"- **{match.name}** (`{match.key}`) items={match.item_count} score={match.match_score}"
                )
            return "\n".join(lines)

        if isinstance(response, BatchGetMetadataResponse):
            lines = [
                "# Batch Metadata",
                "",
                f"**Requested:** {response.total_requested}",
                f"**Successful:** {response.successful}",
                f"**Failed:** {response.failed}",
            ]
            for result in response.results:
                if result.success and result.data:
                    lines.append(f"- {result.data.title} (`{result.data.key}`) ok")
                else:
                    lines.append(f"- {result.item_key}: failed")
            return "\n".join(lines)

        if isinstance(response, BaseResponse):
            if response.success:
                return "Success."
            return f"❌ {response.error or 'Operation failed.'}"

        if isinstance(response, dict):
            return cls._truncate_json(
                json.dumps(response, indent=2, ensure_ascii=False)
            )

        return str(response)
