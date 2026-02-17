"""Shared pagination helpers for async offset-based scanning."""

from collections.abc import AsyncIterator, Awaitable, Callable
from typing import Any


async def iter_offset_batches(
    fetch_page: Callable[[int, int], Awaitable[list[Any]]],
    *,
    batch_size: int,
    start: int = 0,
) -> AsyncIterator[tuple[int, list[Any]]]:
    """
    Yield paged results using offset + limit semantics.

    Stops when:
    - page is empty, or
    - returned page size is smaller than requested batch_size.
    """
    offset = start
    while True:
        page = await fetch_page(offset, batch_size)
        if not page:
            return

        yield offset, page

        if len(page) < batch_size:
            return

        offset += batch_size
