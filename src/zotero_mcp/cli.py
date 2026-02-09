"""
Command-line interface for Zotero MCP server.
"""

import argparse
import asyncio
import json
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
        help="Configure for Zotero Web API instead of local API",
    )
    setup_parser.add_argument("--api-key", help="Zotero API key")
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
        help="Only configure semantic search",
    )

    # Update database command
    update_db_parser = subparsers.add_parser(
        "update-db", help="Update semantic search database"
    )
    update_db_parser.add_argument(
        "--force-rebuild", action="store_true", help="Force complete rebuild"
    )
    update_db_parser.add_argument(
        "--scan-limit",
        type=int,
        default=100,
        help="Number of items to fetch per batch from API (default: 100)",
    )
    update_db_parser.add_argument(
        "--treated-limit",
        type=int,
        help="Maximum total number of items to process",
    )
    update_db_parser.add_argument(
        "--fulltext", action="store_true", help="Extract fulltext content"
    )
    update_db_parser.add_argument(
        "--config-path", help="Path to semantic search config"
    )
    update_db_parser.add_argument("--db-path", help="Path to Zotero database file")

    # Database status command
    db_status_parser = subparsers.add_parser("db-status", help="Show database status")
    db_status_parser.add_argument(
        "--config-path", help="Path to semantic search config"
    )

    # DB inspect command
    inspect_parser = subparsers.add_parser(
        "db-inspect", help="Inspect indexed documents"
    )
    inspect_parser.add_argument(
        "--limit", type=int, default=20, help="How many records to show"
    )
    inspect_parser.add_argument(
        "--filter", dest="filter_text", help="Filter by title/creator"
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
        default="01_SHORTTERMS",
        help="Move items to this collection after analysis (default: 01_SHORTTERMS)",
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
    dedup_parser.add_argument(
        "--trash-collection",
        default="06_TRASHES",
        help="Name of collection to move duplicates to (default: '06_TRASHES')",
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

    elif args.command == "update-db":
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
                extract_fulltext=args.fulltext,
            )

            print("\nUpdate Complete:")
            for k, v in stats.items():
                print(f"- {k}: {v}")

        except Exception as e:
            print(f"Error: {e}")
            sys.exit(1)

    elif args.command == "db-status":
        load_config()
        from zotero_mcp.services.zotero.semantic_search import create_semantic_search

        try:
            search = create_semantic_search(args.config_path)
            status = search.get_database_status()
            print(json.dumps(status, indent=2, default=str))
        except Exception as e:
            print(f"Error: {e}")
            sys.exit(1)

    elif args.command == "db-inspect":
        load_config()
        from zotero_mcp.services.zotero.semantic_search import create_semantic_search

        try:
            search = create_semantic_search(args.config_path)
            # Access underlying client for inspection
            col = search.chroma_client.collection

            if args.stats:
                print(f"Count: {col.count()}")
                return

            results = col.get(
                limit=args.limit,
                include=(
                    ["metadatas", "documents"] if args.show_documents else ["metadatas"]
                ),
            )

            metadatas = results.get("metadatas") or []
            for i, meta in enumerate(metadatas):
                print(f"- {meta.get('title', 'Untitled')}")
                if args.show_documents and results["documents"]:
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
                    print(f"  Total processed: {result['total']}")
                    print(f"  Updated: {result['updated']}")
                    print(f"  Skipped: {result['skipped']}")
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
                    trash_collection=args.trash_collection,
                )
                print("\n=== Deduplication Results ===")
                print(f"  Total scanned: {result['total_scanned']}")
                print(f"  Duplicates found: {result['duplicates_found']}")
                print(
                    f"  Cross-folder copies (skipped): {result.get('cross_folder_copies', 0)}"
                )
                print(
                    f"  Duplicates moved to {args.trash_collection}: {result['duplicates_removed']}"
                )
                if result.get("dry_run"):
                    print("  Mode: DRY RUN (no items were moved)")
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
                        # Note: duplicate_keys may include notes/attachments that will be skipped
                        total_to_move = len(group.duplicate_keys)
                        if total_to_move > 0:
                            print(f"      🗑️  准备移动到垃圾箱: {total_to_move} 个条目")
                        else:
                            print("      ⊘ 无需移动（仅保留条目）")
                        if total_to_move <= 3:
                            for dup_key in group.duplicate_keys:
                                print(f"         - {dup_key}")
                        else:
                            print(
                                f"         - {group.duplicate_keys[0]} 等 {len(group.duplicate_keys)} 个条目"
                            )
                        print()

            except Exception as e:
                print(f"Error: {e}")
                sys.exit(1)

        asyncio.run(deduplicate())

    elif args.command == "serve":
        load_config()
        asyncio.run(serve())


if __name__ == "__main__":
    main()
