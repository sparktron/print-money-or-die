"""Tests for pmod.utils.retry — backoff and rate-limiting."""

import time
from unittest.mock import MagicMock

import pytest

from pmod.utils.retry import RateLimiter, with_backoff


class TestWithBackoff:
    def test_succeeds_on_first_try(self) -> None:
        @with_backoff(max_retries=3, base_delay=0.01)
        def ok() -> str:
            return "done"

        assert ok() == "done"

    def test_retries_on_transient_failure(self) -> None:
        call_count = 0

        @with_backoff(max_retries=3, base_delay=0.01, retry_on=(ValueError,))
        def flaky() -> str:
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise ValueError("transient")
            return "recovered"

        assert flaky() == "recovered"
        assert call_count == 3

    def test_raises_after_max_retries(self) -> None:
        @with_backoff(max_retries=2, base_delay=0.01, retry_on=(RuntimeError,))
        def always_fails() -> None:
            raise RuntimeError("permanent")

        with pytest.raises(RuntimeError, match="permanent"):
            always_fails()

    def test_does_not_retry_unexpected_exceptions(self) -> None:
        call_count = 0

        @with_backoff(max_retries=3, base_delay=0.01, retry_on=(ValueError,))
        def wrong_error() -> None:
            nonlocal call_count
            call_count += 1
            raise TypeError("not retried")

        with pytest.raises(TypeError):
            wrong_error()
        assert call_count == 1

    def test_zero_retries_means_no_retry(self) -> None:
        call_count = 0

        @with_backoff(max_retries=0, base_delay=0.01)
        def once() -> None:
            nonlocal call_count
            call_count += 1
            raise RuntimeError("fail")

        with pytest.raises(RuntimeError):
            once()
        assert call_count == 1


class TestRateLimiter:
    def test_first_call_is_immediate(self) -> None:
        limiter = RateLimiter(calls_per_minute=600)  # 10/sec
        start = time.monotonic()
        limiter.acquire()
        elapsed = time.monotonic() - start
        assert elapsed < 0.05

    def test_enforces_minimum_interval(self) -> None:
        limiter = RateLimiter(calls_per_minute=60)  # 1/sec
        limiter.acquire()
        start = time.monotonic()
        limiter.acquire()
        elapsed = time.monotonic() - start
        assert elapsed >= 0.9  # should wait ~1 second

    def test_rejects_zero_rate(self) -> None:
        with pytest.raises(ValueError):
            RateLimiter(calls_per_minute=0)

    def test_rejects_negative_rate(self) -> None:
        with pytest.raises(ValueError):
            RateLimiter(calls_per_minute=-5)

    def test_calls_per_minute_property(self) -> None:
        limiter = RateLimiter(calls_per_minute=120)
        assert limiter.calls_per_minute == pytest.approx(120.0)
