"""
LLM client for Zotero MCP.

Provides unified interface for calling LLM APIs (DeepSeek, OpenAI, Gemini)
to analyze research papers and generate structured notes.
"""

import asyncio
import logging
import os
from typing import Any, Literal

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


# -------------------- Analysis Template --------------------


ANALYSIS_TEMPLATE = """你是一位专业的科研文献分析助手。请仔细阅读以下论文内容，并按照指定的结构进行分析。

## 论文基本信息

- **标题**: {title}
- **作者**: {authors}
- **期刊**: {journal}
- **发表日期**: {date}
- **DOI**: {doi}

## 论文全文

{fulltext}

{annotations_section}

---

## 分析要求

请按照以下结构进行详细分析，以 Markdown 格式返回：

### 📖 粗读筛选
- 简要评估这篇论文的质量和阅读价值

### 📚 前言及文献综述
- **引用文献评估**: 引用的文献是否最新、全面？以往文献有什么不足？
- **聚焦问题**: 本研究聚焦的问题是什么？逻辑思路、可行性和可靠性如何？
- **选题新颖性**: 作者选题角度是否新颖？有什么价值？

### 💡 创新点
- **科学问题**: 提出了什么新的科学问题？
- **制备方法**: 在制备方法上有什么创新？
- **研究思路**: 研究思路有何独特之处？
- **研究工具**: 使用了什么新的研究工具或技术？
- **研究理论**: 在理论方面有何贡献？

### ✨ 笔记原子化

#### 🔧 制备
- 提取关键的制备方法和步骤

#### 📊 表征
- 总结使用的表征方法和主要结果

#### ⚡ 性能
- 提取关键性能数据和指标

#### 🔬 机制
- 阐述作者提出的机制解释

#### ✨ 理论
- 总结理论基础和模型

### 🤔 思考
- **优缺点**: 这篇论文有什么优点和不足？
- **疑问**: 你对哪些内容产生了疑问？
- **启发**: 这篇论文给你带来了什么研究启发？

---

**注意事项**:
1. 请保持客观、专业的分析风格
2. 使用中文撰写分析内容
3. 关键术语可以用英文标注
4. 如果某个部分在论文中没有相关内容，请注明"本文未涉及"
5. 尽量提取具体的数据、方法和结论
"""


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
        prompt = ANALYSIS_TEMPLATE.format(
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
        except ImportError:
            raise ImportError(
                "openai package not installed. Install with: pip install openai"
            )

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
        except ImportError:
            raise ImportError(
                "google-generativeai package not installed. "
                "Install with: pip install google-generativeai"
            )

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
    return LLMClient(provider=provider, model=model)


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
