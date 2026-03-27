"""Shared retry/backoff and rate-limiting utilities for external API calls.

CLAUDE.md mandates:
  - Schwab API: 120 req/min
  - Polygon free tier: 5 req/min
  - Both with backoff on transient failures
"""
from __future__ import annotations

import functools
import threading
import time
from typing import Any, Callable, TypeVar

import structlog

log = structlog.get_logger()

F = TypeVar("F", bound=Callable[..., Any])


# ── Exponential backoff decorator ─────────────────────────────────────────

def with_backoff(
    max_retries: int = 3,
    base_delay: float = 1.0,
    max_delay: float = 30.0,
    retry_on: tuple[type[BaseException], ...] = (Exception,),
) -> Callable[[F], F]:
    """Retry a function with exponential backoff on transient failures.

    Args:
        max_retries:  Maximum number of retry attempts (0 = no retries).
        base_delay:   Initial delay in seconds before the first retry.
        max_delay:    Ceiling for the delay (prevents unreasonable waits).
        retry_on:     Tuple of exception types that trigger a retry.

    On final failure the original exception is re-raised.
    """
    def decorator(fn: F) -> F:
        @functools.wraps(fn)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            for attempt in range(max_retries + 1):
                try:
                    return fn(*args, **kwargs)
                except retry_on as exc:
                    if attempt == max_retries:
                        raise
                    delay = min(base_delay * (2 ** attempt), max_delay)
                    log.warning(
                        "retry_backoff",
                        fn=fn.__qualname__,
                        attempt=attempt + 1,
                        delay_s=round(delay, 2),
                        error=str(exc)[:120],
                    )
                    time.sleep(delay)
            # unreachable, but satisfies the type checker
            raise RuntimeError("retry loop exited unexpectedly")  # pragma: no cover
        return wrapper  # type: ignore[return-value]
    return decorator


# ── Token-bucket rate limiter ─────────────────────────────────────────────

class RateLimiter:
    """Thread-safe token-bucket rate limiter.

    Usage::

        _schwab_limiter = RateLimiter(calls_per_minute=120)

        def call_schwab():
            _schwab_limiter.acquire()  # blocks until a slot is available
            return httpx.get(...)
    """

    def __init__(self, calls_per_minute: int) -> None:
        if calls_per_minute <= 0:
            raise ValueError("calls_per_minute must be positive")
        self._interval = 60.0 / calls_per_minute
        self._lock = threading.Lock()
        self._last_call = 0.0

    def acquire(self) -> None:
        """Block until a rate-limit slot is available."""
        with self._lock:
            now = time.monotonic()
            wait = self._interval - (now - self._last_call)
            if wait > 0:
                time.sleep(wait)
            self._last_call = time.monotonic()

    @property
    def calls_per_minute(self) -> float:
        return 60.0 / self._interval


# ── Pre-configured limiters for external APIs ─────────────────────────────

schwab_limiter = RateLimiter(calls_per_minute=120)
polygon_limiter = RateLimiter(calls_per_minute=5)
