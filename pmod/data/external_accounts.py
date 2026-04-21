"""CSV import and query helpers for manually-tracked external accounts."""
from __future__ import annotations

import csv
import io
import re
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import IO

import structlog

from pmod.data.models import ExternalAccount, ExternalPosition, get_session

log = structlog.get_logger()

# Tickers must start with a letter and contain only letters, digits, dots,
# dashes, or slashes — and be no longer than 10 characters.
# This rejects footer rows, long sector-name strings, and all-numeric tokens.
_TICKER_RE = re.compile(r'^[A-Z][A-Z0-9./\-]{0,9}$')

# ---------------------------------------------------------------------------
# Column name normalisation
# Map every plausible header variant → canonical field name.
# ---------------------------------------------------------------------------
_HEADER_MAP: dict[str, str] = {
    # ticker
    "symbol": "ticker",
    "ticker": "ticker",
    "cusip": "ticker",
    # company name
    "description": "company_name",
    "name": "company_name",
    "company": "company_name",
    "company name": "company_name",
    "security": "company_name",
    "security name": "company_name",
    # shares
    "quantity": "shares",
    "shares": "shares",
    "units": "shares",
    # average / cost basis
    "average cost": "avg_cost",
    "avg cost": "avg_cost",
    "average price": "avg_cost",
    "cost basis": "avg_cost",
    "cost basis total": "avg_cost",  # Schwab exports total; handled below
    # current price
    "price": "current_price",
    "current price": "current_price",
    "last price": "current_price",
    "close price": "current_price",
    "nav": "current_price",
    # market value
    "market value": "market_value",
    "value": "market_value",
    "total value": "market_value",
    "account value": "market_value",
}


def _normalise_headers(raw_headers: list[str]) -> list[str]:
    return [_HEADER_MAP.get(h.lower().strip(), h.lower().strip()) for h in raw_headers]


def _parse_float(val: str) -> float | None:
    """Strip $, commas, %, parentheses then coerce to float. Returns None on failure."""
    val = val.strip().replace("$", "").replace(",", "").replace("%", "")
    # Schwab uses (1.23) for negatives
    if val.startswith("(") and val.endswith(")"):
        val = "-" + val[1:-1]
    try:
        return float(val)
    except ValueError:
        return None


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

@dataclass
class ImportedRow:
    ticker: str
    company_name: str | None
    shares: float | None
    avg_cost: float | None
    current_price: float | None
    market_value: float | None


def parse_csv(source: str | Path | IO[str]) -> list[ImportedRow]:
    """Parse a position CSV and return a list of ImportedRow objects.

    Accepts a file path, path string, or any readable text stream.
    Skips rows where ticker is empty, non-alphabetic (e.g. "Cash & Cash Investments"),
    or clearly a footer/total line.
    """
    if isinstance(source, (str, Path)):
        text = Path(source).read_text(encoding="utf-8-sig")  # utf-8-sig strips BOM
        reader = csv.DictReader(io.StringIO(text))
    else:
        reader = csv.DictReader(source)

    raw_headers = reader.fieldnames or []
    norm = _normalise_headers(raw_headers)
    # Build a mapping: canonical_name → original_header
    col_map: dict[str, str] = {}
    for orig, canonical in zip(raw_headers, norm):
        if canonical not in col_map:
            col_map[canonical] = orig

    def get(row: dict, canonical: str) -> str:
        orig = col_map.get(canonical, "")
        return row.get(orig, "").strip()

    rows: list[ImportedRow] = []
    for row in reader:
        ticker = get(row, "ticker").upper()
        # Reject blank, whitespace-containing, all-numeric, or implausibly long strings
        if not _TICKER_RE.match(ticker):
            continue
        # Skip common footer / cash-row patterns
        if ticker.lower() in ("total", "totals", "grand total", "account total", "cash"):
            continue

        shares_raw = _parse_float(get(row, "shares"))
        avg_cost_raw = _parse_float(get(row, "avg_cost"))
        price_raw = _parse_float(get(row, "current_price"))
        mv_raw = _parse_float(get(row, "market_value"))

        # If avg_cost came from a "cost basis total" column, convert to per-share
        if avg_cost_raw is not None and shares_raw and shares_raw > 0:
            # Heuristic: if avg_cost >> price, it's probably a total cost basis
            if price_raw and avg_cost_raw > price_raw * shares_raw * 0.5:
                avg_cost_raw = avg_cost_raw / shares_raw

        # Derive market_value from shares * price if not directly provided
        if mv_raw is None and shares_raw and price_raw:
            mv_raw = shares_raw * price_raw

        rows.append(
            ImportedRow(
                ticker=ticker,
                company_name=get(row, "company_name") or None,
                shares=shares_raw,
                avg_cost=avg_cost_raw,
                current_price=price_raw,
                market_value=mv_raw,
            )
        )

    return rows


def import_positions(
    account_name: str,
    rows: list[ImportedRow],
    account_type: str | None = None,
) -> int:
    """Upsert positions for *account_name*, replacing all previous positions.

    Returns the number of rows written.
    """
    with get_session() as session:
        acct = session.query(ExternalAccount).filter_by(name=account_name).first()
        if acct is None:
            acct = ExternalAccount(name=account_name, account_type=account_type)
            session.add(acct)
            session.flush()
        else:
            if account_type:
                acct.account_type = account_type
            # Delete existing positions for a clean replace
            session.query(ExternalPosition).filter_by(account_id=acct.id).delete()

        acct.last_imported_at = datetime.utcnow()

        for r in rows:
            session.add(
                ExternalPosition(
                    account_id=acct.id,
                    ticker=r.ticker,
                    company_name=r.company_name,
                    shares=r.shares,
                    avg_cost=r.avg_cost,
                    current_price=r.current_price,
                    market_value=r.market_value,
                )
            )

    log.info("external_positions_imported", account=account_name, count=len(rows))
    return len(rows)


def list_accounts() -> list[dict]:
    """Return all external accounts with position count and total value.

    Uses a single aggregated query rather than one SELECT per account.
    """
    from sqlalchemy import func as sa_func

    with get_session() as session:
        rows = (
            session.query(
                ExternalAccount,
                sa_func.count(ExternalPosition.id).label("position_count"),
                sa_func.coalesce(sa_func.sum(ExternalPosition.market_value), 0.0).label("total_value"),
            )
            .outerjoin(ExternalPosition, ExternalPosition.account_id == ExternalAccount.id)
            .group_by(ExternalAccount.id)
            .all()
        )
        return [
            {
                "id": acct.id,
                "name": acct.name,
                "account_type": acct.account_type,
                "last_imported_at": acct.last_imported_at,
                "position_count": position_count,
                "total_value": float(total_value),
            }
            for acct, position_count, total_value in rows
        ]


def get_positions(account_name: str) -> list[ExternalPosition]:
    """Return all positions for the named account."""
    with get_session() as session:
        acct = session.query(ExternalAccount).filter_by(name=account_name).first()
        if acct is None:
            return []
        return session.query(ExternalPosition).filter_by(account_id=acct.id).all()


def clear_account(account_name: str) -> bool:
    """Delete all positions (and the account record) for *account_name*.

    Returns True if the account existed, False if not found.
    """
    with get_session() as session:
        acct = session.query(ExternalAccount).filter_by(name=account_name).first()
        if acct is None:
            return False
        session.query(ExternalPosition).filter_by(account_id=acct.id).delete()
        session.delete(acct)
    log.info("external_account_cleared", account=account_name)
    return True
