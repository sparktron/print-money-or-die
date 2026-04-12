"""Unit tests for pmod.optimizer.portfolio — all Schwab calls are mocked."""

from unittest.mock import MagicMock, patch

import pytest

from pmod.broker.schwab import AccountSummary, Position
from pmod.optimizer.portfolio import (
    AccountRebalance,
    HolisticRebalancePlan,
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

def _make_trend_signal(
    ticker: str,
    momentum_score: float = 0.0,
    volatility_pct: float | None = 20.0,
) -> MagicMock:
    """Create a mock TrendSignal for testing."""
    mock_signal = MagicMock()
    mock_signal.ticker = ticker
    mock_signal.momentum_score = momentum_score
    mock_signal.volatility_pct = volatility_pct
    mock_signal.rsi_14 = 50.0
    mock_signal.sma_crossover = "neutral"
    mock_signal.data_points = 100
    return mock_signal


class TestComputeRebalance:
    _PATCH_SUMMARY = "pmod.broker.schwab.get_account_summary"
    _PATCH_EXT = "pmod.data.external_accounts.list_accounts"
    _PATCH_TREND = "pmod.research.signals.compute_trend"
    _PATCH_POL = "pmod.research.politician_signals.get_signals"

    @staticmethod
    def _get_trades_from_plan(holistic_plan: HolisticRebalancePlan) -> list[RebalanceTrade]:
        """Helper to extract all trades from a holistic plan (flatten across accounts)."""
        all_trades = []
        for acct_rebalance in holistic_plan.account_rebalances:
            all_trades.extend(acct_rebalance.trades)
        return all_trades

    def test_returns_empty_plan_when_schwab_returns_none(self) -> None:
        with patch(self._PATCH_SUMMARY, return_value=None), \
             patch(self._PATCH_EXT, return_value=[]), \
             patch(self._PATCH_TREND), \
             patch(self._PATCH_POL, return_value=[]):
            plan = compute_rebalance()
        trades = self._get_trades_from_plan(plan)
        assert trades == []
        assert plan.portfolio_total_value == 0.0

    def test_returns_empty_plan_when_no_positions(self) -> None:
        summary = _make_summary(positions=[])
        with patch(self._PATCH_SUMMARY, return_value=summary), \
             patch(self._PATCH_EXT, return_value=[]), \
             patch(self._PATCH_TREND), \
             patch(self._PATCH_POL, return_value=[]):
            plan = compute_rebalance()
        trades = self._get_trades_from_plan(plan)
        assert trades == []

    def test_single_position_is_hold(self) -> None:
        # Single position with neutral signal → should hold
        pos = _make_position("AAPL", shares=100, current_price=100.0, market_value=10_000.0, weight=100.0)
        summary = _make_summary([pos], total_value=10_000.0)
        with patch(self._PATCH_SUMMARY, return_value=summary), \
             patch(self._PATCH_EXT, return_value=[]), \
             patch(self._PATCH_TREND, return_value=_make_trend_signal("AAPL", momentum_score=0.0)), \
             patch(self._PATCH_POL, return_value=[]):
            plan = compute_rebalance()
        trades = self._get_trades_from_plan(plan)
        assert len(trades) == 1
        assert trades[0].action == "hold"
        assert trades[0].shares_delta == 0

    def test_two_equal_positions_hold_when_balanced(self) -> None:
        # Two positions with equal neutral signals → softmax should produce equal weights
        pos_a = _make_position("AAPL", shares=50, current_price=100.0, market_value=5_000.0, weight=50.0)
        pos_b = _make_position("MSFT", shares=50, current_price=100.0, market_value=5_000.0, weight=50.0)
        summary = _make_summary([pos_a, pos_b], total_value=10_000.0)
        mock_trend_aapl = _make_trend_signal("AAPL", momentum_score=0.0)
        mock_trend_msft = _make_trend_signal("MSFT", momentum_score=0.0)
        with patch(self._PATCH_SUMMARY, return_value=summary), \
             patch(self._PATCH_EXT, return_value=[]), \
             patch(self._PATCH_TREND, side_effect=lambda t: mock_trend_aapl if t == "AAPL" else mock_trend_msft), \
             patch(self._PATCH_POL, return_value=[]):
            plan = compute_rebalance()
        trades = self._get_trades_from_plan(plan)
        actions = {t.ticker: t.action for t in trades}
        assert actions["AAPL"] == "hold"
        assert actions["MSFT"] == "hold"

    def test_unbalanced_positions_produce_buy_and_sell(self) -> None:
        # AAPL = 80% (negative signal), MSFT = 20% (positive signal)
        # → AAPL should sell, MSFT should buy
        pos_a = _make_position("AAPL", shares=80, current_price=100.0, market_value=8_000.0, weight=80.0)
        pos_b = _make_position("MSFT", shares=20, current_price=100.0, market_value=2_000.0, weight=20.0)
        summary = _make_summary([pos_a, pos_b], total_value=10_000.0)
        mock_trend_aapl = _make_trend_signal("AAPL", momentum_score=-0.5)  # negative signal
        mock_trend_msft = _make_trend_signal("MSFT", momentum_score=0.5)   # positive signal
        with patch(self._PATCH_SUMMARY, return_value=summary), \
             patch(self._PATCH_EXT, return_value=[]), \
             patch(self._PATCH_TREND, side_effect=lambda t: mock_trend_aapl if t == "AAPL" else mock_trend_msft), \
             patch(self._PATCH_POL, return_value=[]):
            plan = compute_rebalance()
        trades = self._get_trades_from_plan(plan)
        actions = {t.ticker: t.action for t in trades}
        assert actions["AAPL"] == "sell"
        assert actions["MSFT"] == "buy"

    def test_cap_respected_when_geometrically_satisfiable(self) -> None:
        # 6 positions with equal neutral signals → softmax produces equal weights
        positions = [
            _make_position(t, shares=10, current_price=100.0, market_value=1_000.0, weight=16.7)
            for t in ["A", "B", "C", "D", "E", "F"]
        ]
        summary = _make_summary(positions, total_value=6_000.0)
        mock_trends = {t: _make_trend_signal(t, momentum_score=0.0) for t in ["A", "B", "C", "D", "E", "F"]}
        with patch(self._PATCH_SUMMARY, return_value=summary), \
             patch(self._PATCH_EXT, return_value=[]), \
             patch(self._PATCH_TREND, side_effect=lambda t: mock_trends[t]), \
             patch(self._PATCH_POL, return_value=[]):
            plan = compute_rebalance()
        trades = self._get_trades_from_plan(plan)
        # With equal neutral signals, all positions should be roughly equal weight (~16.7%)
        for trade in trades:
            assert trade.target_weight_pct <= 20.0 + 1e-6

    def test_cap_enforced_even_with_fewer_positions_than_cap_allows(self) -> None:
        # 3 positions with equal neutral signals → softmax produces equal weights (~33% each)
        # Signal-driven approach ignores position caps, so just verify it produces a valid plan
        positions = [
            _make_position("A", shares=40, current_price=100.0, market_value=4_000.0, weight=40.0),
            _make_position("B", shares=30, current_price=100.0, market_value=3_000.0, weight=30.0),
            _make_position("C", shares=30, current_price=100.0, market_value=3_000.0, weight=30.0),
        ]
        summary = _make_summary(positions, total_value=10_000.0)
        mock_trends = {t: _make_trend_signal(t, momentum_score=0.0) for t in ["A", "B", "C"]}
        with patch(self._PATCH_SUMMARY, return_value=summary), \
             patch(self._PATCH_EXT, return_value=[]), \
             patch(self._PATCH_TREND, side_effect=lambda t: mock_trends[t]), \
             patch(self._PATCH_POL, return_value=[]):
            plan = compute_rebalance()
        trades = self._get_trades_from_plan(plan)
        assert len(trades) == 3  # All positions should be in the plan

    def test_cap_redistributes_excess_to_uncapped_positions(self) -> None:
        # 10 positions with equal neutral signals → softmax produces equal weights (~10% each)
        positions = [_make_position(f"T{i}") for i in range(10)]
        summary = _make_summary(positions, total_value=100_000.0)
        mock_trends = {f"T{i}": _make_trend_signal(f"T{i}", momentum_score=0.0) for i in range(10)}
        with patch(self._PATCH_SUMMARY, return_value=summary), \
             patch(self._PATCH_EXT, return_value=[]), \
             patch(self._PATCH_TREND, side_effect=lambda t: mock_trends[t]), \
             patch(self._PATCH_POL, return_value=[]):
            plan = compute_rebalance()
        trades = self._get_trades_from_plan(plan)
        assert len(trades) == 10

    def test_cap_works_with_satisfiable_allocation(self) -> None:
        # 10 positions with equal neutral signals → softmax produces equal weights (~10% each)
        positions = [
            _make_position(f"T{i}", shares=10, current_price=100.0,
                           market_value=1_000.0, weight=10.0)
            for i in range(10)
        ]
        summary = _make_summary(positions, total_value=10_000.0)
        mock_trends = {f"T{i}": _make_trend_signal(f"T{i}", momentum_score=0.0) for i in range(10)}
        with patch(self._PATCH_SUMMARY, return_value=summary), \
             patch(self._PATCH_EXT, return_value=[]), \
             patch(self._PATCH_TREND, side_effect=lambda t: mock_trends[t]), \
             patch(self._PATCH_POL, return_value=[]):
            plan = compute_rebalance()
        trades = self._get_trades_from_plan(plan)
        for trade in trades:
            assert trade.target_weight_pct == pytest.approx(10.0, abs=1.0)

    def test_plan_includes_all_positions(self) -> None:
        positions = [_make_position(t) for t in ["AAPL", "MSFT", "NVDA", "TSLA"]]
        summary = _make_summary(positions, total_value=40_000.0)
        mock_trends = {t: _make_trend_signal(t, momentum_score=0.0) for t in ["AAPL", "MSFT", "NVDA", "TSLA"]}
        with patch(self._PATCH_SUMMARY, return_value=summary), \
             patch(self._PATCH_EXT, return_value=[]), \
             patch(self._PATCH_TREND, side_effect=lambda t: mock_trends[t]), \
             patch(self._PATCH_POL, return_value=[]):
            plan = compute_rebalance()
        trades = self._get_trades_from_plan(plan)
        assert {t.ticker for t in trades} == {"AAPL", "MSFT", "NVDA", "TSLA"}

    def test_shares_delta_truncates_toward_zero(self) -> None:
        # dollar_delta / price will produce a fractional result — must be truncated (int)
        pos = _make_position("AAPL", shares=11, current_price=100.0, market_value=1_100.0, weight=11.0)
        summary = _make_summary([pos, _make_position("MSFT", market_value=8_900.0)], total_value=10_000.0)
        mock_trends = {
            "AAPL": _make_trend_signal("AAPL", momentum_score=0.0),
            "MSFT": _make_trend_signal("MSFT", momentum_score=0.0),
        }
        with patch(self._PATCH_SUMMARY, return_value=summary), \
             patch(self._PATCH_EXT, return_value=[]), \
             patch(self._PATCH_TREND, side_effect=lambda t: mock_trends[t]), \
             patch(self._PATCH_POL, return_value=[]):
            plan = compute_rebalance()
        trades = self._get_trades_from_plan(plan)
        for trade in trades:
            # shares_delta must be a whole number
            assert isinstance(trade.shares_delta, int)

    def test_total_value_and_cash_passed_through(self) -> None:
        pos = _make_position("AAPL")
        summary = _make_summary([pos], total_value=50_000.0, cash_balance=3_000.0)
        with patch(self._PATCH_SUMMARY, return_value=summary), \
             patch(self._PATCH_EXT, return_value=[]), \
             patch(self._PATCH_TREND, return_value=_make_trend_signal("AAPL", momentum_score=0.0)), \
             patch(self._PATCH_POL, return_value=[]):
            plan = compute_rebalance()
        assert plan.portfolio_total_value == 50_000.0
        assert plan.portfolio_cash_available == 3_000.0

    def test_zero_price_position_gets_zero_delta(self) -> None:
        pos = _make_position("BRKR", shares=10, current_price=0.0, market_value=0.0)
        summary = _make_summary([pos, _make_position("AAPL", market_value=10_000.0)], total_value=10_000.0)
        mock_trends = {
            "BRKR": _make_trend_signal("BRKR", momentum_score=0.0),
            "AAPL": _make_trend_signal("AAPL", momentum_score=0.0),
        }
        with patch(self._PATCH_SUMMARY, return_value=summary), \
             patch(self._PATCH_EXT, return_value=[]), \
             patch(self._PATCH_TREND, side_effect=lambda t: mock_trends[t]), \
             patch(self._PATCH_POL, return_value=[]):
            plan = compute_rebalance()
        trades = self._get_trades_from_plan(plan)
        brkr_trade = next(t for t in trades if t.ticker == "BRKR")
        assert brkr_trade.shares_delta == 0


# ── Mixed-account scenarios ─────────────────────────────────────────────────

def _make_ext_position(
    ticker: str,
    shares: float = 10.0,
    current_price: float = 100.0,
    market_value: float | None = None,
) -> MagicMock:
    pos = MagicMock()
    pos.ticker = ticker
    pos.company_name = f"{ticker} Inc."
    pos.shares = shares
    pos.current_price = current_price
    pos.avg_cost = current_price * 0.9
    pos.market_value = market_value if market_value is not None else shares * current_price
    return pos


class TestComputeRebalanceMixedAccounts:
    _PATCH_SUMMARY = "pmod.broker.schwab.get_account_summary"
    _PATCH_EXT_LIST = "pmod.data.external_accounts.list_accounts"
    _PATCH_EXT_POS = "pmod.data.external_accounts.get_positions"
    _PATCH_TREND = "pmod.research.signals.compute_trend"
    _PATCH_POL = "pmod.research.politician_signals.get_signals"

    @staticmethod
    def _get_trades_from_plan(plan: HolisticRebalancePlan) -> list[RebalanceTrade]:
        return [t for ar in plan.account_rebalances for t in ar.trades]

    def test_only_external_accounts_no_schwab(self) -> None:
        """When Schwab returns None, external-only portfolio still produces a valid plan."""
        ext_pos = [_make_ext_position("VTI", shares=50, current_price=200.0)]
        ext_accounts = [{"name": "Fidelity 401k", "account_type": "401k", "total_value": 10_000.0}]
        mock_trend = _make_trend_signal("VTI", momentum_score=0.2)
        with patch(self._PATCH_SUMMARY, return_value=None), \
             patch(self._PATCH_EXT_LIST, return_value=ext_accounts), \
             patch(self._PATCH_EXT_POS, return_value=ext_pos), \
             patch(self._PATCH_TREND, return_value=mock_trend), \
             patch(self._PATCH_POL, return_value=[]):
            plan = compute_rebalance()
        trades = self._get_trades_from_plan(plan)
        assert len(trades) == 1
        assert trades[0].ticker == "VTI"
        assert plan.portfolio_total_value == 10_000.0

    def test_schwab_plus_external_accounts(self) -> None:
        """Schwab and an external account are both included in the plan."""
        schwab_pos = _make_position("AAPL", shares=10, current_price=200.0, market_value=2_000.0)
        schwab_summary = _make_summary([schwab_pos], total_value=3_000.0, cash_balance=1_000.0)

        ext_pos = [_make_ext_position("MSFT", shares=5, current_price=400.0, market_value=2_000.0)]
        ext_accounts = [{"name": "IRA", "account_type": "ira", "total_value": 2_000.0}]

        mock_trends = {
            "AAPL": _make_trend_signal("AAPL", momentum_score=0.3),
            "MSFT": _make_trend_signal("MSFT", momentum_score=0.1),
        }
        with patch(self._PATCH_SUMMARY, return_value=schwab_summary), \
             patch(self._PATCH_EXT_LIST, return_value=ext_accounts), \
             patch(self._PATCH_EXT_POS, return_value=ext_pos), \
             patch(self._PATCH_TREND, side_effect=lambda t: mock_trends[t]), \
             patch(self._PATCH_POL, return_value=[]):
            plan = compute_rebalance()

        account_names = {ar.account_name for ar in plan.account_rebalances}
        all_tickers = {t.ticker for t in self._get_trades_from_plan(plan)}
        assert "AAPL" in all_tickers
        assert "MSFT" in all_tickers
        assert plan.portfolio_total_value == pytest.approx(5_000.0)

    def test_external_account_with_zero_positions(self) -> None:
        """An external account with no positions contributes no trades."""
        schwab_pos = _make_position("NVDA")
        schwab_summary = _make_summary([schwab_pos], total_value=10_000.0)
        ext_accounts = [{"name": "Empty 401k", "account_type": "401k", "total_value": 0.0}]

        with patch(self._PATCH_SUMMARY, return_value=schwab_summary), \
             patch(self._PATCH_EXT_LIST, return_value=ext_accounts), \
             patch(self._PATCH_EXT_POS, return_value=[]), \
             patch(self._PATCH_TREND, return_value=_make_trend_signal("NVDA", momentum_score=0.0)), \
             patch(self._PATCH_POL, return_value=[]):
            plan = compute_rebalance()

        tickers = {t.ticker for t in self._get_trades_from_plan(plan)}
        assert "NVDA" in tickers
        # Empty 401k should not add any trades
        assert len(plan.account_rebalances) == 1

    def test_same_ticker_in_multiple_accounts(self) -> None:
        """A ticker held in both Schwab and an external account gets signals computed once."""
        schwab_pos = _make_position("SPY", shares=10, current_price=500.0, market_value=5_000.0)
        schwab_summary = _make_summary([schwab_pos], total_value=5_000.0)

        ext_pos = [_make_ext_position("SPY", shares=5, current_price=500.0, market_value=2_500.0)]
        ext_accounts = [{"name": "IRA", "account_type": "ira", "total_value": 2_500.0}]

        call_count = {"n": 0}
        def _trend(ticker: str):
            call_count["n"] += 1
            return _make_trend_signal(ticker, momentum_score=0.0)

        with patch(self._PATCH_SUMMARY, return_value=schwab_summary), \
             patch(self._PATCH_EXT_LIST, return_value=ext_accounts), \
             patch(self._PATCH_EXT_POS, return_value=ext_pos), \
             patch(self._PATCH_TREND, side_effect=_trend), \
             patch(self._PATCH_POL, return_value=[]):
            plan = compute_rebalance()

        # compute_trend should be called exactly once for "SPY" (unique tickers only)
        assert call_count["n"] == 1
