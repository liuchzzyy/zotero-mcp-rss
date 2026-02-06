"""DeepSeek LLM client."""

from __future__ import annotations

from typing import Any, Dict

from paper_analyzer.clients.openai_client import OpenAIClient


class DeepSeekClient(OpenAIClient):
    """
    DeepSeek API client.

    Uses OpenAI-compatible API at https://api.deepseek.com/v1.
    """

    def __init__(
        self,
        api_key: str,
        model: str = "deepseek-chat",
        base_url: str = "https://api.deepseek.com/v1",
        max_tokens: int = 4000,
        temperature: float = 0.7,
        timeout: int = 120,
    ):
        super().__init__(
            api_key=api_key,
            base_url=base_url,
            model=model,
            max_tokens=max_tokens,
            temperature=temperature,
            timeout=timeout,
        )

    def supports_vision(self) -> bool:
        return False

    def get_model_info(self) -> Dict[str, Any]:
        return {
            "provider": "deepseek",
            "model": self.model,
            "base_url": self.base_url,
            "supports_vision": False,
            "max_tokens": self.max_tokens,
        }
