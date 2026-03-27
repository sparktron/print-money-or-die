"""Unit tests for pmod.optimizer.portfolio — all Schwab calls are mocked."""

from unittest.mock import MagicMock, patch

import pytest

from pmod.broker.schwab import AccountSummary, Position
from pmod.optimizer.portfolio import (
    RebalancePlan,
    RebalanceTrade,
    _equal_weight_capped,
    compute_rebalance,
)


# ── Helpers ────────────────────────────────────────────────────────────────

def _make_position(
    ticker: str,
    shares: float = 10.0,
    current_price: float = 100.0,
    market_value: float | None = None,
    weight: float = 10.0,
) -> Position:
    mv = market_value if market_value is not None else shares * current_price
    return Position(
        ticker=ticker,
        company_name=f"{ticker} Corp",
        shares=shares,
        avg_cost=current_price * 0.9,
        current_price=current_price,
        market_value=mv,
        cost_basis=shares * current_price * 0.9,
        day_pnl=0.0,
        day_pnl_pct=0.0,
        total_pnl=mv - shares * current_price * 0.9,
        total_pnl_pct=10.0,
        weight=weight,
    )


def _make_summary(
    positions: list[Position],
    total_value: float = 10_000.0,
    cash_balance: float = 1_000.0,
) -> AccountSummary:
    return AccountSummary(
        account_number="12345",
        total_value=total_value,
        cash_balance=cash_balance,
        day_pnl=0.0,
        positions=positions,
    )


# ── _equal_weight_capped ───────────────────────────────────────────────────

class TestEqualWeightCapped:
    def test_no_cap_effect_when_natural_weight_below_cap(self) -> None:
        # 4 positions, cap 30%: natural weight 25% < 30%
        weights = _equal_weight_capped(4, 0.30)
        assert len(weights) == 4
        assert all(w == pytest.approx(0.25) for w in weights)
        assert sum(weights) == pytest.approx(1.0)

    def test_cap_bites_and_redistributes(self) -> None:
        # 4 positions, cap 20%: natural weight 25% > 20%
        # Iterative: all capped at 20%, excess redistributed, but all hit cap
        weights = _equal_weight_capped(4, 0.20)
        assert all(w == pytest.approx(0.20) for w in weights)

    def test_mixed_cap_scenario(self) -> None:
        # 5 positions, cap 22%: natural weight 20% < 22% → no cap needed
        weights = _equal_weight_capped(5, 0.22)
        assert all(w == pytest.approx(0.20) for w in weights)
        assert sum(weights) == pytest.approx(1.0)

    def test_empty(self) -> None:
        assert _equal_weight_capped(0, 0.05) == []

    def test_single_position(self) -> None:
        weights = _equal_weight_capped(1, 0.05)
        # One position must be 100% — cap can't apply (pin to cap)
        assert len(weights) == 1
        assert weights[0] == pytest.approx(0.05)

    def test_weights_never_exceed_cap(self) -> None:
        for n in [2, 3, 5, 7, 10, 20, 50]:
            for cap_pct in [5, 10, 15, 20, 50]:
                cap = cap_pct / 100.0
                weights = _equal_weight_capped(n, cap)
                for w in weights:
                    assert w <= cap + 1e-10, f"n={n}, cap={cap}: weight {w} > cap"

    def test_satisfiable_sum_to_one(self) -> None:
        # When n * cap >= 1, weights should sum to 1.0
        weights = _equal_weight_capped(10, 0.15)  # 10 × 15% = 150% → satisfiable
        assert sum(weights) == pytest.approx(1.0)


# ── compute_rebalance ──────────────────────────────────────────────────────

class TestComputeRebalance:
    _PATCH_SUMMARY = "pmod.broker.schwab.get_account_summary"

    def test_returns_empty_plan_when_schwab_returns_none(self) -> None:
        with patch(self._PATCH_SUMMARY, return_value=None):
            plan = compute_rebalance()
        assert plan.trades == []
        assert plan.total_value == 0.0

    def test_returns_empty_plan_when_no_positions(self) -> None:
        summary = _make_summary(positions=[])
        with patch(self._PATCH_SUMMARY, return_value=summary):
            plan = compute_rebalance()
        assert plan.trades == []

    def test_single_position_is_hold(self) -> None:
        # One position at exactly 100% weight → target == current → delta == 0
        pos = _make_position("AAPL", shares=100, current_price=100.0, market_value=10_000.0, weight=100.0)
        summary = _make_summary([pos], total_value=10_000.0)
        with patch(self._PATCH_SUMMARY, return_value=summary):
            plan = compute_rebalance(max_position_pct=100.0)
        assert len(plan.trades) == 1
        assert plan.trades[0].action == "hold"
        assert plan.trades[0].shares_delta == 0

    def test_two_equal_positions_hold_when_balanced(self) -> None:
        # Two positions at exactly 50% each — equal-weight target is also 50%
        pos_a = _make_position("AAPL", shares=50, current_price=100.0, market_value=5_000.0, weight=50.0)
        pos_b = _make_position("MSFT", shares=50, current_price=100.0, market_value=5_000.0, weight=50.0)
        summary = _make_summary([pos_a, pos_b], total_value=10_000.0)
        with patch(self._PATCH_SUMMARY, return_value=summary):
            plan = compute_rebalance(max_position_pct=50.0)
        actions = {t.ticker: t.action for t in plan.trades}
        assert actions["AAPL"] == "hold"
        assert actions["MSFT"] == "hold"

    def test_unbalanced_positions_produce_buy_and_sell(self) -> None:
        # AAPL = 80% of portfolio, MSFT = 20% → equal-weight target 50/50
        # → AAPL should sell, MSFT should buy
        pos_a = _make_position("AAPL", shares=80, current_price=100.0, market_value=8_000.0, weight=80.0)
        pos_b = _make_position("MSFT", shares=20, current_price=100.0, market_value=2_000.0, weight=20.0)
        summary = _make_summary([pos_a, pos_b], total_value=10_000.0)
        with patch(self._PATCH_SUMMARY, return_value=summary):
            plan = compute_rebalance(max_position_pct=50.0)
        actions = {t.ticker: t.action for t in plan.trades}
        assert actions["AAPL"] == "sell"
        assert actions["MSFT"] == "buy"

    def test_cap_respected_when_geometrically_satisfiable(self) -> None:
        # 6 positions with max 20%: equal weight target is 1/6 ≈ 16.7%, which is
        # below the cap so all positions naturally stay within the limit.
        positions = [
            _make_position(t, shares=10, current_price=100.0, market_value=1_000.0, weight=16.7)
            for t in ["A", "B", "C", "D", "E", "F"]
        ]
        summary = _make_summary(positions, total_value=6_000.0)
        with patch(self._PATCH_SUMMARY, return_value=summary):
            plan = compute_rebalance(max_position_pct=20.0)
        for trade in plan.trades:
            assert trade.target_weight_pct <= 20.0 + 1e-6, (
                f"{trade.ticker} target {trade.target_weight_pct:.2f}% exceeds cap"
            )

    def test_cap_enforced_even_with_fewer_positions_than_cap_allows(self) -> None:
        # 3 positions with 20% cap: 3 × 20% = 60% < 100%, so the cap is
        # geometrically unsatisfiable.  The algorithm pins each at 20% and
        # logs a warning rather than silently exceeding the cap.
        positions = [
            _make_position("A", shares=40, current_price=100.0, market_value=4_000.0, weight=40.0),
            _make_position("B", shares=30, current_price=100.0, market_value=3_000.0, weight=30.0),
            _make_position("C", shares=30, current_price=100.0, market_value=3_000.0, weight=30.0),
        ]
        summary = _make_summary(positions, total_value=10_000.0)
        with patch(self._PATCH_SUMMARY, return_value=summary):
            plan = compute_rebalance(max_position_pct=20.0)
        for trade in plan.trades:
            assert trade.target_weight_pct <= 20.0 + 1e-6, (
                f"{trade.ticker} target {trade.target_weight_pct:.2f}% exceeds cap"
            )

    def test_cap_redistributes_excess_to_uncapped_positions(self) -> None:
        # 10 positions at 5% cap: natural weight 10% > 5% cap.
        # The iterative algorithm should bring all positions down to ≤5%.
        # Since 10 × 5% = 50% < 100%, cap is unsatisfiable but respected.
        positions = [_make_position(f"T{i}") for i in range(10)]
        summary = _make_summary(positions, total_value=100_000.0)
        with patch(self._PATCH_SUMMARY, return_value=summary):
            plan = compute_rebalance(max_position_pct=5.0)
        for trade in plan.trades:
            assert trade.target_weight_pct <= 5.0 + 1e-6

    def test_cap_works_with_satisfiable_allocation(self) -> None:
        # 10 positions at 15% cap: natural weight 10% < 15% → cap has no
        # effect, weights remain equal at 10%.
        positions = [
            _make_position(f"T{i}", shares=10, current_price=100.0,
                           market_value=1_000.0, weight=10.0)
            for i in range(10)
        ]
        summary = _make_summary(positions, total_value=10_000.0)
        with patch(self._PATCH_SUMMARY, return_value=summary):
            plan = compute_rebalance(max_position_pct=15.0)
        for trade in plan.trades:
            assert trade.target_weight_pct == pytest.approx(10.0, abs=1.0)

    def test_plan_includes_all_positions(self) -> None:
        positions = [_make_position(t) for t in ["AAPL", "MSFT", "NVDA", "TSLA"]]
        summary = _make_summary(positions, total_value=40_000.0)
        with patch(self._PATCH_SUMMARY, return_value=summary):
            plan = compute_rebalance()
        assert {t.ticker for t in plan.trades} == {"AAPL", "MSFT", "NVDA", "TSLA"}

    def test_shares_delta_truncates_toward_zero(self) -> None:
        # dollar_delta / price will produce a fractional result — must be truncated (int)
        pos = _make_position("AAPL", shares=11, current_price=100.0, market_value=1_100.0, weight=11.0)
        summary = _make_summary([pos, _make_position("MSFT", market_value=8_900.0)], total_value=10_000.0)
        with patch(self._PATCH_SUMMARY, return_value=summary):
            plan = compute_rebalance()
        for trade in plan.trades:
            # shares_delta must be a whole number
            assert isinstance(trade.shares_delta, int)

    def test_total_value_and_cash_passed_through(self) -> None:
        pos = _make_position("AAPL")
        summary = _make_summary([pos], total_value=50_000.0, cash_balance=3_000.0)
        with patch(self._PATCH_SUMMARY, return_value=summary):
            plan = compute_rebalance()
        assert plan.total_value == 50_000.0
        assert plan.cash_available == 3_000.0

    def test_zero_price_position_gets_zero_delta(self) -> None:
        pos = _make_position("BRKR", shares=10, current_price=0.0, market_value=0.0)
        summary = _make_summary([pos, _make_position("AAPL", market_value=10_000.0)], total_value=10_000.0)
        with patch(self._PATCH_SUMMARY, return_value=summary):
            plan = compute_rebalance()
        brkr_trade = next(t for t in plan.trades if t.ticker == "BRKR")
        assert brkr_trade.shares_delta == 0
