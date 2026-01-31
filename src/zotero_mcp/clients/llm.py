"""
LLM client for Zotero MCP.

Provides DeepSeek API integration for analyzing research papers
and generating structured notes.

Features:
- Automatic retry with exponential backoff
- Timeout control
- DeepSeek API (OpenAI-compatible)
"""

import asyncio
import logging
import os
from typing import Any

from zotero_mcp.utils.templates import get_analysis_template

logger = logging.getLogger(__name__)


# -------------------- Configuration --------------------


# API call configuration
MAX_RETRIES = 3
RETRY_DELAY = 1.0  # Base delay in seconds
REQUEST_TIMEOUT = 360  # Timeout in seconds (6 minutes for PDF analysis)


# -------------------- Provider Configuration --------------------


PROVIDER = "deepseek"

DEEPSEEK_CONFIG = {
    "base_url": "https://api.deepseek.com",
    "default_model": "deepseek-chat",
    "api_style": "openai",  # OpenAI-compatible API
    "env_key": "DEEPSEEK_API_KEY",
    "env_base_url": "DEEPSEEK_BASE_URL",
    "env_model": "DEEPSEEK_MODEL",
}


# -------------------- LLM Client --------------------


class LLMClient:
    """
    DeepSeek LLM client for paper analysis.

    Simplified to only support DeepSeek API (OpenAI-compatible).
    """

    def __init__(
        self,
        model: str | None = None,
        api_key: str | None = None,
        base_url: str | None = None,
    ):
        """
        Initialize DeepSeek LLM client.

        Args:
            model: Model name (overrides default)
            api_key: API key (overrides env var)
            base_url: Base URL (overrides env var)
        """
        # Get API key
        self.api_key = api_key or os.getenv(DEEPSEEK_CONFIG["env_key"])
        if not self.api_key:
            raise ValueError(
                f"DeepSeek API key not found. "
                f"Set {DEEPSEEK_CONFIG['env_key']} environment variable."
            )

        # Get base URL
        self.base_url = (
            base_url
            or os.getenv(DEEPSEEK_CONFIG["env_base_url"])
            or DEEPSEEK_CONFIG["base_url"]
        )

        # Get model
        self.model = (
            model
            or os.getenv(DEEPSEEK_CONFIG["env_model"])
            or DEEPSEEK_CONFIG["default_model"]
        )

        logger.info(
            f"Initialized DeepSeek LLM client: "
            f"model={self.model}, base_url={self.base_url}"
        )

        # Store provider for downstream use
        self.provider = "deepseek"

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
        Analyze a research paper and generate structured notes using DeepSeek API.

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

                annotations_section += f"**批注 {i}** ({ann_type})"
                if page:
                    annotations_section += f", 第{page}页"
                annotations_section += ":\n"

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

        # Call DeepSeek API with retry
        return await self._call_with_retry(self._call_deepseek_api, prompt)

    async def _call_with_retry(self, api_call, *args, **kwargs) -> str:
        """
        Call API with retry mechanism and exponential backoff.

        Args:
            api_call: The async function to call
            *args: Positional arguments for the API call
            **kwargs: Keyword arguments for the API call

        Returns:
            API response content

        Raises:
            Exception: If all retry attempts fail
        """
        last_exception = None

        for attempt in range(MAX_RETRIES):
            try:
                # Add timeout control
                result = await asyncio.wait_for(
                    api_call(*args, **kwargs),
                    timeout=REQUEST_TIMEOUT,
                )
                return result

            except asyncio.TimeoutError as e:
                last_exception = e
                logger.warning(
                    f"API call timeout (attempt {attempt + 1}/{MAX_RETRIES}): {e}"
                )

            except Exception as e:
                last_exception = e
                # Check if error is retryable
                if not self._is_retryable_error(e):
                    logger.error(f"Non-retryable error: {e}")
                    raise

                logger.warning(
                    f"API call failed (attempt {attempt + 1}/{MAX_RETRIES}): {e}"
                )

            # Don't sleep after last attempt
            if attempt < MAX_RETRIES - 1:
                # Exponential backoff
                delay = RETRY_DELAY * (2**attempt)
                logger.info(f"Retrying in {delay}s...")
                await asyncio.sleep(delay)

        # All retries failed
        logger.error(f"API call failed after {MAX_RETRIES} attempts")
        raise last_exception or Exception("API call failed")

    def _is_retryable_error(self, error: Exception) -> bool:
        """
        Determine if an error is retryable.

        Args:
            error: The exception to check

        Returns:
            True if error should be retried, False otherwise
        """
        error_str = str(error).lower()

        # Non-retryable errors
        non_retryable = [
            "authentication",
            "auth",
            "permission",
            "invalid",
            "key",
            "not found",
            "401",
            "403",
            "404",
        ]

        if any(keyword in error_str for keyword in non_retryable):
            return False

        # Retryable errors
        retryable = [
            "timeout",
            "connection",
            "network",
            "rate limit",
            "429",
            "502",
            "503",
            "504",
            "500",
        ]

        if any(keyword in error_str for keyword in retryable):
            return True

        # Default: retry on unknown errors
        return True

    async def _call_deepseek_api(self, prompt: str) -> str:
        """
        Call DeepSeek API (OpenAI-compatible).

        Args:
            prompt: The prompt to send

        Returns:
            Generated text response
        """
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
                max_tokens=8000,  # Increased for complete JSON output
            )

            content = response.choices[0].message.content
            if not content:
                raise ValueError("Empty response from DeepSeek API")

            return content

        except Exception as e:
            logger.error(f"DeepSeek API call failed: {e}")
            raise


# -------------------- Helper Functions --------------------


def get_llm_client(
    provider: str = "auto",
    model: str | None = None,
) -> Any:
    """
    Get configured LLM client.

    Args:
        provider: LLM provider ("deepseek", "claude-cli", "auto")
        model: Model name (optional)

    Returns:
        Configured LLMClient or CLILLMClient
    """
    if provider == "claude-cli":
        from zotero_mcp.clients.cli_llm import CLILLMClient

        return CLILLMClient(model=model)

    # Default: DeepSeek API client
    return LLMClient(model=model)


def is_llm_configured() -> bool:
    """Check if DeepSeek API is configured."""
    return bool(os.getenv(DEEPSEEK_CONFIG["env_key"]))


def get_configured_provider() -> str:
    """Get the configured provider (always returns 'deepseek')."""
    return "deepseek"
