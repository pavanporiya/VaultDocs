"""
In-process sliding-window rate limiting for authentication endpoints.

Single-process limiter (sufficient for the current single-uvicorn deployment).
Keys are opaque strings; no user data is stored beyond transient counters.
"""

from __future__ import annotations

import time
from collections import deque
from typing import TYPE_CHECKING

from vaultdocs.core.settings import settings

if TYPE_CHECKING:
    from collections.abc import Iterator


class RateLimitError(Exception):
    """Raised when a rate limit is exceeded."""

    def __init__(self, message: str, retry_after_seconds: int) -> None:
        super().__init__(message)
        self.retry_after_seconds = max(1, retry_after_seconds)


class SlidingWindowRateLimiter:
    """
    Thread-safe-enough sliding window limiter (asyncio single-thread usage).
    """

    def __init__(self) -> None:
        self._events: dict[str, deque[float]] = {}

    def check(self, key: str, limit: int, window_seconds: int) -> None:
        """
        Record an attempt for `key` and raise RateLimitError when the caller
        exceeded `limit` attempts within the sliding `window_seconds` window.
        """
        if not settings.rate_limit_enabled:
            return

        now = time.monotonic()
        cutoff = now - window_seconds
        events = self._events.setdefault(key, deque())

        while events and events[0] <= cutoff:
            events.popleft()

        if len(events) >= limit:
            retry_after = int(events[0] + window_seconds - now) + 1
            raise RateLimitError(
                "Too many attempts. Please wait before trying again.",
                retry_after_seconds=retry_after,
            )

        events.append(now)

    def reset(self) -> None:
        """Clear all recorded attempts (used by tests)."""
        self._events.clear()

    def prune(self) -> None:
        """
        Drop empty windows to bound memory growth.
        """
        empty_keys = [key for key, events in self._events.items() if not events]
        for key in empty_keys:
            del self._events[key]

    def __iter__(self) -> Iterator[str]:
        return iter(list(self._events))


rate_limiter = SlidingWindowRateLimiter()
