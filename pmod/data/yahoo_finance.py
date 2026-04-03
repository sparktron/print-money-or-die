"""Fetch historical closing prices from Yahoo Finance (free, no API key required)."""
from __future__ import annotations

from datetime import date, datetime, timedelta

import structlog

log = structlog.get_logger()


def get_closing_prices(ticker: str, days: int = 120) -> dict[date, float] | None:
    """Fetch historical closing prices for *ticker* from Yahoo Finance.

    Args:
        ticker: Stock ticker (e.g., 'AAPL', 'VTI')
        days: Number of days of history to fetch

    Returns:
        Dict mapping date → closing price, or None if fetch fails.
        Most recent prices are included.
    """
    try:
        import yfinance
    except ImportError:
        log.error("yahoo_finance_import_failed", message="yfinance not installed. Run: pip install yfinance")
        return None

    try:
        end_date = date.today()
        start_date = end_date - timedelta(days=days + 30)  # Extra buffer for weekends/holidays

        df = yfinance.download(
            ticker.upper(),
            start=start_date,
            end=end_date,
            progress=False,
        )

        if df.empty:
            log.warning("yahoo_finance_no_data", ticker=ticker)
            return None

        # Convert DataFrame to dict mapping date → close price
        # row['Close'] may be a single-element Series in newer yfinance versions
        closes = {}
        for idx, row in df.iterrows():
            bar_date = idx.date() if hasattr(idx, 'date') else idx
            close_val = row['Close']
            closes[bar_date] = float(close_val.iloc[0]) if hasattr(close_val, 'iloc') else float(close_val)

        log.debug("yahoo_finance_fetched", ticker=ticker, days=len(closes))
        return closes

    except Exception as exc:
        log.error("yahoo_finance_fetch_failed", ticker=ticker, error=str(exc)[:120])
        return None
