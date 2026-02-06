"""Base LLM client interface."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional


class BaseLLMClient(ABC):
    """Abstract base class for LLM clients."""

    def __init__(
        self,
        api_key: str,
        base_url: Optional[str] = None,
        model: str = "default",
        max_tokens: int = 4000,
        temperature: float = 0.7,
    ):
        self.api_key = api_key
        self.base_url = base_url
        self.model = model
        self.max_tokens = max_tokens
        self.temperature = temperature

    @abstractmethod
    async def analyze(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        images: Optional[List[str]] = None,
        **kwargs: Any,
    ) -> str:
        """
        Send an analysis request to the LLM.

        Args:
            prompt: User prompt
            system_prompt: System prompt
            images: Base64-encoded images for multi-modal
            **kwargs: Extra parameters (max_tokens, temperature overrides)

        Returns:
            LLM response text
        """

    @abstractmethod
    def supports_vision(self) -> bool:
        """Whether this client supports vision/multi-modal input."""

    @abstractmethod
    def get_model_info(self) -> Dict[str, Any]:
        """Return model metadata."""
