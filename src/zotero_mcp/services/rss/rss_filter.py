"""
RSS Filter Service - DeepSeek-powered keyword extraction and filtering.

This module provides AI-powered filtering of RSS feed items based on
research interests defined in a prompt file. It uses a two-stage
keyword extraction pipeline for efficiency:

1. Generate candidate keywords from research interest prompt
2. Select the best 10 keywords for matching
3. Filter articles by matching keywords against titles (local, fast)

Reference: https://github.com/liuchzzyy/RSS_Papers
"""

import asyncio
import json
import logging
import os
import re
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from openai import OpenAI

from zotero_mcp.models.rss import RSSItem

logger = logging.getLogger(__name__)


class RSSFilter:
    """Filter RSS items based on research interests using DeepSeek API."""

    def __init__(
        self,
        prompt_file: str | None = None,
        api_key: str | None = None,
        model: str = "deepseek-chat",
    ):
        """
        Initialize the RSS filter.

        Args:
            prompt_file: Path to the prompt.txt file with research interests
            api_key: DeepSeek API key (defaults to DEEPSEEK_API_KEY env var)
            model: DeepSeek model to use (default: deepseek-chat)
        """
        self.api_key = api_key or os.getenv("DEEPSEEK_API_KEY")
        self.model = model
        self.prompt_file = prompt_file
        self._client: OpenAI | None = None
        self._keywords: list[str] | None = None

    @property
    def client(self) -> OpenAI:
        """Lazy-initialize the OpenAI client for DeepSeek."""
        if self._client is None:
            if not self.api_key:
                raise ValueError(
                    "DeepSeek API key not found. Set DEEPSEEK_API_KEY environment variable."
                )
            self._client = OpenAI(
                api_key=self.api_key,
                base_url="https://api.deepseek.com/v1",
            )
        return self._client

    def load_prompt(self, prompt_file: str | None = None) -> str:
        """Load research interests from prompt file."""
        path = Path(prompt_file or self.prompt_file or "RSS/prompt.txt")
        if not path.exists():
            raise FileNotFoundError(f"Prompt file not found: {path}")

        content = path.read_text(encoding="utf-8").strip()
        if not content:
            raise ValueError(f"Prompt file is empty: {path}")

        logger.info(f"Loaded research interests from: {path}")
        return content

    def _generate_candidates(self, research_prompt: str) -> list[str]:
        """Generate candidate keywords from research interests."""
        system_prompt = """You are an expert scientific keyword extraction assistant.
Your task is to analyze the user's research interest prompt and extract a comprehensive list of 10 highly relevant English keywords.

Guidelines:
1. **Precision**: Use specific scientific terms (e.g., "Zn-MnO2 battery", "operando XAS") rather than broad categories.
2. **Coverage**: Include related techniques, materials, and methods.
3. **Variations**: Include common acronyms, chemical formulas, and synonym variations (e.g., "Li-ion" and "Lithium-ion").
4. **English Only**: All keywords must be in English, even if the prompt is in another language.

You MUST respond with ONLY a valid JSON object in this exact format:
{"keywords": ["keyword1", "keyword2", "keyword3", ...]}

Do not include any other text, explanation, or markdown formatting."""

        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {
                        "role": "user",
                        "content": f"Extract keywords from this research interest:\n\n{research_prompt}",
                    },
                ],
                temperature=0.7,  # Some creativity for diverse candidates
                max_tokens=500,
            )

            content = response.choices[0].message.content or ""
            return self._parse_keywords_json(content)

        except Exception as e:
            logger.error(f"Error generating candidate keywords: {e}")
            return []

    def _select_best_keywords(self, candidates: list[str]) -> list[str]:
        """Select the 10 best keywords from candidates."""
        if len(candidates) <= 10:
            return candidates

        unique_candidates = list(set(candidates))
        if len(unique_candidates) <= 10:
            return unique_candidates

        system_prompt = """You are a keyword selection expert.
From the provided list of candidate keywords, select the 10 BEST keywords that:
1. Are most specific and precise
2. Cover diverse aspects of the research area
3. Are most likely to match relevant paper titles

You MUST respond with ONLY a valid JSON object in this exact format:
{"keywords": ["keyword1", "keyword2", "keyword3", ...]}

Select exactly 10 keywords. Do not include any other text."""

        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {
                        "role": "user",
                        "content": f"Select the 10 best keywords from:\n{json.dumps(unique_candidates)}",
                    },
                ],
                temperature=0.3,  # Lower temperature for more consistent selection
                max_tokens=300,
            )

            content = response.choices[0].message.content or ""
            return self._parse_keywords_json(content)[:10]

        except Exception as e:
            logger.error(f"Error selecting best keywords: {e}")
            # Fallback: return first 10 unique candidates
            return unique_candidates[:10]

    def _parse_keywords_json(self, content: str) -> list[str]:
        """Parse keywords from JSON response with fallback handling."""
        content = content.strip()

        # Try direct JSON parse
        try:
            data = json.loads(content)
            if isinstance(data, dict) and "keywords" in data:
                return [str(k) for k in data["keywords"] if k]
        except json.JSONDecodeError:
            pass

        # Try extracting JSON from markdown code blocks
        json_match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", content, re.DOTALL)
        if json_match:
            try:
                data = json.loads(json_match.group(1))
                if isinstance(data, dict) and "keywords" in data:
                    return [str(k) for k in data["keywords"] if k]
            except json.JSONDecodeError:
                pass

        # Try extracting array from content
        array_match = re.search(r'\["[^"]+(?:",\s*"[^"]+)*"\]', content)
        if array_match:
            try:
                keywords = json.loads(array_match.group(0))
                return [str(k) for k in keywords if k]
            except json.JSONDecodeError:
                pass

        # Last resort: split by common delimiters
        logger.warning("Failed to parse JSON, falling back to text extraction")
        keywords = re.findall(r'"([^"]+)"', content)
        if keywords:
            return keywords

        return []

    async def extract_keywords(
        self, prompt_file: str | None = None, num_parallel_calls: int = 3
    ) -> list[str]:
        """
        Extract keywords from research interests using parallel API calls.

        This implements the two-stage extraction:
        1. Generate candidates with multiple parallel calls
        2. Select the best 10 keywords

        Args:
            prompt_file: Path to prompt file (optional, uses default if not set)
            num_parallel_calls: Number of parallel candidate generation calls

        Returns:
            List of 10 keywords for filtering
        """
        research_prompt = self.load_prompt(prompt_file)

        # Stage 1: Generate candidates in parallel
        logger.info(
            f"Generating candidate keywords with {num_parallel_calls} parallel calls..."
        )

        loop = asyncio.get_event_loop()
        with ThreadPoolExecutor(max_workers=num_parallel_calls) as executor:
            futures = [
                loop.run_in_executor(
                    executor, self._generate_candidates, research_prompt
                )
                for _ in range(num_parallel_calls)
            ]
            results = await asyncio.gather(*futures)

        # Flatten and deduplicate candidates
        all_candidates = []
        for result in results:
            all_candidates.extend(result)

        unique_candidates = list(set(all_candidates))
        logger.info(f"Generated {len(unique_candidates)} unique candidate keywords")

        if not unique_candidates:
            logger.error("No keywords generated. Check API key and prompt file.")
            return []

        # Stage 2: Select best keywords
        logger.info("Selecting best 10 keywords...")
        best_keywords = await asyncio.to_thread(
            self._select_best_keywords, unique_candidates
        )

        self._keywords = best_keywords
        logger.info(f"Final keywords: {best_keywords}")
        return best_keywords

    def filter_items(
        self,
        items: list[RSSItem],
        keywords: list[str] | None = None,
    ) -> tuple[list[RSSItem], list[RSSItem]]:
        """
        Filter RSS items by matching keywords against titles.

        Args:
            items: List of RSSItem to filter
            keywords: Keywords to match (uses cached if not provided)

        Returns:
            Tuple of (relevant_items, irrelevant_items)
        """
        kw_list = keywords or self._keywords
        if not kw_list:
            raise ValueError(
                "No keywords available. Call extract_keywords() first or provide keywords."
            )

        # Prepare keywords for case-insensitive matching
        kw_lower = [kw.lower() for kw in kw_list]

        relevant = []
        irrelevant = []

        for item in items:
            title_lower = item.title.lower()
            # Check if any keyword is in the title
            is_relevant = any(kw in title_lower for kw in kw_lower)

            if is_relevant:
                relevant.append(item)
            else:
                irrelevant.append(item)

        logger.info(
            f"Filtering complete: {len(relevant)} relevant, {len(irrelevant)} irrelevant"
        )
        return relevant, irrelevant

    async def filter_with_keywords(
        self,
        items: list[RSSItem],
        prompt_file: str | None = None,
    ) -> tuple[list[RSSItem], list[RSSItem], list[str]]:
        """
        Full pipeline: extract keywords and filter items.

        Args:
            items: List of RSSItem to filter
            prompt_file: Path to prompt file (optional)

        Returns:
            Tuple of (relevant_items, irrelevant_items, keywords_used)
        """
        keywords = await self.extract_keywords(prompt_file)
        if not keywords:
            logger.warning("No keywords extracted. Returning all items as irrelevant.")
            return [], items, []

        relevant, irrelevant = self.filter_items(items, keywords)
        return relevant, irrelevant, keywords
