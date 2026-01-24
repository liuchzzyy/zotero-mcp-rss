"""
Batch operation models.
"""

from pydantic import BaseModel, Field

from zotero_mcp.models.common import BaseInput, BaseResponse, ItemDetailResponse


class BatchGetMetadataInput(BaseInput):
    """Input for batch metadata retrieval."""

    item_keys: list[str] = Field(
        ...,
        min_length=1,
        max_length=50,  # Limit batch size
        description="List of item keys to retrieve",
    )
    output_format: str = Field(default="json", description="Output format")


class BatchItemResult(BaseModel):
    """Single item result in batch operation."""

    item_key: str = Field(..., description="Item key")
    success: bool = Field(..., description="Whether retrieval succeeded")
    data: ItemDetailResponse | None = Field(
        default=None, description="Item data if successful"
    )
    error: str | None = Field(default=None, description="Error message if failed")


class BatchGetMetadataResponse(BaseResponse):
    """Response for batch metadata retrieval."""

    total_requested: int = Field(..., description="Total items requested")
    successful: int = Field(..., description="Successfully retrieved items")
    failed: int = Field(..., description="Failed items")
    results: list[BatchItemResult] = Field(
        default_factory=list, description="Individual item results"
    )
