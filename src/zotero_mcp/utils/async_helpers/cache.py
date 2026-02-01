"""
Response caching layer.
"""

from datetime import datetime, timedelta
from functools import wraps
import hashlib
import json
from typing import Any


class ResponseCache:
    """Simple in-memory cache for tool responses."""

    def __init__(self, ttl_seconds: int = 300):
        """
        Initialize cache.

        Args:
            ttl_seconds: Time-to-live for cache entries (default: 5 minutes)
        """
        self._cache: dict[str, tuple[Any, datetime]] = {}
        self._ttl = timedelta(seconds=ttl_seconds)

    def _make_key(self, tool_name: str, params: dict) -> str:
        """Generate cache key from tool name and parameters."""
        # Sort params for consistent hashing
        param_str = json.dumps(params, sort_keys=True, default=str)
        key_str = f"{tool_name}:{param_str}"
        return hashlib.md5(key_str.encode()).hexdigest()

    def get(self, tool_name: str, params: dict) -> Any | None:
        """Get cached response if available and not expired."""
        key = self._make_key(tool_name, params)

        if key in self._cache:
            response, timestamp = self._cache[key]

            # Check if expired
            if datetime.now() - timestamp < self._ttl:
                return response
            else:
                # Remove expired entry
                del self._cache[key]

        return None

    def set(self, tool_name: str, params: dict, response: Any) -> None:
        """Cache a response."""
        key = self._make_key(tool_name, params)
        self._cache[key] = (response, datetime.now())

    def clear(self) -> None:
        """Clear all cached entries."""
        self._cache.clear()

    def invalidate(self, tool_name: str, params: dict) -> None:
        """Invalidate specific cache entry."""
        key = self._make_key(tool_name, params)
        if key in self._cache:
            del self._cache[key]


# Global cache instance
_global_cache = ResponseCache(ttl_seconds=300)


def cached_tool(ttl_seconds: int | None = None):
    """
    Decorator to cache tool responses.

    Args:
        ttl_seconds: Override default TTL for this tool

    Example:
        @cached_tool(ttl_seconds=600)
        async def zotero_search(params: SearchItemsInput, ctx: Context):
            ...
    """

    def decorator(func):
        @wraps(func)
        async def wrapper(params, ctx, **kwargs):
            # Only cache read-only operations
            tool_name = func.__name__
            cache = _global_cache if ttl_seconds is None else ResponseCache(ttl_seconds)

            # Try to get from cache
            try:
                # params is a Pydantic model, use model_dump()
                params_dict: dict[str, Any] | str = params.model_dump()
            except AttributeError:
                # fallback if params is a dict (unlikely with FastMCP but possible)
                params_dict = params if isinstance(params, dict) else str(params)

            cached_response = cache.get(tool_name, params_dict)  # type: ignore[arg-type]
            if cached_response is not None:
                await ctx.info(f"Cache hit for {tool_name}")
                return cached_response

            # Call actual function
            response = await func(params, ctx, **kwargs)

            # Cache successful responses
            # Check for 'success' attribute (BaseResponse)
            if getattr(response, "success", True):
                cache.set(tool_name, params_dict, response)  # type: ignore[arg-type]

            return response

        return wrapper

    return decorator


# Alias for compatibility
tool_cache = _global_cache
