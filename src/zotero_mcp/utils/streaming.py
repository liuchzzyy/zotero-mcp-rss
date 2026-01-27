"""
Streaming response utilities.
"""

from collections.abc import AsyncIterator
from typing import Any, TypeVar

from zotero_mcp.models.common import SearchResultItem
from zotero_mcp.services import get_data_service

T = TypeVar("T")


async def stream_search_results(
    service: Any, query: str, batch_size: int = 50
) -> AsyncIterator[list[SearchResultItem]]:
    """
    Stream search results in batches.

    Args:
        service: Data access service
        query: Search query
        batch_size: Number of items per batch

    Yields:
        Batches of search results
    """
    offset = 0

    while True:
        # Fetch batch
        results = await service.search_items(
            query=query,
            limit=batch_size,
            offset=offset,
        )

        if not results:
            break

        # Convert to SearchResultItem
        items = [
            SearchResultItem(
                key=r.key,
                title=r.title,
                authors=r.authors,
                date=r.date,
                item_type=r.item_type,
                abstract=r.abstract,
                tags=r.tags or [],
            )
            for r in results
        ]

        # Yield batch
        yield items

        # Check if more results available
        if len(results) < batch_size:
            break

        offset += batch_size


# Usage example
async def process_all_results(query: str):
    """Process large result set with streaming."""
    service = get_data_service()
    total_processed = 0

    async for batch in stream_search_results(service, query):
        # Process each batch
        for _ in batch:
            # Do something with item
            # process_item(item)
            pass
        total_processed += len(batch)
        print(f"Processed {total_processed} items...")
