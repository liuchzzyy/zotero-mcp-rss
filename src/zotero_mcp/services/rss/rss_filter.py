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
from concurrent.futures import ThreadPoolExecutor
import hashlib
import json
import logging
import os
from pathlib import Path
import re

from openai import OpenAI

from zotero_mcp.models.rss import RSSItem

logger = logging.getLogger(__name__)

KEYWORDS_CACHE_FILE = Path("RSS/keywords_cache.json")


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
        """
        Load research interests from environment variable or prompt file.

        Priority:
        1. RSS_PROMPT environment variable
        2. Explicitly provided prompt_file
        3. Default "RSS/prompt.txt"
        """
        # 1. Check environment variable
        env_prompt = os.getenv("RSS_PROMPT")
        if env_prompt and env_prompt.strip():
            logger.info(
                "Loaded research interests from RSS_PROMPT environment variable"
            )
            return env_prompt.strip()

        # 2. Check file
        path = Path(prompt_file or self.prompt_file or "RSS/prompt.txt")
        if not path.exists():
            raise FileNotFoundError(
                f"Research interest prompt not found. Set RSS_PROMPT env var or ensure file exists: {path}"
            )

        content = path.read_text(encoding="utf-8").strip()
        if not content:
            raise ValueError(f"Prompt file is empty: {path}")

        logger.info(f"Loaded research interests from file: {path}")
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
                temperature=0.0,  # Zero temperature for deterministic generation
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
                temperature=0.0,  # Zero temperature for deterministic selection
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

        # Calculate hash of the prompt for caching
        prompt_hash = hashlib.sha256(research_prompt.encode("utf-8")).hexdigest()

        # Check cache
        if KEYWORDS_CACHE_FILE.exists():
            try:
                cache_data = json.loads(KEYWORDS_CACHE_FILE.read_text(encoding="utf-8"))
                if cache_data.get("hash") == prompt_hash:
                    cached_keywords = cache_data.get("keywords", [])
                    if cached_keywords:
                        logger.info("Using cached keywords (prompt unchanged)")
                        self._keywords = cached_keywords
                        return cached_keywords
            except Exception as e:
                logger.warning(f"Failed to load keyword cache: {e}")

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

        # Save to cache
        try:
            KEYWORDS_CACHE_FILE.parent.mkdir(parents=True, exist_ok=True)
            cache_data = {
                "hash": prompt_hash,
                "keywords": best_keywords,
                "source": "env"
                if os.getenv("RSS_PROMPT")
                else str(prompt_file or self.prompt_file or "RSS/prompt.txt"),
            }
            KEYWORDS_CACHE_FILE.write_text(
                json.dumps(cache_data, indent=2), encoding="utf-8"
            )
            logger.info(f"Saved keywords to cache: {KEYWORDS_CACHE_FILE}")
        except Exception as e:
            logger.warning(f"Failed to save keyword cache: {e}")

        self._keywords = best_keywords
        logger.info(f"Final keywords: {best_keywords}")
        return best_keywords

    # Chemical element synonyms: name <-> symbol mappings
    CHEMICAL_SYNONYMS: dict[str, str] = {
        # Common battery materials
        "zinc": "zn",
        "zn": "zinc",
        "lithium": "li",
        "li": "lithium",
        "sodium": "na",
        "na": "sodium",
        "potassium": "k",
        "k": "potassium",
        "manganese": "mn",
        "mn": "manganese",
        "iron": "fe",
        "fe": "iron",
        "cobalt": "co",
        "co": "cobalt",
        "nickel": "ni",
        "ni": "nickel",
        "copper": "cu",
        "cu": "copper",
        "aluminum": "al",
        "al": "aluminum",
        "aluminium": "al",
        "titanium": "ti",
        "ti": "titanium",
        "vanadium": "v",
        "v": "vanadium",
        "oxygen": "o",
        "o": "oxygen",
        "sulfur": "s",
        "s": "sulfur",
        "sulphur": "s",
        "carbon": "c",
        "c": "carbon",
        "silicon": "si",
        "si": "silicon",
        "phosphorus": "p",
        "p": "phosphorus",
        "magnesium": "mg",
        "mg": "magnesium",
        "calcium": "ca",
        "ca": "calcium",
    }

    # Core scientific terms that should match independently
    # These terms are significant enough that their presence alone indicates relevance
    # Only include specialized technique/method terms, NOT generic material terms
    CORE_TERMS: set[str] = {
        # Characterization techniques (specialized, should match independently)
        "operando",
        "in-situ",
        "insitu",
        "in situ",
        "synchrotron",
        "xas",
        "xanes",
        "exafs",
        "xrd",
        # Note: Removed generic terms like "battery", "cathode", "anode"
        # as they cause false positives
    }

    def _expand_with_synonyms(self, text: str) -> str:
        """
        Expand text with chemical synonyms.

        For each word that has a synonym, add the synonym to the text.
        E.g., "zinc anode" -> "zinc zn anode"
        """
        words = text.lower().split()
        expanded_words = []
        for word in words:
            expanded_words.append(word)
            if word in self.CHEMICAL_SYNONYMS:
                expanded_words.append(self.CHEMICAL_SYNONYMS[word])
        return " ".join(expanded_words)

    def _normalize_text(self, text: str) -> str:
        """
        Normalize text for flexible matching.

        - Lowercase
        - Replace hyphens with spaces (Zn-MnO2 -> zn mno2)
        - Remove common punctuation
        - Normalize whitespace
        """
        text = text.lower()
        # Replace hyphens and underscores with spaces
        text = re.sub(r"[-_]", " ", text)
        # Remove punctuation except alphanumeric and spaces
        text = re.sub(r"[^\w\s]", " ", text)
        # Normalize whitespace
        text = re.sub(r"\s+", " ", text).strip()
        return text

    def _get_word_stem(self, word: str) -> str:
        """
        Get the stem of a single word.

        Simple stemming: remove common suffixes (s, es, ed, ing, ion, ies).
        """
        word = word.lower()
        # Simple suffix removal for common variations
        if word.endswith("ies") and len(word) > 3:
            return word[:-3] + "y"  # batteries -> battery
        elif word.endswith("es") and len(word) > 2:
            return word[:-2]  # watches -> watch
        elif word.endswith("s") and len(word) > 2 and not word.endswith("ss"):
            return word[:-1]  # items -> item
        elif word.endswith("ed") and len(word) > 2:
            return word[:-2]  # filtered -> filter
        elif word.endswith("ing") and len(word) > 3:
            return word[:-3]  # running -> run
        return word

    def _get_word_stems(self, text: str) -> set[str]:
        """
        Extract word stems for matching.

        Returns a set of stems (one per word, not both original and stem).
        """
        words = self._normalize_text(text).split()
        return {self._get_word_stem(word) for word in words}

    def _matches_keyword(self, title: str, keyword: str) -> bool:
        """
        Check if a title matches a keyword using flexible matching.

        Matching strategies:
        1. Exact substring match (after normalization)
        2. All words in keyword appear in title (word-level match)
        3. Stem-based matching for singular/plural variations
        4. Chemical synonym matching (zinc <-> Zn, etc.)
        5. Core term matching (operando, synchrotron, etc. match independently)
        """
        title_norm = self._normalize_text(title)
        kw_norm = self._normalize_text(keyword)

        # Strategy 1: Exact substring match
        if kw_norm in title_norm:
            return True

        # Strategy 2: All keyword words appear in title
        kw_words = set(kw_norm.split())
        title_words = set(title_norm.split())
        if kw_words and kw_words.issubset(title_words):
            return True

        # Strategy 3: Stem-based matching
        title_stems = self._get_word_stems(title)
        kw_stems = self._get_word_stems(keyword)
        if kw_stems and kw_stems.issubset(title_stems):
            return True

        # Strategy 4: Chemical synonym matching
        # Expand both title and keyword with synonyms, then check word overlap
        title_expanded = self._expand_with_synonyms(title_norm)
        kw_expanded = self._expand_with_synonyms(kw_norm)
        title_expanded_words = set(title_expanded.split())
        kw_expanded_words = set(kw_expanded.split())
        if kw_expanded_words and kw_expanded_words.issubset(title_expanded_words):
            return True

        # Strategy 5: Core term matching
        # If keyword contains a core term and that term appears in title, match
        kw_words_lower = {w.lower() for w in kw_norm.split()}
        title_words_lower = {w.lower() for w in title_norm.split()}
        for core_term in self.CORE_TERMS:
            core_term_normalized = self._normalize_text(core_term)
            core_words = set(core_term_normalized.split())
            # Check if the core term (or its words) is in the keyword
            if core_words.issubset(kw_words_lower) or core_term_normalized in kw_norm:
                # And if it also appears in the title
                if (
                    core_words.issubset(title_words_lower)
                    or core_term_normalized in title_norm
                ):
                    return True

        return False

    def filter_items(
        self,
        items: list[RSSItem],
        keywords: list[str] | None = None,
    ) -> tuple[list[RSSItem], list[RSSItem]]:
        """
        Filter RSS items by matching keywords against titles.

        Uses flexible matching that handles:
        - Case insensitivity
        - Hyphen/space variations (Zn-MnO2 vs Zn MnO2)
        - Singular/plural variations (battery vs batteries)
        - Word-level matching (all words in keyword appear in title)

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

        relevant = []
        irrelevant = []

        for item in items:
            # Check if any keyword matches the title
            is_relevant = any(self._matches_keyword(item.title, kw) for kw in kw_list)

            if is_relevant:
                relevant.append(item)
                logger.debug(f"  ✓ Matched: {item.title[:60]}...")
            else:
                irrelevant.append(item)
                logger.debug(f"  ✗ No match: {item.title[:60]}...")

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
