"""Unit tests for pmod.broker.schwab — all Schwab API calls are mocked."""

from unittest.mock import MagicMock, patch

import pytest

from pmod.broker.schwab import (
    AccountSummary,
    OrderRequest,
    OrderResult,
    Position,
    _parse_positions,
    _unwrap_account,
    get_account_summary,
    place_order,
)


# ── _unwrap_account ────────────────────────────────────────────────────────

class TestUnwrapAccount:
    def test_unwraps_securities_account_key(self) -> None:
        raw = {"securitiesAccount": {"accountNumber": "123"}}
        assert _unwrap_account(raw) == {"accountNumber": "123"}

    def test_passthrough_when_key_absent(self) -> None:
        raw = {"accountNumber": "456"}
        assert _unwrap_account(raw) == raw


# ── _parse_positions ───────────────────────────────────────────────────────

def _make_raw_position(
    symbol: str = "AAPL",
    asset_type: str = "EQUITY",
    long_qty: float = 10.0,
    avg_price: float = 150.0,
    market_value: float = 1_600.0,
    day_pnl: float = 20.0,
) -> dict:
    return {
        "instrument": {"symbol": symbol, "assetType": asset_type, "description": f"{symbol} Corp"},
        "longQuantity": long_qty,
        "averagePrice": avg_price,
        "marketValue": market_value,
        "currentDayProfitLoss": day_pnl,
    }


class TestParsePositions:
    def test_basic_equity(self) -> None:
        raw = [_make_raw_position()]
        positions = _parse_positions(raw, total_value=10_000.0)
        assert len(positions) == 1
        p = positions[0]
        assert p.ticker == "AAPL"
        assert p.shares == 10.0
        assert p.market_value == 1_600.0

    def test_weight_calculated_correctly(self) -> None:
        raw = [_make_raw_position(market_value=500.0)]
        positions = _parse_positions(raw, total_value=1_000.0)
        assert positions[0].weight == pytest.approx(50.0)

    def test_non_equity_filtered_out(self) -> None:
        raw = [_make_raw_position(asset_type="OPTION")]
        positions = _parse_positions(raw, total_value=10_000.0)
        assert positions == []

    def test_zero_shares_filtered_out(self) -> None:
        raw = [_make_raw_position(long_qty=0)]
        positions = _parse_positions(raw, total_value=10_000.0)
        assert positions == []

    def test_multiple_positions_sorted_by_value_desc(self) -> None:
        raw = [
            _make_raw_position("AAPL", market_value=500.0),
            _make_raw_position("TSLA", market_value=2_000.0),
            _make_raw_position("MSFT", market_value=1_000.0),
        ]
        positions = _parse_positions(raw, total_value=3_500.0)
        values = [p.market_value for p in positions]
        assert values == sorted(values, reverse=True)

    def test_pnl_calculations(self) -> None:
        # 10 shares, avg cost $100, current market value $1200 → total P&L = $200
        raw = [_make_raw_position(long_qty=10, avg_price=100.0, market_value=1_200.0)]
        positions = _parse_positions(raw, total_value=10_000.0)
        p = positions[0]
        assert p.cost_basis == pytest.approx(1_000.0)
        assert p.total_pnl == pytest.approx(200.0)
        assert p.total_pnl_pct == pytest.approx(20.0)

    def test_zero_total_value_does_not_divide_by_zero(self) -> None:
        raw = [_make_raw_position()]
        positions = _parse_positions(raw, total_value=0.0)
        assert positions[0].weight == 0.0

    def test_empty_ticker_skipped(self) -> None:
        raw = [_make_raw_position(symbol="")]
        assert _parse_positions(raw, total_value=1_000.0) == []

    def test_etf_asset_type_included(self) -> None:
        raw = [_make_raw_position(asset_type="ETF")]
        assert len(_parse_positions(raw, total_value=1_000.0)) == 1


# ── get_account_summary ────────────────────────────────────────────────────

class TestGetAccountSummary:
    # get_client is imported inside the function body, so we patch it at its
    # definition site (pmod.auth.schwab) rather than in pmod.broker.schwab.
    _PATCH_GET_CLIENT = "pmod.auth.schwab.get_client"

    def _mock_response(self, accounts: list[dict], status: int = 200) -> MagicMock:
        resp = MagicMock()
        resp.status_code = status
        resp.json.return_value = accounts
        resp.raise_for_status = MagicMock()
        return resp

    def test_returns_none_on_api_error(self) -> None:
        with patch(self._PATCH_GET_CLIENT) as mock_client:
            mock_client.return_value.get_accounts.side_effect = RuntimeError("network error")
            result = get_account_summary()
        assert result is None

    def test_returns_none_when_no_accounts(self) -> None:
        with patch(self._PATCH_GET_CLIENT) as mock_client:
            mock_client.return_value.get_accounts.return_value = self._mock_response([])
            result = get_account_summary()
        assert result is None

    def test_parses_account_summary(self) -> None:
        fake_account = {
            "securitiesAccount": {
                "accountNumber": "99887766",
                "currentBalances": {
                    "liquidationValue": 50_000.0,
                    "cashBalance": 5_000.0,
                },
                "positions": [_make_raw_position("NVDA", market_value=10_000.0)],
            }
        }
        with patch(self._PATCH_GET_CLIENT) as mock_client:
            mock_client.return_value.get_accounts.return_value = self._mock_response([fake_account])
            result = get_account_summary()

        assert result is not None
        assert result.account_number == "99887766"
        assert result.total_value == 50_000.0
        assert result.cash_balance == 5_000.0
        assert len(result.positions) == 1
        assert result.positions[0].ticker == "NVDA"


# ── place_order ────────────────────────────────────────────────────────────

class TestPlaceOrder:
    # get_client and equity_* builders are imported inside place_order, so
    # patch them at their definition sites, not inside pmod.broker.schwab.
    _PATCH_GET_CLIENT = "pmod.auth.schwab.get_client"
    _PATCH_BUY_MKT = "schwab.orders.equities.equity_buy_market"
    _PATCH_SELL_MKT = "schwab.orders.equities.equity_sell_market"
    _PATCH_BUY_LMT = "schwab.orders.equities.equity_buy_limit"
    _PATCH_SELL_LMT = "schwab.orders.equities.equity_sell_limit"
    _PATCH_ACCT_NUM = "pmod.broker.schwab._get_account_number"

    def _mock_client(self, status: int = 201, location: str = "/orders/42") -> MagicMock:
        client = MagicMock()
        resp = MagicMock()
        resp.status_code = status
        resp.headers = {"Location": location}
        resp.text = ""
        client.place_order.return_value = resp
        return client

    def test_rejects_zero_quantity(self) -> None:
        req = OrderRequest(ticker="AAPL", instruction="buy", quantity=0)
        result = place_order(req)
        assert result.success is False
        assert "Quantity" in result.message

    def test_rejects_negative_quantity(self) -> None:
        req = OrderRequest(ticker="AAPL", instruction="buy", quantity=-5)
        result = place_order(req)
        assert result.success is False

    def test_market_buy_success(self) -> None:
        with (
            patch(self._PATCH_GET_CLIENT, return_value=self._mock_client()),
            patch(self._PATCH_ACCT_NUM, return_value="12345"),
        ):
            result = place_order(OrderRequest(ticker="AAPL", instruction="buy", quantity=10))
        assert result.success is True
        assert result.order_id == "42"

    def test_market_sell_success(self) -> None:
        with (
            patch(self._PATCH_GET_CLIENT, return_value=self._mock_client()),
            patch(self._PATCH_ACCT_NUM, return_value="12345"),
        ):
            result = place_order(OrderRequest(ticker="TSLA", instruction="sell", quantity=5))
        assert result.success is True

    def test_limit_buy_uses_limit_builder(self) -> None:
        client = self._mock_client()
        with (
            patch(self._PATCH_GET_CLIENT, return_value=client),
            patch(self._PATCH_ACCT_NUM, return_value="12345"),
            patch(self._PATCH_BUY_LMT) as mock_limit,
        ):
            mock_limit.return_value = MagicMock()
            place_order(OrderRequest(ticker="AAPL", instruction="buy", quantity=1,
                                     order_type="limit", limit_price=150.0))
        mock_limit.assert_called_once_with("AAPL", 1, 150.0)

    def test_unknown_instruction_returns_failure(self) -> None:
        with (
            patch(self._PATCH_GET_CLIENT, return_value=self._mock_client()),
            patch(self._PATCH_ACCT_NUM, return_value="12345"),
        ):
            result = place_order(OrderRequest(ticker="AAPL", instruction="hold", quantity=1))
        assert result.success is False
        assert "Unknown instruction" in result.message

    def test_rejected_order_returns_failure(self) -> None:
        client = self._mock_client(status=400)
        client.place_order.return_value.text = "Insufficient funds"
        with (
            patch(self._PATCH_GET_CLIENT, return_value=client),
            patch(self._PATCH_ACCT_NUM, return_value="12345"),
        ):
            result = place_order(OrderRequest(ticker="AAPL", instruction="buy", quantity=999))
        assert result.success is False

    def test_api_exception_returns_failure(self) -> None:
        client = self._mock_client()
        client.place_order.side_effect = RuntimeError("timeout")
        with (
            patch(self._PATCH_GET_CLIENT, return_value=client),
            patch(self._PATCH_ACCT_NUM, return_value="12345"),
        ):
            result = place_order(OrderRequest(ticker="AAPL", instruction="buy", quantity=1))
        assert result.success is False
        assert "timeout" in result.message
