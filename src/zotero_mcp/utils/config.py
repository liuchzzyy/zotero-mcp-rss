"""
Configuration loading and management for Zotero MCP.

Supports loading configuration from:
- Opencode CLI config (~/.opencode/)
- Standalone config (~/.config/zotero-mcp/config.json)
"""

import json
import os
import sys
from pathlib import Path
from typing import Any


def get_config_path() -> Path:
    """
    Get the path to the Zotero MCP config directory.

    Returns:
        Path to ~/.config/zotero-mcp/
    """
    config_dir = Path.home() / ".config" / "zotero-mcp"
    config_dir.mkdir(parents=True, exist_ok=True)
    return config_dir


def get_config_file_path() -> Path:
    """
    Get the path to the main config file.

    Returns:
        Path to ~/.config/zotero-mcp/config.json
    """
    return get_config_path() / "config.json"


def find_opencode_config() -> Path | None:
    """
    Find Opencode CLI config file path.

    Searches for ~/.opencode/ configuration directory.

    Returns:
        Path to opencode config.json if found, None otherwise.
    """
    # Opencode uses ~/.opencode/ on all platforms
    opencode_dir = Path.home() / ".opencode"

    # Common config file names to check
    config_names = ["config.json", "settings.json", "mcp.json"]

    for name in config_names:
        config_path = opencode_dir / name
        if config_path.exists():
            return config_path

    return None


def load_opencode_config() -> dict[str, Any]:
    """
    Load configuration from Opencode CLI config.

    Returns:
        Dictionary with environment variables from Opencode config,
        or empty dict if not found.
    """
    config_path = find_opencode_config()
    if not config_path:
        return {}

    try:
        with open(config_path) as f:
            config = json.load(f)

        # Opencode may store MCP servers in different formats
        # Try common patterns
        mcp_servers = config.get("mcpServers", config.get("mcp_servers", {}))
        zotero_config = mcp_servers.get("zotero", {})

        return zotero_config.get("env", {})
    except (json.JSONDecodeError, OSError):
        return {}


def load_standalone_config() -> dict[str, Any]:
    """
    Load configuration from standalone config file.

    Returns:
        Full configuration dictionary from ~/.config/zotero-mcp/config.json,
        or empty dict if not found.
    """
    config_path = get_config_file_path()
    if not config_path.exists():
        return {}

    try:
        with open(config_path) as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        return {}


def load_config() -> dict[str, Any]:
    """
    Load configuration from all available sources.

    Priority order:
    1. Environment variables (highest priority)
    2. Standalone config (~/.config/zotero-mcp/config.json)
    3. Opencode CLI config (lowest priority)

    Returns:
        Merged configuration dictionary with 'env' and 'semantic_search' keys.
    """
    # Start with lowest priority and override with higher
    env_config: dict[str, str] = {}

    # Load from Opencode (lowest priority)
    opencode_env = load_opencode_config()
    env_config.update(opencode_env)

    # Load standalone config
    standalone = load_standalone_config()
    client_env = standalone.get("client_env", {})
    env_config.update(client_env)

    # Apply to os.environ for backward compatibility,
    # but don't override existing env vars
    for key, value in env_config.items():
        if key not in os.environ:
            os.environ[key] = str(value)

    return {
        "env": env_config,
        "semantic_search": standalone.get("semantic_search", {}),
    }


def get_semantic_search_config() -> dict[str, Any]:
    """
    Get semantic search configuration.

    Returns:
        Semantic search configuration dictionary.
    """
    config = load_config()
    return config.get("semantic_search", {})


def get_llm_config() -> dict[str, Any]:
    """
    Get LLM configuration for workflow tools.

    Returns:
        Dictionary with LLM provider settings and API keys.
    """
    config = load_config()
    env = config.get("env", {})

    # Build LLM config from environment variables
    llm_config = {
        "deepseek_api_key": env.get("DEEPSEEK_API_KEY", os.getenv("DEEPSEEK_API_KEY")),
        "openai_api_key": env.get("OPENAI_API_KEY", os.getenv("OPENAI_API_KEY")),
        "gemini_api_key": env.get("GEMINI_API_KEY", os.getenv("GEMINI_API_KEY")),
        "deepseek_model": env.get(
            "DEEPSEEK_MODEL", os.getenv("DEEPSEEK_MODEL", "deepseek-chat")
        ),
        "openai_model": env.get(
            "OPENAI_MODEL", os.getenv("OPENAI_MODEL", "gpt-4o-mini")
        ),
        "gemini_model": env.get(
            "GEMINI_MODEL", os.getenv("GEMINI_MODEL", "gemini-2.0-flash-exp")
        ),
    }

    return llm_config


def save_config(config: dict[str, Any]) -> bool:
    """
    Save configuration to standalone config file.

    Args:
        config: Configuration dictionary to save.

    Returns:
        True if saved successfully, False otherwise.
    """
    config_path = get_config_file_path()

    try:
        with open(config_path, "w") as f:
            json.dump(config, f, indent=2)
        return True
    except OSError:
        return False


def is_opencode_configured() -> bool:
    """Check if Opencode CLI is configured with Zotero MCP."""
    return find_opencode_config() is not None and bool(load_opencode_config())


def get_zotero_mode() -> str:
    """
    Get the current Zotero access mode.

    Returns:
        "local" if using local API, "web" if using web API.
    """
    config = load_config()
    local_value = config.get("env", {}).get(
        "ZOTERO_LOCAL", os.getenv("ZOTERO_LOCAL", "")
    )
    if local_value.lower() in {"true", "yes", "1"}:
        return "local"
    return "web"
