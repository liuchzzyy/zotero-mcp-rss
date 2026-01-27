import json
import os
from unittest.mock import patch

import pytest

from zotero_mcp.utils.config import load_config


@pytest.fixture
def mock_home(tmp_path):
    with patch("pathlib.Path.home", return_value=tmp_path):
        yield tmp_path


def test_load_config_empty(mock_home):
    """Test loading with no config files and no env vars."""
    with patch.dict(os.environ, {}, clear=True):
        config = load_config()
        # Should return empty dict or dict with empty sub-dicts
        assert config.get("env") == {} or config == {}


def test_load_config_env_vars(mock_home):
    """Test environment variables are loaded."""
    env = {"ZOTERO_LOCAL": "true", "ZOTERO_API_KEY": "env_key"}
    with patch.dict(os.environ, env, clear=True):
        config = load_config()
        # The structure of returned config depends on implementation
        # Assuming it returns a dict with "env" key or merged dict
        # Based on setup.py usage: config.get("env", {})

        loaded_env = config.get("env", {})
        assert loaded_env.get("ZOTERO_LOCAL") == "true"
        assert loaded_env.get("ZOTERO_API_KEY") == "env_key"


def test_load_config_file(mock_home):
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

    with patch.dict(os.environ, {}, clear=True):
        config = load_config()

        # Verify env vars from file are loaded
        loaded_env = config.get("env", {})
        assert loaded_env.get("ZOTERO_LIBRARY_ID") == "file_id"

        # Verify semantic config
        assert config.get("semantic_search", {}).get("model") == "test"


def test_priority(mock_home):
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
        config = load_config()
        loaded_env = config.get("env", {})

        # Env var should win
        assert loaded_env.get("ZOTERO_API_KEY") == "env_key"
        # File var should persist if not overridden
        assert loaded_env.get("ZOTERO_LIBRARY_ID") == "file_id"
