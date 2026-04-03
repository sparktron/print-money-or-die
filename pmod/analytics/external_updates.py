"""Update external account positions with current market prices.

Reads share counts from external_positions_config.csv, fetches current prices
from Yahoo Finance (free, no rate limit), and stores daily snapshots in
AccountDailyValue.
"""
from __future__ import annotations

import csv
from datetime import date, datetime
from pathlib import Path

import structlog

from pmod.data.models import AccountDailyValue, ExternalAccount, ExternalPosition, get_session
from pmod.data.yahoo_finance import get_closing_prices

log = structlog.get_logger()

# Location of the share config file relative to project root
_CONFIG_PATH = Path(__file__).parent.parent.parent / "external_positions_config.csv"


def _load_share_config() -> dict[tuple[str, str], float]:
    """Load share counts from external_positions_config.csv.

    Returns a dict mapping (account_name, ticker) → shares.
    If config file doesn't exist or has parsing errors, returns empty dict.
    """
    if not _CONFIG_PATH.exists():
        return {}

    config = {}
    try:
        with open(_CONFIG_PATH, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                if not row or not row.get("account_name") or not row.get("ticker"):
                    continue
                account_name = row["account_name"].strip()
                ticker = row["ticker"].strip().upper()
                try:
                    shares = float(row.get("shares", "0"))
                    config[(account_name, ticker)] = shares
                except ValueError:
                    log.warning("share_config_parse_error",
                               account=account_name, ticker=ticker,
                               shares_val=row.get("shares"))
    except Exception as exc:
        log.error("share_config_load_error", error=str(exc)[:120])

    return config


def update_external_account_daily_values() -> None:
    """Fetch current prices for configured external positions and store daily snapshot.

    For each (account, ticker, shares) in the config file:
    1. Fetch the latest closing price from Yahoo Finance (no rate limit)
    2. Calculate market_value = shares × price
    3. Update the ExternalPosition record
    4. Insert an AccountDailyValue record for today

    Idempotent — if a snapshot already exists for today, it will be skipped.
    """
    config = _load_share_config()
    if not config:
        log.debug("external_updates_no_config")
        return

    # Use UTC throughout so the "already stored today" check is consistent with
    # the UTC timestamps written to captured_at.  Using date.today() (local
    # time) would mismatch against datetime.utcnow() stored values.
    today_utc = datetime.utcnow().date()
    captured_accounts = set()
    prices_fetched = 0
    prices_failed = 0
    daily_values_stored = 0

    with get_session() as session:
        # Group config by account_name to calculate per-account totals
        account_tickers = {}
        for (acct_name, ticker), shares in config.items():
            if acct_name not in account_tickers:
                account_tickers[acct_name] = []
            account_tickers[acct_name].append((ticker, shares))

        for account_name, ticker_shares in account_tickers.items():
            account_total_value = 0.0

            for ticker, shares in ticker_shares:
                if shares <= 0:
                    continue

                # Fetch latest closing price from Yahoo Finance (no rate limit)
                closes = get_closing_prices(ticker, days=1)
                if not closes:
                    log.warning("external_price_fetch_failed",
                               account=account_name, ticker=ticker)
                    prices_failed += 1
                    continue

                # Get the latest close price
                latest_price = list(closes.values())[-1] if closes else None
                if latest_price is None:
                    prices_failed += 1
                    continue

                prices_fetched += 1
                market_value = shares * latest_price
                account_total_value += market_value

                # Update ExternalPosition record (find by account + ticker)
                # Join ExternalPosition with ExternalAccount by account_id
                position = (
                    session.query(ExternalPosition)
                    .join(ExternalAccount, ExternalPosition.account_id == ExternalAccount.id)
                    .filter(
                        ExternalAccount.name == account_name,
                        ExternalPosition.ticker == ticker,
                    )
                    .first()
                )

                if position:
                    position.current_price = latest_price
                    position.market_value = market_value
                    log.debug("external_position_updated",
                             account=account_name, ticker=ticker,
                             price=round(latest_price, 2),
                             value=round(market_value, 2))

            # Store daily snapshot for this account
            if account_total_value > 0:
                # Check if we already have a snapshot for today
                today_start_utc = datetime(today_utc.year, today_utc.month, today_utc.day)
                existing = (
                    session.query(AccountDailyValue)
                    .filter(
                        AccountDailyValue.account_name == account_name,
                        AccountDailyValue.captured_at >= today_start_utc,
                    )
                    .first()
                )

                if not existing:
                    snapshot = AccountDailyValue(
                        account_name=account_name,
                        total_value=account_total_value,
                        captured_at=datetime.utcnow(),
                    )
                    session.add(snapshot)
                    daily_values_stored += 1
                    log.debug("external_daily_value_stored",
                             account=account_name,
                             value=round(account_total_value, 2))

                captured_accounts.add(account_name)

    log.info("external_accounts_updated",
            accounts=len(captured_accounts),
            prices_fetched=prices_fetched,
            prices_failed=prices_failed,
            daily_values_stored=daily_values_stored)
