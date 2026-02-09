"""Tests for zotero-mcp config module."""

from zotero_mcp.config import Config, get_config, reset_config


class TestConfig:
    def setup_method(self):
        reset_config()

    def test_from_env_defaults(self, monkeypatch):
        for key in [
            "ZOTERO_LIBRARY_ID",
            "ZOTERO_API_KEY",
            "LLM_API_KEY",
            "LLM_PROVIDER",
            "DEBUG",
        ]:
            monkeypatch.delenv(key, raising=False)

        config = Config.from_env()
        assert config.zotero_library_id == ""
        assert config.zotero_api_key == ""
        assert config.llm_provider == "deepseek"
        assert config.llm_model == "deepseek-chat"
        assert config.debug is False

    def test_from_env_with_values(self, monkeypatch):
        monkeypatch.setenv("ZOTERO_LIBRARY_ID", "12345")
        monkeypatch.setenv("ZOTERO_API_KEY", "secret-key")
        monkeypatch.setenv("LLM_PROVIDER", "openai")
        monkeypatch.setenv("LLM_API_KEY", "llm-key")
        monkeypatch.setenv("DEBUG", "true")

        config = Config.from_env()
        assert config.zotero_library_id == "12345"
        assert config.zotero_api_key == "secret-key"
        assert config.llm_provider == "openai"
        assert config.llm_api_key == "llm-key"
        assert config.debug is True

    def test_has_zotero(self):
        config = Config(zotero_library_id="123", zotero_api_key="key")
        assert config.has_zotero is True

        config2 = Config(zotero_library_id="", zotero_api_key="key")
        assert config2.has_zotero is False

    def test_has_llm(self):
        config = Config(llm_api_key="key")
        assert config.has_llm is True

        config2 = Config(llm_api_key="")
        assert config2.has_llm is False

    def test_has_semantic(self):
        config = Config(embedding_api_key="key")
        assert config.has_semantic is True

        config2 = Config(embedding_api_key="")
        assert config2.has_semantic is False

    def test_singleton(self, monkeypatch):
        monkeypatch.setenv("ZOTERO_LIBRARY_ID", "test-id")
        monkeypatch.setenv("ZOTERO_API_KEY", "test-key")

        reset_config()
        c1 = get_config()
        c2 = get_config()
        assert c1 is c2
        assert c1.zotero_library_id == "test-id"

    def test_reset_config(self, monkeypatch):
        monkeypatch.setenv("ZOTERO_LIBRARY_ID", "first")
        monkeypatch.setenv("ZOTERO_API_KEY", "key")

        c1 = get_config()
        assert c1.zotero_library_id == "first"

        reset_config()
        monkeypatch.setenv("ZOTERO_LIBRARY_ID", "second")
        c2 = get_config()
        assert c2.zotero_library_id == "second"
        assert c1 is not c2
