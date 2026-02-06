"""Example usage of export adapters.

This demonstrates how to use the JSONAdapter and ZoteroAdapter
to export papers to different destinations.
"""

import asyncio
from pathlib import Path

from paper_feed import PaperItem, JSONAdapter
from paper_feed.adapters import ZoteroAdapter
from datetime import date


async def main():
    """Demonstrate adapter usage."""
    # Create sample papers
    papers = [
        PaperItem(
            title="Deep Learning for Computer Vision",
            authors=["Zhang San", "Li Si"],
            abstract="This paper explores deep learning techniques...",
            published_date=date(2024, 1, 15),
            doi="10.1234/dlcv2024",
            url="https://example.com/paper1",
            source="arXiv",
            source_type="rss",
            categories=["Computer Science", "AI"],
            tags=["deep learning", "computer vision"],
        ),
        PaperItem(
            title="Quantum Computing Advances",
            authors=["Wang Wu"],
            abstract="Recent breakthroughs in quantum computing...",
            published_date=date(2024, 2, 20),
            doi="10.1234/qc2024",
            pdf_url="https://example.com/paper2.pdf",
            source="Nature",
            source_type="email",
            categories=["Physics", "Quantum"],
            tags=["quantum computing", "algorithms"],
        ),
    ]

    # Example 1: Export to JSON (with metadata)
    print("Example 1: Export to JSON with metadata")
    json_adapter = JSONAdapter()
    result = await json_adapter.export(
        papers=papers,
        filepath="output/papers_with_metadata.json",
        include_metadata=True,
    )
    print(f"  Exported {result['count']} papers to {result['filepath']}")

    # Example 2: Export to JSON (without metadata)
    print("\nExample 2: Export to JSON without metadata")
    result = await json_adapter.export(
        papers=papers,
        filepath="output/papers_clean.json",
        include_metadata=False,
    )
    print(f"  Exported {result['count']} papers to {result['filepath']}")

    # Example 3: Export to Zotero (requires zotero-core)
    print("\nExample 3: Export to Zotero")
    try:
        zotero_adapter = ZoteroAdapter(
            library_id="your_library_id",
            api_key="your_api_key",
            library_type="user",
        )
        result = await zotero_adapter.export(
            papers=papers,
            collection_id="ABC123",  # Optional collection ID
        )
        print(f"  Successfully exported {result['success_count']}/{result['total']} papers")
        if result['failures']:
            print(f"  Failures: {result['failures']}")
    except ImportError as e:
        print(f"  Skipped: {e}")

    print("\n✅ All examples completed!")


if __name__ == "__main__":
    # Create output directory
    Path("output").mkdir(exist_ok=True)

    # Run examples
    asyncio.run(main())
