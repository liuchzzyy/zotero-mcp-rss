"""Resource command groups: items, notes, annotations, pdfs, collections."""

from __future__ import annotations

import argparse
import asyncio
from collections.abc import Awaitable, Callable
import json
from pathlib import Path
from typing import Any

from zotero_mcp.cli_app.common import (
    add_output_arg,
    add_scan_limit_arg,
    add_treated_limit_arg,
)
from zotero_mcp.cli_app.output import emit
from zotero_mcp.utils.config import load_config
from zotero_mcp.utils.formatting.helpers import normalize_item_key


async def _await_handler[T](handler: Callable[[], Awaitable[T]]) -> T:
    return await handler()


def _add_paging(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--limit", type=int, default=25)
    parser.add_argument("--offset", type=int, default=0)


def _exit_code(payload: Any) -> int:
    if not isinstance(payload, dict):
        return 0
    if payload.get("error"):
        return 1
    if payload.get("success") is False:
        return 1
    return 0


def _emit_result(args: argparse.Namespace, payload: Any) -> int:
    emit(args, payload)
    return _exit_code(payload)


def register_items(subparsers: argparse._SubParsersAction) -> None:
    items = subparsers.add_parser("items", help="Item operations")
    items_sub = items.add_subparsers(dest="subcommand", required=True)

    get_cmd = items_sub.add_parser("get", help="Get one item by key")
    get_cmd.add_argument("--item-key", required=True)
    add_output_arg(get_cmd)

    list_cmd = items_sub.add_parser("list", help="List items")
    _add_paging(list_cmd)
    list_cmd.add_argument("--item-type")
    add_output_arg(list_cmd)

    children = items_sub.add_parser("children", help="List child items")
    children.add_argument("--item-key", required=True)
    children.add_argument("--item-type", choices=["attachment", "note", "annotation"])
    add_output_arg(children)

    fulltext = items_sub.add_parser("fulltext", help="Get fulltext")
    fulltext.add_argument("--item-key", required=True)
    add_output_arg(fulltext)

    bundle = items_sub.add_parser("bundle", help="Get item bundle")
    bundle.add_argument("--item-key", required=True)
    bundle.add_argument("--include-fulltext", action="store_true")
    bundle.add_argument(
        "--include-annotations", action=argparse.BooleanOptionalAction, default=True
    )
    bundle.add_argument(
        "--include-notes", action=argparse.BooleanOptionalAction, default=True
    )
    add_output_arg(bundle)

    delete = items_sub.add_parser("delete", help="Delete item")
    delete.add_argument("--item-key", required=True)
    add_output_arg(delete)

    update = items_sub.add_parser("update", help="Update item from JSON file")
    update.add_argument(
        "--input-file",
        required=True,
        help="Path to JSON file containing full item object",
    )
    add_output_arg(update)

    create = items_sub.add_parser("create", help="Create items from JSON file")
    create.add_argument(
        "--input-file",
        required=True,
        help="Path to JSON file containing one item or list of items",
    )
    add_output_arg(create)

    tags = items_sub.add_parser("add-tags", help="Add tags to item")
    tags.add_argument("--item-key", required=True)
    tags.add_argument("--tags", nargs="+", required=True)
    add_output_arg(tags)

    add_col = items_sub.add_parser("add-to-collection", help="Add item to collection")
    add_col.add_argument("--item-key", required=True)
    add_col.add_argument("--collection-key", required=True)
    add_output_arg(add_col)

    remove_col = items_sub.add_parser(
        "remove-from-collection", help="Remove item from collection"
    )
    remove_col.add_argument("--item-key", required=True)
    remove_col.add_argument("--collection-key", required=True)
    add_output_arg(remove_col)

    delete_empty = items_sub.add_parser(
        "delete-empty", help="Find and delete empty items (no title, no attachments)"
    )
    delete_empty.add_argument(
        "--collection", help="Limit to specific collection (by name)"
    )
    add_scan_limit_arg(delete_empty, default=500)
    add_treated_limit_arg(
        delete_empty,
        default=100,
        help_text="Maximum total number of items to delete (default: 100)",
    )
    delete_empty.add_argument(
        "--dry-run",
        action=argparse.BooleanOptionalAction,
        default=False,
        help="Preview empty items without deleting (default: disabled)",
    )
    add_output_arg(delete_empty)


def run_items(args: argparse.Namespace) -> int:
    load_config()
    from zotero_mcp.services.resource_service import ResourceService
    from zotero_mcp.services.zotero.maintenance_service import LibraryMaintenanceService

    service = ResourceService()
    maintenance_service = LibraryMaintenanceService()

    def _load_json(path: str) -> Any:
        with open(path, encoding="utf-8") as file:
            return json.load(file)

    handlers: dict[str, Callable[[], Awaitable[Any]]] = {
        "get": lambda: service.get_item(normalize_item_key(args.item_key)),
        "list": lambda: service.list_items(
            limit=args.limit,
            offset=args.offset,
            item_type=args.item_type,
        ),
        "children": lambda: service.list_item_children(
            item_key=normalize_item_key(args.item_key),
            item_type=args.item_type,
        ),
        "fulltext": lambda: service.get_item_fulltext(
            normalize_item_key(args.item_key)
        ),
        "bundle": lambda: service.get_item_bundle(
            item_key=normalize_item_key(args.item_key),
            include_fulltext=args.include_fulltext,
            include_annotations=args.include_annotations,
            include_notes=args.include_notes,
        ),
        "delete": lambda: service.delete_item(normalize_item_key(args.item_key)),
        "update": lambda: service.update_item(_load_json(args.input_file)),
        "create": lambda: service.create_items(_load_json(args.input_file)),
        "add-tags": lambda: service.add_tags_to_item(
            item_key=normalize_item_key(args.item_key),
            tags=args.tags,
        ),
        "add-to-collection": lambda: service.add_item_to_collection(
            collection_key=args.collection_key,
            item_key=normalize_item_key(args.item_key),
        ),
        "remove-from-collection": lambda: service.remove_item_from_collection(
            collection_key=args.collection_key,
            item_key=normalize_item_key(args.item_key),
        ),
        "delete-empty": lambda: maintenance_service.clean_empty_items(
            collection_name=args.collection,
            scan_limit=args.scan_limit,
            treated_limit=args.treated_limit,
            dry_run=args.dry_run,
        ),
    }

    handler = handlers.get(args.subcommand)
    if handler is None:
        raise ValueError(f"Unknown items subcommand: {args.subcommand}")

    return _emit_result(args, asyncio.run(_await_handler(handler)))


def register_notes(subparsers: argparse._SubParsersAction) -> None:
    notes = subparsers.add_parser("notes", help="Note operations")
    notes_sub = notes.add_subparsers(dest="subcommand", required=True)

    list_cmd = notes_sub.add_parser("list", help="List notes under item")
    list_cmd.add_argument("--item-key", required=True)
    _add_paging(list_cmd)
    add_output_arg(list_cmd)

    create = notes_sub.add_parser("create", help="Create a note")
    create.add_argument("--item-key", required=True)
    create.add_argument("--content", help="Note content")
    create.add_argument("--content-file", help="Path to note content file")
    create.add_argument("--tags", nargs="*", default=[])
    add_output_arg(create)

    search = notes_sub.add_parser("search", help="Search note text")
    search.add_argument("--query", required=True)
    _add_paging(search)
    add_output_arg(search)

    delete = notes_sub.add_parser("delete", help="Delete note by key")
    delete.add_argument("--note-key", required=True)
    add_output_arg(delete)

    relate = notes_sub.add_parser(
        "relate",
        help="Analyze one note against library/collection notes and write relations",
    )
    relate.add_argument("--note-key", required=True)
    relate.add_argument(
        "--collection",
        default="all",
        help="'all' for entire library, or a collection key/name (default: all)",
    )
    relate.add_argument(
        "--dry-run",
        action="store_true",
        help="Analyze only; do not write relations or update note",
    )
    relate.add_argument(
        "--bidirectional",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Write reciprocal dc:relation on candidate notes (default: true)",
    )
    add_output_arg(relate)


def run_notes(args: argparse.Namespace) -> int:
    load_config()
    from zotero_mcp.services.resource_service import ResourceService

    if args.subcommand == "create" and bool(args.content) == bool(args.content_file):
        raise ValueError("Provide exactly one of --content or --content-file")
    service = ResourceService()

    def _resolve_note_content() -> str:
        if args.content_file:
            return Path(args.content_file).read_text(encoding="utf-8")
        return args.content or ""

    handlers: dict[str, Callable[[], Awaitable[Any]]] = {
        "list": lambda: service.list_notes(
            item_key=normalize_item_key(args.item_key),
            limit=args.limit,
            offset=args.offset,
        ),
        "create": lambda: service.create_note(
            item_key=normalize_item_key(args.item_key),
            content=_resolve_note_content(),
            tags=args.tags,
        ),
        "search": lambda: service.search_notes(
            query=args.query,
            limit=args.limit,
            offset=args.offset,
        ),
        "delete": lambda: service.delete_note(normalize_item_key(args.note_key)),
        "relate": lambda: service.relate_note(
            note_key=normalize_item_key(args.note_key),
            collection=args.collection,
            dry_run=args.dry_run,
            bidirectional=args.bidirectional,
        ),
    }

    handler = handlers.get(args.subcommand)
    if handler is None:
        raise ValueError(f"Unknown notes subcommand: {args.subcommand}")

    return _emit_result(args, asyncio.run(_await_handler(handler)))


def register_annotations(subparsers: argparse._SubParsersAction) -> None:
    annotations = subparsers.add_parser("annotations", help="Annotation operations")
    ann_sub = annotations.add_subparsers(dest="subcommand", required=True)

    list_cmd = ann_sub.add_parser("list", help="List annotations for item")
    list_cmd.add_argument("--item-key", required=True)
    list_cmd.add_argument("--annotation-type", default="all")
    _add_paging(list_cmd)
    add_output_arg(list_cmd)

    add_cmd = ann_sub.add_parser("add", help="Add annotation to item")
    add_cmd.add_argument("--item-key", required=True)
    add_cmd.add_argument(
        "--annotation-type",
        default="highlight",
        choices=["highlight", "note", "underline", "image"],
    )
    add_cmd.add_argument("--text", required=True)
    add_cmd.add_argument("--comment")
    add_cmd.add_argument("--page-label")
    add_cmd.add_argument("--color")
    add_output_arg(add_cmd)

    search_cmd = ann_sub.add_parser("search", help="Search annotations")
    search_cmd.add_argument("--query", required=True)
    search_cmd.add_argument(
        "--annotation-type",
        default="all",
        choices=["all", "highlight", "note", "underline", "image"],
    )
    _add_paging(search_cmd)
    add_output_arg(search_cmd)

    delete_cmd = ann_sub.add_parser("delete", help="Delete annotation by key")
    delete_cmd.add_argument("--annotation-key", required=True)
    add_output_arg(delete_cmd)


def run_annotations(args: argparse.Namespace) -> int:
    load_config()
    from zotero_mcp.services.resource_service import ResourceService

    service = ResourceService()
    handlers: dict[str, Callable[[], Awaitable[Any]]] = {
        "list": lambda: service.list_annotations(
            item_key=normalize_item_key(args.item_key),
            annotation_type=args.annotation_type,
            limit=args.limit,
            offset=args.offset,
        ),
        "add": lambda: service.create_annotation(
            item_key=normalize_item_key(args.item_key),
            annotation_type=args.annotation_type,
            text=args.text,
            comment=args.comment,
            page_label=args.page_label,
            color=args.color,
        ),
        "search": lambda: service.search_annotations(
            query=args.query,
            limit=args.limit,
            offset=args.offset,
            annotation_type=args.annotation_type,
        ),
        "delete": lambda: service.delete_annotation(
            normalize_item_key(args.annotation_key)
        ),
    }

    handler = handlers.get(args.subcommand)
    if handler is None:
        raise ValueError(f"Unknown annotations subcommand: {args.subcommand}")

    return _emit_result(args, asyncio.run(_await_handler(handler)))


def register_pdfs(subparsers: argparse._SubParsersAction) -> None:
    pdfs = subparsers.add_parser("pdfs", help="PDF attachment operations")
    pdf_sub = pdfs.add_subparsers(dest="subcommand", required=True)

    list_cmd = pdf_sub.add_parser("list", help="List PDFs under an item")
    list_cmd.add_argument("--item-key", required=True)
    _add_paging(list_cmd)
    add_output_arg(list_cmd)

    add_cmd = pdf_sub.add_parser("add", help="Add PDF attachment")
    add_cmd.add_argument("--item-key", required=True)
    add_cmd.add_argument("--file", required=True, help="Local PDF file path")
    add_cmd.add_argument("--title")
    add_output_arg(add_cmd)

    delete_cmd = pdf_sub.add_parser("delete", help="Delete PDF attachment by key")
    delete_cmd.add_argument("--item-key", required=True)
    add_output_arg(delete_cmd)

    search_cmd = pdf_sub.add_parser("search", help="Search PDFs")
    search_cmd.add_argument("--query", required=True)
    _add_paging(search_cmd)
    add_output_arg(search_cmd)


def run_pdfs(args: argparse.Namespace) -> int:
    load_config()
    from zotero_mcp.services.resource_service import ResourceService

    service = ResourceService()
    handlers: dict[str, Callable[[], Awaitable[Any]]] = {
        "list": lambda: service.list_pdfs(
            item_key=normalize_item_key(args.item_key),
            limit=args.limit,
            offset=args.offset,
        ),
        "add": lambda: service.upload_pdf(
            item_key=normalize_item_key(args.item_key),
            file_path=args.file,
            title=args.title,
        ),
        "delete": lambda: service.delete_pdf(normalize_item_key(args.item_key)),
        "search": lambda: service.search_pdfs(
            query=args.query,
            limit=args.limit,
            offset=args.offset,
        ),
    }

    handler = handlers.get(args.subcommand)
    if handler is None:
        raise ValueError(f"Unknown pdfs subcommand: {args.subcommand}")

    return _emit_result(args, asyncio.run(_await_handler(handler)))


def register_collections(subparsers: argparse._SubParsersAction) -> None:
    collections = subparsers.add_parser("collections", help="Collection operations")
    col_sub = collections.add_subparsers(dest="subcommand", required=True)

    list_cmd = col_sub.add_parser("list", help="List collections")
    add_output_arg(list_cmd)

    find = col_sub.add_parser("find", help="Find collection by name")
    find.add_argument("--name", required=True)
    find.add_argument("--exact", action="store_true")
    add_output_arg(find)

    create = col_sub.add_parser("create", help="Create collection")
    create.add_argument("--name", required=True)
    create.add_argument("--parent-key")
    add_output_arg(create)

    rename = col_sub.add_parser("rename", help="Rename collection")
    rename.add_argument("--collection-key", required=True)
    rename.add_argument("--name", required=True)
    add_output_arg(rename)

    move = col_sub.add_parser("move", help="Move collection")
    move.add_argument("--collection-key", required=True)
    move.add_argument("--parent-key", default="")
    add_output_arg(move)

    delete = col_sub.add_parser("delete", help="Delete collection")
    delete.add_argument("--collection-key", required=True)
    add_output_arg(delete)

    delete_empty = col_sub.add_parser(
        "delete-empty", help="Delete empty collections (no items)"
    )
    delete_empty.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Maximum number of empty collections to process",
    )
    delete_empty.add_argument(
        "--dry-run",
        action=argparse.BooleanOptionalAction,
        default=False,
        help="Preview without deleting (default: disabled)",
    )
    add_output_arg(delete_empty)

    items = col_sub.add_parser("items", help="List items in collection")
    items.add_argument("--collection-key", required=True)
    _add_paging(items)
    add_output_arg(items)


def run_collections(args: argparse.Namespace) -> int:
    load_config()
    from zotero_mcp.services.resource_service import ResourceService

    service = ResourceService()
    handlers: dict[str, Callable[[], Awaitable[Any]]] = {
        "list": service.list_collections,
        "find": lambda: service.find_collections(name=args.name, exact=args.exact),
        "create": lambda: service.create_collection(
            name=args.name, parent_key=args.parent_key
        ),
        "rename": lambda: service.rename_collection(
            collection_key=args.collection_key,
            name=args.name,
        ),
        "move": lambda: service.move_collection(
            collection_key=args.collection_key,
            parent_key=args.parent_key,
        ),
        "delete": lambda: service.delete_collection(args.collection_key),
        "delete-empty": lambda: service.delete_empty_collections(
            dry_run=args.dry_run,
            limit=args.limit,
        ),
        "items": lambda: service.list_collection_items(
            collection_key=args.collection_key,
            limit=args.limit,
            offset=args.offset,
        ),
    }

    handler = handlers.get(args.subcommand)
    if handler is None:
        raise ValueError(f"Unknown collections subcommand: {args.subcommand}")

    return _emit_result(args, asyncio.run(_await_handler(handler)))


__all__ = [
    "register_items",
    "run_items",
    "register_notes",
    "run_notes",
    "register_annotations",
    "run_annotations",
    "register_pdfs",
    "run_pdfs",
    "register_collections",
    "run_collections",
]
