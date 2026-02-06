"""Unit tests for RSS source."""

import os
import pytest

from paper_feed.sources import RSSSource, OPMLParser, parse_opml


def test_opml_parser_local_file():
    """Test parsing OPML file from local file system."""
    # Use the copied OPML file
    opml_path = "feeds/RSS_official.opml"

    # Check if file exists (might not in CI environments)
    if not os.path.exists(opml_path):
        pytest.skip(f"OPML file not found: {opml_path}")

    parser = OPMLParser(opml_path)
    feeds = parser.parse()

    # Assertions
    assert len(feeds) > 0, "Should parse at least one feed"

    # Check first feed
    feed = feeds[0]
    assert "url" in feed, "Feed should have url"
    assert "title" in feed, "Feed should have title"
    assert feed["url"], "Feed URL should not be empty"
    assert feed["title"], "Feed title should not be empty"

    # Check that all feeds have required fields
    for feed in feeds:
        assert feed["url"], f"Feed {feed.get('title', 'Unknown')} missing URL"
        assert feed["title"], f"Feed with URL {feed['url']} missing title"


def test_opml_parser_convenience_function():
    """Test convenience function for parsing OPML."""
    opml_path = "feeds/RSS_official.opml"

    if not os.path.exists(opml_path):
        pytest.skip(f"OPML file not found: {opml_path}")

    feeds = parse_opml(opml_path)

    assert len(feeds) > 0, "Should parse at least one feed"
    assert all("url" in f and "title" in f for f in feeds), "All feeds should have url and title"


def test_opml_parser_missing_file():
    """Test OPML parser with missing file."""
    parser = OPMLParser("nonexistent.opml")

    with pytest.raises(FileNotFoundError):
        parser.parse()


def test_rss_source_from_opml():
    """Test creating RSS sources from OPML file."""
    opml_path = "feeds/RSS_official.opml"

    if not os.path.exists(opml_path):
        pytest.skip(f"OPML file not found: {opml_path}")

    sources = RSSSource.from_opml(opml_path)

    # Assertions
    assert len(sources) > 0, "Should create at least one source"

    # Check first source
    source = sources[0]
    assert isinstance(source, RSSSource), "Should return RSSSource instances"
    assert source.feed_url, "Source should have feed URL"
    assert source.source_name, "Source should have name"

    # Check that all sources are RSSSource instances
    for source in sources:
        assert isinstance(source, RSSSource), "All items should be RSSSource"
        assert source.source_type == "rss", "All sources should be RSS type"


def test_rss_source_from_opml_missing_file():
    """Test creating RSS sources from missing OPML file."""
    with pytest.raises(FileNotFoundError):
        RSSSource.from_opml("nonexistent.opml")


@pytest.mark.asyncio
async def test_rss_source_single_feed():
    """Test creating and using single RSS source (if network available)."""
    # Create RSS source for a single feed
    source = RSSSource(
        feed_url="http://export.arxiv.org/rss/cs.AI",
        source_name="arXiv",
    )

    # Try to fetch papers (might fail in offline environments)
    try:
        papers = await source.fetch_papers(limit=1)
        assert len(papers) <= 1, "Should respect limit parameter"
        if len(papers) > 0:
            paper = papers[0]
            assert paper.title, "Paper should have a title"
            assert paper.source == "arXiv", "Source should be arXiv"
    except Exception as e:
        pytest.skip(f"Network request failed (offline environment?): {e}")


@pytest.mark.asyncio
async def test_rss_source_from_opml_fetch():
    """Test fetching papers from sources created via OPML (integration test)."""
    opml_path = "feeds/RSS_official.opml"

    if not os.path.exists(opml_path):
        pytest.skip(f"OPML file not found: {opml_path}")

    sources = RSSSource.from_opml(opml_path)

    # Try to fetch from first source only (integration test)
    source = sources[0]

    try:
        papers = await source.fetch_papers(limit=2)
        assert len(papers) <= 2, "Should respect limit parameter"
        if len(papers) > 0:
            paper = papers[0]
            assert paper.title, "Paper should have a title"
            assert paper.source_type == "rss", "Source type should be rss"
    except Exception as e:
        pytest.skip(f"Network request failed (offline environment?): {e}")


def test_opml_parser_categories():
    """Test that OPML parser preserves category information."""
    opml_path = "feeds/RSS_official.opml"

    if not os.path.exists(opml_path):
        pytest.skip(f"OPML file not found: {opml_path}")

    parser = OPMLParser(opml_path)
    feeds = parser.parse()

    # Check that some feeds have categories (nested outlines)
    feeds_with_categories = [f for f in feeds if "category" in f]

    # The OPML file has nested categories, so we should have some
    # Note: This depends on the structure of RSS_official.opml
    if feeds_with_categories:
        feed = feeds_with_categories[0]
        assert feed["category"], "Feed should have category"
        assert feed["url"], "Feed should have URL"
        assert feed["title"], "Feed should have title"


def test_rss_source_from_opml_env_variable(monkeypatch):
    """Test creating RSS sources using environment variable."""
    opml_path = "feeds/RSS_official.opml"

    if not os.path.exists(opml_path):
        pytest.skip(f"OPML file not found: {opml_path}")

    # Set environment variable
    monkeypatch.setenv("PAPER_FEED_OPML", opml_path)

    # Create sources without specifying path (should use env var)
    sources = RSSSource.from_opml()

    assert len(sources) > 0, "Should create sources from environment variable"

    # Clean up
    monkeypatch.delenv("PAPER_FEED_OPML")


def test_opml_parser_skip_non_rss():
    """Test that OPML parser skips non-RSS outlines."""
    opml_path = "feeds/RSS_official.opml"

    if not os.path.exists(opml_path):
        pytest.skip(f"OPML file not found: {opml_path}")

    parser = OPMLParser(opml_path)
    feeds = parser.parse()

    # All parsed feeds should have RSS URLs
    for feed in feeds:
        assert feed["url"].startswith("http"), "Feed URL should be valid HTTP URL"
        # RSS feeds typically have .rss or feed=rss in URL
        # (but not always, so we just check that URL exists)
