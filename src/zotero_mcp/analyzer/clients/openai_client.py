"""OpenAI-compatible LLM client."""

from __future__ import annotations

from typing import Any

import httpx

from zotero_mcp.analyzer.clients.base import BaseLLMClient


class OpenAIClient(BaseLLMClient):
    """
    OpenAI API client (compatible with any OpenAI-compatible API).
    """

    VISION_MODELS = {
        "gpt-4o",
        "gpt-4-vision-preview",
        "gpt-4o-mini",
        "claude-3",
        "claude-3.5",
        "gemini-pro-vision",
    }

    def __init__(
        self,
        api_key: str,
        base_url: str = "https://api.openai.com/v1",
        model: str = "gpt-3.5-turbo",
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
        )
        self.timeout = timeout

    async def analyze(
        self,
        prompt: str,
        system_prompt: str | None = None,
        images: list[str] | None = None,
        **kwargs: Any,
    ) -> str:
        """Send analysis request to OpenAI-compatible API."""
        messages: list[dict[str, Any]] = []

        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})

        # Build user message
        if images and self.supports_vision():
            content: list[dict[str, Any]] = [{"type": "text", "text": prompt}]
            for img_base64 in images:
                content.append(
                    {
                        "type": "image_url",
                        "image_url": {"url": f"data:image/png;base64,{img_base64}"},
                    }
                )
            messages.append({"role": "user", "content": content})
        else:
            messages.append({"role": "user", "content": prompt})

        payload = {
            "model": self.model,
            "messages": messages,
            "max_tokens": kwargs.get("max_tokens", self.max_tokens),
            "temperature": kwargs.get("temperature", self.temperature),
        }

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.post(
                f"{self.base_url}/chat/completions",
                json=payload,
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json",
                },
            )
            response.raise_for_status()
            data = response.json()

        return data["choices"][0]["message"]["content"]

    def supports_vision(self) -> bool:
        model_lower = self.model.lower()
        return any(vm in model_lower for vm in self.VISION_MODELS)

    def get_model_info(self) -> dict[str, Any]:
        return {
            "provider": "openai",
            "model": self.model,
            "base_url": self.base_url,
            "supports_vision": self.supports_vision(),
            "max_tokens": self.max_tokens,
        }
