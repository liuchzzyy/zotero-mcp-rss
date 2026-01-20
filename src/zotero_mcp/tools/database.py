"""
Database tools for Zotero MCP.

Provides tools for managing the semantic search database:
- zotero_update_database: Update the semantic search database
- zotero_database_status: Check database status
"""

from typing import Literal

from fastmcp import FastMCP, Context

from zotero_mcp.models.common import ResponseFormat
from zotero_mcp.services import get_data_service
from zotero_mcp.utils.errors import handle_error


def register_database_tools(mcp: FastMCP) -> None:
    """Register all database tools with the MCP server."""

    @mcp.tool(
        name="zotero_update_database",
        description="Update the semantic search database. "
        "Run this after adding new items to your Zotero library.",
    )
    async def zotero_update_database(
        force_rebuild: bool = False,
        include_fulltext: bool = False,
        limit: int | None = None,
        *,
        ctx: Context,
    ) -> str:
        """
        Update the semantic search database.

        Args:
            force_rebuild: Force complete rebuild (slower but fixes issues)
            include_fulltext: Include full-text from PDFs (slower but more comprehensive)
            limit: Limit number of items to process (useful for testing)

        Returns:
            Status message with update results
        """
        try:
            # Import semantic search module
            from zotero_mcp.services.semantic import update_database

            ctx.info("Starting semantic search database update...")

            result = await update_database(
                force_rebuild=force_rebuild,
                include_fulltext=include_fulltext,
                limit=limit,
            )

            if isinstance(result, dict):
                items_processed = result.get("items_processed", 0)
                items_added = result.get("items_added", 0)
                items_updated = result.get("items_updated", 0)
                duration = result.get("duration_seconds", 0)

                lines = [
                    "# Semantic Search Database Update Complete",
                    "",
                    f"**Items Processed:** {items_processed}",
                    f"**Items Added:** {items_added}",
                    f"**Items Updated:** {items_updated}",
                    f"**Duration:** {duration:.1f} seconds",
                    "",
                ]

                if force_rebuild:
                    lines.append("*Database was rebuilt from scratch.*")
                if include_fulltext:
                    lines.append("*Full-text content was indexed.*")

                return "\n".join(lines)

            return "✅ Database update completed successfully."

        except ImportError:
            return (
                "❌ Semantic search module not available. "
                "Please install the required dependencies: `pip install chromadb sentence-transformers`"
            )
        except Exception as e:
            return handle_error(e, ctx, "update database")

    @mcp.tool(
        name="zotero_database_status",
        description="Get the status of the semantic search database, "
        "including item count, last update time, and configuration.",
    )
    async def zotero_database_status(
        response_format: Literal["markdown", "json"] = "markdown",
        *,
        ctx: Context,
    ) -> str:
        """
        Get semantic search database status.

        Args:
            response_format: Output format

        Returns:
            Database status and configuration
        """
        try:
            # Import semantic search module
            from zotero_mcp.services.semantic import get_database_status

            status = await get_database_status()

            if response_format == "json":
                import json

                return json.dumps(status, indent=2, default=str)

            # Markdown format
            lines = [
                "# Semantic Search Database Status",
                "",
            ]

            if status.get("exists", False):
                lines.extend(
                    [
                        "**Status:** ✅ Initialized",
                        "",
                        f"**Total Items:** {status.get('item_count', 0)}",
                        f"**Last Updated:** {status.get('last_updated', 'Unknown')}",
                        "",
                        "## Configuration",
                        "",
                        f"**Embedding Model:** {status.get('embedding_model', 'default')}",
                    ]
                )

                if model_name := status.get("model_name"):
                    lines.append(f"**Model Name:** {model_name}")

                update_config = status.get("update_config", {})
                if update_config:
                    auto_update = update_config.get("auto_update", False)
                    frequency = update_config.get("update_frequency", "manual")
                    lines.extend(
                        [
                            "",
                            "## Update Settings",
                            "",
                            f"**Auto Update:** {'Yes' if auto_update else 'No'}",
                            f"**Frequency:** {frequency}",
                        ]
                    )

                if fulltext_enabled := status.get("fulltext_enabled"):
                    lines.append(
                        f"**Full-text Indexing:** {'Enabled' if fulltext_enabled else 'Disabled'}"
                    )

                lines.extend(
                    [
                        "",
                        "---",
                        "*Use `zotero_update_database` to update the database.*",
                    ]
                )

            else:
                lines.extend(
                    [
                        "**Status:** ⚠️ Not Initialized",
                        "",
                        "The semantic search database has not been created yet.",
                        "",
                        "To initialize, run:",
                        "```",
                        "zotero-mcp update-db",
                        "```",
                        "",
                        "Or use the `zotero_update_database` tool.",
                    ]
                )

            return "\n".join(lines)

        except ImportError:
            return (
                "# Semantic Search Status\n\n"
                "**Status:** ❌ Not Available\n\n"
                "Semantic search dependencies are not installed.\n\n"
                "Install with: `pip install chromadb sentence-transformers`"
            )
        except Exception as e:
            return handle_error(e, ctx, "database status")
