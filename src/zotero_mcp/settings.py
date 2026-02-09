"""Configuration management using Pydantic Settings."""

from importlib.metadata import version as _pkg_version

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


def _get_version() -> str:
    try:
        return _pkg_version("zotero-mcp")
    except Exception:
        return "0.0.0"


class ZoteroSettings(BaseSettings):
    """Zotero MCP Server settings loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        env_prefix="ZOTERO_",
        extra="ignore",
    )

    # Server metadata
    server_name: str = Field(default="zotero-mcp")
    server_version: str = Field(default_factory=_get_version)

    # Feature flags
    enable_semantic_search: bool = Field(default=True)
    enable_workflows: bool = Field(default=True)
    enable_database_tools: bool = Field(default=True)
    enable_collection_tools: bool = Field(default=True)


settings = ZoteroSettings()
