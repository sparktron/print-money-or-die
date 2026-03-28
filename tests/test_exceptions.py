"""Tests for pmod.exceptions — typed exception hierarchy."""

import pytest

from pmod.exceptions import (
    AuthError,
    BrokerError,
    ConfigError,
    InsufficientDataError,
    MarketDataError,
    OrderRejectedError,
    PmodError,
    RateLimitError,
    TokenExpiredError,
)


class TestExceptionHierarchy:
    def test_all_inherit_from_pmod_error(self) -> None:
        for exc_class in [
            AuthError, TokenExpiredError, BrokerError, OrderRejectedError,
            MarketDataError, RateLimitError, ConfigError, InsufficientDataError,
        ]:
            assert issubclass(exc_class, PmodError)

    def test_token_expired_is_auth_error(self) -> None:
        assert issubclass(TokenExpiredError, AuthError)

    def test_order_rejected_is_broker_error(self) -> None:
        assert issubclass(OrderRejectedError, BrokerError)

    def test_rate_limit_is_market_data_error(self) -> None:
        assert issubclass(RateLimitError, MarketDataError)

    def test_catch_pmod_error_catches_all(self) -> None:
        with pytest.raises(PmodError):
            raise TokenExpiredError("refresh token expired")

        with pytest.raises(PmodError):
            raise OrderRejectedError("insufficient funds", status_code=400)

        with pytest.raises(PmodError):
            raise RateLimitError("429 too many requests")

    def test_order_rejected_stores_status_code(self) -> None:
        exc = OrderRejectedError("rejected", status_code=403)
        assert exc.status_code == 403
        assert str(exc) == "rejected"

    def test_order_rejected_default_status_code(self) -> None:
        exc = OrderRejectedError("rejected")
        assert exc.status_code is None
