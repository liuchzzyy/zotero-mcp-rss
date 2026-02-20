"""Workflow command group."""

from __future__ import annotations

import argparse
import asyncio
import sys
from typing import Any

from zotero_mcp.cli_app.common import (
    add_output_arg,
    add_scan_limit_arg,
    add_treated_limit_arg,
)
from zotero_mcp.cli_app.output import emit
from zotero_mcp.utils.config import load_config


def register(subparsers: argparse._SubParsersAction) -> None:
    workflow = subparsers.add_parser("workflow", help="Batch workflow commands")
    workflow_sub = workflow.add_subparsers(dest="subcommand", required=True)

    item_analysis = workflow_sub.add_parser(
        "item-analysis", help="Scan library and analyze items without AI notes"
    )
    add_scan_limit_arg(item_analysis, default=100)
    add_treated_limit_arg(
        item_analysis,
        default=20,
        help_text="Maximum total items to process (default: 20)",
    )
    item_analysis.add_argument(
        "--target-collection",
        required=True,
        help="Move items to this collection after analysis (required)",
    )
    item_analysis.add_argument(
        "--dry-run",
        action=argparse.BooleanOptionalAction,
        default=False,
        help="Preview without processing (default: disabled)",
    )
    item_analysis.add_argument(
        "--llm-provider",
        choices=["auto", "claude-cli", "deepseek", "openai", "gemini"],
        default="auto",
        help="LLM provider for analysis (default: auto)",
    )
    item_analysis.add_argument(
        "--source-collection",
        default="00_INBOXS",
        help="Collection to scan first (default: 00_INBOXS)",
    )
    item_analysis.add_argument(
        "--multimodal",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Enable/disable multi-modal analysis (default: enabled)",
    )
    add_output_arg(item_analysis)

    metadata = workflow_sub.add_parser(
        "metadata-update", help="Update item metadata from external APIs"
    )
    metadata.add_argument("--collection", help="Limit to specific collection (by key)")
    add_scan_limit_arg(metadata, default=500)
    add_treated_limit_arg(metadata)
    metadata.add_argument("--item-key", help="Update a specific item by key")
    metadata.add_argument(
        "--dry-run",
        action=argparse.BooleanOptionalAction,
        default=False,
        help="Preview metadata updates without applying changes (default: disabled)",
    )
    add_output_arg(metadata)

    dedup = workflow_sub.add_parser(
        "deduplicate", help="Find and remove duplicate items"
    )
    dedup.add_argument("--collection", help="Limit to specific collection (by key)")
    add_scan_limit_arg(dedup, default=500)
    add_treated_limit_arg(
        dedup,
        default=100,
        help_text="Maximum total number of items to scan (default: 100)",
    )
    dedup.add_argument(
        "--dry-run",
        action=argparse.BooleanOptionalAction,
        default=False,
        help="Preview duplicates without deleting (default: disabled)",
    )
    add_output_arg(dedup)

async def _run_item_analysis(args: argparse.Namespace) -> dict[str, Any]:
    from zotero_mcp.services.scanner import GlobalScanner

    scanner = GlobalScanner()
    return await scanner.scan_and_process(
        scan_limit=args.scan_limit,
        treated_limit=args.treated_limit,
        target_collection=args.target_collection,
        dry_run=args.dry_run,
        llm_provider=args.llm_provider,
        source_collection=args.source_collection,
        include_multimodal=args.multimodal,
    )


async def _run_metadata_update(args: argparse.Namespace) -> dict[str, Any]:
    from zotero_mcp.services.data_access import DataAccessService
    from zotero_mcp.services.zotero.metadata_update_service import MetadataUpdateService

    data_service = DataAccessService()
    update_service = MetadataUpdateService(
        data_service.item_service,
        data_service.metadata_service,
    )
    if args.item_key:
        return await update_service.update_item_metadata(
            args.item_key,
            dry_run=args.dry_run,
        )
    return await update_service.update_all_items(
        collection_key=args.collection,
        scan_limit=args.scan_limit,
        treated_limit=args.treated_limit,
        dry_run=args.dry_run,
    )


async def _run_deduplicate(args: argparse.Namespace) -> dict[str, Any]:
    from zotero_mcp.services.data_access import DataAccessService
    from zotero_mcp.services.zotero.duplicate_service import DuplicateDetectionService

    data_service = DataAccessService()
    service = DuplicateDetectionService(data_service.item_service)
    return await service.find_and_remove_duplicates(
        collection_key=args.collection,
        scan_limit=args.scan_limit,
        treated_limit=args.treated_limit,
        dry_run=args.dry_run,
    )


def _exit_code(result: dict[str, Any]) -> int:
    if result.get("error"):
        return 1
    success = result.get("success")
    if success is False:
        return 1
    return 0


def run(args: argparse.Namespace) -> int:
    load_config()

    handlers = {
        "item-analysis": _run_item_analysis,
        "metadata-update": _run_metadata_update,
        "deduplicate": _run_deduplicate,
    }

    handler = handlers.get(args.subcommand)
    if handler is None:
        print(f"Unknown workflow subcommand: {args.subcommand}", file=sys.stderr)
        return 1

    result = asyncio.run(handler(args))
    emit(args, result)
    return _exit_code(result)


__all__ = ["register", "run"]
