"""Tests for politician trade tracking and signal generation."""

from datetime import datetime, timedelta
from unittest.mock import MagicMock, patch

import pytest

from pmod.data.politician_trades import (
    _normalize_trade_type,
    _parse_amount,
    _parse_date,
    _parse_filing_row,
    get_top_tickers,
)
from pmod.research.politician_signals import (
    _amount_weight,
    _build_rationale,
    _recency_multiplier,
    _score_to_signal,
    _aggregate_trades,
)


# ── Parsing helpers ────────────────────────────────────────────────────────

class TestParseDate:
    def test_iso_format(self) -> None:
        result = _parse_date("2024-03-15")
        assert result == datetime(2024, 3, 15)

    def test_us_format(self) -> None:
        result = _parse_date("03/15/2024")
        assert result == datetime(2024, 3, 15)

    def test_none_input(self) -> None:
        assert _parse_date(None) is None

    def test_invalid_string(self) -> None:
        assert _parse_date("not-a-date") is None

    def test_empty_string(self) -> None:
        assert _parse_date("") is None


class TestParseAmount:
    def test_known_range(self) -> None:
        low, high = _parse_amount("$1,001 - $15,000")
        assert low == 1_001
        assert high == 15_000

    def test_large_range(self) -> None:
        low, high = _parse_amount("$1,000,001 - $5,000,000")
        assert low == 1_000_001
        assert high == 5_000_000

    def test_unknown_range(self) -> None:
        low, high = _parse_amount("Some weird amount")
        assert low is None
        assert high is None

    def test_none_input(self) -> None:
        low, high = _parse_amount(None)
        assert low is None
        assert high is None


class TestNormalizeTradeType:
    def test_purchase(self) -> None:
        assert _normalize_trade_type("Purchase") == "purchase"
        assert _normalize_trade_type("purchase") == "purchase"

    def test_sale(self) -> None:
        assert _normalize_trade_type("Sale") == "sale"
        assert _normalize_trade_type("SALE") == "sale"

    def test_sale_partial(self) -> None:
        assert _normalize_trade_type("Sale (Partial)") == "sale_partial"

    def test_exchange(self) -> None:
        assert _normalize_trade_type("Exchange") == "exchange"

    def test_unknown(self) -> None:
        assert _normalize_trade_type("Transfer") is None


class TestParseFilingRow:
    """Tests for _parse_filing_row using the actual 5-field Senate EFD row format.

    Row layout (per the function docstring):
      [0] first_name   e.g. "David H"
      [1] last_name    e.g. "McCormick"
      [2] full_name    e.g. "McCormick, David H. (Senator)"  — plain text used for name
      [3] link_cell    HTML anchor containing the PTR report href
      [4] date         plain text "MM/DD/YYYY"
    """

    def _html_row(
        self,
        full_name: str = "Smith, John (Senator)",
        date: str = "03/15/2024",
        url_path: str = "/search/view/ptr/abc123/",
    ) -> list[str]:
        return [
            "John",                                      # [0] first_name
            "Smith",                                     # [1] last_name
            full_name,                                   # [2] full_name (plain text)
            f'<a href="{url_path}">View Report</a>',    # [3] link_cell with href
            date,                                        # [4] date (plain text)
        ]

    def test_extracts_name_and_url(self) -> None:
        row = self._html_row()
        result = _parse_filing_row(row)
        assert result is not None
        name, _, url = result
        assert name == "Smith, John (Senator)"
        assert "abc123" in url

    def test_relative_url_becomes_absolute(self) -> None:
        row = self._html_row(url_path="/search/view/ptr/abc/")
        result = _parse_filing_row(row)
        assert result is not None
        _, _, url = result
        assert url.startswith("https://efdsearch.senate.gov")

    def test_extracts_date_string(self) -> None:
        row = self._html_row(date="01/31/2025")
        result = _parse_filing_row(row)
        assert result is not None
        _, date_str, _ = result
        assert date_str == "01/31/2025"

    def test_empty_row_returns_none(self) -> None:
        assert _parse_filing_row([]) is None
        assert _parse_filing_row(["cell"]) is None

    def test_row_without_href_returns_none(self) -> None:
        # link_cell has no href attribute — should be rejected
        row = [
            "John", "Smith", "Smith, John (Senator)",
            "<td>No link here</td>",
            "03/15/2024",
        ]
        assert _parse_filing_row(row) is None


# ── Signal generation ──────────────────────────────────────────────────────

class TestAmountWeight:
    def test_small_amount_lower_than_large(self) -> None:
        small = _amount_weight(1_001, 15_000)
        large = _amount_weight(1_000_001, 5_000_000)
        assert small < large

    def test_large_amount_high_weight(self) -> None:
        w = _amount_weight(50_000_001, None)
        assert w >= 1.8

    def test_unknown_amount_uses_default_midpoint(self) -> None:
        w_unknown = _amount_weight(None, None)
        w_small = _amount_weight(1_001, 15_000)
        # Default midpoint is the same as the smallest range midpoint
        assert abs(w_unknown - w_small) < 0.001


class TestRecencyMultiplier:
    def test_recent_trade_gets_double(self) -> None:
        now = datetime.utcnow()
        recent = now - timedelta(days=10)
        assert _recency_multiplier(recent, now) == 2.0

    def test_old_trade_gets_one(self) -> None:
        now = datetime.utcnow()
        old = now - timedelta(days=60)
        assert _recency_multiplier(old, now) == 1.0

    def test_none_date_gets_one(self) -> None:
        assert _recency_multiplier(None, datetime.utcnow()) == 1.0


class TestScoreToSignal:
    def test_strong_buy(self) -> None:
        signal, conf = _score_to_signal(0.8, 1.0)
        assert signal == "strong_buy"
        assert conf >= 0.6

    def test_buy(self) -> None:
        signal, conf = _score_to_signal(0.3, 1.0)
        assert signal == "buy"

    def test_hold(self) -> None:
        signal, conf = _score_to_signal(0.1, 1.0)
        assert signal == "hold"

    def test_sell(self) -> None:
        signal, conf = _score_to_signal(-0.5, 1.0)
        assert signal == "sell"

    def test_zero_total_weight(self) -> None:
        signal, conf = _score_to_signal(0.0, 0.0)
        assert signal == "hold"
        assert conf == 0.0


class TestBuildRationale:
    def test_strong_buy_rationale(self) -> None:
        text = _build_rationale("AAPL", buy_count=10, sell_count=2, unique_pols=8, signal="strong_buy")
        assert "AAPL" in text
        assert "10 purchase" in text
        assert "2 sale" in text
        assert "8 members" in text

    def test_sell_rationale(self) -> None:
        text = _build_rationale("CVX", buy_count=2, sell_count=10, unique_pols=5, signal="sell")
        assert "CVX" in text
        assert "net sold" in text

    def test_singular_politician(self) -> None:
        text = _build_rationale("X", buy_count=1, sell_count=0, unique_pols=1, signal="strong_buy")
        assert "1 member of Congress" in text
        assert "member" in text and "members" not in text


class TestAggregateTradesLogic:
    def _make_trade(
        self,
        ticker: str,
        trade_type: str,
        amount_low: int | None = 1_001,
        amount_high: int | None = 15_000,
        days_ago: int = 10,
        politician: str = "Rep. A",
    ) -> MagicMock:
        trade = MagicMock()
        trade.ticker = ticker
        trade.trade_type = trade_type
        trade.amount_low = amount_low
        trade.amount_high = amount_high
        trade.disclosure_date = datetime.utcnow() - timedelta(days=days_ago)
        trade.politician_name = politician
        trade.company_name = f"{ticker} Corp"
        return trade

    def test_purchases_add_positive_score(self) -> None:
        trades = [self._make_trade("AAPL", "purchase")]
        agg = _aggregate_trades(trades, datetime.utcnow())
        assert agg["AAPL"]["net_score"] > 0

    def test_sales_add_negative_score(self) -> None:
        trades = [self._make_trade("AAPL", "sale")]
        agg = _aggregate_trades(trades, datetime.utcnow())
        assert agg["AAPL"]["net_score"] < 0

    def test_unique_politicians_counted(self) -> None:
        trades = [
            self._make_trade("AAPL", "purchase", politician="Rep. A"),
            self._make_trade("AAPL", "purchase", politician="Rep. A"),  # same person
            self._make_trade("AAPL", "purchase", politician="Rep. B"),
        ]
        agg = _aggregate_trades(trades, datetime.utcnow())
        assert agg["AAPL"]["politicians"] == {"Rep. A", "Rep. B"}

    def test_buy_sell_counts(self) -> None:
        trades = [
            self._make_trade("MSFT", "purchase"),
            self._make_trade("MSFT", "purchase"),
            self._make_trade("MSFT", "sale"),
        ]
        agg = _aggregate_trades(trades, datetime.utcnow())
        assert agg["MSFT"]["buy_count"] == 2
        assert agg["MSFT"]["sell_count"] == 1
