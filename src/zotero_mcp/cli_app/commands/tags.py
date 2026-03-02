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
from zotero_mcp.utils.formatting.tags import (
    normalize_input_tags,
    normalize_tag_names,
    to_tag_objects,
)

_STATUS_VALUES: tuple[str, ...] = (
    "new",
    "reading",
    "read",
    "todo",
    "cited",
    "skip",
    "archive",
)
_STATUS_PREFIX = "status/"
_VALID_STATUS_TAGS = {f"{_STATUS_PREFIX}{value}" for value in _STATUS_VALUES}


async def _await_handler(
    handler: Callable[[], Awaitable[dict[str, Any]]],
) -> dict[str, Any]:
    return await handler()


def register(subparsers: argparse._SubParsersAction) -> None:
    tags_cmd = subparsers.add_parser("tags", help="Tag operations")
    tags_sub = tags_cmd.add_subparsers(dest="subcommand", required=True)

    list_cmd = tags_sub.add_parser("list", help="List tags in library")
    list_cmd.add_argument("--item-key", help="List tags for a specific item key")
    list_cmd.add_argument("--limit", type=int, default=100)
    add_output_arg(list_cmd)

    add_cmd = tags_sub.add_parser("add", help="Add tags to an item")
    add_cmd.add_argument("--item-key", required=True)
    add_cmd.add_argument("--tags", nargs="+", required=True)
    add_output_arg(add_cmd)

    set_status_cmd = tags_sub.add_parser(
        "set-status",
        help="Set exclusive status tag on an item (replaces existing status/* tags)",
    )
    set_status_cmd.add_argument("--item-key", required=True)
    set_status_cmd.add_argument(
        "--status",
        required=True,
        help=(
            "Status value or full tag. "
            f"Allowed: {', '.join(_STATUS_VALUES)} or status/<value>"
        ),
    )
    set_status_cmd.add_argument(
        "--dry-run",
        action=argparse.BooleanOptionalAction,
        default=False,
        help="Preview changes without updating (default: disabled)",
    )
    add_output_arg(set_status_cmd)

    search = tags_sub.add_parser("search", help="Search items by tags")
    search.add_argument("--tags", nargs="+", required=True)
    search.add_argument("--exclude-tags", nargs="*", default=[])
    search.add_argument("--limit", type=int, default=25)
    add_output_arg(search)

    delete = tags_sub.add_parser("delete", help="Delete tags from an item")
    delete.add_argument("--item-key", required=True)
    delete_mode = delete.add_mutually_exclusive_group(required=True)
    delete_mode.add_argument(
        "--tags",
        nargs="+",
        help="Tags to remove from the item",
    )
    delete_mode.add_argument(
        "--all",
        action="store_true",
        help="Remove all tags from the item",
    )
    delete.add_argument(
        "--dry-run",
        action=argparse.BooleanOptionalAction,
        default=False,
        help="Preview changes without updating (default: disabled)",
    )
    add_output_arg(delete)

    purge = tags_sub.add_parser(
        "purge", help="Purge selected tags in library or a named collection"
    )
    purge.add_argument("--tags", nargs="+", required=True)
    purge.add_argument("--collection", help="Limit to specific collection (by name)")
    purge.add_argument(
        "--batch-size",
        type=int,
        default=50,
        help="Number of items to process per batch (default: 50)",
    )
    purge.add_argument(
        "--scan-limit",
        type=int,
        default=None,
        help="Maximum total number of items to scan",
    )
    purge.add_argument(
        "--update-limit",
        type=int,
        default=None,
        help="Maximum total number of items to update",
    )
    purge.add_argument(
        "--dry-run",
        action=argparse.BooleanOptionalAction,
        default=False,
        help="Preview changes without updating (default: disabled)",
    )
    add_output_arg(purge)

    rename = tags_sub.add_parser("rename", help="Rename a tag across matched items")
    rename.add_argument("--old-name", required=True, help="Current tag name")
    rename.add_argument("--new-name", required=True, help="New tag name")
    rename.add_argument(
        "--limit",
        type=int,
        default=100,
        help="Maximum number of matched items to process (default: 100)",
    )
    rename.add_argument(
        "--dry-run",
        action=argparse.BooleanOptionalAction,
        default=False,
        help="Preview changes without updating (default: disabled)",
    )
    add_output_arg(rename)


def _exit_code(payload: Any) -> int:
    if not isinstance(payload, dict):
        return 0
    if payload.get("error"):
        return 1
    if payload.get("success") is False:
        return 1
    return 0


def _normalize_status_tag(raw_status: str) -> str | None:
    candidate = str(raw_status).strip().lower()
    if not candidate:
        return None

    if candidate.startswith(_STATUS_PREFIX):
        return candidate if candidate in _VALID_STATUS_TAGS else None

    tag = f"{_STATUS_PREFIX}{candidate}"
    return tag if tag in _VALID_STATUS_TAGS else None


def run(args: argparse.Namespace) -> int:
    load_config()

    from zotero_mcp.services.data_access import DataAccessService
    from zotero_mcp.services.zotero.maintenance_service import LibraryMaintenanceService

    data_service = DataAccessService()
    maintenance_service = LibraryMaintenanceService(data_service=data_service)

    async def _list_tags() -> dict[str, Any]:
        if args.item_key:
            item = await data_service.get_item(normalize_item_key(args.item_key))
            item_data = item.get("data", {})
            tag_names = normalize_tag_names(item_data.get("tags", []))
            return {
                "item_key": normalize_item_key(args.item_key),
                "count": len(tag_names),
                "tags": tag_names,
            }
        tags = await data_service.get_tags(limit=args.limit)
        return {"count": len(tags), "tags": tags}

    async def _add_tags() -> dict[str, Any]:
        normalized_tags = normalize_input_tags(args.tags)
        if not normalized_tags:
            return {"error": "At least one non-empty tag is required"}
        return await data_service.add_tags_to_item(
            item_key=normalize_item_key(args.item_key),
            tags=normalized_tags,
        )

    async def _set_status() -> dict[str, Any]:
        target_status_tag = _normalize_status_tag(args.status)
        if target_status_tag is None:
            allowed = ", ".join(_STATUS_VALUES)
            return {
                "error": (
                    f"Invalid status '{args.status}'. "
                    f"Allowed values: {allowed} or status/<value>"
                )
            }

        item_key = normalize_item_key(args.item_key)
        item = await data_service.get_item(item_key)
        item_data = item.get("data", {})
        existing_tags = normalize_tag_names(item_data.get("tags", []))
        removed_status_tags = [
            tag for tag in existing_tags if tag.startswith(_STATUS_PREFIX)
        ]
        kept_non_status_tags = [
            tag for tag in existing_tags if not tag.startswith(_STATUS_PREFIX)
        ]
        updated_tags = normalize_input_tags([*kept_non_status_tags, target_status_tag])
        changed = normalize_input_tags(existing_tags) != updated_tags

        if changed and not args.dry_run:
            item["data"]["tags"] = to_tag_objects(updated_tags)
            await data_service.update_item(item)

        return {
            "item_key": item_key,
            "dry_run": args.dry_run,
            "status": target_status_tag,
            "changed": changed,
            "removed_status_count": len(removed_status_tags),
            "removed_status_tags": sorted(set(removed_status_tags)),
            "total_before": len(existing_tags),
            "total_after": len(updated_tags),
            "tags": updated_tags,
        }

    async def _search_tags() -> dict[str, Any]:
        include_tags = normalize_input_tags(args.tags)
        exclude_tags = normalize_input_tags(args.exclude_tags)
        if not include_tags:
            return {"error": "At least one non-empty tag is required"}

        results = await data_service.search_by_tag(
            tags=include_tags,
            exclude_tags=exclude_tags or None,
            limit=args.limit,
        )
        return {
            "query": {
                "tags": include_tags,
                "exclude_tags": exclude_tags,
                "limit": args.limit,
            },
            "count": len(results),
            "items": [item.model_dump() for item in results],
        }

    async def _delete_tags() -> dict[str, Any]:
        item_key = normalize_item_key(args.item_key)
        item = await data_service.get_item(item_key)
        item_data = item.get("data", {})
        existing_tags = normalize_tag_names(item_data.get("tags", []))

        if args.all:
            removed_tags = existing_tags
            kept_tags: list[str] = []
            requested_tags: list[str] = []
        else:
            requested_tags = normalize_input_tags(args.tags)
            remove_set = set(requested_tags)
            removed_tags = [tag for tag in existing_tags if tag in remove_set]
            kept_tags = [tag for tag in existing_tags if tag not in remove_set]

        if removed_tags and not args.dry_run:
            item["data"]["tags"] = to_tag_objects(kept_tags)
            await data_service.update_item(item)

        return {
            "item_key": item_key,
            "dry_run": args.dry_run,
            "all": bool(args.all),
            "requested_tags": requested_tags,
            "total_before": len(existing_tags),
            "removed_count": len(removed_tags),
            "removed_tags": sorted(set(removed_tags)),
            "total_after": len(kept_tags),
            "tags": kept_tags,
        }

    async def _purge_tags() -> dict[str, Any]:
        return await maintenance_service.purge_tags(
            tags=args.tags,
            collection_name=args.collection,
            batch_size=args.batch_size,
            scan_limit=args.scan_limit,
            update_limit=args.update_limit,
            dry_run=args.dry_run,
        )

    async def _rename_tags() -> dict[str, Any]:
        old_name = str(args.old_name).strip()
        new_name = str(args.new_name).strip()
        if not old_name or not new_name:
            return {"error": "old-name and new-name must be non-empty"}

        if old_name == new_name:
            return {
                "old_name": old_name,
                "new_name": new_name,
                "matched_items": 0,
                "renamed_items": 0,
                "failed": 0,
                "details": [],
                "dry_run": args.dry_run,
                "message": "old-name and new-name are identical; nothing changed",
            }

        results = await data_service.search_by_tag(
            tags=[old_name],
            limit=args.limit,
        )
        details: list[dict[str, Any]] = []
        renamed_items = 0
        failed = 0

        for item in results:
            try:
                full_item = await data_service.get_item(item.key)
                item_data = full_item.get("data", {})
                normalized_tag_names = normalize_tag_names(item_data.get("tags", []))
                changed = False

                renamed_tag_names: list[str] = []
                seen: set[str] = set()
                for tag_name in normalized_tag_names:
                    if tag_name == old_name:
                        tag_name = new_name
                        changed = True

                    if not tag_name or tag_name in seen:
                        continue
                    seen.add(tag_name)
                    renamed_tag_names.append(tag_name)

                if changed:
                    details.append(
                        {
                            "item_key": item.key,
                            "title": item.title,
                            "from": old_name,
                            "to": new_name,
                        }
                    )
                    if not args.dry_run:
                        full_item["data"]["tags"] = to_tag_objects(renamed_tag_names)
                        await data_service.update_item(full_item)
                    renamed_items += 1
            except Exception as exc:
                failed += 1
                details.append(
                    {
                        "item_key": item.key,
                        "title": item.title,
                        "error": str(exc),
                    }
                )

        return {
            "old_name": old_name,
            "new_name": new_name,
            "matched_items": len(results),
            "renamed_items": renamed_items,
            "failed": failed,
            "details": details,
            "dry_run": args.dry_run,
        }

    handlers: dict[str, Callable[[], Awaitable[dict[str, Any]]]] = {
        "list": _list_tags,
        "add": _add_tags,
        "set-status": _set_status,
        "search": _search_tags,
        "delete": _delete_tags,
        "purge": _purge_tags,
        "rename": _rename_tags,
    }

    handler = handlers.get(args.subcommand)
    if handler is None:
        raise ValueError(f"Unknown tags subcommand: {args.subcommand}")

    payload = asyncio.run(_await_handler(handler))
    emit(args, payload)
    return _exit_code(payload)


__all__ = ["register", "run"]
