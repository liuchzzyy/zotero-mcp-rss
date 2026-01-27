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


ANALYSIS_TEMPLATE = """你是一位专业的科研文献分析助手。请仔细阅读以下论文内容，并按照指定的结构进行深入、全面的分析。

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

请从以下维度快速评估这篇论文的质量和阅读价值：
- 论文发表期刊的影响力和领域地位
- 研究问题的重要性和前沿性
- 方法和结论的可靠性和创新性
- **结论**: 是否建议深入阅读？适合哪类研究者？

### 📚 前言及文献综述

#### 引用文献评估
- 引用的文献是否**最新**、**全面**？
- 以往文献有什么**不足**或**研究空白**？
- 作者如何定位本研究与前人工作的关系？

#### 聚焦问题
- 本研究**聚焦的核心科学问题**是什么？
- 研究的**逻辑思路**是什么？（从问题到方法到结论的完整链条）
- **可行性**：方法设计是否合理？技术路线是否可行？
- **可靠性**：实验设计是否严谨？对照组设置是否合理？

#### 选题新颖性
- 作者选题角度是否**新颖**？
- 这项研究有什么**科学价值**和**应用前景**？

### 💡 创新点

请从以下五个维度分析创新点：

#### 科学问题
- 提出了什么新的科学问题或研究视角？

#### 制备方法  
- 在材料制备或样品准备上有什么创新？
- 是否开发了新的合成路线或工艺？

#### 研究思路
- 研究设计有何独特之处？
- 是否采用了新的研究范式或策略？

#### 研究工具
- 使用了什么新的研究工具、技术或表征手段？
- 是否开发了新的测试方法或分析手段？

#### 研究理论
- 在理论层面有何贡献？
- 是否提出了新的模型、机制解释或理论框架？

---

### ✨ 笔记原子化

以下部分请**提取具体数据和关键信息**，便于后续引用：

#### 🔧 制备
- **原料/前驱体**: 列出关键材料和化学试剂
- **制备步骤**: 简要描述核心工艺流程（温度、时间、气氛等关键参数）
- **关键条件**: 影响结果的关键实验条件

#### 📊 表征
- **表征方法**: 使用了哪些表征技术？（XRD, SEM, TEM, XPS, BET等）
- **主要结果**: 每种表征方法得到的关键结论
- **数据支持**: 提取关键的数值数据（如晶格常数、粒径、比表面积等）

#### ⚡ 性能
- **性能指标**: 列出关键性能参数（如活性、选择性、稳定性、效率等）
- **具体数值**: 提取准确的数值和单位
- **对比基准**: 与文献报道或商业标准的对比结果
- **优势体现**: 性能优势体现在哪些方面？

#### 🔬 机制
- **机制假设**: 作者提出的反应机制或作用机理
- **证据支持**: 哪些实验数据或表征结果支持这一机制？
- **关键步骤**: 机制中的关键反应步骤或物理化学过程
- **争议点**: 是否存在其他可能的机制解释？

#### ✨ 理论
- **理论模型**: 使用或建立了什么理论模型？
- **计算方法**: 如涉及理论计算，使用了什么方法？（DFT, MD等）
- **理论预测**: 理论计算或模型预测了什么？
- **实验验证**: 理论预测是否得到实验验证？

---

### 🤔 思考

#### 优缺点分析
- **主要优点**: 这篇论文的突出贡献（至少3点）
- **主要缺点**: 存在的问题或不足（至少2点）
  - 实验设计的局限性
  - 数据完整性或说服力的欠缺
  - 机制解释的不足或争议

#### 疑问与争议
- 你对哪些内容产生了疑问？
- 哪些结论的可靠性需要进一步验证？
- 是否存在替代性解释或争议性观点？

#### 研究启发
- 这篇论文给你带来了什么研究启发？
- 可以如何改进或扩展这项工作？
- 对你自己的研究有什么借鉴意义？

---

### 🪸 重组分子化（深度批判性分析）

请对论文的逻辑严密性进行批判性评估：

#### 逻辑链完整性
- 围绕某一个实验现象的逻辑链是否**完整**、**令人信服**？
  - 从问题提出 → 实验设计 → 数据呈现 → 结论推导
  - 论证过程中是否存在**逻辑缺环**？
  - 是否存在**其他可能的解释角度**？

#### 数据可信度
- 实验数据的**可重复性**如何？
- 对照实验是否充分？
- 统计分析是否规范？
- 数据是否支持作者的结论？

#### 结论合理性
- 结论是否**超出数据的支持范围**？
- 是否存在**过度解读**或**过度推广**？
- 作者的推测与确凿证据之间的界限是否清晰？

---

## 输出格式要求

1. **保持客观、专业的分析风格**，避免主观臆断
2. **使用中文**撰写分析内容，关键术语可用英文标注
3. **提取具体数据**：数值、单位、条件等具体信息
4. **引用原文**：重要结论可以引用原文表述
5. **标注不确定性**：如果某个部分在论文中没有相关内容，请明确注明"本文未涉及"或"数据不足"
6. **保持结构完整**：即使某部分内容较少，也要保留标题结构

---

**分析目标**: 帮助研究者快速把握论文核心内容，提取可引用的关键信息，发现潜在问题和研究机会。
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
            # Use default template
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
