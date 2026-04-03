"""Tests for bad / degenerate API data inputs.

Every external data source (Polygon, Schwab, Yahoo Finance, CSV) is exercised
with the malformed or edge-case payloads that real APIs actually return:
missing fields, zero/null values, partial responses, HTTP errors, and
encoding oddities.  All network calls are mocked.
"""

from __future__ import annotations

import io
from datetime import date, datetime
from unittest.mock import MagicMock, patch

import pytest

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _mock_http_response(
    json_body: dict,
    status_code: int = 200,
) -> MagicMock:
    """Return a mock httpx.Response with a fixed JSON body and status code."""
    resp = MagicMock()
    resp.status_code = status_code
    resp.json.return_value = json_body
    resp.raise_for_status = MagicMock(
        side_effect=(
            None
            if status_code < 400
            else _raise_http_status(status_code)
        )
    )
    return resp


def _raise_http_status(status_code: int):
    """Return a side-effect that raises an httpx.HTTPStatusError."""
    import httpx

    def _raise(*_args, **_kwargs):
        request = MagicMock()
        response = MagicMock()
        response.status_code = status_code
        raise httpx.HTTPStatusError(
            f"HTTP {status_code}", request=request, response=response
        )

    return _raise


# ===========================================================================
# Polygon.io — get_quote
# ===========================================================================

class TestGetQuoteBadInputs:
    """Polygon /prev endpoint bad/empty/degenerate responses."""

    _PATCH_GET = "pmod.data.market._get"

    def test_empty_results_list_returns_none(self) -> None:
        from pmod.data.market import get_quote

        with patch(self._PATCH_GET, return_value={"results": []}):
            assert get_quote("AAPL") is None

    def test_missing_results_key_returns_none(self) -> None:
        from pmod.data.market import get_quote

        with patch(self._PATCH_GET, return_value={}):
            assert get_quote("AAPL") is None

    def test_missing_close_field_defaults_to_zero(self) -> None:
        from pmod.data.market import get_quote

        # Bar has volume but no close price ('c' absent)
        with patch(self._PATCH_GET, return_value={"results": [{"v": 1_000_000}]}):
            quote = get_quote("AAPL")
        assert quote is not None
        assert quote.price == 0.0

    def test_zero_open_price_no_division_by_zero(self) -> None:
        """change_pct must be 0.0, not ZeroDivisionError, when open == 0."""
        from pmod.data.market import get_quote

        with patch(self._PATCH_GET, return_value={"results": [{"c": 150.0, "o": 0.0, "v": 500}]}):
            quote = get_quote("AAPL")
        assert quote is not None
        assert quote.change_pct == 0.0

    def test_prev_close_differs_from_price(self) -> None:
        """After the bug-fix, prev_close should be the open, not the close."""
        from pmod.data.market import get_quote

        with patch(self._PATCH_GET, return_value={"results": [{"c": 200.0, "o": 190.0, "v": 1000}]}):
            quote = get_quote("TSLA")
        assert quote is not None
        assert quote.price == 200.0
        assert quote.prev_close == 190.0           # open, not close
        assert quote.prev_close != quote.price     # must be distinct

    def test_404_returns_none(self) -> None:
        import httpx
        from pmod.data.market import get_quote

        def _raise_404(*_a, **_k):
            req = MagicMock()
            resp = MagicMock()
            resp.status_code = 404
            raise httpx.HTTPStatusError("404", request=req, response=resp)

        with patch(self._PATCH_GET, side_effect=_raise_404):
            assert get_quote("FAKE") is None

    def test_non_404_http_error_propagates(self) -> None:
        """A 500 from Polygon should raise, not silently return None."""
        import httpx
        from pmod.data.market import get_quote

        def _raise_500(*_a, **_k):
            req = MagicMock()
            resp = MagicMock()
            resp.status_code = 500
            raise httpx.HTTPStatusError("500", request=req, response=resp)

        with patch(self._PATCH_GET, side_effect=_raise_500):
            with pytest.raises(httpx.HTTPStatusError):
                get_quote("AAPL")

    def test_ticker_uppercased_in_result(self) -> None:
        from pmod.data.market import get_quote

        with patch(self._PATCH_GET, return_value={"results": [{"c": 100.0, "o": 99.0, "v": 200}]}):
            quote = get_quote("aapl")
        assert quote is not None
        assert quote.ticker == "AAPL"

    def test_missing_volume_defaults_to_zero(self) -> None:
        from pmod.data.market import get_quote

        with patch(self._PATCH_GET, return_value={"results": [{"c": 50.0, "o": 49.0}]}):
            quote = get_quote("SPY")
        assert quote is not None
        assert quote.volume == 0


# ===========================================================================
# Polygon.io — get_price_history
# ===========================================================================

class TestGetPriceHistoryBadInputs:
    _PATCH_GET = "pmod.data.market._get"

    def test_empty_results_returns_none(self) -> None:
        from pmod.data.market import get_price_history

        with patch(self._PATCH_GET, return_value={"results": []}):
            assert get_price_history("AAPL") is None

    def test_missing_results_key_returns_none(self) -> None:
        from pmod.data.market import get_price_history

        with patch(self._PATCH_GET, return_value={"ticker": "AAPL", "status": "OK"}):
            assert get_price_history("AAPL") is None

    def test_bar_with_missing_timestamp_uses_fallback_date(self) -> None:
        """A bar with t=0/absent should not crash — it uses end date as fallback."""
        from pmod.data.market import get_price_history

        bar = {"c": 100.0, "o": 99.0, "h": 101.0, "l": 98.0, "v": 5000}  # no 't'
        with patch(self._PATCH_GET, return_value={"results": [bar]}):
            history = get_price_history("AAPL")
        assert history is not None
        assert len(history.bars) == 1
        assert history.bars[0].close == 100.0

    def test_bar_with_zero_close_is_included(self) -> None:
        """Zero close prices are valid market data and must be preserved."""
        from pmod.data.market import get_price_history

        bar = {"t": 1_700_000_000_000, "c": 0.0, "o": 0.0, "h": 0.0, "l": 0.0, "v": 0}
        with patch(self._PATCH_GET, return_value={"results": [bar]}):
            history = get_price_history("BRKR")
        assert history is not None
        assert history.closes == [0.0]

    def test_multiple_bars_produces_ordered_closes(self) -> None:
        from pmod.data.market import get_price_history

        bars = [
            {"t": 1_700_000_000_000 + i * 86_400_000, "c": float(100 + i), "o": 99.0, "h": 102.0, "l": 98.0, "v": 1000}
            for i in range(5)
        ]
        with patch(self._PATCH_GET, return_value={"results": bars}):
            history = get_price_history("AAPL")
        assert history is not None
        assert len(history.closes) == 5
        assert history.closes == [100.0, 101.0, 102.0, 103.0, 104.0]

    def test_missing_ohlcv_fields_default_to_zero(self) -> None:
        """Bars with no OHLCV keys should parse as zeros, not crash."""
        from pmod.data.market import get_price_history

        bar = {"t": 1_700_000_000_000}  # timestamp only
        with patch(self._PATCH_GET, return_value={"results": [bar]}):
            history = get_price_history("X")
        assert history is not None
        b = history.bars[0]
        assert b.open == 0.0
        assert b.close == 0.0
        assert b.volume == 0

    def test_404_returns_none(self) -> None:
        import httpx
        from pmod.data.market import get_price_history

        def _raise(*_a, **_k):
            req, resp = MagicMock(), MagicMock()
            resp.status_code = 404
            raise httpx.HTTPStatusError("404", request=req, response=resp)

        with patch(self._PATCH_GET, side_effect=_raise):
            assert get_price_history("FAKE") is None


# ===========================================================================
# Polygon.io — get_quotes_batch
# ===========================================================================

class TestGetQuotesBatchBadInputs:
    _PATCH_GET_QUOTE = "pmod.data.market.get_quote"

    def test_all_tickers_fail_returns_empty_dict(self) -> None:
        from pmod.data.market import get_quotes_batch

        with patch(self._PATCH_GET_QUOTE, side_effect=RuntimeError("API down")):
            result = get_quotes_batch(["AAPL", "TSLA", "NVDA"])
        assert result == {}

    def test_partial_failure_returns_successful_tickers_only(self) -> None:
        """If AAPL succeeds and TSLA fails, only AAPL appears in result."""
        from pmod.data.market import Quote, get_quotes_batch

        good_quote = Quote(ticker="AAPL", price=200.0, change_pct=1.0, prev_close=198.0, volume=1_000_000)

        def _side_effect(ticker: str):
            if ticker == "AAPL":
                return good_quote
            raise RuntimeError("rate limited")

        with patch(self._PATCH_GET_QUOTE, side_effect=_side_effect):
            result = get_quotes_batch(["AAPL", "TSLA"])
        assert "AAPL" in result
        assert "TSLA" not in result

    def test_none_quote_excluded_from_result(self) -> None:
        """Tickers for which get_quote returns None are silently dropped."""
        from pmod.data.market import get_quotes_batch

        with patch(self._PATCH_GET_QUOTE, return_value=None):
            result = get_quotes_batch(["FAKE1", "FAKE2"])
        assert result == {}

    def test_empty_ticker_list_returns_empty_dict(self) -> None:
        from pmod.data.market import get_quotes_batch

        assert get_quotes_batch([]) == {}


# ===========================================================================
# Schwab — _parse_positions (bad Schwab API payloads)
# ===========================================================================

class TestParsePositionsBadInputs:
    """Edge-case and malformed position dicts from the Schwab API."""

    def test_missing_instrument_key_skips_position(self) -> None:
        from pmod.broker.schwab import _parse_positions

        raw = [{"longQuantity": 10, "marketValue": 1000.0}]  # no 'instrument'
        assert _parse_positions(raw, total_value=10_000.0) == []

    def test_empty_instrument_dict_skips_position(self) -> None:
        from pmod.broker.schwab import _parse_positions

        raw = [{"instrument": {}, "longQuantity": 10, "marketValue": 1000.0}]
        assert _parse_positions(raw, total_value=10_000.0) == []

    def test_unknown_asset_type_skipped(self) -> None:
        from pmod.broker.schwab import _parse_positions

        raw = [{
            "instrument": {"symbol": "VIX", "assetType": "INDEX", "description": "VIX"},
            "longQuantity": 1,
            "averagePrice": 20.0,
            "marketValue": 20.0,
            "currentDayProfitLoss": 0.0,
        }]
        assert _parse_positions(raw, total_value=10_000.0) == []

    def test_equity_etf_asset_type_accepted(self) -> None:
        from pmod.broker.schwab import _parse_positions

        raw = [{
            "instrument": {"symbol": "SPY", "assetType": "EQUITY_ETF", "description": "S&P 500 ETF"},
            "longQuantity": 10.0,
            "averagePrice": 400.0,
            "marketValue": 4200.0,
            "currentDayProfitLoss": 20.0,
        }]
        positions = _parse_positions(raw, total_value=10_000.0)
        assert len(positions) == 1
        assert positions[0].ticker == "SPY"

    def test_missing_average_price_defaults_cost_basis_to_zero(self) -> None:
        from pmod.broker.schwab import _parse_positions

        raw = [{
            "instrument": {"symbol": "AAPL", "assetType": "EQUITY"},
            "longQuantity": 10.0,
            "marketValue": 1500.0,
            "currentDayProfitLoss": 0.0,
            # averagePrice intentionally absent
        }]
        positions = _parse_positions(raw, total_value=10_000.0)
        assert len(positions) == 1
        assert positions[0].avg_cost == 0.0
        assert positions[0].cost_basis == 0.0

    def test_current_price_derived_from_market_value_and_shares(self) -> None:
        """current_price = market_value / shares — no direct field from Schwab."""
        from pmod.broker.schwab import _parse_positions

        raw = [{
            "instrument": {"symbol": "MSFT", "assetType": "EQUITY"},
            "longQuantity": 5.0,
            "averagePrice": 390.0,
            "marketValue": 2_100.0,   # → current_price = 420
            "currentDayProfitLoss": 50.0,
        }]
        positions = _parse_positions(raw, total_value=10_000.0)
        assert positions[0].current_price == pytest.approx(420.0)

    def test_whitespace_in_symbol_is_stripped(self) -> None:
        from pmod.broker.schwab import _parse_positions

        raw = [{
            "instrument": {"symbol": "  NVDA  ", "assetType": "EQUITY"},
            "longQuantity": 10.0,
            "averagePrice": 800.0,
            "marketValue": 9_000.0,
            "currentDayProfitLoss": 0.0,
        }]
        positions = _parse_positions(raw, total_value=10_000.0)
        assert len(positions) == 1
        assert positions[0].ticker == "NVDA"

    def test_alternate_day_pnl_pct_field_name(self) -> None:
        """Schwab uses 'currentDayProfitLossPercentage' on some account types."""
        from pmod.broker.schwab import _parse_positions

        raw = [{
            "instrument": {"symbol": "AAPL", "assetType": "EQUITY"},
            "longQuantity": 10.0,
            "averagePrice": 150.0,
            "marketValue": 1_800.0,
            "currentDayProfitLoss": 30.0,
            "currentDayProfitLossPercentage": 1.69,
        }]
        positions = _parse_positions(raw, total_value=10_000.0)
        assert positions[0].day_pnl_pct == pytest.approx(1.69)

    def test_zero_shares_in_long_quantity_skipped(self) -> None:
        from pmod.broker.schwab import _parse_positions

        raw = [{
            "instrument": {"symbol": "AAPL", "assetType": "EQUITY"},
            "longQuantity": 0.0,
            "averagePrice": 150.0,
            "marketValue": 0.0,
            "currentDayProfitLoss": 0.0,
        }]
        assert _parse_positions(raw, total_value=10_000.0) == []

    def test_negative_long_quantity_skipped(self) -> None:
        """Negative longQuantity is not a real long position — skip it."""
        from pmod.broker.schwab import _parse_positions

        raw = [{
            "instrument": {"symbol": "AAPL", "assetType": "EQUITY"},
            "longQuantity": -5.0,
            "averagePrice": 150.0,
            "marketValue": 750.0,
            "currentDayProfitLoss": 0.0,
        }]
        assert _parse_positions(raw, total_value=10_000.0) == []


# ===========================================================================
# Schwab — get_account_summary (balance field variations)
# ===========================================================================

class TestGetAccountSummaryBadInputs:
    _PATCH_GET_CLIENT = "pmod.auth.schwab.get_client"

    def _make_client_with_accounts(self, accounts: list[dict]) -> MagicMock:
        resp = MagicMock()
        resp.json.return_value = accounts
        resp.raise_for_status = MagicMock()
        client = MagicMock()
        client.get_accounts.return_value = resp
        return client

    def test_equity_fallback_used_when_liquidation_value_absent(self) -> None:
        """Falls back to 'equity' when 'liquidationValue' is missing."""
        from pmod.broker.schwab import get_account_summary

        account = {
            "securitiesAccount": {
                "accountNumber": "111",
                "currentBalances": {"equity": 30_000.0, "cashBalance": 2_000.0},
                "positions": [],
            }
        }
        with patch(self._PATCH_GET_CLIENT, return_value=self._make_client_with_accounts([account])):
            result = get_account_summary()
        assert result is not None
        assert result.total_value == 30_000.0

    def test_zero_total_value_when_all_balance_fields_absent(self) -> None:
        """Gracefully handles account with no balance fields at all."""
        from pmod.broker.schwab import get_account_summary

        account = {
            "securitiesAccount": {
                "accountNumber": "222",
                "currentBalances": {},   # empty
                "positions": [],
            }
        }
        with patch(self._PATCH_GET_CLIENT, return_value=self._make_client_with_accounts([account])):
            result = get_account_summary()
        assert result is not None
        assert result.total_value == 0.0
        assert result.cash_balance == 0.0

    def test_missing_positions_key_returns_empty_positions(self) -> None:
        from pmod.broker.schwab import get_account_summary

        account = {
            "securitiesAccount": {
                "accountNumber": "333",
                "currentBalances": {"liquidationValue": 5_000.0},
                # 'positions' key absent entirely
            }
        }
        with patch(self._PATCH_GET_CLIENT, return_value=self._make_client_with_accounts([account])):
            result = get_account_summary()
        assert result is not None
        assert result.positions == []

    def test_account_number_absent_returns_empty_string(self) -> None:
        from pmod.broker.schwab import get_account_summary

        account = {
            "securitiesAccount": {
                # no 'accountNumber'
                "currentBalances": {"liquidationValue": 1_000.0},
                "positions": [],
            }
        }
        with patch(self._PATCH_GET_CLIENT, return_value=self._make_client_with_accounts([account])):
            result = get_account_summary()
        assert result is not None
        assert result.account_number == ""

    def test_mixed_valid_and_invalid_positions(self) -> None:
        """Valid positions are returned even when the list contains bad entries."""
        from pmod.broker.schwab import get_account_summary

        account = {
            "securitiesAccount": {
                "accountNumber": "444",
                "currentBalances": {"liquidationValue": 20_000.0},
                "positions": [
                    # valid equity
                    {
                        "instrument": {"symbol": "NVDA", "assetType": "EQUITY", "description": "NVIDIA"},
                        "longQuantity": 5.0,
                        "averagePrice": 800.0,
                        "marketValue": 4_500.0,
                        "currentDayProfitLoss": 100.0,
                    },
                    # bad: no instrument key
                    {"longQuantity": 10, "marketValue": 1000.0},
                    # bad: OPTION type
                    {
                        "instrument": {"symbol": "AAPL240621C00200000", "assetType": "OPTION"},
                        "longQuantity": 1.0,
                        "marketValue": 500.0,
                        "currentDayProfitLoss": 0.0,
                    },
                ],
            }
        }
        with patch(self._PATCH_GET_CLIENT, return_value=self._make_client_with_accounts([account])):
            result = get_account_summary()
        assert result is not None
        assert len(result.positions) == 1
        assert result.positions[0].ticker == "NVDA"


# ===========================================================================
# CSV Import — parse_csv (bad / edge-case files)
# ===========================================================================

class TestParseCsvBadInputs:

    def _csv(self, content: str) -> io.StringIO:
        return io.StringIO(content)

    def test_empty_file_returns_empty_list(self) -> None:
        from pmod.data.external_accounts import parse_csv

        assert parse_csv(self._csv("")) == []

    def test_header_only_no_data_rows(self) -> None:
        from pmod.data.external_accounts import parse_csv

        assert parse_csv(self._csv("Symbol,Quantity,Price\n")) == []

    def test_cash_row_skipped(self) -> None:
        from pmod.data.external_accounts import parse_csv

        csv_text = "Symbol,Quantity,Price\nCash,0,1.00\nAAPL,10,150.00\n"
        rows = parse_csv(self._csv(csv_text))
        assert len(rows) == 1
        assert rows[0].ticker == "AAPL"

    def test_total_row_skipped(self) -> None:
        from pmod.data.external_accounts import parse_csv

        csv_text = "Symbol,Quantity,Price\nAAPL,10,150.00\nTotal,,\n"
        rows = parse_csv(self._csv(csv_text))
        assert len(rows) == 1

    def test_ticker_with_space_skipped(self) -> None:
        """Tickers with spaces (e.g. 'Cash & Cash Investments') are not real tickers."""
        from pmod.data.external_accounts import parse_csv

        csv_text = "Symbol,Quantity\nCash & Cash Investments,0\nMSFT,5\n"
        rows = parse_csv(self._csv(csv_text))
        assert all(r.ticker == "MSFT" for r in rows)

    def test_dollar_signs_and_commas_stripped_from_price(self) -> None:
        from pmod.data.external_accounts import parse_csv

        # Numbers with commas must be quoted in CSV so the parser doesn't
        # split on the comma; dollar signs are stripped by _parse_float.
        csv_text = 'Symbol,Quantity,Price,Market Value\nAAPL,10,"$1,234.56","$12,345.60"\n'
        rows = parse_csv(self._csv(csv_text))
        assert len(rows) == 1
        assert rows[0].current_price == pytest.approx(1234.56)
        assert rows[0].market_value == pytest.approx(12345.60)

    def test_parenthetical_negative_parsed_correctly(self) -> None:
        """Schwab exports negative values as (1.23) — must parse as -1.23."""
        from pmod.data.external_accounts import parse_csv

        csv_text = "Symbol,Quantity,Average Cost,Market Value\nXYZ,10,(5.00),(50.00)\n"
        rows = parse_csv(self._csv(csv_text))
        assert len(rows) == 1
        assert rows[0].avg_cost == pytest.approx(-5.0)
        assert rows[0].market_value == pytest.approx(-50.0)

    def test_non_numeric_shares_skips_field(self) -> None:
        from pmod.data.external_accounts import parse_csv

        csv_text = "Symbol,Quantity,Price\nAAPL,N/A,150.00\n"
        rows = parse_csv(self._csv(csv_text))
        assert len(rows) == 1
        assert rows[0].shares is None
        assert rows[0].current_price == pytest.approx(150.0)

    def test_market_value_derived_when_absent(self) -> None:
        """If Market Value column is missing, it is inferred from shares × price."""
        from pmod.data.external_accounts import parse_csv

        csv_text = "Symbol,Quantity,Price\nAAPL,10,150.00\n"
        rows = parse_csv(self._csv(csv_text))
        assert len(rows) == 1
        assert rows[0].market_value == pytest.approx(1500.0)

    def test_no_valid_rows_all_bad_tickers(self) -> None:
        from pmod.data.external_accounts import parse_csv

        # All rows that should be skipped: purely numeric (no alpha), blank,
        # or the literal "cash" keyword.
        csv_text = "Symbol,Quantity\n12345,10\n999,5\n,0\ncash,100\n"
        rows = parse_csv(self._csv(csv_text))
        assert rows == []

    def test_bom_prefix_handled(self) -> None:
        """UTF-8 BOM at the start of a file must not corrupt headers.

        parse_csv opens files with 'utf-8-sig' encoding which strips the BOM
        automatically.  We write the file with utf-8-sig so the BOM is present
        on disk; the reader must still parse the Symbol column correctly.
        """
        from pmod.data.external_accounts import parse_csv
        import tempfile, os

        csv_content = "Symbol,Quantity,Price\nAAPL,10,150.00\n"
        with tempfile.NamedTemporaryFile(mode="w", suffix=".csv", delete=False,
                                         encoding="utf-8-sig") as f:
            f.write(csv_content)
            path = f.name
        try:
            rows = parse_csv(path)
            assert len(rows) == 1
            assert rows[0].ticker == "AAPL"
        finally:
            os.unlink(path)

    def test_multiple_rows_with_mixed_quality(self) -> None:
        from pmod.data.external_accounts import parse_csv

        csv_text = (
            "Symbol,Quantity,Price,Market Value\n"
            "AAPL,10,150.00,1500.00\n"
            "Cash,0,,\n"        # skipped: 'cash' keyword
            "Total,,,\n"        # skipped: 'total' keyword
            "MSFT,5,350.00,1750.00\n"
            "123456,2,10.00,20.00\n"   # skipped: no alpha chars
        )
        rows = parse_csv(self._csv(csv_text))
        tickers = {r.ticker for r in rows}
        assert tickers == {"AAPL", "MSFT"}


# ===========================================================================
# Signals — compute_volatility / compute_rsi (bad close price series)
# ===========================================================================

class TestSignalsBadPriceData:

    def test_compute_volatility_handles_zero_close_in_series(self) -> None:
        """log(x/0) is undefined — zero closes must be filtered, not crash."""
        from pmod.research.signals import compute_volatility

        closes = [100.0, 0.0, 100.0, 101.0, 99.0, 100.5]
        # Should not raise; returns a float or None
        result = compute_volatility(closes)
        assert result is None or isinstance(result, float)

    def test_compute_rsi_with_exactly_period_plus_one_returns_value(self) -> None:
        """Minimum viable input: exactly period+1 closes."""
        from pmod.research.signals import compute_rsi

        closes = [float(100 + i) for i in range(15)]  # 15 items, period=14
        rsi = compute_rsi(closes, period=14)
        assert rsi is not None
        assert 0.0 <= rsi <= 100.0

    def test_compute_rsi_with_period_plus_zero_returns_none(self) -> None:
        """Exactly period items is insufficient (need period+1 for one delta)."""
        from pmod.research.signals import compute_rsi

        closes = [float(100 + i) for i in range(14)]  # exactly 14
        assert compute_rsi(closes, period=14) is None

    def test_compute_momentum_with_all_zeros_returns_zero(self) -> None:
        """All-zero close prices must not produce NaN or crash."""
        from pmod.research.signals import compute_momentum_score

        closes = [0.0] * 90
        score = compute_momentum_score(closes)
        assert score == 0.0

    def test_compute_volatility_fewer_than_five_points_returns_none(self) -> None:
        from pmod.research.signals import compute_volatility

        assert compute_volatility([100.0, 101.0, 99.0]) is None

    def test_compute_sma_crossover_with_zero_long_sma_returns_neutral(self) -> None:
        """Long SMA of zero (all-zero prices) must not divide by zero."""
        from pmod.research.signals import compute_sma_crossover

        closes = [0.0] * 60
        result = compute_sma_crossover(closes, short=20, long=50)
        assert result == "neutral"


# ===========================================================================
# Alpha calculation — bad/empty historical data
# ===========================================================================

class TestAlphaCalculationBadInputs:

    def test_returns_none_when_no_portfolio_snapshots(self) -> None:
        from pmod.analytics.alpha import calculate_alpha

        with patch("pmod.analytics.alpha.get_historical_returns", return_value=None):
            assert calculate_alpha() is None

    def test_returns_none_when_fewer_than_two_common_dates(self) -> None:
        """With only one aligned date point there is no return to compute."""
        from pmod.analytics.alpha import get_historical_returns
        from contextlib import contextmanager

        p_snap = MagicMock()
        p_snap.captured_at = datetime(2025, 1, 2)
        p_snap.total_value = 100_000.0

        b_snap = MagicMock()
        b_snap.captured_at = datetime(2025, 1, 2)
        b_snap.close_price = 480.0

        session = MagicMock()
        session.query.return_value.filter.return_value.order_by.return_value.all.side_effect = [
            [p_snap],   # portfolio query result
            [b_snap],   # benchmark query result
        ]

        @contextmanager
        def _fake_session():
            yield session

        # alpha.py imports get_session directly — patch at that module's namespace
        with patch("pmod.analytics.alpha.get_session", _fake_session):
            result = get_historical_returns(days=365)

        assert result is None

    def test_alpha_computed_correctly_from_real_returns(self) -> None:
        from pmod.analytics.alpha import calculate_alpha

        # Portfolio +20%, benchmark +10% → alpha +10%
        portfolio = [100_000.0, 120_000.0]
        benchmark = [400.0, 440.0]
        dates = ["2024-01-02", "2024-12-31"]

        with patch("pmod.analytics.alpha.get_historical_returns", return_value=(portfolio, benchmark, dates)):
            result = calculate_alpha()

        assert result is not None
        assert result["total_return_pct"] == pytest.approx(20.0)
        assert result["benchmark_return_pct"] == pytest.approx(10.0)
        assert result["alpha_pct"] == pytest.approx(10.0)

    def test_alpha_negative_when_underperforming(self) -> None:
        from pmod.analytics.alpha import calculate_alpha

        portfolio = [100_000.0, 95_000.0]   # -5%
        benchmark = [400.0, 420.0]           # +5%
        dates = ["2024-01-02", "2024-12-31"]

        with patch("pmod.analytics.alpha.get_historical_returns", return_value=(portfolio, benchmark, dates)):
            result = calculate_alpha()

        assert result is not None
        assert result["alpha_pct"] < 0


# ===========================================================================
# Optimizer — external position with None market_value (regression test)
# ===========================================================================

class TestOptimizerNullMarketValue:
    """Regression: pos.market_value = None for external positions must not crash."""

    _PATCH_SUMMARY = "pmod.broker.schwab.get_account_summary"
    _PATCH_EXT_LIST = "pmod.data.external_accounts.list_accounts"
    _PATCH_EXT_POS  = "pmod.data.external_accounts.get_positions"
    _PATCH_TREND    = "pmod.research.signals.compute_trend"
    _PATCH_POL      = "pmod.research.politician_signals.get_signals"

    def _make_ext_position(
        self,
        ticker: str,
        market_value: float | None = None,
        current_price: float | None = None,
        shares: float | None = None,
    ) -> MagicMock:
        pos = MagicMock()
        pos.ticker = ticker
        pos.company_name = f"{ticker} Fund"
        pos.market_value = market_value
        pos.current_price = current_price
        pos.shares = shares
        return pos

    def test_none_market_value_does_not_crash(self) -> None:
        from pmod.optimizer.portfolio import compute_rebalance

        trend = MagicMock()
        trend.momentum_score = 0.0
        trend.volatility_pct = 20.0

        with (
            patch(self._PATCH_SUMMARY, return_value=None),
            patch(self._PATCH_EXT_LIST, return_value=[{
                "name": "My 401k",
                "account_type": "401k",
                "total_value": 0.0,
                "position_count": 1,
                "last_imported_at": None,
            }]),
            patch(self._PATCH_EXT_POS, return_value=[
                self._make_ext_position("VTSAX", market_value=None, current_price=None, shares=None),
            ]),
            patch(self._PATCH_TREND, return_value=trend),
            patch(self._PATCH_POL, return_value=[]),
        ):
            # Must not raise TypeError
            plan = compute_rebalance()

        assert plan is not None

    def test_zero_price_external_position_gets_zero_shares_delta(self) -> None:
        from pmod.optimizer.portfolio import compute_rebalance

        trend = MagicMock()
        trend.momentum_score = 0.3
        trend.volatility_pct = 15.0

        with (
            patch(self._PATCH_SUMMARY, return_value=None),
            patch(self._PATCH_EXT_LIST, return_value=[{
                "name": "IRA",
                "account_type": "ira",
                "total_value": 5_000.0,
                "position_count": 1,
                "last_imported_at": None,
            }]),
            patch(self._PATCH_EXT_POS, return_value=[
                self._make_ext_position("BIEKX", market_value=5_000.0, current_price=0.0, shares=100.0),
            ]),
            patch(self._PATCH_TREND, return_value=trend),
            patch(self._PATCH_POL, return_value=[]),
        ):
            plan = compute_rebalance()

        all_trades = [t for ar in plan.account_rebalances for t in ar.trades]
        biekx = next((t for t in all_trades if t.ticker == "BIEKX"), None)
        assert biekx is not None
        assert biekx.shares_delta == 0  # can't compute shares without a price
