"""Generic retry utility with exponential backoff."""

import asyncio
from collections.abc import Awaitable, Callable
import logging
from typing import TypeVar

T = TypeVar("T")

logger = logging.getLogger(__name__)


async def async_retry_with_backoff(
    func: Callable[[], Awaitable[T]],
    *,
    max_retries: int = 3,
    base_delay: float = 2.0,
    description: str = "Operation",
) -> T:
    """
    Execute an async function with retry and exponential backoff.

    Args:
        func: Async function to execute
        max_retries: Maximum number of retry attempts
        base_delay: Base delay in seconds (will be doubled each retry)
        description: Description for logging

    Returns:
        Result from func

    Raises:
        Last exception if all retries fail
    """
    last_exception = None

    for attempt in range(max_retries):
        try:
            return await func()
        except Exception as e:
            last_exception = e
            error_msg = str(e).lower()

            # Check if error is retryable
            is_retryable = any(
                keyword in error_msg
                for keyword in [
                    "timed out",
                    "timeout",
                    "503",
                    "502",
                    "504",
                    "429",  # Rate limit
                    "connection",
                    "temporary",
                    "reset",  # Connection reset
                ]
            )

            if not is_retryable or attempt == max_retries - 1:
                raise

            delay = base_delay * (2**attempt)
            logger.warning(
                f"  ↻ {description} failed (attempt {attempt + 1}/{max_retries}): "
                f"{e}. Retrying in {delay:.0f}s..."
            )
            await asyncio.sleep(delay)

    # Should never reach here, but satisfies type checker
    if last_exception:
        raise last_exception
    raise RuntimeError(f"{description} failed after {max_retries} retries")
