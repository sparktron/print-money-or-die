"""Market data ingestion — quotes, history, and news via Polygon.io.

Polygon free tier: 5 API calls per minute.  All calls go through the
module-level ``polygon_limiter`` and ``@with_backoff`` decorator so the
rest of the codebase never has to think about rate limits.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, timedelta

import httpx
import structlog

from pmod.config import get_settings
from pmod.utils.retry import polygon_limiter, with_backoff

log = structlog.get_logger()

_BASE = "https://api.polygon.io"


# ── Data classes ──────────────────────────────────────────────────────────

@dataclass
class Quote:
    """Latest-day snapshot for a single ticker."""
    ticker: str
    price: float
    change_pct: float
    prev_close: float
    volume: int
    market_cap: float | None = None


@dataclass
class PriceBar:
    """Single OHLCV bar."""
    date: date
    open: float
    high: float
    low: float
    close: float
    volume: int


@dataclass
class PriceHistory:
    """Time series of daily price bars for a ticker."""
    ticker: str
    bars: list[PriceBar] = field(default_factory=list)

    @property
    def closes(self) -> list[float]:
        return [b.close for b in self.bars]

    @property
    def dates(self) -> list[date]:
        return [b.date for b in self.bars]

    @property
    def volumes(self) -> list[int]:
        return [b.volume for b in self.bars]


@dataclass
class NewsArticle:
    """Summary of a single news article."""
    title: str
    url: str
    published: str
    source: str
    tickers: list[str] = field(default_factory=list)


# ── Internal helpers ──────────────────────────────────────────────────────

def _api_key() -> str:
    key = get_settings().polygon_api_key
    if not key:
        raise RuntimeError(
            "POLYGON_API_KEY is not set. Add it to your .env file."
        )
    return key


def _get(path: str, params: dict | None = None) -> dict:
    """Rate-limited GET against Polygon.io with retry."""
    polygon_limiter.acquire()
    all_params = {"apiKey": _api_key(), **(params or {})}
    resp = httpx.get(f"{_BASE}{path}", params=all_params, timeout=15)
    resp.raise_for_status()
    return resp.json()


# ── Public API ────────────────────────────────────────────────────────────

@with_backoff(max_retries=2, base_delay=2.0, retry_on=(httpx.HTTPError,))
def get_quote(ticker: str) -> Quote | None:
    """Fetch the previous-day close snapshot for *ticker*.

    Uses Polygon's ``/v2/aggs/ticker/{ticker}/prev`` endpoint (1 API call,
    free-tier eligible).  Returns None if the ticker is not found.
    """
    try:
        data = _get(f"/v2/aggs/ticker/{ticker.upper()}/prev")
    except httpx.HTTPStatusError as exc:
        if exc.response.status_code == 404:
            return None
        raise

    results = data.get("results", [])
    if not results:
        return None

    r = results[0]
    close = float(r.get("c", 0))
    open_price = float(r.get("o", close))
    # change_pct: intraday return for the previous trading session (close vs open).
    # The /prev endpoint returns only one bar so a true day-over-day comparison
    # is not possible without an additional API call.
    change_pct = ((close - open_price) / open_price * 100) if open_price else 0.0

    return Quote(
        ticker=ticker.upper(),
        price=close,
        change_pct=round(change_pct, 2),
        # prev_close stores the session open so callers have a meaningful
        # reference price distinct from the closing price.
        prev_close=open_price,
        volume=int(r.get("v", 0)),
    )


@with_backoff(max_retries=2, base_delay=2.0, retry_on=(httpx.HTTPError,))
def get_price_history(ticker: str, days: int = 90) -> PriceHistory | None:
    """Fetch daily OHLCV bars for the last *days* trading days.

    Uses ``/v2/aggs/ticker/{ticker}/range/1/day/{from}/{to}`` (1 API call).
    Returns None if no data is available.
    """
    end = date.today()
    start = end - timedelta(days=days)
    try:
        data = _get(
            f"/v2/aggs/ticker/{ticker.upper()}/range/1/day/{start}/{end}",
            params={"adjusted": "true", "sort": "asc", "limit": str(days + 30)},
        )
    except httpx.HTTPStatusError as exc:
        if exc.response.status_code == 404:
            return None
        raise

    results = data.get("results", [])
    if not results:
        return None

    bars = []
    for r in results:
        ts_ms = r.get("t", 0)
        bar_date = date.fromtimestamp(ts_ms / 1000) if ts_ms else end
        bars.append(PriceBar(
            date=bar_date,
            open=float(r.get("o", 0)),
            high=float(r.get("h", 0)),
            low=float(r.get("l", 0)),
            close=float(r.get("c", 0)),
            volume=int(r.get("v", 0)),
        ))

    return PriceHistory(ticker=ticker.upper(), bars=bars)


@with_backoff(max_retries=2, base_delay=2.0, retry_on=(httpx.HTTPError,))
def get_ticker_news(ticker: str, limit: int = 5) -> list[NewsArticle]:
    """Fetch recent news articles mentioning *ticker*.

    Uses ``/v2/reference/news`` (1 API call).
    """
    try:
        data = _get(
            "/v2/reference/news",
            params={"ticker": ticker.upper(), "limit": str(limit), "order": "desc"},
        )
    except httpx.HTTPStatusError:
        return []

    articles = []
    for item in data.get("results", []):
        articles.append(NewsArticle(
            title=item.get("title", ""),
            url=item.get("article_url", ""),
            published=item.get("published_utc", ""),
            source=item.get("publisher", {}).get("name", ""),
            tickers=item.get("tickers", []),
        ))
    return articles


def get_quotes_batch(tickers: list[str]) -> dict[str, Quote]:
    """Fetch quotes for multiple tickers, respecting rate limits.

    Returns a dict mapping ticker → Quote.  Tickers that fail silently
    are omitted from the result.
    """
    results: dict[str, Quote] = {}
    for ticker in tickers:
        try:
            quote = get_quote(ticker)
            if quote is not None:
                results[ticker.upper()] = quote
        except Exception as exc:
            log.warning("quote_fetch_failed", ticker=ticker, error=str(exc)[:80])
    return results
