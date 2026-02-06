"""
Configuration management for zotero-mcp v3.

Loads settings from environment variables and .env files.
Priority: Environment vars > .env file > defaults
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Optional

from pydantic import BaseModel, Field

# Global config singleton
_config: Optional[Config] = None


class Config(BaseModel):
    """Application configuration loaded from environment."""

    # Zotero
    zotero_library_id: str = Field(default="")
    zotero_api_key: str = Field(default="")
    zotero_library_type: str = Field(default="user")

    # LLM (for paper-analyzer)
    llm_provider: str = Field(default="deepseek")
    llm_api_key: str = Field(default="")
    llm_base_url: str = Field(default="")
    llm_model: str = Field(default="deepseek-chat")

    # Semantic search
    chromadb_persist_dir: str = Field(default="./chromadb_data")
    embedding_provider: str = Field(default="openai")
    embedding_api_key: str = Field(default="")
    embedding_model: str = Field(default="text-embedding-3-small")

    # Logging
    log_level: str = Field(default="INFO")
    debug: bool = Field(default=False)

    @classmethod
    def from_env(cls) -> Config:
        """Create config from environment variables."""
        return cls(
            zotero_library_id=os.getenv("ZOTERO_LIBRARY_ID", ""),
            zotero_api_key=os.getenv("ZOTERO_API_KEY", ""),
            zotero_library_type=os.getenv("ZOTERO_LIBRARY_TYPE", "user"),
            llm_provider=os.getenv("LLM_PROVIDER", "deepseek"),
            llm_api_key=os.getenv("LLM_API_KEY", ""),
            llm_base_url=os.getenv("LLM_BASE_URL", ""),
            llm_model=os.getenv("LLM_MODEL", "deepseek-chat"),
            chromadb_persist_dir=os.getenv(
                "CHROMADB_PERSIST_DIR", "./chromadb_data"
            ),
            embedding_provider=os.getenv("EMBEDDING_PROVIDER", "openai"),
            embedding_api_key=os.getenv("EMBEDDING_API_KEY", ""),
            embedding_model=os.getenv(
                "EMBEDDING_MODEL", "text-embedding-3-small"
            ),
            log_level=os.getenv("LOG_LEVEL", "INFO"),
            debug=os.getenv("DEBUG", "false").lower() in ("true", "1"),
        )

    @classmethod
    def load(cls, env_file: str = ".env") -> Config:
        """Load config from .env file, then environment variables."""
        try:
            from dotenv import load_dotenv

            env_path = Path(env_file)
            if env_path.exists():
                load_dotenv(env_path)
        except ImportError:
            pass

        return cls.from_env()

    @property
    def has_zotero(self) -> bool:
        """Whether Zotero credentials are configured."""
        return bool(self.zotero_library_id and self.zotero_api_key)

    @property
    def has_llm(self) -> bool:
        """Whether LLM API key is configured."""
        return bool(self.llm_api_key)

    @property
    def has_semantic(self) -> bool:
        """Whether semantic search is configured."""
        return bool(self.embedding_api_key)


def get_config() -> Config:
    """Get or create the global config singleton."""
    global _config
    if _config is None:
        _config = Config.load()
    return _config


def reset_config() -> None:
    """Reset the global config (for testing)."""
    global _config
    _config = None
