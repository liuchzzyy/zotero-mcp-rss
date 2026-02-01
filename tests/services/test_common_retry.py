"""Test retry utility."""

import pytest

from zotero_mcp.services.common.retry import async_retry_with_backoff


@pytest.mark.asyncio
async def test_retry_success_on_second_attempt():
    """Test that retry succeeds after one failure."""
    attempt_count = 0

    async def flaky_function():
        nonlocal attempt_count
        attempt_count += 1
        if attempt_count < 2:
            raise ValueError("Temporary failure")
        return "success"

    result = await async_retry_with_backoff(
        flaky_function,
        max_retries=3,
        base_delay=0.01,
    )
    assert result == "success"
    assert attempt_count == 2


@pytest.mark.asyncio
async def test_retry_fails_after_max_attempts():
    """Test that retry gives up after max attempts."""

    async def always_fail_function():
        raise ValueError("Permanent failure")

    with pytest.raises(ValueError, match="Permanent failure"):
        await async_retry_with_backoff(
            always_fail_function,
            max_retries=2,
            base_delay=0.01,
        )
