"""Tests for LLM clients."""

from paper_analyzer.clients.base import BaseLLMClient
from paper_analyzer.clients.openai_client import OpenAIClient
from paper_analyzer.clients.deepseek import DeepSeekClient


class TestOpenAIClient:
    def test_init_defaults(self):
        client = OpenAIClient(api_key="test-key")
        assert client.api_key == "test-key"
        assert client.base_url == "https://api.openai.com/v1"
        assert client.model == "gpt-3.5-turbo"
        assert client.max_tokens == 4000
        assert client.temperature == 0.7

    def test_supports_vision_gpt4o(self):
        client = OpenAIClient(api_key="key", model="gpt-4o")
        assert client.supports_vision() is True

    def test_supports_vision_gpt4_vision(self):
        client = OpenAIClient(
            api_key="key", model="gpt-4-vision-preview"
        )
        assert client.supports_vision() is True

    def test_no_vision_gpt35(self):
        client = OpenAIClient(api_key="key", model="gpt-3.5-turbo")
        assert client.supports_vision() is False

    def test_get_model_info(self):
        client = OpenAIClient(
            api_key="key",
            model="gpt-4o",
            base_url="https://api.openai.com/v1",
        )
        info = client.get_model_info()
        assert info["provider"] == "openai"
        assert info["model"] == "gpt-4o"
        assert info["supports_vision"] is True

    def test_custom_base_url(self):
        client = OpenAIClient(
            api_key="key",
            base_url="https://custom.api.com/v1",
            model="custom-model",
        )
        assert client.base_url == "https://custom.api.com/v1"


class TestDeepSeekClient:
    def test_init_defaults(self):
        client = DeepSeekClient(api_key="test-key")
        assert client.base_url == "https://api.deepseek.com/v1"
        assert client.model == "deepseek-chat"

    def test_no_vision(self):
        client = DeepSeekClient(api_key="key")
        assert client.supports_vision() is False

    def test_get_model_info(self):
        client = DeepSeekClient(api_key="key")
        info = client.get_model_info()
        assert info["provider"] == "deepseek"
        assert info["supports_vision"] is False

    def test_custom_model(self):
        client = DeepSeekClient(api_key="key", model="deepseek-coder")
        assert client.model == "deepseek-coder"

    def test_inherits_openai(self):
        client = DeepSeekClient(api_key="key")
        assert isinstance(client, OpenAIClient)
        assert isinstance(client, BaseLLMClient)
