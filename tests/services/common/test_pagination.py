import pytest

from zotero_mcp.services.common.pagination import iter_offset_batches


@pytest.mark.asyncio
async def test_iter_offset_batches_stops_on_short_page():
    calls = []

    async def fetch_page(offset: int, limit: int):
        calls.append((offset, limit))
        if offset == 0:
            return [1, 2, 3]
        if offset == 3:
            return [4]
        return []

    pages = []
    async for offset, page in iter_offset_batches(fetch_page, batch_size=3):
        pages.append((offset, page))

    assert pages == [(0, [1, 2, 3]), (3, [4])]
    assert calls == [(0, 3), (3, 3)]
