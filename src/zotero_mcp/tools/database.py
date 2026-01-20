"""
Database tools for Zotero MCP.

Provides tools for managing the semantic search database:
- zotero_update_database: Update the semantic search database
- zotero_database_status: Check database status
"""

from fastmcp import FastMCP, Context
from mcp.types import ToolAnnotations

from zotero_mcp.models.common import DatabaseStatusResponse, DatabaseUpdateResponse
from zotero_mcp.models.database import DatabaseStatusInput, UpdateDatabaseInput


def register_database_tools(mcp: FastMCP) -> None:
    """Register all database tools with the MCP server."""

    @mcp.tool(
        name="zotero_update_database",
        annotations=ToolAnnotations(
            title="Update Semantic Search Database",
            readOnlyHint=False,
            destructiveHint=False,
            idempotentHint=False,
            openWorldHint=False,
        ),
    )
    async def zotero_update_database(
        params: UpdateDatabaseInput, ctx: Context
    ) -> DatabaseUpdateResponse:
        """
        Update the semantic search database.

        Indexes your Zotero library for semantic similarity search using embeddings.
        Run this after adding new items to your library to make them searchable.

        Args:
            params: Input containing:
                - force_rebuild (bool): Whether to rebuild the entire database from scratch
                - limit (int | None): Maximum number of items to process (useful for testing)
                - extract_fulltext (bool): Whether to extract and index full text content (slower but more comprehensive)
                - response_format (str): Output format preference (inherited from BaseInput)

        Returns:
            DatabaseUpdateResponse: Update results with statistics.

        Example:
            Use when: "Update my library's search database"
            Use when: "Rebuild the semantic search index"
            Use when: "Index new papers I added"

        Note:
            First-time indexing may take several minutes depending on library size.
            Subsequent updates are incremental and faster.
        """
        try:
            # Import semantic search module
            from zotero_mcp.services.semantic import update_database

            ctx.info("Starting semantic search database update...")

            result = await update_database(
                force_rebuild=params.force_rebuild,
                include_fulltext=params.extract_fulltext,
                limit=params.limit,
            )

            if isinstance(result, dict):
                items_processed = result.get("items_processed", 0)
                items_added = result.get("items_added", 0)
                items_updated = result.get("items_updated", 0)
                duration = result.get("duration_seconds", 0)

                message_lines = [
                    f"Processed {items_processed} items",
                    f"Added {items_added} new items",
                    f"Updated {items_updated} items",
                    f"Completed in {duration:.1f} seconds",
                ]

                if params.force_rebuild:
                    message_lines.insert(0, "Database rebuilt from scratch")
                if params.extract_fulltext:
                    message_lines.insert(0, "Full-text content indexed")

                return DatabaseUpdateResponse(
                    items_processed=items_processed,
                    items_added=items_added,
                    items_updated=items_updated,
                    duration_seconds=duration,
                    message="\n".join(message_lines),
                )

            # Fallback if result format is unexpected
            return DatabaseUpdateResponse(
                items_processed=0,
                items_added=0,
                items_updated=0,
                duration_seconds=0,
                message="Database update completed successfully",
            )

        except ImportError:
            await ctx.error("Semantic search module not available")
            return DatabaseUpdateResponse(
                success=False,
                error="Semantic search module not available. Install dependencies: pip install chromadb sentence-transformers",
                items_processed=0,
                items_added=0,
                items_updated=0,
                duration_seconds=0,
            )
        except Exception as e:
            await ctx.error(f"Failed to update database: {str(e)}")
            return DatabaseUpdateResponse(
                success=False,
                error=f"Database update error: {str(e)}",
                items_processed=0,
                items_added=0,
                items_updated=0,
                duration_seconds=0,
            )

    @mcp.tool(
        name="zotero_database_status",
        annotations=ToolAnnotations(
            title="Get Database Status",
            readOnlyHint=True,
            destructiveHint=False,
            idempotentHint=True,
            openWorldHint=False,
        ),
    )
    async def zotero_database_status(
        params: DatabaseStatusInput, ctx: Context
    ) -> DatabaseStatusResponse:
        """
        Get the status of the semantic search database.

        Provides information about database initialization, item count,
        last update time, embedding configuration, and update settings.

        Args:
            params: Input containing:
                - response_format (str): Output format preference (inherited from BaseInput)

        Returns:
            DatabaseStatusResponse: Database status and configuration.

        Example:
            Use when: "Is my search database initialized?"
            Use when: "How many papers are indexed?"
            Use when: "When was the database last updated?"
            Use when: "What embedding model am I using?"
        """
        try:
            # Import semantic search module
            from zotero_mcp.services.semantic import get_database_status

            status = await get_database_status()

            if not isinstance(status, dict):
                status = {}

            exists = status.get("exists", False)
            item_count = status.get("item_count", 0)
            last_updated = status.get("last_updated", "Unknown")
            embedding_model = status.get("embedding_model", "default")
            model_name = status.get("model_name")
            fulltext_enabled = status.get("fulltext_enabled", False)

            # Extract update configuration
            update_config = status.get("update_config", {})
            auto_update = (
                update_config.get("auto_update", False) if update_config else False
            )
            update_frequency = (
                update_config.get("update_frequency", "manual")
                if update_config
                else "manual"
            )

            message_lines = []
            if exists:
                message_lines.extend(
                    [
                        f"Database initialized with {item_count} items",
                        f"Last updated: {last_updated}",
                        f"Embedding model: {embedding_model}",
                    ]
                )
                if model_name:
                    message_lines.append(f"Model name: {model_name}")
                message_lines.append(
                    f"Auto-update: {'Enabled' if auto_update else 'Disabled'} ({update_frequency})"
                )
                message_lines.append(
                    f"Full-text indexing: {'Enabled' if fulltext_enabled else 'Disabled'}"
                )
            else:
                message_lines.append(
                    "Database not initialized. Run zotero_update_database to create it."
                )

            return DatabaseStatusResponse(
                exists=exists,
                item_count=item_count,
                last_updated=last_updated,
                embedding_model=embedding_model,
                model_name=model_name,
                fulltext_enabled=fulltext_enabled,
                auto_update=auto_update,
                update_frequency=update_frequency,
                message="\n".join(message_lines),
            )

        except ImportError:
            await ctx.error("Semantic search module not available")
            return DatabaseStatusResponse(
                success=False,
                error="Semantic search module not available. Install dependencies: pip install chromadb sentence-transformers",
                exists=False,
                item_count=0,
                last_updated="Unknown",
                embedding_model="unknown",
            )
        except Exception as e:
            await ctx.error(f"Failed to get database status: {str(e)}")
            return DatabaseStatusResponse(
                success=False,
                error=f"Database status error: {str(e)}",
                exists=False,
                item_count=0,
                last_updated="Unknown",
                embedding_model="unknown",
            )
