"""Unit tests for filter pipeline and stages."""

import pytest
from datetime import date
from paper_feed.core.models import PaperItem, FilterCriteria
from paper_feed.filters import FilterPipeline


@pytest.fixture
def sample_papers():
    """Create sample papers for testing."""
    return [
        PaperItem(
            title="Machine Learning for Natural Language Processing",
            authors=["Alice Smith", "Bob Johnson"],
            abstract="This paper explores machine learning techniques for NLP.",
            published_date=date(2024, 1, 15),
            source="arXiv",
            source_type="rss",
            categories=["Computer Science", "AI"],
            pdf_url="https://example.com/paper1.pdf",
        ),
        PaperItem(
            title="Deep Learning in Computer Vision",
            authors=["Charlie Brown", "Alice Smith"],
            abstract="A comprehensive study of deep learning for vision tasks.",
            published_date=date(2024, 2, 20),
            source="arXiv",
            source_type="rss",
            categories=["Computer Science", "Vision"],
            pdf_url="https://example.com/paper2.pdf",
        ),
        PaperItem(
            title="Quantum Computing Applications",
            authors=["David Lee"],
            abstract="Exploring quantum computing applications in cryptography.",
            published_date=date(2023, 12, 10),
            source="Nature",
            source_type="rss",
            categories=["Physics", "Quantum"],
            pdf_url=None,
        ),
        PaperItem(
            title="Traditional Machine Learning Survey",
            authors=["Eve Wilson"],
            abstract="A survey of traditional machine learning algorithms.",
            published_date=date(2024, 3, 5),
            source="IEEE",
            source_type="rss",
            categories=["Computer Science"],
            pdf_url="https://example.com/paper4.pdf",
        ),
    ]


@pytest.mark.asyncio
async def test_keyword_filter_basic(sample_papers):
    """Test keyword filtering with AND logic."""
    criteria = FilterCriteria(keywords=["machine", "learning"])
    pipeline = FilterPipeline()

    result = await pipeline.filter(sample_papers, criteria)

    # Papers 1 and 4 contain both "machine" AND "learning"
    assert result.passed_count == 2
    assert result.rejected_count == 2
    assert len(result.papers) == 2
    assert "Machine Learning" in result.papers[0].title
    assert "Traditional Machine Learning" in result.papers[1].title


@pytest.mark.asyncio
async def test_exclude_keywords(sample_papers):
    """Test keyword exclusion."""
    criteria = FilterCriteria(exclude_keywords=["quantum"])
    pipeline = FilterPipeline()

    result = await pipeline.filter(sample_papers, criteria)

    # Should exclude paper 3 (contains "quantum")
    assert result.passed_count == 3
    assert result.rejected_count == 1
    assert "Quantum" not in result.papers[0].title
    assert "Quantum" not in result.papers[1].title
    assert "Quantum" not in result.papers[2].title


@pytest.mark.asyncio
async def test_category_filter(sample_papers):
    """Test category filtering with OR logic."""
    criteria = FilterCriteria(categories=["AI", "Vision"])
    pipeline = FilterPipeline()

    result = await pipeline.filter(sample_papers, criteria)

    # Papers 1 (AI) and 2 (Vision) should match
    assert result.passed_count == 2
    assert result.rejected_count == 2
    titles = [paper.title for paper in result.papers]
    assert "Machine Learning for Natural Language Processing" in titles  # Has AI category
    assert "Deep Learning in Computer Vision" in titles  # Has Vision category


@pytest.mark.asyncio
async def test_author_filter(sample_papers):
    """Test author filtering with OR logic."""
    criteria = FilterCriteria(authors=["Alice Smith", "David Lee"])
    pipeline = FilterPipeline()

    result = await pipeline.filter(sample_papers, criteria)

    # Papers 1 and 2 have Alice Smith, paper 3 has David Lee
    assert result.passed_count == 3
    assert result.rejected_count == 1
    # Check that Alice Smith appears in papers 1 and 2
    assert any("Alice Smith" in paper.authors for paper in result.papers)
    # Check that David Lee appears in paper 3
    assert any("David Lee" in paper.authors for paper in result.papers)


@pytest.mark.asyncio
async def test_has_pdf_filter(sample_papers):
    """Test PDF availability filter."""
    criteria = FilterCriteria(has_pdf=True)
    pipeline = FilterPipeline()

    result = await pipeline.filter(sample_papers, criteria)

    # Paper 3 has no PDF
    assert result.passed_count == 3
    assert result.rejected_count == 1
    assert all(paper.pdf_url is not None for paper in result.papers)


@pytest.mark.asyncio
async def test_date_filter(sample_papers):
    """Test minimum date filtering."""
    criteria = FilterCriteria(min_date=date(2024, 1, 1))
    pipeline = FilterPipeline()

    result = await pipeline.filter(sample_papers, criteria)

    # Paper 3 is from 2023, should be excluded
    assert result.passed_count == 3
    assert result.rejected_count == 1
    assert all(
        paper.published_date is None or paper.published_date >= date(2024, 1, 1)
        for paper in result.papers
    )


@pytest.mark.asyncio
async def test_combined_filters(sample_papers):
    """Test multiple filters combined."""
    criteria = FilterCriteria(
        keywords=["learning"],  # AND logic
        categories=["Computer Science"],  # OR logic
        has_pdf=True,
        min_date=date(2024, 1, 1),
    )
    pipeline = FilterPipeline()

    result = await pipeline.filter(sample_papers, criteria)

    # Should match papers with "learning" in title/abstract,
    # "Computer Science" category, has PDF, and published after 2024-01-01
    # Papers 1, 2, and 4 all match these criteria
    assert result.passed_count == 3
    assert result.rejected_count == 1
    assert all(paper.pdf_url is not None for paper in result.papers)
    assert all(
        "Computer Science" in paper.categories for paper in result.papers
    )


@pytest.mark.asyncio
async def test_filter_pipeline_stats(sample_papers):
    """Test FilterResult statistics."""
    criteria = FilterCriteria(keywords=["machine"])
    pipeline = FilterPipeline()

    result = await pipeline.filter(sample_papers, criteria)

    assert result.total_count == 4
    assert result.passed_count == 2
    assert result.rejected_count == 2
    assert "keyword_filter" in result.filter_stats
    assert result.filter_stats["keyword_filter"]["input_count"] == 4
    assert result.filter_stats["keyword_filter"]["output_count"] == 2


@pytest.mark.asyncio
async def test_empty_criteria(sample_papers):
    """Test that empty criteria returns all papers."""
    criteria = FilterCriteria()
    pipeline = FilterPipeline()

    result = await pipeline.filter(sample_papers, criteria)

    # No filters applied, should return all papers
    assert result.passed_count == 4
    assert result.rejected_count == 0
    assert len(result.papers) == 4


@pytest.mark.asyncio
async def test_no_matches(sample_papers):
    """Test filter that rejects all papers."""
    criteria = FilterCriteria(
        keywords=["nonexistent"], authors=["Unknown Author"]
    )
    pipeline = FilterPipeline()

    result = await pipeline.filter(sample_papers, criteria)

    # No papers should match
    assert result.passed_count == 0
    assert result.rejected_count == 4
    assert len(result.papers) == 0


@pytest.mark.asyncio
async def test_case_insensitive_filtering(sample_papers):
    """Test that filtering is case-insensitive."""
    # Mix of uppercase, lowercase, and mixed case
    criteria = FilterCriteria(
        keywords=["MACHINE", "LeArNiNg"],  # Uppercase and mixed case
        exclude_keywords=["QUANTUM"],  # Uppercase
    )
    pipeline = FilterPipeline()

    result = await pipeline.filter(sample_papers, criteria)

    # Should match papers with "machine learning" in any case
    # and exclude "quantum" paper
    assert result.passed_count == 2
    assert result.rejected_count == 2
    assert "Quantum" not in result.papers[0].title
    assert "Quantum" not in result.papers[1].title


@pytest.mark.asyncio
async def test_keyword_and_logic(sample_papers):
    """Test that keywords use AND logic (all must be present)."""
    criteria = FilterCriteria(keywords=["machine", "deep", "learning"])
    pipeline = FilterPipeline()

    result = await pipeline.filter(sample_papers, criteria)

    # Only papers with ALL three keywords should pass
    # Paper 1: "machine learning" (no "deep")
    # Paper 2: "deep learning" (no "machine")
    # Paper 4: "machine learning" (no "deep")
    assert result.passed_count == 0  # No paper has all three keywords
    assert result.rejected_count == 4


@pytest.mark.asyncio
async def test_category_or_logic(sample_papers):
    """Test that categories use OR logic (any can match)."""
    criteria = FilterCriteria(categories=["AI", "Quantum"])
    pipeline = FilterPipeline()

    result = await pipeline.filter(sample_papers, criteria)

    # Papers with AI OR Quantum category should pass
    # Paper 1: AI, Paper 2: neither, Paper 3: Quantum, Paper 4: neither
    assert result.passed_count == 2
    assert result.rejected_count == 2
