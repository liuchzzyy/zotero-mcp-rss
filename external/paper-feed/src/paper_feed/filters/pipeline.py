"""Filter pipeline for applying multiple filter stages."""

from typing import List, Any, Dict
from paper_feed.core.models import PaperItem, FilterCriteria, FilterResult
from paper_feed.filters.keyword import KeywordFilterStage


class FilterPipeline:
    """Pipeline for applying multiple filter stages to papers.

    The pipeline applies filter stages in sequence, with each stage
    processing the output of the previous stage. Currently supports:
    - KeywordFilterStage: keyword, category, author, date, PDF filters

    Future stages can include AI-powered filtering, etc.
    """

    def __init__(self, llm_client=None) -> None:
        """Initialize filter pipeline.

        Args:
            llm_client: Optional LLM client for AI-powered filtering
        """
        self.keyword_stage = KeywordFilterStage()
        self.llm_client = llm_client

    async def filter(
        self, papers: List[PaperItem], criteria: FilterCriteria
    ) -> FilterResult:
        """Apply filter pipeline to papers.

        Args:
            papers: List of papers to filter
            criteria: Filter criteria to apply

        Returns:
            FilterResult with filtered papers and statistics
        """
        total_count = len(papers)
        filter_stats: Dict[str, Any] = {}
        all_messages: List[str] = []

        # Stage 1: Keyword-based filtering
        if self.keyword_stage.is_applicable(criteria):
            papers, messages = await self.keyword_stage.filter(papers, criteria)
            all_messages.extend(messages)
            filter_stats["keyword_filter"] = {
                "input_count": total_count,
                "output_count": len(papers),
                "messages": messages,
            }
        else:
            filter_stats["keyword_filter"] = {
                "skipped": True,
                "reason": "No keyword criteria specified",
            }

        # Build final result
        passed_count = len(papers)
        rejected_count = total_count - passed_count

        return FilterResult(
            papers=papers,
            total_count=total_count,
            passed_count=passed_count,
            rejected_count=rejected_count,
            filter_stats=filter_stats,
        )
