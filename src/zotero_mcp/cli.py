"""
Command-line interface for Zotero MCP server.
"""

import argparse
import asyncio
import json
import os
from pathlib import Path
import shutil
import sys

from zotero_mcp.server import serve
from zotero_mcp.utils.config import load_config
from zotero_mcp.utils.config.logging import (
    initialize_logging,
)


def obfuscate_sensitive_value(value: str | None, keep_chars: int = 4) -> str | None:
    """Obfuscate sensitive values by showing only the first few characters."""
    if not value or not isinstance(value, str):
        return value
    if len(value) <= keep_chars:
        return "*" * len(value)
    return value[:keep_chars] + "*" * (len(value) - keep_chars)


def obfuscate_config_for_display(config: dict) -> dict:
    """Create a copy of config with sensitive values obfuscated."""
    if not isinstance(config, dict):
        return config

    obfuscated = config.copy()
    sensitive_keys = [
        "ZOTERO_API_KEY",
        "ZOTERO_LIBRARY_ID",
        "API_KEY",
        "LIBRARY_ID",
    ]

    for key in sensitive_keys:
        if key in obfuscated:
            obfuscated[key] = obfuscate_sensitive_value(obfuscated[key])

    return obfuscated


def _save_zotero_db_path_to_config(config_path: Path, db_path: str) -> None:
    """
    Save the Zotero database path to the configuration file.
    """
    try:
        config_path.parent.mkdir(parents=True, exist_ok=True)

        full_config = {}
        if config_path.exists():
            try:
                with open(config_path) as f:
                    full_config = json.load(f)
            except Exception:
                pass

        if "semantic_search" not in full_config:
            full_config["semantic_search"] = {}

        full_config["semantic_search"]["zotero_db_path"] = db_path

        with open(config_path, "w") as f:
            json.dump(full_config, f, indent=2)

        print(f"Saved Zotero database path to config: {config_path}")

    except Exception as e:
        print(f"Warning: Could not save db_path to config: {e}")


def main():
    """Main entry point for the CLI."""
    parser = argparse.ArgumentParser(description="Zotero Model Context Protocol server")

    subparsers = parser.add_subparsers(dest="command", help="Command to run")

    # Server command
    subparsers.add_parser("serve", help="Run the MCP server over stdio")

    # Setup command
    setup_parser = subparsers.add_parser("setup", help="Configure zotero-mcp")
    setup_parser.add_argument(
        "--no-local",
        action="store_true",
        default=True,
        help="Configure for Zotero Web API instead of local API",
    )
    setup_parser.add_argument(
        "--zotero-api-key",
        default=os.getenv("ZOTERO_API_KEY"),
        help="Zotero API key (default: from .env or environment)",
    )
    setup_parser.add_argument("--library-id", help="Zotero library ID")
    setup_parser.add_argument(
        "--library-type",
        choices=["user", "group"],
        default="user",
        help="Zotero library type",
    )
    setup_parser.add_argument(
        "--skip-semantic-search",
        action="store_true",
        help="Skip semantic search configuration",
    )
    setup_parser.add_argument(
        "--semantic-config-only",
        action="store_true",
        default=True,
        help="Only configure semantic search",
    )

    # Update database command
    update_db_parser = subparsers.add_parser(
        "semantic-db-update", help="Update semantic search database"
    )
    update_db_parser.add_argument(
        "--force-rebuild", action="store_true", help="Force complete rebuild"
    )
    update_db_parser.add_argument(
        "--scan-limit",
        type=int,
        default=500,
        help="Number of items to fetch per batch from API (default: 500)",
    )
    update_db_parser.add_argument(
        "--treated-limit",
        type=int,
        default=100,
        help="Maximum total number of items to process (default: 100)",
    )
    update_db_parser.add_argument(
        "--no-fulltext",
        action="store_true",
        help="Disable fulltext extraction (default: enabled)",
    )
    update_db_parser.add_argument(
        "--config-path", help="Path to semantic search config"
    )
    update_db_parser.add_argument("--db-path", help="Path to Zotero database file")

    # Database status command
    db_status_parser = subparsers.add_parser(
        "semantic-db-status", help="Show database status"
    )
    db_status_parser.add_argument(
        "--config-path", help="Path to semantic search config"
    )

    # DB inspect command
    inspect_parser = subparsers.add_parser(
        "semantic-db-inspect", help="Inspect indexed documents"
    )
    inspect_parser.add_argument(
        "--limit", type=int, default=20, help="How many records to show"
    )
    inspect_parser.add_argument(
        "--filter", dest="filter_text", help="Filter by title/creator"
    )
    inspect_parser.add_argument(
        "--filter-field",
        choices=["doi", "title", "author"],
        default="title",
        help="Field to filter by (default: title)",
    )
    inspect_parser.add_argument(
        "--show-documents", action="store_true", help="Show document text"
    )
    inspect_parser.add_argument(
        "--stats", action="store_true", help="Show aggregate stats"
    )
    inspect_parser.add_argument("--config-path", help="Path to semantic search config")

    # Update command
    update_parser = subparsers.add_parser("update", help="Update zotero-mcp")
    update_parser.add_argument(
        "--check-only", action="store_true", help="Only check for updates"
    )
    update_parser.add_argument("--force", action="store_true", help="Force update")
    update_parser.add_argument(
        "--method",
        choices=["pip", "uv", "conda", "pipx"],
        help="Override installation method",
    )

    # Scan command (global analysis)
    scan_parser = subparsers.add_parser(
        "scan",
        help="Scan library and analyze items without AI notes",
        description="""
Scan library and analyze research papers with AI.

NEW: Multi-modal support! Use --multimodal to extract images and tables from PDFs.

Available LLM providers:
- auto (default): Automatically selects best provider based on content
- claude-cli: Supports text, images, and tables (multi-modal)
- deepseek: Text only (fast, good for papers without figures)
- openai: Supports text and images (OpenAI GPT-4 Vision)
- gemini: Supports text and images (Google Gemini Vision)

Examples:
    zotero-mcp scan -c "Recent Papers" --llm auto
    zotero-mcp scan -c "Figures" --llm claude-cli --multimodal
    zotero-mcp scan -c "Text Only" --llm deepseek --no-multimodal
    zotero-mcp scan --llm openai --multimodal --treated-limit 5
        """,
    )
    scan_parser.add_argument(
        "--scan-limit",
        type=int,
        default=100,
        help="Number of items to fetch per batch from API (default: 100)",
    )
    scan_parser.add_argument(
        "--treated-limit",
        type=int,
        default=20,
        help="Maximum total items to process (default: 20)",
    )
    scan_parser.add_argument(
        "--target-collection",
        required=True,
        help="Move items to this collection after analysis (required)",
    )
    scan_parser.add_argument(
        "--dry-run", action="store_true", help="Preview without processing"
    )
    scan_parser.add_argument(
        "--llm-provider",
        choices=["auto", "claude-cli", "deepseek", "openai", "gemini"],
        default="auto",
        help="LLM provider for analysis (default: auto)",
    )
    scan_parser.add_argument(
        "--source-collection",
        default="00_INBOXS",
        help="Collection to scan first (default: 00_INBOXS)",
    )
    scan_parser.add_argument(
        "--multimodal",
        action="store_true",
        default=True,
        help="Enable multi-modal analysis (images and tables) (default: enabled)",
    )
    scan_parser.add_argument(
        "--no-multimodal",
        action="store_true",
        help="Disable multi-modal analysis (text only)",
    )

    # Update metadata command
    update_metadata_parser = subparsers.add_parser(
        "update-metadata", help="Update item metadata from external APIs"
    )
    update_metadata_parser.add_argument(
        "--collection",
        help="Limit to specific collection (by key)",
    )
    update_metadata_parser.add_argument(
        "--scan-limit",
        type=int,
        default=500,
        help="Number of items to fetch per batch from API (default: 500)",
    )
    update_metadata_parser.add_argument(
        "--treated-limit",
        type=int,
        help="Maximum total number of items to process",
    )
    update_metadata_parser.add_argument(
        "--item-key",
        help="Update a specific item by key",
    )
    update_metadata_parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Preview metadata updates without applying changes",
    )

    # Deduplicate command
    dedup_parser = subparsers.add_parser(
        "deduplicate", help="Find and remove duplicate items"
    )
    dedup_parser.add_argument(
        "--collection",
        help="Limit to specific collection (by key)",
    )
    dedup_parser.add_argument(
        "--scan-limit",
        type=int,
        default=500,
        help="Number of items to fetch per batch from API (default: 500)",
    )
    dedup_parser.add_argument(
        "--treated-limit",
        type=int,
        default=100,
        help="Maximum total number of items to scan (default: 100)",
    )
    dedup_parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Preview duplicates without deleting",
    )

    # Clean empty items command
    clean_empty_parser = subparsers.add_parser(
        "clean-empty", help="Find and delete empty items (no title, no attachments)"
    )
    clean_empty_parser.add_argument(
        "--collection",
        help="Limit to specific collection (by name)",
    )
    clean_empty_parser.add_argument(
        "--scan-limit",
        type=int,
        default=500,
        help="Number of items to fetch per batch from API (default: 500)",
    )
    clean_empty_parser.add_argument(
        "--treated-limit",
        type=int,
        default=100,
        help="Maximum total number of items to delete (default: 100)",
    )
    clean_empty_parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Preview empty items without deleting",
    )

    # Clean tags command
    clean_tags_parser = subparsers.add_parser(
        "clean-tags", help="Remove all tags except those starting with 'AI'"
    )
    clean_tags_parser.add_argument(
        "--collection",
        help="Limit to specific collection (by name)",
    )
    clean_tags_parser.add_argument(
        "--batch-size",
        type=int,
        default=50,
        help="Number of items to process per batch (default: 50)",
    )
    clean_tags_parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Maximum total number of items to process (default: no limit)",
    )
    clean_tags_parser.add_argument(
        "--keep-prefix",
        default="AI",
        help="Keep tags starting with this prefix (default: 'AI')",
    )
    clean_tags_parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Preview changes without updating",
    )

    # Version command
    subparsers.add_parser("version", help="Print version information")

    # Setup info command
    subparsers.add_parser("setup-info", help="Show installation info")

    args = parser.parse_args()

    # Initialize logging system
    initialize_logging()

    if not args.command:
        args.command = "serve"

    if args.command == "version":
        from zotero_mcp import __version__

        print(f"Zotero MCP v{__version__}")
        sys.exit(0)

    elif args.command == "setup-info":
        # Load config to get environment
        config = load_config()
        env_vars = config.get("env", {})

        executable_path = (
            shutil.which("zotero-mcp") or sys.executable + " -m zotero_mcp"
        )

        print("=== Zotero MCP Setup Information ===")
        print()
        print("🔧 Installation Details:")
        print(f"  Command path: {executable_path}")
        print(f"  Python path: {sys.executable}")

        print()
        print("⚙️  Configuration:")
        obfuscated = obfuscate_config_for_display(env_vars)
        print(f"  Environment: {json.dumps(obfuscated, indent=2)}")

        # Check semantic search
        try:
            from zotero_mcp.services.zotero.semantic_search import (
                create_semantic_search,
            )

            search = create_semantic_search()
            status = search.get_database_status()

            print()
            print("🧠 Semantic Search:")
            print(
                f"  Status: {'Initialized' if status.get('exists') else 'Not Initialized'}"
            )
            print(f"  Items: {status.get('item_count')}")
            print(f"  Model: {status.get('embedding_model')}")
        except Exception as e:
            print(f"\n❌ Semantic Search Error: {e}")

        sys.exit(0)

    elif args.command == "setup":
        from zotero_mcp.utils.system.setup import main as setup_main

        sys.exit(setup_main(args))

    elif args.command == "semantic-db-update":
        # Ensure environment is loaded
        load_config()
        from zotero_mcp.services.zotero.semantic_search import create_semantic_search

        config_path = args.config_path
        db_path = getattr(args, "db_path", None)

        if db_path:
            # Save override to config
            cfg_path = (
                Path(config_path)
                if config_path
                else Path.home() / ".config" / "zotero-mcp" / "config.json"
            )
            _save_zotero_db_path_to_config(cfg_path, db_path)

        try:
            search = create_semantic_search(config_path, db_path=db_path)
            print("Starting database update...")

            stats = search.update_database(
                force_full_rebuild=args.force_rebuild,
                scan_limit=args.scan_limit,
                treated_limit=args.treated_limit,
                extract_fulltext=not args.no_fulltext,
            )

            print("\nUpdate Complete:")
            for k, v in stats.items():
                print(f"- {k}: {v}")

        except Exception as e:
            print(f"Error: {e}")
            sys.exit(1)

    elif args.command == "semantic-db-status":
        load_config()
        from zotero_mcp.services.zotero.semantic_search import create_semantic_search

        try:
            search = create_semantic_search(args.config_path)
            status = search.get_database_status()
            print(json.dumps(status, indent=2, default=str))
        except Exception as e:
            print(f"Error: {e}")
            sys.exit(1)

    elif args.command == "semantic-db-inspect":
        load_config()
        from zotero_mcp.services.zotero.semantic_search import create_semantic_search

        try:
            search = create_semantic_search(args.config_path)
            # Access underlying client for inspection
            col = search.chroma_client.collection

            if args.stats:
                print(f"Count: {col.count()}")
                return

            include = (
                ["metadatas", "documents"] if args.show_documents else ["metadatas"]
            )

            if args.filter_text:
                field_map = {"doi": "doi", "title": "title", "author": "creators"}
                target_field = field_map[args.filter_field]
                needle = args.filter_text.lower()
                # ChromaDB metadata where doesn't support $contains,
                # so fetch a larger batch and filter client-side.
                fetch_limit = max(args.limit * 10, 500)
                results = col.get(limit=fetch_limit, include=include)
                metadatas = results.get("metadatas") or []
                documents = results.get("documents") or []
                shown = 0
                for i, meta in enumerate(metadatas):
                    val = meta.get(target_field, "")
                    if needle not in str(val).lower():
                        continue
                    print(f"- {meta.get('title', 'Untitled')}")
                    if args.show_documents and documents:
                        print(f"  {documents[i][:100]}...")
                    shown += 1
                    if shown >= args.limit:
                        break
            else:
                results = col.get(limit=args.limit, include=include)
                metadatas = results.get("metadatas") or []
                for i, meta in enumerate(metadatas):
                    print(f"- {meta.get('title', 'Untitled')}")
                    if args.show_documents and results.get("documents"):
                        print(f"  {results['documents'][i][:100]}...")

        except Exception as e:
            print(f"Error: {e}")
            sys.exit(1)

    elif args.command == "update":
        from zotero_mcp.utils.system.updater import update_zotero_mcp

        update_zotero_mcp(
            check_only=args.check_only, force=args.force, method=args.method
        )

    elif args.command == "scan":
        load_config()
        from zotero_mcp.services.scanner import GlobalScanner

        scanner = GlobalScanner()
        try:
            # Handle multimodal flag
            multimodal = args.multimodal and not args.no_multimodal

            result = asyncio.run(
                scanner.scan_and_process(
                    scan_limit=args.scan_limit,
                    treated_limit=args.treated_limit,
                    target_collection=args.target_collection,
                    dry_run=args.dry_run,
                    llm_provider=args.llm_provider,
                    source_collection=args.source_collection,
                    include_multimodal=multimodal,
                )
            )

            print("\n=== Global Scan Results ===")
            print(f"  Total scanned: {result.get('total_scanned', 0)}")
            print(f"  Candidates: {result.get('candidates', 0)}")
            print(f"  Processed: {result.get('processed', 0)}")
            print(f"  Failed: {result.get('failed', 0)}")
            if result.get("message"):
                print(f"  Message: {result['message']}")
            if result.get("error"):
                print(f"  Error: {result['error']}")
                sys.exit(1)
            if result.get("items"):
                print("\n  Items to process:")
                for title in result["items"]:
                    print(f"    - {title}")

        except Exception as e:
            print(f"Error: {e}")
            sys.exit(1)

    elif args.command == "update-metadata":
        load_config()
        from zotero_mcp.services.data_access import DataAccessService
        from zotero_mcp.services.zotero.metadata_update_service import (
            MetadataUpdateService,
        )

        async def update_metadata():
            data_service = DataAccessService()
            metadata_service = data_service.metadata_service
            item_service = data_service.item_service

            update_service = MetadataUpdateService(item_service, metadata_service)

            try:
                if args.item_key:
                    # Update single item
                    result = await update_service.update_item_metadata(
                        args.item_key, dry_run=args.dry_run
                    )
                    print("\n=== Update Result ===")
                    print(f"  Success: {result['success']}")
                    print(f"  Updated: {result['updated']}")
                    print(f"  Message: {result['message']}")
                    print(f"  Source: {result['source']}")
                    if args.dry_run:
                        print("  Mode: DRY RUN (no changes were applied)")
                else:
                    # Update multiple items
                    result = await update_service.update_all_items(
                        collection_key=args.collection,
                        scan_limit=args.scan_limit,
                        treated_limit=args.treated_limit,
                        dry_run=args.dry_run,
                    )
                    print("\n=== Metadata Update Results ===")
                    print(f"  Items: {result.get('items', result['total'])}")
                    if "processed_candidates" in result:
                        print(
                            f"  Candidates processed: {result['processed_candidates']}"
                        )
                    print(f"  Updated: {result['updated']}")
                    print(f"  Skipped: {result['skipped']}")
                    if "ai_metadata_tagged" in result:
                        print(
                            f"  AI元数据-tagged (skipped): {result['ai_metadata_tagged']}"
                        )
                    print(f"  Failed: {result['failed']}")
                    if args.dry_run:
                        print("  Mode: DRY RUN (no changes were applied)")

            except Exception as e:
                print(f"Error: {e}")
                sys.exit(1)

        asyncio.run(update_metadata())

    elif args.command == "deduplicate":
        load_config()
        from zotero_mcp.services.data_access import DataAccessService
        from zotero_mcp.services.zotero.duplicate_service import (
            DuplicateDetectionService,
        )

        async def deduplicate():
            data_service = DataAccessService()
            item_service = data_service.item_service

            dedup_service = DuplicateDetectionService(item_service)

            try:
                result = await dedup_service.find_and_remove_duplicates(
                    collection_key=args.collection,
                    scan_limit=args.scan_limit,
                    treated_limit=args.treated_limit,
                    dry_run=args.dry_run,
                )
                print("\n=== Deduplication Results ===")
                print(f"  Total scanned: {result['total_scanned']}")
                print(f"  Duplicates found: {result['duplicates_found']}")
                cross_folder = result.get('cross_folder_copies', 0)
                print(f"  Cross-folder copies (skipped): {cross_folder}")
                print(f"  Duplicates deleted: {result['duplicates_removed']}")
                if result.get("dry_run"):
                    print("  Mode: DRY RUN (no items were deleted)")
                print(f"  Duplicate groups: {len(result.get('groups', []))}")

                if result.get("groups"):
                    print("\n  📋 重复条目详情:")
                    print(f"  共发现 {len(result['groups'])} 组重复条目\\n")
                    for i, group in enumerate(result["groups"][:10], 1):
                        match_name = {"doi": "DOI", "title": "标题", "url": "URL"}.get(
                            group.match_reason, group.match_reason
                        )

                        print(f"  [{i}] 匹配类型: {match_name}")
                        print(f"      匹配值: {group.match_value[:60]}...")
                        print(f"      ✅ 保留: {group.primary_key} (信息最全)")
                        # Note: duplicate_keys may include notes/attachments
                        # that will be skipped
                        total_to_delete = len(group.duplicate_keys)
                        if total_to_delete > 0:
                            print(f"      🗑️  准备删除: {total_to_delete} 个条目")
                        else:
                            print("      ⊘ 无需删除（仅保留条目）")
                        if total_to_delete <= 3:
                            for dup_key in group.duplicate_keys:
                                print(f"         - {dup_key}")
                        else:
                            msg = (
                                f"- {group.duplicate_keys[0]} 等 "
                                f"{len(group.duplicate_keys)} 个条目"
                            )
                            print(f"         {msg}")
                        print()

            except Exception as e:
                print(f"Error: {e}")
                sys.exit(1)

        asyncio.run(deduplicate())

    elif args.command == "clean-empty":
        load_config()
        from zotero_mcp.services.data_access import DataAccessService

        async def clean_empty() -> None:
            data_service = DataAccessService()

            # Resolve collections to scan
            if args.collection:
                matches = await data_service.find_collection_by_name(
                    args.collection, exact_match=True
                )
                if not matches:
                    print(f"Collection not found: {args.collection}")
                    sys.exit(1)
                collections = matches
            else:
                collections = await data_service.get_collections()

            candidates: list[tuple[str, str, str]] = []  # (key, title, collection_name)
            total_scanned = 0

            for col in collections:
                col_key = col.get("key", "")
                col_name = col.get("data", {}).get("name", col.get("name", "Unknown"))
                offset = 0

                while len(candidates) < args.treated_limit:
                    items = await data_service.get_collection_items(
                        col_key, limit=args.scan_limit, start=offset
                    )
                    if not items:
                        break

                    for item in items:
                        total_scanned += 1
                        # Skip child item types (attachments, notes)
                        if item.item_type in ("attachment", "note"):
                            continue
                        title = item.title or ""
                        if title.strip() and title.strip() != "Untitled":
                            continue

                        # Check for children (attachments, notes)
                        try:
                            children = await data_service.get_item_children(item.key)
                        except Exception:
                            continue
                        if children:
                            continue

                        candidates.append((item.key, title or "(empty)", col_name))
                        if len(candidates) >= args.treated_limit:
                            break

                    if len(items) < args.scan_limit:
                        break
                    offset += args.scan_limit

                if len(candidates) >= args.treated_limit:
                    break

            print("\n=== Clean Empty Items ===")
            print(f"  Total scanned: {total_scanned}")
            print(f"  Empty items found: {len(candidates)}")

            if not candidates:
                print("  No empty items to clean.")
                return

            print("\n  Empty items:")
            for key, title, col_name in candidates:
                print(f"    - [{col_name}] {key}: {title}")

            if args.dry_run:
                print("\n  Mode: DRY RUN (no items were deleted)")
                return

            deleted = 0
            failed = 0
            for key, _title, _col_name in candidates:
                try:
                    await data_service.delete_item(key)
                    deleted += 1
                except Exception as e:
                    print(f"  Failed to delete {key}: {e}")
                    failed += 1

            print(f"\n  Deleted: {deleted}")
            if failed:
                print(f"  Failed: {failed}")

        asyncio.run(clean_empty())

    elif args.command == "clean-tags":
        load_config()
        from zotero_mcp.clients.zotero.api_client import get_zotero_client
        from zotero_mcp.services.data_access import DataAccessService

        async def clean_tags() -> None:
            api_client = get_zotero_client()
            data_service = DataAccessService()

            # Resolve collections to scan
            if args.collection:
                matches = await data_service.find_collection_by_name(
                    args.collection, exact_match=True
                )
                if not matches:
                    print(f"Collection not found: {args.collection}")
                    sys.exit(1)
                collections = matches
            else:
                collections = await data_service.get_collections()

            keep_prefix = args.keep_prefix
            items_updated: list[tuple[str, str, str, int, int]] = []
            total_scanned = 0
            total_tags_removed = 0
            limit = args.limit

            for col in collections:
                if limit and len(items_updated) >= limit:
                    break
                col_key = col.get("key", "")
                col_name = col.get("data", {}).get("name", col.get("name", "Unknown"))
                offset = 0

                try:
                    while limit is None or len(items_updated) < limit:
                        remaining = (
                            limit - len(items_updated) if limit else args.batch_size
                        )
                        batch_size = min(args.batch_size, remaining)
                        items = await data_service.get_collection_items(
                            col_key, limit=batch_size, start=offset
                        )
                        if not items:
                            break

                        for item in items:
                            total_scanned += 1
                            # Get full item data with tags
                            full_item = await api_client.get_item(item.key)
                            item_data = full_item.get("data", {})
                            existing_tags = item_data.get("tags", [])

                            # Filter tags: keep only those starting with prefix
                            kept_tags = [
                                t
                                for t in existing_tags
                                if isinstance(t, dict)
                                and t.get("tag", "").startswith(keep_prefix)
                            ]
                            removed_tags = [
                                t
                                for t in existing_tags
                                if isinstance(t, dict)
                                and not t.get("tag", "").startswith(keep_prefix)
                            ]

                            if removed_tags:
                                removed_count = len(removed_tags)
                                total_tags_removed += removed_count
                                items_updated.append(
                                    (
                                        item.key,
                                        item.title or "(no title)",
                                        col_name,
                                        len(kept_tags),
                                        removed_count,
                                    )
                                )

                                if not args.dry_run:
                                    # Update item with only kept tags
                                    full_item["data"]["tags"] = kept_tags
                                    await api_client.update_item(full_item)

                            if limit and len(items_updated) >= limit:
                                break

                        if len(items) < batch_size:
                            break
                        offset += batch_size
                except Exception as e:
                    print(
                        f"  Warning: Error processing collection '{col_name}' ({col_key}): {e}"
                    )
                    continue

            print("\n=== Clean Tags ===")
            print(f"  Keep prefix: '{keep_prefix}'")
            print(f"  Total items scanned: {total_scanned}")
            print(f"  Items updated: {len(items_updated)}")
            print(f"  Total tags removed: {total_tags_removed}")

            if not items_updated:
                print("  No items needed tag cleanup.")
                return

            print("\n  Items with tags removed:")
            for key, title, col_name, kept, removed in items_updated[
                :20
            ]:  # Show first 20
                short_title = (title[:40] + "...") if len(title) > 40 else title
                print(f"    - [{col_name}] {key[:8]}...: '{short_title}'")
                print(f"      Kept: {kept}, Removed: {removed}")

            if len(items_updated) > 20:
                print(f"    ... and {len(items_updated) - 20} more")

            if args.dry_run:
                print("\n  Mode: DRY RUN (no items were updated)")

        asyncio.run(clean_tags())

    elif args.command == "serve":
        load_config()
        asyncio.run(serve())


if __name__ == "__main__":
    main()
