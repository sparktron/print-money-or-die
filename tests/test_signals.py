"""Tests for pmod.research.signals — technical indicators."""

import pytest

from pmod.research.signals import (
    compute_momentum_score,
    compute_rsi,
    compute_sma,
    compute_sma_crossover,
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
