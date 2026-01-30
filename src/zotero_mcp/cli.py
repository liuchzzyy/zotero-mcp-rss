"""
Command-line interface for Zotero MCP server.
"""

import argparse
import json
from pathlib import Path
import shutil
import sys

from zotero_mcp.server import mcp
from zotero_mcp.utils.config import load_config
from zotero_mcp.utils.logging_config import (
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
        "OPENAI_API_KEY",
        "GEMINI_API_KEY",
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
    server_parser = subparsers.add_parser("serve", help="Run the MCP server")
    server_parser.add_argument(
        "--transport",
        choices=["stdio", "streamable-http", "sse"],
        default="stdio",
        help="Transport to use (default: stdio)",
    )
    server_parser.add_argument(
        "--host",
        default="localhost",
        help="Host to bind to for SSE transport (default: localhost)",
    )
    server_parser.add_argument(
        "--port",
        type=int,
        default=8000,
        help="Port to bind to for SSE transport (default: 8000)",
    )

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
    update_db_parser.add_argument("--limit", type=int, help="Limit items to process")
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

    # RSS command
    rss_parser = subparsers.add_parser("rss", help="RSS feed management")
    rss_subparsers = rss_parser.add_subparsers(
        dest="rss_command", help="RSS subcommand"
    )

    rss_fetch_parser = rss_subparsers.add_parser(
        "fetch", help="Fetch and import RSS feeds"
    )
    rss_fetch_parser.add_argument(
        "--opml", default="RSS/RSS_official.opml", help="Path to OPML file"
    )
    rss_fetch_parser.add_argument(
        "--prompt",
        help="Path to research interest prompt file (falls back to RSS_PROMPT env var)",
    )
    rss_fetch_parser.add_argument(
        "--collection", default="00_INBOXS", help="Target Zotero collection name"
    )
    rss_fetch_parser.add_argument(
        "--days", type=int, default=15, help="Import articles from the last N days"
    )
    rss_fetch_parser.add_argument("--max-items", type=int, help="Limit items to import")
    rss_fetch_parser.add_argument(
        "--dry-run", action="store_true", help="Preview items without importing"
    )

    # Gmail command
    gmail_parser = subparsers.add_parser("gmail", help="Gmail email processing")
    gmail_subparsers = gmail_parser.add_subparsers(
        dest="gmail_command", help="Gmail subcommand"
    )

    gmail_process_parser = gmail_subparsers.add_parser(
        "process", help="Process emails and import to Zotero"
    )
    gmail_process_parser.add_argument("--sender", help="Filter by sender email address")
    gmail_process_parser.add_argument(
        "--subject", help="Filter by subject (partial match)"
    )
    gmail_process_parser.add_argument(
        "--query", help="Raw Gmail search query (overrides sender/subject)"
    )
    gmail_process_parser.add_argument(
        "--collection", default="00_INBOXS", help="Target Zotero collection name"
    )
    gmail_process_parser.add_argument(
        "--max-emails", type=int, default=50, help="Maximum emails to process"
    )
    gmail_process_parser.add_argument(
        "--no-delete", action="store_true", help="Don't delete emails after processing"
    )
    gmail_process_parser.add_argument(
        "--permanent-delete",
        action="store_true",
        help="Permanently delete (default: trash)",
    )
    gmail_process_parser.add_argument(
        "--dry-run", action="store_true", help="Preview without importing or deleting"
    )

    gmail_auth_parser = gmail_subparsers.add_parser(
        "auth", help="Authenticate with Gmail"
    )
    gmail_auth_parser.add_argument(
        "--credentials", help="Path to OAuth2 credentials.json from Google Cloud"
    )

    # Scan command (global analysis)
    scan_parser = subparsers.add_parser(
        "scan", help="Scan library and analyze items without AI notes"
    )
    scan_parser.add_argument(
        "--limit", type=int, default=20, help="Maximum items to process (default: 20)"
    )
    scan_parser.add_argument(
        "--target-collection",
        default=None,
        help="Move items to this collection after analysis",
    )
    scan_parser.add_argument(
        "--dry-run", action="store_true", help="Preview without processing"
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
        args.transport = "stdio"

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
            from zotero_mcp.services.semantic import create_semantic_search

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
        from zotero_mcp.utils.setup import main as setup_main

        sys.exit(setup_main(args))

    elif args.command == "update-db":
        # Ensure environment is loaded
        load_config()
        from zotero_mcp.services.semantic import create_semantic_search

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
                limit=args.limit,
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
        from zotero_mcp.services.semantic import create_semantic_search

        try:
            search = create_semantic_search(args.config_path)
            status = search.get_database_status()
            print(json.dumps(status, indent=2, default=str))
        except Exception as e:
            print(f"Error: {e}")
            sys.exit(1)

    elif args.command == "db-inspect":
        load_config()
        from zotero_mcp.services.semantic import create_semantic_search

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
        from zotero_mcp.utils.updater import update_zotero_mcp

        update_zotero_mcp(
            check_only=args.check_only, force=args.force, method=args.method
        )

    elif args.command == "rss":
        if args.rss_command == "fetch":
            load_config()
            import asyncio

            from zotero_mcp.services.rss.rss_service import RSSService
            from zotero_mcp.utils.config import get_rss_config

            # Apply env var defaults for CLI args not explicitly provided
            rss_config = get_rss_config()
            if args.opml == "RSS/RSS_official.opml":
                args.opml = rss_config.get("opml_path", "RSS/RSS_official.opml")
                print(f"Using RSS_OPML_PATH: {args.opml}")
            if args.collection == "00_INBOXS":
                config_collection = rss_config.get("collection", "00_INBOXS")
                if config_collection:
                    args.collection = config_collection
            if args.days == 15:
                config_days = rss_config.get("days_back", 15)
                if config_days != 15:
                    args.days = config_days

            service = RSSService()
            try:
                result = asyncio.run(
                    service.process_rss_workflow(
                        opml_path=args.opml,
                        prompt_path=args.prompt,
                        collection_name=args.collection,
                        days_back=args.days,
                        max_items=args.max_items,
                        dry_run=args.dry_run,
                    )
                )

                print("\n=== RSS Processing Results ===")
                print(f"  Feeds fetched: {result.feeds_fetched}")
                print(f"  Items found: {result.items_found}")
                print(f"  Items after date filter: {result.items_after_date_filter}")
                print(f"  Items after AI filter: {result.items_filtered}")
                print(f"  Items imported: {result.items_imported}")
                print(f"  Items duplicate: {result.items_duplicate}")

                if result.errors:
                    print(f"\nErrors ({len(result.errors)}):")
                    for err in result.errors[:5]:
                        print(f"  - {err}")

            except Exception as e:
                print(f"Error: {e}")
                sys.exit(1)

    elif args.command == "gmail":
        if args.gmail_command == "auth":
            from zotero_mcp.clients.gmail import DEFAULT_CREDENTIALS_PATH, GmailClient

            credentials_path = args.credentials or DEFAULT_CREDENTIALS_PATH
            print(f"Authenticating with Gmail using credentials: {credentials_path}")

            try:
                client = GmailClient(credentials_path=credentials_path)
                # Force authentication by accessing service
                _ = client.service
                print("✓ Gmail authentication successful!")
                print(f"  Token saved to: {client.token_path}")
            except FileNotFoundError as e:
                print(f"✗ {e}")
                print("\nTo set up Gmail API:")
                print("1. Go to Google Cloud Console")
                print("2. Create OAuth2 credentials (Desktop app)")
                print("3. Download credentials.json")
                print(f"4. Place it at: {DEFAULT_CREDENTIALS_PATH}")
                print("   Or specify with: --credentials /path/to/credentials.json")
                sys.exit(1)
            except Exception as e:
                print(f"✗ Authentication failed: {e}")
                sys.exit(1)

        elif args.gmail_command == "process":
            load_config()
            import asyncio

            from zotero_mcp.services.gmail.gmail_service import GmailService
            from zotero_mcp.utils.config import get_gmail_config

            # Apply env var defaults for CLI args not explicitly provided
            gmail_config = get_gmail_config()
            if not args.sender and gmail_config.get("sender_filter"):
                args.sender = gmail_config["sender_filter"]
                print(f"Using GMAIL_SENDER_FILTER: {args.sender}")
            if not args.subject and gmail_config.get("subject_filter"):
                args.subject = gmail_config["subject_filter"]
                print(f"Using GMAIL_SUBJECT_FILTER: {args.subject}")
            if not args.collection or args.collection == "00_INBOXS":
                config_collection = gmail_config.get("collection", "00_INBOXS")
                if config_collection:
                    args.collection = config_collection

            if not args.sender and not args.subject and not args.query:
                args.query = "is:unread"
                print(
                    "Warning: No --sender, --subject, or --query specified. "
                    'Defaulting to --query "is:unread"'
                )

            service = GmailService()
            try:
                result = asyncio.run(
                    service.process_gmail_workflow(
                        sender=args.sender,
                        subject=args.subject,
                        query=args.query,
                        collection_name=args.collection,
                        max_emails=args.max_emails,
                        delete_after=not args.no_delete,
                        trash_only=not args.permanent_delete,
                        dry_run=args.dry_run,
                    )
                )

                print("\n=== Gmail Processing Results ===")
                print(f"  Emails found: {result.emails_found}")
                print(f"  Emails processed: {result.emails_processed}")
                print(f"  Items extracted: {result.items_extracted}")
                print(f"  Items filtered (relevant): {result.items_filtered}")
                print(f"  Items imported: {result.items_imported}")
                print(f"  Items duplicate: {result.items_duplicate}")
                print(f"  Emails deleted: {result.emails_deleted}")

                if result.keywords_used:
                    print(f"\nKeywords used: {', '.join(result.keywords_used)}")

                if result.errors:
                    print(f"\nErrors ({len(result.errors)}):")
                    for err in result.errors[:5]:
                        print(f"  - {err}")

            except Exception as e:
                print(f"Error: {e}")
                sys.exit(1)

    elif args.command == "scan":
        load_config()
        import asyncio

        from zotero_mcp.services.scanner import GlobalScanner

        scanner = GlobalScanner()
        try:
            result = asyncio.run(
                scanner.scan_and_process(
                    limit=args.limit,
                    target_collection=args.target_collection,
                    dry_run=args.dry_run,
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

    elif args.command == "serve":
        load_config()
        if args.transport == "stdio":
            mcp.run(transport="stdio")
        elif args.transport == "streamable-http":
            mcp.run(transport="streamable-http", host=args.host, port=args.port)
        elif args.transport == "sse":
            import warnings

            warnings.warn("SSE deprecated", UserWarning, stacklevel=2)
            mcp.run(transport="sse", host=args.host, port=args.port)


if __name__ == "__main__":
    main()
