"""
LLM capability detection and registry.

Defines what each LLM provider can handle:
- Text input
- Image/vision input
- Token limits
- Special features
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class LLMCapability:
    """Defines LLM capabilities."""

    provider: str
    supports_text: bool
    supports_images: bool
    supports_video: bool = False
    max_input_tokens: int = 128000
    max_output_tokens: int = 4096
    supports_streaming: bool = True

    def can_handle_text(self) -> bool:
        """Check if LLM can handle text input."""
        return self.supports_text

    def can_handle_images(self) -> bool:
        """Check if LLM can handle image input."""
        return self.supports_images

    def is_multimodal(self) -> bool:
        """Check if LLM is multi-modal (text + images)."""
        return self.supports_text and self.supports_images


# Provider Capability Registry
PROVIDER_CAPABILITIES: dict[str, LLMCapability] = {
    "deepseek": LLMCapability(
        provider="deepseek",
        supports_text=True,
        supports_images=False,  # DeepSeek is text-only
        max_input_tokens=128000,
        max_output_tokens=8192,
    ),
    "claude-cli": LLMCapability(
        provider="claude-cli",
        supports_text=True,
        supports_images=True,  # Claude CLI supports vision
        max_input_tokens=200000,
        max_output_tokens=8192,
    ),
    "openai": LLMCapability(
        provider="openai",
        supports_text=True,
        supports_images=True,  # GPT-4V supports vision
        max_input_tokens=128000,
        max_output_tokens=4096,
    ),
    "gemini": LLMCapability(
        provider="gemini",
        supports_text=True,
        supports_images=True,  # Gemini Pro Vision
        max_input_tokens=128000,
        max_output_tokens=8192,
    ),
}


def get_provider_capability(provider: str) -> LLMCapability:
    """
    Get capability info for a provider.

    Args:
        provider: Provider name ('deepseek', 'claude-cli', etc.)

    Returns:
        LLMCapability object

    Raises:
        ValueError: If provider not found
    """
    if provider not in PROVIDER_CAPABILITIES:
        raise ValueError(
            f"Unknown provider: {provider}. "
            f"Available: {list(PROVIDER_CAPABILITIES.keys())}"
        )

    return PROVIDER_CAPABILITIES[provider]
