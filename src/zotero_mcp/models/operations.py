"""Shared operation parameter models for service entrypoints."""

from pydantic import BaseModel, ConfigDict, Field


class ScannerRunParams(BaseModel):
    """Explicit runtime parameters for GlobalScanner.scan_and_process."""

    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    scan_limit: int = Field(default=100, ge=1)
    treated_limit: int = Field(default=20, ge=1)
    target_collection: str = Field(..., min_length=1)
    dry_run: bool = Field(default=False)
    llm_provider: str = Field(default="auto")
    source_collection: str | None = Field(default="00_INBOXS")
    include_multimodal: bool = Field(default=True)


class MetadataUpdateBatchParams(BaseModel):
    """Explicit runtime parameters for MetadataUpdateService.update_all_items."""

    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    collection_key: str | None = Field(default=None)
    scan_limit: int = Field(default=100, ge=1)
    treated_limit: int | None = Field(default=None, ge=1)
    dry_run: bool = Field(default=False)


class DuplicateScanParams(BaseModel):
    """Explicit runtime parameters for duplicate detection scans."""

    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    collection_key: str | None = Field(default=None)
    scan_limit: int = Field(default=500, ge=1)
    treated_limit: int = Field(default=1000, ge=1)
    dry_run: bool = Field(default=False)
