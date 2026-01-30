"""
LLM client for Zotero MCP.

Provides unified interface for calling LLM APIs (DeepSeek, OpenAI, Gemini)
to analyze research papers and generate structured notes.
"""

import asyncio
import logging
import os
from typing import Any, Literal

from zotero_mcp.utils.templates import get_analysis_template

logger = logging.getLogger(__name__)


# -------------------- Provider Configuration --------------------


PROVIDERS = {
    "deepseek": {
        "base_url": "https://api.deepseek.com",
        "default_model": "deepseek-chat",
        "api_style": "openai",  # OpenAI-compatible API
        "env_key": "DEEPSEEK_API_KEY",
        "env_base_url": "DEEPSEEK_BASE_URL",
        "env_model": "DEEPSEEK_MODEL",
    },
    "openai": {
        "base_url": "https://api.openai.com/v1",
        "default_model": "gpt-4o-mini",
        "api_style": "openai",
        "env_key": "OPENAI_API_KEY",
        "env_base_url": "OPENAI_BASE_URL",
        "env_model": "OPENAI_MODEL",
    },
    "gemini": {
        "base_url": "https://generativelanguage.googleapis.com",
        "default_model": "gemini-1.5-flash",
        "api_style": "google",
        "env_key": "GEMINI_API_KEY",
        "env_base_url": "GEMINI_BASE_URL",
        "env_model": "GEMINI_MODEL",
    },
}


# -------------------- LLM Client --------------------


class LLMClient:
    """
    Unified LLM client supporting multiple providers.

    Supports:
    - DeepSeek (OpenAI-compatible)
    - OpenAI
    - Google Gemini
    """

    def __init__(
        self,
        provider: Literal["deepseek", "openai", "gemini", "auto"] = "auto",
        model: str | None = None,
        api_key: str | None = None,
        base_url: str | None = None,
    ):
        """
        Initialize LLM client.

        Args:
            provider: LLM provider to use
            model: Model name (overrides default)
            api_key: API key (overrides env var)
            base_url: Base URL (overrides default)
        """
        self.provider = self._select_provider(provider)
        self.config = PROVIDERS[self.provider]

        # Get API key
        self.api_key = api_key or os.getenv(self.config["env_key"])
        if not self.api_key:
            raise ValueError(
                f"{self.provider.upper()} API key not found. "
                f"Set {self.config['env_key']} environment variable."
            )

        # Get base URL
        self.base_url = (
            base_url
            or os.getenv(self.config["env_base_url"])
            or self.config["base_url"]
        )

        # Get model
        self.model = (
            model or os.getenv(self.config["env_model"]) or self.config["default_model"]
        )

        logger.info(
            f"Initialized LLM client: provider={self.provider}, "
            f"model={self.model}, base_url={self.base_url}"
        )

    def _select_provider(self, provider: str) -> str:
        """Auto-select provider if set to 'auto'."""
        if provider != "auto":
            if provider not in PROVIDERS:
                raise ValueError(
                    f"Unknown provider: {provider}. Available: {list(PROVIDERS.keys())}"
                )
            return provider

        # Auto-select based on available API keys
        for prov, config in PROVIDERS.items():
            if os.getenv(config["env_key"]):
                logger.info(f"Auto-selected provider: {prov}")
                return prov

        raise ValueError(
            "No LLM API key found. Set one of: "
            + ", ".join(config["env_key"] for config in PROVIDERS.values())
        )

    async def analyze_paper(
        self,
        title: str,
        authors: str | None,
        journal: str | None,
        date: str | None,
        doi: str | None,
        fulltext: str,
        annotations: list[dict[str, Any]] | None = None,
        template: str | None = None,
    ) -> str:
        """
        Analyze a research paper and generate structured notes.

        Args:
            title: Paper title
            authors: Authors
            journal: Journal name
            date: Publication date
            doi: DOI
            fulltext: Full text content
            annotations: PDF annotations
            template: Custom analysis template/instruction

        Returns:
            Markdown-formatted analysis
        """
        # Build annotations section
        annotations_section = ""
        if annotations:
            annotations_section = "\n## PDF 批注\n\n"
            for i, ann in enumerate(annotations, 1):
                ann_type = ann.get("type", "note")
                text = ann.get("text", "")
                comment = ann.get("comment", "")
                page = ann.get("page", "")

                annotations_section += f"**批注 {i}** ({ann_type}"
                if page:
                    annotations_section += f", 第{page}页"
                annotations_section += "):\n"

                if text:
                    annotations_section += f"> {text}\n"
                if comment:
                    annotations_section += f"*评论*: {comment}\n"
                annotations_section += "\n"

        # Build prompt
        if template:
            # Use custom template strategy
            prompt = f"""你是一位专业的科研文献分析助手。请仔细阅读以下论文内容，并按照提供的模板结构进行分析。

## 论文基本信息

- **标题**: {title or "未知"}
- **作者**: {authors or "未知"}
- **期刊**: {journal or "未知"}
- **发表日期**: {date or "未知"}
- **DOI**: {doi or "未知"}

## 论文全文

{fulltext[:50000]}

{annotations_section}

---

## 分析要求

请阅读上述内容，并严格按照以下模板格式生成分析报告：

{template}

**注意事项**:
1. 请保持客观、专业的分析风格
2. 使用中文撰写分析内容
3. 如果模板中有占位符(如 ${{...}})，请替换为实际分析内容
4. 尽量提取具体的数据、方法和结论
"""
        else:
            # Use default template from configuration
            template = get_analysis_template()
            prompt = template.format(
                title=title or "未知",
                authors=authors or "未知",
                journal=journal or "未知",
                date=date or "未知",
                doi=doi or "未知",
                fulltext=fulltext[:50000],  # Limit to ~50k chars
                annotations_section=annotations_section,
            )

        # Call LLM
        if self.config["api_style"] == "openai":
            return await self._call_openai_style(prompt)
        elif self.config["api_style"] == "google":
            return await self._call_google_style(prompt)
        else:
            raise ValueError(f"Unknown API style: {self.config['api_style']}")

    async def _call_openai_style(self, prompt: str) -> str:
        """Call OpenAI-compatible API (DeepSeek, OpenAI)."""
        try:
            from openai import AsyncOpenAI
        except ImportError as e:
            raise ImportError(
                "openai package not installed. Install with: pip install openai"
            ) from e

        client = AsyncOpenAI(api_key=self.api_key, base_url=self.base_url)

        try:
            response = await client.chat.completions.create(
                model=self.model,
                messages=[
                    {
                        "role": "system",
                        "content": "你是一位专业的科研文献分析助手，擅长深入分析学术论文并提取关键信息。",
                    },
                    {"role": "user", "content": prompt},
                ],
                temperature=0.7,
                max_tokens=4000,
            )

            return response.choices[0].message.content or ""

        except Exception as e:
            logger.error(f"LLM API call failed: {e}")
            raise

    async def _call_google_style(self, prompt: str) -> str:
        """Call Google Gemini API."""
        try:
            import google.generativeai as genai
        except ImportError as e:
            raise ImportError(
                "google-generativeai package not installed. "
                "Install with: pip install google-generativeai"
            ) from e

        genai.configure(api_key=self.api_key)

        model = genai.GenerativeModel(self.model)

        try:
            loop = asyncio.get_event_loop()
            response = await loop.run_in_executor(
                None, lambda: model.generate_content(prompt)
            )

            return response.text

        except Exception as e:
            logger.error(f"Gemini API call failed: {e}")
            raise


# -------------------- Helper Functions --------------------


def get_llm_client(
    provider: str = "auto",
    model: str | None = None,
) -> LLMClient:
    """
    Get configured LLM client.

    Args:
        provider: Provider name or "auto"
        model: Model name (optional)

    Returns:
        Configured LLMClient
    """
    return LLMClient(provider=provider, model=model)  # type: ignore[arg-type]


def is_llm_configured() -> bool:
    """Check if any LLM API is configured."""
    for config in PROVIDERS.values():
        if os.getenv(config["env_key"]):
            return True
    return False


def get_configured_provider() -> str | None:
    """Get the first configured provider."""
    for prov, config in PROVIDERS.items():
        if os.getenv(config["env_key"]):
            return prov
    return None
