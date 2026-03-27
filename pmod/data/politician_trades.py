"""Politician trade data ingestion from official US government sources.

Senate data: scraped from efdsearch.senate.gov (no API key required).
  - Two-step flow: GET the search page to obtain a CSRF token, then POST
    to the data endpoint which returns JSON rows of PTR filings.
  - Each filing is then fetched individually to extract transaction rows
    from the HTML table (ticker, type, amount, date).

House data: individual PTR filings are PDFs — not implemented without a
  PDF-parsing library. Run `pmod politicians fetch` to get Senate data only.
"""

import re
from datetime import datetime, timedelta
from typing import Any

import httpx
import structlog

from pmod.data.models import PoliticianTrade, get_session

log = structlog.get_logger()

_SENATE_SEARCH_URL = "https://efdsearch.senate.gov/search/"
_SENATE_HOME_URL = "https://efdsearch.senate.gov/search/home/"
_SENATE_DATA_URL = "https://efdsearch.senate.gov/search/report/data/"
_SENATE_REPORT_BASE = "https://efdsearch.senate.gov"
_SENATE_PTR_REPORT_TYPE = "11"

_DATE_FORMATS = ["%Y-%m-%d", "%m/%d/%Y", "%Y/%m/%d", "%m/%d/%Y %H:%M:%S"]

_AMOUNT_MAP: dict[str, tuple[int, int | None]] = {
    "$1,001 - $15,000": (1_001, 15_000),
    "$15,001 - $50,000": (15_001, 50_000),
    "$50,001 - $100,000": (50_001, 100_000),
    "$100,001 - $250,000": (100_001, 250_000),
    "$250,001 - $500,000": (250_001, 500_000),
    "$500,001 - $1,000,000": (500_001, 1_000_000),
    "$1,000,001 - $5,000,000": (1_000_001, 5_000_000),
    "$5,000,001 - $25,000,000": (5_000_001, 25_000_000),
    "$25,000,001 - $50,000,000": (25_000_001, 50_000_000),
    "Over $50,000,000": (50_000_001, None),
}


def _parse_date(raw: str | None) -> datetime | None:
    """Try each known date format; return None if all fail."""
    if not raw:
        return None
    cleaned = raw.strip()
    for fmt in _DATE_FORMATS:
        try:
            return datetime.strptime(cleaned, fmt)
        except ValueError:
            continue
    return None


def _parse_amount(raw: str | None) -> tuple[int | None, int | None]:
    """Parse a disclosure amount range string into (low, high) ints."""
    if not raw:
        return None, None
    cleaned = re.sub(r"\s+", " ", raw.strip())
    return _AMOUNT_MAP.get(cleaned, (None, None))


def _normalize_trade_type(raw: str) -> str | None:
    """Normalize trade type strings to canonical enum values."""
    lower = raw.lower().strip()
    if "purchase" in lower or lower == "buy":
        return "purchase"
    if "sale (partial)" in lower or "partial" in lower:
        return "sale_partial"
    if "sale" in lower or "sell" in lower:
        return "sale"
    if "exchange" in lower:
        return "exchange"
    return None


def _strip_tags(html: str) -> str:
    """Remove all HTML tags from a string."""
    return re.sub(r"<[^>]+>", "", html).strip()


def _extract_csrf_and_agree(client: httpx.Client) -> str:
    """Load the Senate EFD home page, submit the terms agreement, and return CSRF.

    The site requires POSTing the prohibition agreement to /search/home/ before
    individual PTR report pages are accessible. Without this step every report
    URL redirects back to the home page and returns no data.
    """
    # GET /search/ redirects to /search/home/ where the agreement form lives.
    resp = client.get(_SENATE_SEARCH_URL)
    resp.raise_for_status()
    csrf = client.cookies.get("csrftoken", "")
    if not csrf:
        m = re.search(r'name="csrfmiddlewaretoken"\s+value="([^"]+)"', resp.text)
        if not m:
            raise RuntimeError(
                "Could not extract CSRF token from efdsearch.senate.gov — "
                "the site structure may have changed."
            )
        csrf = m.group(1)

    # Submit the agreement form to /search/home/ (not /search/).
    client.post(
        _SENATE_HOME_URL,
        data={"prohibition_agreement": "1", "csrfmiddlewaretoken": csrf},
        headers={"Referer": _SENATE_HOME_URL},
    )
    return client.cookies.get("csrftoken", csrf)


def _search_ptrs(
    client: httpx.Client,
    csrf: str,
    start: int = 0,
    length: int = 100,
    days: int = 90,
) -> dict[str, Any]:
    """POST to Senate EFD to get a page of recent PTR filings."""
    from_date = (datetime.utcnow() - timedelta(days=days)).strftime(
        "%m/%d/%Y 00:00:00"
    )
    resp = client.post(
        _SENATE_DATA_URL,
        data={
            "start": str(start),
            "length": str(length),
            "report_types[]": _SENATE_PTR_REPORT_TYPE,
            "submitted_start_date": from_date,
            "submitted_end_date": "",
            "filer_first_name": "",
            "filer_last_name": "",
            "filer_suffix": "",
            "agreement_number": "",
            "request_type": "search",
        },
        headers={
            "X-CSRFToken": csrf,
            "X-Requested-With": "XMLHttpRequest",
            "Referer": _SENATE_SEARCH_URL,
        },
    )
    resp.raise_for_status()
    return resp.json()  # type: ignore[no-any-return]


def _parse_filing_row(row: list[str]) -> tuple[str, str, str | None] | None:
    """Return (senator_name, disclosure_date_str, report_url) from a search row.

    Actual Senate EFD search result row layout (5 fields):
      [0] first_name   e.g. "David H"
      [1] last_name    e.g. "McCormick"
      [2] full_name    e.g. "McCormick, David H. (Senator)"
      [3] link_cell    HTML anchor with the PTR report href
      [4] date         plain text "MM/DD/YYYY"
    """
    if len(row) < 5:
        return None
    name = _strip_tags(row[2])
    date_str = _strip_tags(row[4]).strip()
    m = re.search(r'href=["\']([^"\']+)["\']', row[3])
    if not m:
        return None
    path = m.group(1)
    url = path if path.startswith("http") else _SENATE_REPORT_BASE + path
    if not name or not url:
        return None
    return name, date_str, url


def _parse_ptr_report(html: str, senator: str, disclosure_date: datetime | None, report_url: str = "") -> list[PoliticianTrade]:
    """Parse an individual Senate PTR report page into trade records.

    Actual table column layout (9 fields, 0-indexed):
      [0] #            row number (skip)
      [1] Date         transaction date MM/DD/YYYY
      [2] Owner        "Self" / "Spouse" / "Joint"
      [3] Ticker       stock symbol or "--" for non-equity assets
      [4] Asset Name   company / instrument name
      [5] Asset Type   "Stock", "Municipal Security", etc.
      [6] Type         "Purchase", "Sale (Full)", "Sale (Partial)", etc.
      [7] Amount       "$X - $Y" range string
      [8] Comment
    """
    trades: list[PoliticianTrade] = []
    for row_html in re.findall(r"<tr[^>]*>(.*?)</tr>", html, re.DOTALL | re.IGNORECASE):
        cells = [
            _strip_tags(c)
            for c in re.findall(r"<td[^>]*>(.*?)</td>", row_html, re.DOTALL | re.IGNORECASE)
        ]
        if len(cells) < 8:
            continue
        ticker = cells[3].strip().upper()
        if not ticker or ticker in ("--", "N/A", "TICKER", ""):
            continue
        # Filter to stocks only (cells[5] is asset type)
        asset_type = cells[5].lower()
        if asset_type and asset_type not in ("stock", "stocks", ""):
            continue
        trade_type = _normalize_trade_type(cells[6])
        if trade_type is None:
            continue
        tx_date = _parse_date(cells[1])
        amount_low, amount_high = _parse_amount(cells[7])
        trades.append(
            PoliticianTrade(
                politician_name=senator,
                chamber="senate",
                ticker=ticker,
                company_name=cells[4] or None,
                trade_type=trade_type,
                transaction_date=tx_date,
                disclosure_date=disclosure_date or tx_date,
                amount_low=amount_low,
                amount_high=amount_high,
                report_url=report_url or None,
            )
        )
    return trades


def _fetch_senate_trades(days: int = 90, max_filings: int = 300) -> list[PoliticianTrade]:
    """Scrape Senate PTR disclosures from efdsearch.senate.gov.

    Paginates through filings up to max_filings, then fetches each
    individual report page to extract the transaction rows.
    """
    all_trades: list[PoliticianTrade] = []

    with httpx.Client(follow_redirects=True, timeout=30) as client:
        log.info("fetching Senate EFD CSRF token and submitting agreement")
        csrf = _extract_csrf_and_agree(client)

        start = 0
        length = 100
        total_seen = 0

        while total_seen < max_filings:
            log.info("searching Senate PTR filings", start=start, days=days)
            data = _search_ptrs(client, csrf, start=start, length=length, days=days)
            rows: list[list[str]] = data.get("data", [])
            if not rows:
                break

            for row in rows:
                parsed = _parse_filing_row(row)
                if parsed is None:
                    continue
                senator, date_str, url = parsed
                disclosure_date = _parse_date(date_str)

                try:
                    report_resp = client.get(url)
                    report_resp.raise_for_status()
                    trades = _parse_ptr_report(report_resp.text, senator, disclosure_date, report_url=url)
                    all_trades.extend(trades)
                    log.debug("parsed PTR report", senator=senator, trades=len(trades))
                except Exception as exc:
                    log.warning("failed to fetch PTR report", url=url, error=str(exc))

            total_seen += len(rows)
            if len(rows) < length:
                break  # last page
            start += length

    log.info("senate trades fetched", count=len(all_trades))
    return all_trades


def fetch_and_store_trades(days: int = 90) -> dict[str, int]:
    """Fetch Senate PTR disclosures and store them in the DB.

    House PTR data is not available without PDF parsing (individual filings
    are published as PDFs only by the House Clerk).

    Returns counts: {"senate": N, "errors": K}.
    """
    session = get_session()
    counts: dict[str, int] = {"senate": 0, "errors": 0}

    try:
        trades = _fetch_senate_trades(days=days)
        session.query(PoliticianTrade).filter(
            PoliticianTrade.chamber == "senate"
        ).delete()

        for trade in trades:
            if trade.ticker:
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
    """Return the most-traded tickers by politicians in the given window."""
    from collections import defaultdict

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


def get_all_politician_summaries(days: int = 365) -> list[dict]:
    """Return each unique politician with aggregate trade stats, sorted by trade count."""
    from collections import defaultdict

    session = get_session()
    try:
        cutoff = datetime.utcnow() - timedelta(days=days)
        trades = session.query(PoliticianTrade).filter(
            PoliticianTrade.disclosure_date >= cutoff
        ).all()
    finally:
        session.close()

    stats: dict[str, dict] = defaultdict(lambda: {
        "buy_count": 0, "sell_count": 0, "tickers": set(),
        "chamber": "", "party": "", "state": "", "latest_date": None,
    })
    for t in trades:
        s = stats[t.politician_name]
        s["chamber"] = t.chamber or s["chamber"]
        s["party"] = t.party or s["party"]
        s["state"] = t.state or s["state"]
        if t.trade_type == "purchase":
            s["buy_count"] += 1
        elif t.trade_type in ("sale", "sale_partial"):
            s["sell_count"] += 1
        s["tickers"].add(t.ticker)
        if t.disclosure_date and (s["latest_date"] is None or t.disclosure_date > s["latest_date"]):
            s["latest_date"] = t.disclosure_date

    results = [
        {
            "name": name,
            "chamber": s["chamber"],
            "party": s["party"],
            "state": s["state"],
            "buy_count": s["buy_count"],
            "sell_count": s["sell_count"],
            "total_trades": s["buy_count"] + s["sell_count"],
            "unique_tickers": len(s["tickers"]),
            "latest_date": s["latest_date"],
        }
        for name, s in stats.items()
    ]
    results.sort(key=lambda x: x["total_trades"], reverse=True)
    return results


def get_politician_trades_history(name: str, days: int = 730) -> list[PoliticianTrade]:
    """Return all trades for a specific politician, newest first."""
    session = get_session()
    try:
        cutoff = datetime.utcnow() - timedelta(days=days)
        return (
            session.query(PoliticianTrade)
            .filter(
                PoliticianTrade.politician_name == name,
                PoliticianTrade.disclosure_date >= cutoff,
            )
            .order_by(PoliticianTrade.disclosure_date.desc())
            .all()
        )
    finally:
        session.close()


def get_politicians_for_ticker(ticker: str, days: int = 365) -> list[dict]:
    """Return every trade on a ticker with politician details, newest first."""
    session = get_session()
    try:
        cutoff = datetime.utcnow() - timedelta(days=days)
        trades = (
            session.query(PoliticianTrade)
            .filter(
                PoliticianTrade.ticker == ticker.upper(),
                PoliticianTrade.disclosure_date >= cutoff,
            )
            .order_by(PoliticianTrade.disclosure_date.desc())
            .all()
        )
    finally:
        session.close()

    results = []
    for t in trades:
        if t.amount_low and t.amount_high:
            amount = f"${t.amount_low:,} – ${t.amount_high:,}"
        elif t.amount_low:
            amount = f"${t.amount_low:,}+"
        else:
            amount = "Undisclosed"
        results.append({
            "politician_name": t.politician_name,
            "chamber": t.chamber or "",
            "party": t.party or "",
            "state": t.state or "",
            "trade_type": t.trade_type,
            "disclosure_date": t.disclosure_date.strftime("%Y-%m-%d") if t.disclosure_date else "N/A",
            "amount": amount,
            "report_url": t.report_url or "",
        })
    return results
