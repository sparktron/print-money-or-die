"""Politician trade data ingestion from public congressional disclosure APIs.

Uses the House Stock Watcher and Senate Stock Watcher public datasets,
which aggregate STOCK Act filings from house.gov and senate.gov.
No API key required.
"""

import re
from datetime import datetime
from typing import Any

import httpx
import structlog

from pmod.data.models import PoliticianTrade, get_session

log = structlog.get_logger()

_HOUSE_URL = (
    "https://house-stock-watcher-data.s3-us-west-2.amazonaws.com"
    "/data/all_transactions.json"
)
_SENATE_URL = (
    "https://senate-stock-watcher-data.s3-us-west-2.amazonaws.com"
    "/aggregate/all_transactions.json"
)

# Maps disclosure amount strings to (low, high) integer dollar values
_AMOUNT_MAP: dict[str, tuple[int, int]] = {
    "$1,001 - $15,000": (1_001, 15_000),
    "$15,001 - $50,000": (15_001, 50_000),
    "$50,001 - $100,000": (50_001, 100_000),
    "$100,001 - $250,000": (100_001, 250_000),
    "$250,001 - $500,000": (250_001, 500_000),
    "$500,001 - $1,000,000": (500_001, 1_000_000),
    "$1,000,001 - $5,000,000": (1_000_001, 5_000_000),
    "$5,000,001 - $25,000,000": (5_000_001, 25_000_000),
    "$25,000,001 - $50,000,000": (25_000_001, 50_000_000),
    "Over $50,000,000": (50_000_001, None),  # type: ignore[dict-item]
}

_DATE_FORMATS = ["%Y-%m-%d", "%m/%d/%Y", "%Y/%m/%d"]


def _parse_date(raw: str | None) -> datetime | None:
    """Try each known date format, return None if all fail."""
    if not raw:
        return None
    for fmt in _DATE_FORMATS:
        try:
            return datetime.strptime(raw.strip(), fmt)
        except ValueError:
            continue
    return None


def _parse_amount(raw: str | None) -> tuple[int | None, int | None]:
    """Parse a disclosure amount range string into (low, high) ints."""
    if not raw:
        return None, None
    cleaned = re.sub(r"\s+", " ", raw.strip())
    if cleaned in _AMOUNT_MAP:
        return _AMOUNT_MAP[cleaned]
    return None, None


def _normalize_trade_type(raw: str) -> str | None:
    """Normalize trade type strings to canonical enum values."""
    lower = raw.lower().strip()
    if "purchase" in lower or "buy" in lower:
        return "purchase"
    if "sale (partial)" in lower or "partial" in lower:
        return "sale_partial"
    if "sale" in lower or "sell" in lower:
        return "sale"
    if "exchange" in lower:
        return "exchange"
    return None


def _fetch_json(url: str, timeout: int = 30) -> list[dict[str, Any]]:
    """Fetch JSON from a URL with a timeout; raise on HTTP errors."""
    log.info("fetching politician trade data", url=url)
    resp = httpx.get(url, timeout=timeout, follow_redirects=True)
    resp.raise_for_status()
    return resp.json()  # type: ignore[no-any-return]


def _parse_house_record(record: dict[str, Any]) -> PoliticianTrade | None:
    """Convert a raw house stock watcher record to a PoliticianTrade."""
    ticker = (record.get("ticker") or "").strip().upper()
    if not ticker or ticker in ("--", "N/A", ""):
        return None

    trade_type = _normalize_trade_type(record.get("type") or "")
    if trade_type is None:
        return None

    disclosure_date = _parse_date(record.get("disclosure_date"))
    if disclosure_date is None:
        return None

    amount_low, amount_high = _parse_amount(record.get("amount"))

    return PoliticianTrade(
        politician_name=record.get("representative") or "Unknown",
        chamber="house",
        party=record.get("party"),
        state=(record.get("district") or "")[:2] or None,
        ticker=ticker,
        company_name=record.get("asset_description"),
        trade_type=trade_type,
        transaction_date=_parse_date(record.get("transaction_date")),
        disclosure_date=disclosure_date,
        amount_low=amount_low,
        amount_high=amount_high,
    )


def _parse_senate_record(record: dict[str, Any]) -> PoliticianTrade | None:
    """Convert a raw senate stock watcher record to a PoliticianTrade."""
    ticker = (record.get("ticker") or "").strip().upper()
    if not ticker or ticker in ("--", "N/A", ""):
        return None

    trade_type = _normalize_trade_type(record.get("type") or "")
    if trade_type is None:
        return None

    disclosure_date = _parse_date(record.get("disclosure_date"))
    if disclosure_date is None:
        return None

    amount_low, amount_high = _parse_amount(record.get("amount"))

    return PoliticianTrade(
        politician_name=record.get("senator") or "Unknown",
        chamber="senate",
        party=None,
        state=None,
        ticker=ticker,
        company_name=record.get("asset_description"),
        trade_type=trade_type,
        transaction_date=_parse_date(record.get("transaction_date")),
        disclosure_date=disclosure_date,
        amount_low=amount_low,
        amount_high=amount_high,
    )


def fetch_and_store_trades() -> dict[str, int]:
    """Fetch all congressional trade disclosures and upsert into the DB.

    Returns a dict with counts: {"house": N, "senate": M, "errors": K}.
    """
    session = get_session()
    counts: dict[str, int] = {"house": 0, "senate": 0, "errors": 0}

    try:
        # Clear existing records before refreshing (full snapshot data)
        session.query(PoliticianTrade).delete()

        for raw in _fetch_json(_HOUSE_URL):
            trade = _parse_house_record(raw)
            if trade is not None:
                session.add(trade)
                counts["house"] += 1
            else:
                counts["errors"] += 1

        for raw in _fetch_json(_SENATE_URL):
            trade = _parse_senate_record(raw)
            if trade is not None:
                session.add(trade)
                counts["senate"] += 1
            else:
                counts["errors"] += 1

        session.commit()
        log.info("politician trades stored", **counts)
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()

    return counts


def get_recent_trades(
    days: int = 90, ticker: str | None = None
) -> list[PoliticianTrade]:
    """Return recent trades from the DB, optionally filtered by ticker."""
    from datetime import timedelta

    session = get_session()
    try:
        cutoff = datetime.utcnow() - timedelta(days=days)
        query = session.query(PoliticianTrade).filter(
            PoliticianTrade.disclosure_date >= cutoff
        )
        if ticker:
            query = query.filter(PoliticianTrade.ticker == ticker.upper())
        return query.order_by(PoliticianTrade.disclosure_date.desc()).all()
    finally:
        session.close()


def get_top_tickers(days: int = 90, limit: int = 20) -> list[dict[str, Any]]:
    """Return the most-traded tickers by politicians in the given window.

    Each entry: {"ticker": str, "buy_count": int, "sell_count": int, "net": int}.
    """
    from collections import defaultdict
    from datetime import timedelta

    session = get_session()
    try:
        cutoff = datetime.utcnow() - timedelta(days=days)
        trades = (
            session.query(PoliticianTrade)
            .filter(PoliticianTrade.disclosure_date >= cutoff)
            .all()
        )
    finally:
        session.close()

    counts: dict[str, dict[str, int]] = defaultdict(
        lambda: {"buy_count": 0, "sell_count": 0}
    )
    for t in trades:
        if t.trade_type == "purchase":
            counts[t.ticker]["buy_count"] += 1
        elif t.trade_type in ("sale", "sale_partial"):
            counts[t.ticker]["sell_count"] += 1

    ranked = [
        {
            "ticker": ticker,
            "buy_count": v["buy_count"],
            "sell_count": v["sell_count"],
            "net": v["buy_count"] - v["sell_count"],
        }
        for ticker, v in counts.items()
        if v["buy_count"] + v["sell_count"] > 0
    ]
    ranked.sort(key=lambda x: x["buy_count"] + x["sell_count"], reverse=True)
    return ranked[:limit]
