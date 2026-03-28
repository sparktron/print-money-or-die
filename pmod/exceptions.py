"""Typed exceptions for pmod.

Prefer raising these over generic RuntimeError / ValueError so callers
can catch specific failure modes without string-matching.
"""
from __future__ import annotations


class PmodError(Exception):
    """Base class for all pmod exceptions."""


# ── Auth / Broker ─────────────────────────────────────────────────────────

class AuthError(PmodError):
    """Schwab authentication or token error."""


class TokenExpiredError(AuthError):
    """Schwab refresh token has expired (>7 days) — user must re-login."""


class BrokerError(PmodError):
    """Error communicating with the Schwab Trader API."""


class OrderRejectedError(BrokerError):
    """Schwab rejected the order (insufficient funds, invalid ticker, etc.)."""

    def __init__(self, message: str, status_code: int | None = None) -> None:
        super().__init__(message)
        self.status_code = status_code


# ── Market Data ───────────────────────────────────────────────────────────

class MarketDataError(PmodError):
    """Error fetching market data from Polygon / Alpha Vantage."""


class RateLimitError(MarketDataError):
    """Exceeded API rate limit — caller should back off and retry."""


# ── Configuration ─────────────────────────────────────────────────────────

class ConfigError(PmodError):
    """Missing or invalid configuration (e.g., API keys not set)."""


# ── Research / Optimizer ──────────────────────────────────────────────────

class InsufficientDataError(PmodError):
    """Not enough data to compute the requested indicator or score."""
