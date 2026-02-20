"""Tag command group."""

from __future__ import annotations

import argparse
import asyncio
from collections.abc import Awaitable, Callable
from typing import Any

from zotero_mcp.cli_app.common import add_output_arg
from zotero_mcp.cli_app.output import emit
from zotero_mcp.utils.config import load_config
from zotero_mcp.utils.formatting.helpers import normalize_item_key


def register(subparsers: argparse._SubParsersAction) -> None:
    tags_cmd = subparsers.add_parser("tags", help="Tag operations")
    tags_sub = tags_cmd.add_subparsers(dest="subcommand", required=True)

    list_cmd = tags_sub.add_parser("list", help="List tags in library")
    list_cmd.add_argument("--limit", type=int, default=100)
    add_output_arg(list_cmd)

    add_cmd = tags_sub.add_parser("add", help="Add tags to an item")
    add_cmd.add_argument("--item-key", required=True)
    add_cmd.add_argument("--tags", nargs="+", required=True)
    add_output_arg(add_cmd)

    search = tags_sub.add_parser("search", help="Search items by tags")
    search.add_argument("--tags", nargs="+", required=True)
    search.add_argument("--exclude-tags", nargs="*", default=[])
    search.add_argument("--limit", type=int, default=25)
    add_output_arg(search)

    delete = tags_sub.add_parser(
        "delete", help="Remove all tags except those starting with a prefix"
    )
    delete.add_argument("--collection", help="Limit to specific collection (by name)")
    delete.add_argument(
        "--batch-size",
        type=int,
        default=50,
        help="Number of items to process per batch (default: 50)",
    )
    delete.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Maximum total number of items to process",
    )
    delete.add_argument(
        "--keep-prefix",
        default="AI",
        help="Keep tags starting with this prefix (default: 'AI')",
    )
    delete.add_argument(
        "--dry-run", action="store_true", help="Preview changes without updating"
    )
    add_output_arg(delete)


def _exit_code(payload: Any) -> int:
    if not isinstance(payload, dict):
        return 0
    if payload.get("error"):
        return 1
    if payload.get("success") is False:
        return 1
    return 0


def run(args: argparse.Namespace) -> int:
    load_config()

    from zotero_mcp.services.data_access import DataAccessService
    from zotero_mcp.services.zotero.maintenance_service import LibraryMaintenanceService

    data_service = DataAccessService()
    maintenance_service = LibraryMaintenanceService(data_service=data_service)

    async def _list_tags() -> dict[str, Any]:
        tags = await data_service.get_tags(limit=args.limit)
        return {"count": len(tags), "tags": tags}

    async def _add_tags() -> dict[str, Any]:
        return await data_service.add_tags_to_item(
            item_key=normalize_item_key(args.item_key),
            tags=args.tags,
        )

    async def _search_tags() -> dict[str, Any]:
        results = await data_service.search_by_tag(
            tags=args.tags,
            exclude_tags=args.exclude_tags or None,
            limit=args.limit,
        )
        return {
            "query": {
                "tags": args.tags,
                "exclude_tags": args.exclude_tags,
                "limit": args.limit,
            },
            "count": len(results),
            "items": [item.model_dump() for item in results],
        }

    async def _delete_tags() -> dict[str, Any]:
        return await maintenance_service.clean_tags(
            collection_name=args.collection,
            batch_size=args.batch_size,
            limit=args.limit,
            keep_prefix=args.keep_prefix,
            dry_run=args.dry_run,
        )

    handlers: dict[str, Callable[[], Awaitable[dict[str, Any]]]] = {
        "list": _list_tags,
        "add": _add_tags,
        "search": _search_tags,
        "delete": _delete_tags,
    }

    handler = handlers.get(args.subcommand)
    if handler is None:
        raise ValueError(f"Unknown tags subcommand: {args.subcommand}")

    payload = asyncio.run(handler())
    emit(args, payload)
    return _exit_code(payload)


__all__ = ["register", "run"]
