"""
Collection management tools for Zotero MCP.
"""

from fastmcp import Context, FastMCP
from mcp.types import ToolAnnotations

from zotero_mcp.models.zotero import (
    CreateCollectionInput,
    CreateCollectionResponse,
    DeleteCollectionInput,
    MoveCollectionInput,
    RenameCollectionInput,
)
from zotero_mcp.models.common import BaseResponse
from zotero_mcp.services.data_access import get_data_service


def register_collection_tools(mcp: FastMCP) -> None:
    """Register collection management tools."""

    @mcp.tool(
        name="zotero_create_collection",
        annotations=ToolAnnotations(
            title="Create Collection",
            readOnlyHint=False,
            destructiveHint=False,
            idempotentHint=False,
            openWorldHint=False,
        ),
    )
    async def zotero_create_collection(
        params: CreateCollectionInput, ctx: Context
    ) -> CreateCollectionResponse:
        """
        Create a new collection in Zotero.

        Args:
            params: Parameters including name and optional parent_key.

        Returns:
            CreateCollectionResponse: Key and name of the created collection.
        """
        try:
            service = get_data_service()
            result = await service.create_collection(
                name=params.name, parent_key=params.parent_key
            )

            # Extract key from result. Pyzotero returns {'successful': {'0': {'key': '...', ...}}}
            if "successful" in result and result["successful"]:
                # Get the first key from successful dict
                data = list(result["successful"].values())[0]
                return CreateCollectionResponse(
                    key=data["key"],
                    name=data["data"]["name"],
                    parent_key=data["data"].get("parentCollection"),
                )
            else:
                raise Exception(f"API response did not indicate success: {result}")

        except Exception as e:
            await ctx.error(f"Failed to create collection: {str(e)}")
            return CreateCollectionResponse(
                success=False,
                error=f"Error creating collection: {str(e)}",
                key="",
                name=params.name,
            )

    @mcp.tool(
        name="zotero_delete_collection",
        annotations=ToolAnnotations(
            title="Delete Collection",
            readOnlyHint=False,
            destructiveHint=True,
            idempotentHint=False,
            openWorldHint=False,
        ),
    )
    async def zotero_delete_collection(
        params: DeleteCollectionInput, ctx: Context
    ) -> BaseResponse:
        """
        Delete a collection.

        WARNING: This action cannot be undone via API.

        Args:
            params: Parameters including collection_key.
        """
        try:
            service = get_data_service()
            await service.delete_collection(params.collection_key)
            return BaseResponse(success=True)

        except Exception as e:
            await ctx.error(f"Failed to delete collection: {str(e)}")
            return BaseResponse(success=False, error=str(e))

    @mcp.tool(
        name="zotero_move_collection",
        annotations=ToolAnnotations(
            title="Move Collection",
            readOnlyHint=False,
            destructiveHint=False,
            idempotentHint=False,
            openWorldHint=False,
        ),
    )
    async def zotero_move_collection(
        params: MoveCollectionInput, ctx: Context
    ) -> BaseResponse:
        """
        Move a collection to a new parent.

        Args:
            params: Parameters including collection_key and new parent_key.
                    Use "root" or "" as parent_key to move to the top level.
        """
        try:
            service = get_data_service()
            # Handle root keywords
            parent = params.parent_key
            if parent in ["root", ""]:
                parent = None

            await service.update_collection(
                collection_key=params.collection_key, parent_key=parent
            )
            return BaseResponse(success=True)

        except Exception as e:
            await ctx.error(f"Failed to move collection: {str(e)}")
            return BaseResponse(success=False, error=str(e))

    @mcp.tool(
        name="zotero_rename_collection",
        annotations=ToolAnnotations(
            title="Rename Collection",
            readOnlyHint=False,
            destructiveHint=False,
            idempotentHint=False,
            openWorldHint=False,
        ),
    )
    async def zotero_rename_collection(
        params: RenameCollectionInput, ctx: Context
    ) -> BaseResponse:
        """
        Rename a collection.

        Args:
            params: Parameters including collection_key and new_name.
        """
        try:
            service = get_data_service()
            await service.update_collection(
                collection_key=params.collection_key, name=params.new_name
            )
            return BaseResponse(success=True)

        except Exception as e:
            await ctx.error(f"Failed to rename collection: {str(e)}")
            return BaseResponse(success=False, error=str(e))
