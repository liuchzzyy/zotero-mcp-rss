import json
import os
from unittest.mock import patch

import pytest

from zotero_mcp.utils.config import _clear_cache, load_config


@pytest.fixture
def mock_home(tmp_path):
    with patch("pathlib.Path.home", return_value=tmp_path):
        yield tmp_path


@pytest.fixture(autouse=True)
def clear_test_env():
    """Clear all Zotero MCP related environment variables before each test."""
    # Clear config cache first
    _clear_cache()
    # Clear all relevant prefixes
    prefixes = [
        "RSS_",
        "ZOTERO_",
        "OPENAI_",
        "GEMINI_",
        "DEEPSEEK_",
        "GMAIL_",
        "ENV_MODE",
    ]
    to_delete = [
        key for key in os.environ if any(key.startswith(prefix) for prefix in prefixes)
    ]
    for key in to_delete:
        del os.environ[key]
    yield
    # Cleanup after test - only delete if still exists
    for key in to_delete:
        if key in os.environ:
            del os.environ[key]
    # Clear cache after test
    _clear_cache()


def test_load_config_empty(mock_home, clear_test_env):
    """Test loading with no config files and no env vars."""
    config = load_config(load_dotenv_file=False)
    # Should return empty dict or dict with empty sub-dicts
    assert config.get("env") == {} or config == {}


def test_load_config_env_vars(mock_home, clear_test_env):
    """Test environment variables are loaded."""
    env = {"ZOTERO_LOCAL": "true", "ZOTERO_API_KEY": "env_key"}
    with patch.dict(os.environ, env, clear=True):
        config = load_config(load_dotenv_file=False)
        # The structure of returned config depends on implementation
        # Assuming it returns a dict with "env" key or merged dict
        # Based on setup.py usage: config.get("env", {})

        loaded_env = config.get("env", {})
        assert loaded_env.get("ZOTERO_LOCAL") == "true"
        assert loaded_env.get("ZOTERO_API_KEY") == "env_key"


def test_load_config_file(mock_home, clear_test_env):
    """Test loading from standalone config file."""
    # Setup config file
    config_dir = mock_home / ".config" / "zotero-mcp"
    config_dir.mkdir(parents=True)
    config_file = config_dir / "config.json"

    data = {
        "client_env": {"ZOTERO_LIBRARY_ID": "file_id"},
        "semantic_search": {"model": "test"},
    }

    with open(config_file, "w") as f:
        json.dump(data, f)

    config = load_config(load_dotenv_file=False)

    # Verify env vars from file are loaded
    loaded_env = config.get("env", {})
    assert loaded_env.get("ZOTERO_LIBRARY_ID") == "file_id"

    # Verify semantic config
    assert config.get("semantic_search", {}).get("model") == "test"


def test_priority(mock_home, clear_test_env):
    """Test Env Vars > Config File."""
    # Setup config file
    config_dir = mock_home / ".config" / "zotero-mcp"
    config_dir.mkdir(parents=True)
    config_file = config_dir / "config.json"

    data = {
        "client_env": {"ZOTERO_API_KEY": "file_key", "ZOTERO_LIBRARY_ID": "file_id"}
    }

    with open(config_file, "w") as f:
        json.dump(data, f)

    # Setup Env Vars
    env = {"ZOTERO_API_KEY": "env_key"}

    with patch.dict(os.environ, env, clear=True):
        config = load_config(load_dotenv_file=False)
        loaded_env = config.get("env", {})

        # Env var should win
        assert loaded_env.get("ZOTERO_API_KEY") == "env_key"
        # File var should persist if not overridden
        assert loaded_env.get("ZOTERO_LIBRARY_ID") == "file_id"
