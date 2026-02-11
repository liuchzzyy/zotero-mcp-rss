"""
Response caching layer.
"""

from datetime import datetime, timedelta
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
