"""Keyword-based filter stage for paper filtering."""

from typing import List, Tuple
from paper_feed.core.models import PaperItem, FilterCriteria


class KeywordFilterStage:
    """Filter papers based on keyword, category, author, and date criteria.

    This stage applies multiple filtering rules:
    - Exclude keywords (OR logic): exclude if ANY excluded keyword present
    - Required keywords (AND logic): include only if ALL required keywords present
    - Categories (OR logic): include if ANY category matches
    - Authors (OR logic): include if ANY author matches
    - PDF availability: include only if PDF URL is present
    - Minimum date: include only if published on or after min_date
    """

    def is_applicable(self, criteria: FilterCriteria) -> bool:
        """Check if any keyword-based filters are active.

        Args:
            criteria: Filter criteria to check

        Returns:
            True if any keyword filter is specified
        """
        return bool(
            criteria.keywords
            or criteria.categories
            or criteria.exclude_keywords
            or criteria.authors
            or criteria.has_pdf
            or criteria.min_date is not None
        )

    async def filter(
        self, papers: List[PaperItem], criteria: FilterCriteria
    ) -> Tuple[List[PaperItem], List[str]]:
        """Apply keyword-based filtering to papers.

        Args:
            papers: List of papers to filter
            criteria: Filter criteria to apply

        Returns:
            Tuple of (filtered_papers, filter_messages)
        """
        if not self.is_applicable(criteria):
            return papers, []

        filtered = []
        messages = []

        for paper in papers:
            # Check exclude_keywords first (OR logic)
            if criteria.exclude_keywords and self._should_exclude(
                paper, criteria.exclude_keywords
            ):
                messages.append(
                    f"Excluded: '{paper.title[:50]}...' "
                    f"(matched exclude keyword)"
                )
                continue

            # Check required keywords (AND logic)
            if criteria.keywords and not self._matches_keywords(
                paper, criteria.keywords
            ):
                messages.append(
                    f"Filtered: '{paper.title[:50]}...' "
                    f"(missing required keywords: {criteria.keywords})"
                )
                continue

            # Check categories (OR logic)
            if criteria.categories and not self._matches_categories(
                paper, criteria.categories
            ):
                messages.append(
                    f"Filtered: '{paper.title[:50]}...' "
                    f"(no matching categories)"
                )
                continue

            # Check authors (OR logic)
            if criteria.authors and not self._matches_authors(
                paper, criteria.authors
            ):
                messages.append(
                    f"Filtered: '{paper.title[:50]}...' " f"(no matching authors)"
                )
                continue

            # Check PDF availability
            if criteria.has_pdf and not self._has_pdf(paper):
                messages.append(
                    f"Filtered: '{paper.title[:50]}...' " f"(no PDF available)"
                )
                continue

            # Check minimum date
            if criteria.min_date is not None and not self._meets_date_requirement(
                paper, criteria.min_date
            ):
                messages.append(
                    f"Filtered: '{paper.title[:50]}...' "
                    f"(published before {criteria.min_date})"
                )
                continue

            # Paper passed all filters
            filtered.append(paper)

        return filtered, messages

    def _matches_keywords(self, paper: PaperItem, keywords: List[str]) -> bool:
        """Check if paper matches ALL required keywords (AND logic).

        Args:
            paper: Paper to check
            keywords: List of required keywords

        Returns:
            True if ALL keywords are present in title or abstract
        """
        text = (paper.title + " " + paper.abstract).lower()
        return all(keyword.lower() in text for keyword in keywords)

    def _matches_categories(self, paper: PaperItem, categories: List[str]) -> bool:
        """Check if paper matches ANY category (OR logic).

        Args:
            paper: Paper to check
            categories: List of categories to match

        Returns:
            True if ANY category matches
        """
        paper_categories = [cat.lower() for cat in paper.categories]
        return any(
            any(cat.lower() in paper_cat for paper_cat in paper_categories)
            for cat in categories
        )

    def _matches_authors(self, paper: PaperItem, authors: List[str]) -> bool:
        """Check if paper matches ANY author (OR logic).

        Args:
            paper: Paper to check
            authors: List of author names to match

        Returns:
            True if ANY author matches
        """
        paper_authors = [author.lower() for author in paper.authors]
        return any(
            any(auth.lower() in paper_auth for paper_auth in paper_authors)
            for auth in authors
        )

    def _should_exclude(self, paper: PaperItem, exclude_keywords: List[str]) -> bool:
        """Check if paper should be excluded based on keywords.

        Args:
            paper: Paper to check
            exclude_keywords: Keywords that trigger exclusion

        Returns:
            True if ANY exclude keyword is present (OR logic)
        """
        text = (paper.title + " " + paper.abstract).lower()
        return any(keyword.lower() in text for keyword in exclude_keywords)

    def _has_pdf(self, paper: PaperItem) -> bool:
        """Check if paper has PDF available.

        Args:
            paper: Paper to check

        Returns:
            True if pdf_url is not None
        """
        return paper.pdf_url is not None

    def _meets_date_requirement(self, paper: PaperItem, min_date) -> bool:
        """Check if paper meets minimum date requirement.

        Args:
            paper: Paper to check
            min_date: Minimum publication date

        Returns:
            True if published on or after min_date, or if no date is set
        """
        if paper.published_date is None:
            # Papers without dates are included by default
            return True
        return paper.published_date >= min_date
