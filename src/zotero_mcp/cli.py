"""
Command-line interface for Zotero MCP server.
"""

import argparse
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

from zotero_mcp.server import mcp
from zotero_mcp.utils.config import load_config


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
        "--no-claude", action="store_true", help="Skip Claude Desktop config"
    )
    setup_parser.add_argument(
        "--config-path", help="Path to Claude Desktop config file"
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

    # Version command
    subparsers.add_parser("version", help="Print version information")

    # Setup info command
    subparsers.add_parser("setup-info", help="Show installation info")

    args = parser.parse_args()

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
            from zotero_mcp.semantic_search import create_semantic_search

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
        from zotero_mcp.setup_helper import main as setup_main

        sys.exit(setup_main(args))

    elif args.command == "update-db":
        # Ensure environment is loaded
        load_config()
        from zotero_mcp.semantic_search import create_semantic_search

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
        from zotero_mcp.semantic_search import create_semantic_search

        try:
            search = create_semantic_search(args.config_path)
            status = search.get_database_status()
            print(json.dumps(status, indent=2, default=str))
        except Exception as e:
            print(f"Error: {e}")
            sys.exit(1)

    elif args.command == "db-inspect":
        load_config()
        from zotero_mcp.semantic_search import create_semantic_search

        try:
            search = create_semantic_search(args.config_path)
            # Access underlying client for inspection
            col = search.chroma_client.collection

            if args.stats:
                print(f"Count: {col.count()}")
                return

            results = col.get(
                limit=args.limit,
                include=["metadatas", "documents"]
                if args.show_documents
                else ["metadatas"],
            )

            for i, meta in enumerate(results["metadatas"]):
                print(f"- {meta.get('title', 'Untitled')}")
                if args.show_documents and results["documents"]:
                    print(f"  {results['documents'][i][:100]}...")

        except Exception as e:
            print(f"Error: {e}")
            sys.exit(1)

    elif args.command == "update":
        from zotero_mcp.updater import update_zotero_mcp

        update_zotero_mcp(
            check_only=args.check_only, force=args.force, method=args.method
        )

    elif args.command == "serve":
        load_config()
        if args.transport == "stdio":
            mcp.run(transport="stdio")
        elif args.transport == "streamable-http":
            mcp.run(transport="streamable-http", host=args.host, port=args.port)
        elif args.transport == "sse":
            import warnings

            warnings.warn("SSE deprecated", UserWarning)
            mcp.run(transport="sse", host=args.host, port=args.port)


if __name__ == "__main__":
    main()
