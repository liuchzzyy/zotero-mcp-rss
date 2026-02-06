"""Example: Using OPML files to load multiple RSS feeds."""

import asyncio
from paper_feed.sources import RSSSource, parse_opml


async def example_single_feed():
    """Example: Fetch papers from a single RSS feed."""
    print("=== Example 1: Single RSS Feed ===")

    # Create RSS source for a single feed
    source = RSSSource(
        feed_url="http://export.arxiv.org/rss/cs.AI",
        source_name="arXiv CS.AI",
    )

    # Fetch up to 5 papers
    papers = await source.fetch_papers(limit=5)

    print(f"Fetched {len(papers)} papers from {source.source_name}")
    for paper in papers[:2]:  # Show first 2
        print(f"  - {paper.title}")
        print(f"    Authors: {', '.join(paper.authors[:3])}...")
        print()


async def example_opml_file():
    """Example: Load feeds from OPML file."""
    print("=== Example 2: Load from OPML File ===")

    # Parse OPML file to see what feeds are available
    feeds = parse_opml("feeds/RSS_official.opml")

    print(f"Found {len(feeds)} RSS feeds in OPML file")
    print("First 5 feeds:")
    for feed in feeds[:5]:
        print(f"  - {feed['title']}: {feed['url']}")
    print()


async def example_from_opml():
    """Example: Create RSS sources from OPML and fetch papers."""
    print("=== Example 3: Fetch from Multiple OPML Feeds ===")

    # Create RSS sources from OPML file
    sources = RSSSource.from_opml("feeds/RSS_official.opml")

    print(f"Created {len(sources)} RSS sources")

    # Fetch papers from first 2 sources only (for demo)
    for i, source in enumerate(sources[:2]):
        print(f"\nFetching from {source.source_name}...")
        try:
            papers = await source.fetch_papers(limit=3)
            print(f"  Got {len(papers)} papers")
            for paper in papers[:2]:  # Show first 2
                print(f"    - {paper.title[:80]}...")
        except Exception as e:
            print(f"  Error: {e}")


async def example_env_variable():
    """Example: Use environment variable to specify OPML file."""
    import os

    print("=== Example 4: Using Environment Variable ===")

    # Set environment variable (in practice, set this in your shell)
    # export PAPER_FEED_OPML=/path/to/your/feeds.opml
    opml_path = os.environ.get("PAPER_FEED_OPML", "feeds/RSS_official.opml")

    print(f"Using OPML file from: {opml_path}")

    # Create sources (will use env var if no path specified)
    sources = RSSSource.from_opml(opml_path)
    print(f"Loaded {len(sources)} sources")


async def main():
    """Run all examples."""
    await example_single_feed()
    await example_opml_file()
    await example_from_opml()
    await example_env_variable()


if __name__ == "__main__":
    asyncio.run(main())
