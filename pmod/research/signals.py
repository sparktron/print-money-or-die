"""Technical trend analysis, scoring, and signal generation.

Provides lightweight technical indicators (RSI, SMA crossover, volatility)
computed from daily close data. These are combined into a composite trend
score that feeds the screener and watchlist.
"""
from __future__ import annotations

import math
import threading
import time
from dataclasses import dataclass

import structlog

log = structlog.get_logger()


@dataclass
class TrendSignal:
    """Composite technical assessment for a single ticker."""
    ticker: str
    rsi_14: float | None          # 0–100, >70 overbought, <30 oversold
    sma_crossover: str            # "bullish" | "bearish" | "neutral"
    momentum_score: float         # -1.0 (strong sell) to +1.0 (strong buy)
    volatility_pct: float | None  # annualised std-dev of daily returns
    data_points: int              # how many daily closes were available


# Thread-safe in-memory cache for trend results.
# Bounded at _TREND_CACHE_MAX entries; oldest entries are evicted when full.
_TREND_CACHE: dict[str, tuple[TrendSignal, float]] = {}  # {ticker: (signal, timestamp)}
_TREND_CACHE_LOCK = threading.Lock()
_TREND_CACHE_TTL = 3600   # 1 hour in seconds
_TREND_CACHE_MAX = 500    # max entries before eviction


def compute_rsi(closes: list[float], period: int = 14) -> float | None:
    """Compute the Relative Strength Index over *period* bars.

    Returns a value between 0 and 100, or None if insufficient data.
    """
    if len(closes) < period + 1:
        return None

    deltas = [closes[i] - closes[i - 1] for i in range(1, len(closes))]
    recent = deltas[-(period):]

    gains = [d for d in recent if d > 0]
    losses = [-d for d in recent if d < 0]

    avg_gain = sum(gains) / period if gains else 0.0
    avg_loss = sum(losses) / period if losses else 0.0

    if avg_loss == 0:
        return 100.0 if avg_gain > 0 else 50.0

    rs = avg_gain / avg_loss
    return round(100.0 - (100.0 / (1.0 + rs)), 2)


def compute_sma(closes: list[float], period: int) -> float | None:
    """Simple Moving Average over the last *period* closes."""
    if len(closes) < period:
        return None
    return sum(closes[-period:]) / period


def compute_sma_crossover(closes: list[float], short: int = 20, long: int = 50) -> str:
    """Determine SMA crossover direction.

    Returns:
        "bullish"  — short SMA is above long SMA
        "bearish"  — short SMA is below long SMA
        "neutral"  — insufficient data or SMAs are within 0.1% of each other
    """
    sma_short = compute_sma(closes, short)
    sma_long = compute_sma(closes, long)

    if sma_short is None or sma_long is None or sma_long == 0:
        return "neutral"

    pct_diff = (sma_short - sma_long) / sma_long
    if pct_diff > 0.001:
        return "bullish"
    if pct_diff < -0.001:
        return "bearish"
    return "neutral"


def compute_volatility(closes: list[float], annualise: bool = True) -> float | None:
    """Annualised (or daily) volatility from standard deviation of log returns.

    Returns None if fewer than 5 data points.
    """
    if len(closes) < 5:
        return None

    log_returns = [
        math.log(closes[i] / closes[i - 1])
        for i in range(1, len(closes))
        if closes[i - 1] > 0 and closes[i] > 0  # log(0) is undefined
    ]
    if len(log_returns) < 4:
        return None

    mean = sum(log_returns) / len(log_returns)
    variance = sum((r - mean) ** 2 for r in log_returns) / (len(log_returns) - 1)
    daily_vol = math.sqrt(variance)

    if annualise:
        return round(daily_vol * math.sqrt(252) * 100, 2)
    return round(daily_vol * 100, 4)


def compute_momentum_score(closes: list[float]) -> float:
    """Composite momentum score in [-1.0, +1.0].

    Blends:
      - 1-month return (weight 0.4)
      - 3-month return (weight 0.3)
      - RSI distance from neutral (weight 0.3)

    Positive = bullish momentum, negative = bearish.
    """
    if len(closes) < 5:
        return 0.0

    def _ret(n: int) -> float:
        if len(closes) < n + 1 or closes[-(n + 1)] == 0:
            return 0.0
        return (closes[-1] - closes[-(n + 1)]) / closes[-(n + 1)]

    ret_1m = _ret(21)
    ret_3m = _ret(63)

    rsi = compute_rsi(closes) or 50.0
    rsi_score = (rsi - 50.0) / 50.0

    def _clamp(v: float) -> float:
        return max(-1.0, min(1.0, v))

    score = (
        0.4 * _clamp(ret_1m * 5)
        + 0.3 * _clamp(ret_3m * 3)
        + 0.3 * _clamp(rsi_score)
    )
    return round(max(-1.0, min(1.0, score)), 3)


def compute_trend(ticker: str) -> TrendSignal:
    """Full technical assessment for *ticker*, using cached closing prices.

    Pulls from the ClosingPrice cache (populated nightly via Yahoo Finance).
    Falls back to live Polygon fetch if cache is empty. Results are cached
    in-memory for 1 hour to avoid repeated DB queries.
    """
    ticker = ticker.upper()
    now = time.time()

    # Check in-memory cache (lock only for the read to minimise contention)
    with _TREND_CACHE_LOCK:
        cached = _TREND_CACHE.get(ticker)
    if cached is not None:
        cached_signal, cached_at = cached
        age = now - cached_at
        if age < _TREND_CACHE_TTL:
            log.debug("trend_cache_hit", ticker=ticker, age_sec=round(age, 1))
            return cached_signal

    # Try to load from database cache first
    closes = _load_cached_closes(ticker)

    # Fall back to live Polygon fetch if cache is empty
    if not closes:
        from pmod.data.market import get_price_history

        history = get_price_history(ticker, days=120)
        closes = history.closes if history else []
        if closes:
            log.debug("trend_fallback_polygon", ticker=ticker, days=len(closes))

    signal = TrendSignal(
        ticker=ticker,
        rsi_14=compute_rsi(closes),
        sma_crossover=compute_sma_crossover(closes),
        momentum_score=compute_momentum_score(closes),
        volatility_pct=compute_volatility(closes),
        data_points=len(closes),
    )

    # Store in in-memory cache (evict oldest entries when the cache is full)
    with _TREND_CACHE_LOCK:
        if len(_TREND_CACHE) >= _TREND_CACHE_MAX:
            # Remove the 50 least-recently-cached entries
            evict = sorted(_TREND_CACHE, key=lambda t: _TREND_CACHE[t][1])[:50]
            for t in evict:
                del _TREND_CACHE[t]
        _TREND_CACHE[ticker] = (signal, now)

    return signal


def _load_cached_closes(ticker: str) -> list[float]:
    """Load closing prices for *ticker* from the database cache.

    Returns prices in chronological order (oldest to newest).
    """
    try:
        from datetime import datetime, timedelta

        from pmod.data.models import ClosingPrice, get_session

        # Load last 120 days of cached closes
        cutoff = datetime.utcnow() - timedelta(days=130)

        with get_session() as session:
            rows = (
                session.query(ClosingPrice)
                .filter(
                    ClosingPrice.ticker == ticker,
                    ClosingPrice.date >= cutoff,
                )
                .order_by(ClosingPrice.date.asc())
                .all()
            )

            if not rows:
                log.debug("cache_closes_empty", ticker=ticker)
                return []

            closes = [float(r.close) for r in rows]
            log.debug("cache_closes_loaded", ticker=ticker, days=len(closes))
            return closes

    except Exception as exc:
        log.warning("cache_closes_load_failed", ticker=ticker, error=str(exc)[:60])
        return []
