"""CLI parser and dispatch registry."""

from __future__ import annotations

import argparse
from collections.abc import Callable

from zotero_mcp.cli_app.commands import resources, semantic, system, tags, workflow


CommandRunner = Callable[[argparse.Namespace], int]


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Zotero Model Context Protocol server")
    subparsers = parser.add_subparsers(dest="command")

    registrars: tuple[Callable[[argparse._SubParsersAction], None], ...] = (
        system.register,
        workflow.register,
        semantic.register,
        tags.register,
        resources.register_items,
        resources.register_notes,
        resources.register_annotations,
        resources.register_pdfs,
        resources.register_collections,
    )
    for register in registrars:
        register(subparsers)

    return parser


def dispatch(args: argparse.Namespace) -> int:
    command_handlers: dict[str, CommandRunner] = {
        "system": system.run,
        "workflow": workflow.run,
        "semantic": semantic.run,
        "tags": tags.run,
        "items": resources.run_items,
        "notes": resources.run_notes,
        "annotations": resources.run_annotations,
        "pdfs": resources.run_pdfs,
        "collections": resources.run_collections,
    }

    handler = command_handlers.get(args.command)
    if handler is None:
        raise ValueError(f"Unknown command: {args.command}")
    return handler(args)
