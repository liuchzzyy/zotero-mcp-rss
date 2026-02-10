"""
Configuration loading and management for Zotero MCP.

Supports loading configuration from:
- Opencode CLI config (~/.opencode/)
- Standalone config (~/.config/zotero-mcp/config.json)
- Environment variables (.env)

Features:
- Configuration caching for performance
- Environment mode support (development, testing, production)
- Centralized configuration management
"""

import json
import os
from pathlib import Path
from typing import Any

from dotenv import load_dotenv

# -------------------- Configuration Cache --------------------


_config_cache: dict[str, Any] | None = None
_cache_timestamp: float = 0
_CACHE_TTL = 300  # 5 minutes cache TTL


def _clear_cache() -> None:
    """Clear configuration cache."""
    global _config_cache, _cache_timestamp
    _config_cache = None
    _cache_timestamp = 0


def _is_cache_valid() -> bool:
    """Check if cache is still valid."""
    import time

    global _cache_timestamp
    return _config_cache is not None and (time.time() - _cache_timestamp) < _CACHE_TTL


# -------------------- Environment Modes --------------------


ENV_MODES = {
    "development": {
        "ZOTERO_LOCAL": "true",
        "DEBUG": "true",
        "LOG_LEVEL": "DEBUG",
    },
    "testing": {
        "ZOTERO_LOCAL": "true",
        "DEBUG": "true",
        "LOG_LEVEL": "INFO",
    },
    "production": {
        "ZOTERO_LOCAL": "false",
        "DEBUG": "false",
        "LOG_LEVEL": "WARNING",
    },
}


def get_env_mode() -> str:
    """
    Get the current environment mode.

    Checks ENV_MODE environment variable, defaults to 'production'.

    Returns:
        Environment mode: 'development', 'testing', or 'production'
    """
    mode = os.getenv("ENV_MODE", "production").lower()
    if mode not in ENV_MODES:
        mode = "production"
    return mode


def apply_env_mode(mode: str) -> None:
    """
    Apply environment mode settings to environment variables.

    Args:
        mode: Environment mode ('development', 'testing', or 'production')
    """
    if mode not in ENV_MODES:
        raise ValueError(
            f"Invalid environment mode: {mode}. Must be one of: {list(ENV_MODES.keys())}"
        )

    mode_settings = ENV_MODES[mode]
    for key, value in mode_settings.items():
        # Only set if not already set in environment
        if key not in os.environ:
            os.environ[key] = value


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


def load_config(
    use_cache: bool = True, load_dotenv_file: bool = True
) -> dict[str, Any]:
    """
    Load configuration from all available sources.

    Priority order:
    1. Environment variables (highest priority)
    2. Standalone config (~/.config/zotero-mcp/config.json)
    3. Opencode CLI config (lowest priority)

    Args:
        use_cache: Whether to use cached configuration (default: True)
        load_dotenv_file: Whether to load .env file (default: True, set to False in tests)

    Returns:
        Merged configuration dictionary with 'env' and 'semantic_search' keys.
    """
    import time

    global _config_cache, _cache_timestamp

    # Check cache first
    if use_cache and _is_cache_valid():
        assert _config_cache is not None
        return _config_cache

    # Load from .env file
    if load_dotenv_file:
        load_dotenv()

    # Start with lowest priority and override with higher
    env_config: dict[str, str] = {}

    # Load from Opencode (lowest priority)
    opencode_env = load_opencode_config()
    env_config.update(opencode_env)

    # Load standalone config
    standalone = load_standalone_config()
    client_env = standalone.get("client_env", {})
    env_config.update(client_env)

    # Apply environment variables (highest priority)
    # We scan for relevant keys to include in the returned config
    relevant_prefixes = [
        "ZOTERO_",
        "DEEPSEEK_",
        "OPENALEX_",
        "POLITE_POOL_",
        "API_TIMEOUT",
        "ENV_MODE",
    ]
    for key, value in os.environ.items():
        if any(key.startswith(prefix) for prefix in relevant_prefixes):
            env_config[key] = value

    # Apply to os.environ for backward compatibility,
    # but don't override existing env vars
    for key, value in env_config.items():
        if key not in os.environ:
            os.environ[key] = str(value)

    config = {
        "env": env_config,
        "semantic_search": standalone.get("semantic_search", {}),
    }

    # Update cache
    _config_cache = config
    _cache_timestamp = time.time()

    return config


def reload_config() -> dict[str, Any]:
    """
    Force reload configuration, bypassing cache.

    Returns:
        Freshly loaded configuration dictionary.
    """
    _clear_cache()
    return load_config(use_cache=False)


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
        Dictionary with DeepSeek API key and model settings.
    """
    config = load_config()
    env = config.get("env", {})

    # Build LLM config from environment variables
    llm_config = {
        "deepseek_api_key": env.get("DEEPSEEK_API_KEY", os.getenv("DEEPSEEK_API_KEY")),
        "deepseek_model": env.get(
            "DEEPSEEK_MODEL", os.getenv("DEEPSEEK_MODEL", "deepseek-chat")
        ),
    }

    return llm_config


def get_openalex_config() -> dict[str, Any]:
    """Build OpenAlex config from environment variables."""
    config = load_config()
    env = config.get("env", {})
    email = env.get("OPENALEX_EMAIL", os.getenv("OPENALEX_EMAIL"))
    if not email:
        email = env.get("POLITE_POOL_EMAIL", os.getenv("POLITE_POOL_EMAIL"))
    api_timeout = env.get("API_TIMEOUT", os.getenv("API_TIMEOUT"))
    openalex_timeout = env.get("OPENALEX_TIMEOUT", os.getenv("OPENALEX_TIMEOUT"))
    timeout_value = openalex_timeout or api_timeout or "45"
    try:
        timeout = float(timeout_value)
    except (TypeError, ValueError):
        timeout = 45.0

    max_rps_value = env.get(
        "OPENALEX_MAX_REQUESTS_PER_SECOND",
        os.getenv("OPENALEX_MAX_REQUESTS_PER_SECOND", "10"),
    )
    try:
        max_rps = int(max_rps_value)
    except (TypeError, ValueError):
        max_rps = 10

    user_agent = env.get("OPENALEX_USER_AGENT", os.getenv("OPENALEX_USER_AGENT"))

    return {
        "email": email,
        "api_key": env.get("OPENALEX_API_KEY", os.getenv("OPENALEX_API_KEY")),
        "api_base": env.get(
            "OPENALEX_API_BASE",
            os.getenv("OPENALEX_API_BASE", "https://api.openalex.org"),
        ),
        "timeout": timeout,
        "user_agent": user_agent,
        "max_requests_per_second": max_rps,
    }


def get_pdf_max_pages() -> int:
    """
    Get PDF max pages configuration for fulltext extraction.

    Priority order:
    1. ZOTERO_PDF_MAXPAGES environment variable (highest)
    2. config.json semantic_search.extraction.pdf_max_pages
    3. Default value: 10

    Returns:
        Maximum number of pages to extract from PDFs.
    """
    # Check environment variable first
    env_value = os.getenv("ZOTERO_PDF_MAXPAGES")
    if env_value:
        try:
            return int(env_value)
        except ValueError:
            pass  # Fall through to config file

    # Check config file
    config = load_config()
    semantic_config = config.get("semantic_search", {})
    extraction_config = semantic_config.get("extraction", {})
    config_value = extraction_config.get("pdf_max_pages")
    if config_value is not None:
        try:
            return int(config_value)
        except ValueError:
            pass  # Fall through to default

    # Default value
    return 10


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


# Alias for compatibility
get_config = load_config
