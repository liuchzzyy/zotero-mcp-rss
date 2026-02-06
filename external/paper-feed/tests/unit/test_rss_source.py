"""Unit tests for RSS source."""

import pytest

from paper_feed.sources import RSSSource


@pytest.mark.asyncio
async def test_rss_source_fetch():
    """Test fetching papers from arXiv RSS feed."""
    # Create RSS source for arXiv cs.AI
    source = RSSSource(
        feed_url="http://export.arxiv.org/rss/cs.AI",
        source_name="arXiv",
    )

    # Fetch up to 5 papers
    papers = await source.fetch_papers(limit=5)

    # Assertions
    assert len(papers) > 0, "Should fetch at least one paper"
    assert len(papers) <= 5, "Should respect limit parameter"

    # Check first paper
    paper = papers[0]
    assert paper.title, "Paper should have a title"
    assert paper.source == "arXiv", "Source should be arXiv"
    assert paper.source_type == "rss", "Source type should be rss"


@pytest.mark.asyncio
async def test_rss_parser():
    """Test RSS parser extracts metadata correctly."""
    # Create RSS source for arXiv cs.AI
    source = RSSSource(
        feed_url="http://export.arxiv.org/rss/cs.AI",
        source_name="arXiv",
    )

    # Fetch 1 paper
    papers = await source.fetch_papers(limit=1)

    # Assertions
    assert len(papers) == 1, "Should fetch exactly one paper"

    paper = papers[0]
    assert paper.title, "Paper should have a title"
    assert paper.source_type == "rss", "Source type should be rss"

    # Check authors (arXiv usually has authors)
    # Note: Some entries might not have authors, so we just check it's a list
    assert isinstance(paper.authors, list), "Authors should be a list"

    # Check other fields
    assert paper.source == "arXiv", "Source should match"
    assert paper.source_type == "rss", "Source type should be 'rss'"
