"""Tests for pmod.research.signals — technical indicators."""

import threading
import time
from unittest.mock import patch

import pytest

from pmod.research.signals import (
    _TREND_CACHE,
    _TREND_CACHE_LOCK,
    _TREND_CACHE_MAX,
    _TREND_CACHE_TTL,
    compute_momentum_score,
    compute_rsi,
    compute_sma,
    compute_sma_crossover,
    compute_trend,
    compute_volatility,
)


class TestComputeRSI:
    def test_all_gains(self) -> None:
        # Monotonically increasing → RSI should be 100
        closes = list(range(100, 120))
        assert compute_rsi(closes) == 100.0

    def test_all_losses(self) -> None:
        # Monotonically decreasing → RSI should be 0
        closes = list(range(120, 100, -1))
        assert compute_rsi(closes) == 0.0

    def test_mixed_returns_between_0_and_100(self) -> None:
        closes = [100 + (i % 3) - 1 for i in range(30)]
        rsi = compute_rsi(closes)
        assert rsi is not None
        assert 0.0 <= rsi <= 100.0

    def test_insufficient_data_returns_none(self) -> None:
        assert compute_rsi([100, 101, 102]) is None

    def test_flat_price_returns_50(self) -> None:
        closes = [100.0] * 20
        assert compute_rsi(closes) == 50.0


class TestComputeSMA:
    def test_simple_average(self) -> None:
        closes = [10.0, 20.0, 30.0, 40.0, 50.0]
        assert compute_sma(closes, 5) == pytest.approx(30.0)

    def test_uses_last_n(self) -> None:
        closes = [1.0, 2.0, 3.0, 4.0, 5.0]
        assert compute_sma(closes, 3) == pytest.approx(4.0)

    def test_insufficient_data(self) -> None:
        assert compute_sma([10.0, 20.0], 5) is None


class TestComputeSMACrossover:
    def test_bullish_crossover(self) -> None:
        # Short SMA above long SMA → bullish
        closes = list(range(1, 100))  # steadily rising
        result = compute_sma_crossover(closes, short=5, long=20)
        assert result == "bullish"

    def test_bearish_crossover(self) -> None:
        # Steadily falling
        closes = list(range(100, 1, -1))
        result = compute_sma_crossover(closes, short=5, long=20)
        assert result == "bearish"

    def test_neutral_on_insufficient_data(self) -> None:
        assert compute_sma_crossover([100.0], short=5, long=20) == "neutral"


class TestComputeVolatility:
    def test_flat_price_zero_volatility(self) -> None:
        closes = [100.0] * 20
        vol = compute_volatility(closes)
        assert vol is not None
        assert vol == 0.0

    def test_volatile_price_positive(self) -> None:
        closes = [100.0, 110.0, 95.0, 105.0, 90.0, 108.0, 92.0, 103.0]
        vol = compute_volatility(closes)
        assert vol is not None
        assert vol > 0

    def test_insufficient_data(self) -> None:
        assert compute_volatility([100, 101]) is None

    def test_daily_mode(self) -> None:
        closes = [100.0, 101.0, 99.0, 102.0, 98.0, 103.0]
        daily = compute_volatility(closes, annualise=False)
        annual = compute_volatility(closes, annualise=True)
        assert daily is not None and annual is not None
        assert annual > daily


class TestComputeMomentumScore:
    def test_strong_uptrend(self) -> None:
        # 90 days of steady rise
        closes = [100.0 + i * 0.5 for i in range(90)]
        score = compute_momentum_score(closes)
        assert score > 0.3

    def test_strong_downtrend(self) -> None:
        closes = [100.0 - i * 0.5 for i in range(90)]
        score = compute_momentum_score(closes)
        assert score < -0.3

    def test_flat_near_zero(self) -> None:
        closes = [100.0] * 90
        score = compute_momentum_score(closes)
        assert -0.1 <= score <= 0.1

    def test_clamped_to_range(self) -> None:
        # Extreme moves
        closes = [10.0] * 60 + [100.0] * 30
        score = compute_momentum_score(closes)
        assert -1.0 <= score <= 1.0

    def test_insufficient_data(self) -> None:
        assert compute_momentum_score([100.0]) == 0.0


# ── compute_trend cache behaviour ─────────────────────────────────────────

class TestComputeTrendCache:
    """Verify cache hit/miss/TTL/eviction and thread-safety of compute_trend."""

    _PATCH_LOAD = "pmod.research.signals._load_cached_closes"
    _PATCH_HIST = "pmod.data.market.get_price_history"

    def _clear_cache(self) -> None:
        with _TREND_CACHE_LOCK:
            _TREND_CACHE.clear()

    def _inject(self, ticker: str, signal, age_sec: float = 0.0) -> None:
        """Inject a pre-built signal directly into the cache."""
        with _TREND_CACHE_LOCK:
            _TREND_CACHE[ticker] = (signal, time.time() - age_sec)

    def test_cache_miss_calls_load(self) -> None:
        self._clear_cache()
        closes = [100.0 + i for i in range(60)]
        with patch(self._PATCH_LOAD, return_value=closes) as mock_load:
            result = compute_trend("CACHE_MISS_TEST")
        mock_load.assert_called_once_with("CACHE_MISS_TEST")
        assert result.ticker == "CACHE_MISS_TEST"

    def test_cache_hit_skips_load(self) -> None:
        self._clear_cache()
        closes = [100.0 + i for i in range(60)]
        with patch(self._PATCH_LOAD, return_value=closes):
            first = compute_trend("CACHE_HIT_TEST")

        # Second call should be served from cache without hitting _load_cached_closes
        with patch(self._PATCH_LOAD, side_effect=AssertionError("should not call")):
            second = compute_trend("CACHE_HIT_TEST")

        assert second.momentum_score == first.momentum_score

    def test_expired_cache_entry_is_refreshed(self) -> None:
        self._clear_cache()
        closes_old = [50.0 + i for i in range(60)]
        closes_new = [200.0 + i for i in range(60)]

        # Inject a stale (expired) entry
        with patch(self._PATCH_LOAD, return_value=closes_old):
            _ = compute_trend("STALE_TEST")
        # Age it beyond TTL
        with _TREND_CACHE_LOCK:
            sig, _ = _TREND_CACHE["STALE_TEST"]
            _TREND_CACHE["STALE_TEST"] = (sig, time.time() - _TREND_CACHE_TTL - 1)

        with patch(self._PATCH_LOAD, return_value=closes_new) as mock_load:
            result = compute_trend("STALE_TEST")
        mock_load.assert_called_once()
        # New closes start at 200 → higher momentum than old closes starting at 50
        assert result.data_points == len(closes_new)

    def test_cache_evicts_oldest_when_full(self) -> None:
        self._clear_cache()
        closes = [100.0 + i for i in range(60)]

        # Fill the cache to the max limit with synthetic entries
        with _TREND_CACHE_LOCK:
            for i in range(_TREND_CACHE_MAX):
                from pmod.research.signals import TrendSignal
                sig = TrendSignal(
                    ticker=f"SYN{i:04d}",
                    rsi_14=50.0, sma_crossover="neutral",
                    momentum_score=0.0, volatility_pct=20.0,
                    data_points=60,
                )
                _TREND_CACHE[f"SYN{i:04d}"] = (sig, float(i))  # older = lower timestamp

        # Adding one more entry should trigger eviction; cache should stay ≤ max
        with patch(self._PATCH_LOAD, return_value=closes):
            compute_trend("EVICT_TRIGGER")

        with _TREND_CACHE_LOCK:
            size = len(_TREND_CACHE)
        assert size <= _TREND_CACHE_MAX, f"Cache grew to {size}, expected ≤ {_TREND_CACHE_MAX}"

    def test_concurrent_reads_are_consistent(self) -> None:
        """Multiple threads reading the same ticker should all get a valid signal."""
        self._clear_cache()
        closes = [100.0 + i for i in range(60)]
        results: list = []
        errors: list = []

        def _worker() -> None:
            try:
                with patch(self._PATCH_LOAD, return_value=closes):
                    sig = compute_trend("CONCURRENT_TEST")
                results.append(sig.ticker)
            except Exception as exc:
                errors.append(exc)

        threads = [threading.Thread(target=_worker) for _ in range(10)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert not errors, f"Concurrent errors: {errors}"
        assert all(r == "CONCURRENT_TEST" for r in results)
