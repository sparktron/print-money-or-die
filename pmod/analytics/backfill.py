"""Backfill historical portfolio and benchmark snapshots.

For each position we try to get price history in this order:
  1. Direct Polygon fetch (works for stocks/ETFs like RDDT)
  2. ETF proxy fetch (maps mutual fund tickers to liquid ETF equivalents)
  3. SPY scaling (last resort — only used if both above fail)

Per-account daily values are stored in AccountDailyValue so that
per-account performance charts are fast (no API calls at render time).
"""
from __future__ import annotations

from collections import defaultdict
from datetime import date, datetime, timedelta
from typing import Callable

import structlog

from pmod.data.market import get_price_history
from pmod.data.models import (
    AccountDailyValue,
    BenchmarkSnapshot,
    PortfolioSnapshot,
    get_session,
)

log = structlog.get_logger()

# ── ETF proxy map ──────────────────────────────────────────────────────────
# Maps mutual fund / institutional tickers that Polygon doesn't carry to
# liquid ETF equivalents that track the same underlying index/strategy.
TICKER_PROXIES: dict[str, str] = {
    # Vanguard index funds
    "VBILX": "BND",    # Intermediate-Term Bond Index → Vanguard Total Bond ETF
    "VIMAX": "VO",     # Mid-Cap Index Adm → Vanguard Mid-Cap ETF
    "VSIAX": "VBR",    # Small Cap Value Index Adm → Vanguard Small-Cap Value ETF
    "VSMAX": "VB",     # Small Cap Index Adm → Vanguard Small-Cap ETF
    "VSGAX": "VBK",    # S/C Growth Index Adm → Vanguard Small-Cap Growth ETF
    "VTWNX": "AOM",    # Target Rtmnt 2020-Inv → iShares Core Moderate Allocation
    "VLXVX": "VT",     # Target Rtmnt 2065-Inv → Vanguard Total World (growth)
    # Fidelity
    "FXAIX": "IVV",    # 500 Index-IPrem → iShares Core S&P 500 ETF
    "FDKLX": "VT",     # Freedom Index 2060 → Vanguard Total World (aggressive)
    # American Beacon
    "AASRX": "VBR",    # Sm Cap Val-R6 → Vanguard Small-Cap Value ETF
    "AAERX": "EFA",    # Intl Equity-R6 → iShares MSCI EAFE
    # iShares institutional
    "BIEKX": "EFA",    # MSCI EAFE Intl Class K → iShares MSCI EAFE ETF
    # T. Rowe Price
    "TROIX": "EFA",    # Overseas Stock Class I → iShares MSCI EAFE
    # State Street
    "SVSPX": "SPY",    # Equity 500 Class K → SPDR S&P 500 ETF
}


# ── Position collection ────────────────────────────────────────────────────

def _collect_accounts() -> dict[str, list[tuple[str, float, float]]]:
    """Return {account_name: [(ticker, shares, market_value_today), ...]}."""
    accounts: dict[str, list[tuple[str, float, float]]] = {}

    try:
        from pmod.broker.schwab import get_all_account_summaries
        for summary in get_all_account_summaries():
            label = f"Schwab ···{summary.account_number[-4:]}" if summary.account_number else "Schwab"
            positions = []
            for p in summary.positions:
                if p.shares and p.shares > 0:
                    positions.append((p.ticker.upper(), p.shares, p.market_value))
            accounts[label] = positions
    except Exception as exc:
        log.warning("backfill_schwab_fetch_failed", error=str(exc)[:120])

    try:
        from pmod.data.external_accounts import get_positions, list_accounts
        for acct in list_accounts():
            positions = []
            for p in get_positions(acct["name"]):
                mv = p.market_value or 0.0
                if mv > 0:
                    # External positions are always reconstructed via price-ratio
                    # scaling (mv_today × proxy_historical / proxy_latest) rather
                    # than shares × historical_price.  This is because:
                    #   1. Many brokerage CSV exports have inconsistent share counts.
                    #   2. Proxy ETF prices (e.g. VO for VIMAX) have different per-
                    #      share price levels than the actual fund, so implied shares
                    #      from (mv / fund_price) × proxy_price gives wrong results.
                    # Passing shares=0 ensures the ratio-scaling branch is always used.
                    positions.append((p.ticker.upper(), 0.0, mv))
            accounts[acct["name"]] = positions
    except Exception as exc:
        log.warning("backfill_external_fetch_failed", error=str(exc)[:120])

    return accounts


# ── Existing date helpers ──────────────────────────────────────────────────

def _existing_portfolio_dates() -> set[date]:
    with get_session() as s:
        return {r[0].date() for r in s.query(PortfolioSnapshot.captured_at).all()}


def _existing_benchmark_dates() -> set[date]:
    with get_session() as s:
        return {r[0].date() for r in s.query(BenchmarkSnapshot.captured_at).all()}


def _existing_account_dates(account_name: str) -> set[date]:
    with get_session() as s:
        return {
            r[0].date()
            for r in s.query(AccountDailyValue.captured_at)
            .filter(AccountDailyValue.account_name == account_name)
            .all()
        }


# ── Price history fetcher with proxy fallback ──────────────────────────────

def _fetch_prices(ticker: str, days: int) -> tuple[dict[date, float], str]:
    """Fetch daily closes for *ticker*, falling back to its ETF proxy.

    Returns (price_dict, source) where source is one of:
    "direct", "proxy:<ETF>", or "none".
    """
    hist = get_price_history(ticker, days=days + 10)
    if hist and hist.bars:
        return {bar.date: bar.close for bar in hist.bars}, "direct"

    proxy = TICKER_PROXIES.get(ticker)
    if proxy:
        hist = get_price_history(proxy, days=days + 10)
        if hist and hist.bars:
            return {bar.date: bar.close for bar in hist.bars}, f"proxy:{proxy}"

    return {}, "none"


# ── Main backfill ──────────────────────────────────────────────────────────

def backfill_portfolio_history(
    days: int = 365,
    on_progress: Callable[[str], None] | None = None,
) -> dict:
    """Populate PortfolioSnapshot, BenchmarkSnapshot, and AccountDailyValue.

    Returns summary dict: new_portfolio, new_benchmark, new_account_days,
    skipped_tickers.
    """
    def _progress(msg: str) -> None:
        if on_progress:
            on_progress(msg)
        log.info("backfill_progress", msg=msg)

    accounts = _collect_accounts()
    if not accounts:
        return {"new_portfolio": 0, "new_benchmark": 0, "new_account_days": 0, "skipped_tickers": []}

    # Collect all unique tickers across all accounts
    all_tickers: set[str] = {t for positions in accounts.values() for t, _, _ in positions}
    _progress(f"Fetching price history for {len(all_tickers)} tickers + SPY…")

    # ── Fetch SPY benchmark ────────────────────────────────────────────────
    _progress("  SPY…")
    spy_hist = get_price_history("SPY", days=days + 10)
    spy_prices: dict[date, float] = {}
    if spy_hist and spy_hist.bars:
        spy_prices = {bar.date: bar.close for bar in spy_hist.bars}
    spy_today = spy_prices.get(max(spy_prices)) if spy_prices else None

    # ── Fetch each ticker (direct or proxy) ───────────────────────────────
    price_data: dict[str, dict[date, float]] = {}   # ticker → {date: close}
    proxy_used: dict[str, str] = {}
    skipped: list[str] = []

    already_fetched: dict[str, dict[date, float]] = {}  # proxy ETF dedup cache

    for ticker in sorted(all_tickers):
        _progress(f"  {ticker}…")
        proxy = TICKER_PROXIES.get(ticker)

        # Check if we already fetched this proxy for another ticker
        if proxy and proxy in already_fetched:
            price_data[ticker] = already_fetched[proxy]
            proxy_used[ticker] = f"proxy:{proxy}"
            continue

        prices, source = _fetch_prices(ticker, days)
        if prices:
            price_data[ticker] = prices
            proxy_used[ticker] = source
            if source.startswith("proxy:") and proxy:
                already_fetched[proxy] = prices
        else:
            skipped.append(ticker)
            log.warning("backfill_no_data", ticker=ticker)

    # ── Build union of trading days ────────────────────────────────────────
    all_dates: set[date] = set(spy_prices.keys())
    for prices in price_data.values():
        all_dates |= set(prices.keys())

    cutoff = date.today() - timedelta(days=days)
    trading_days = sorted(d for d in all_dates if d >= cutoff)

    if not trading_days:
        return {"new_portfolio": 0, "new_benchmark": 0, "new_account_days": 0, "skipped_tickers": skipped}

    skipped_set = set(skipped)
    existing_portfolio = _existing_portfolio_dates()
    existing_benchmark = _existing_benchmark_dates()

    new_portfolio_rows: list[PortfolioSnapshot] = []
    new_benchmark_rows: list[BenchmarkSnapshot] = []
    new_account_rows: list[AccountDailyValue] = []

    # Per-account existing dates (loaded once per account)
    existing_account: dict[str, set[date]] = {
        name: _existing_account_dates(name) for name in accounts
    }

    # Pre-load existing AccountDailyValue amounts so we can include them in
    # grand_total even when we skip re-computing an already-stored account day.
    with get_session() as _s:
        _existing_adv = {
            (r.account_name, r.captured_at.date()): r.total_value
            for r in _s.query(AccountDailyValue).all()
        }

    for d in trading_days:
        grand_total = 0.0

        for account_name, positions in accounts.items():
            if d in existing_account[account_name]:
                # Already stored — pull the existing value into grand_total so
                # PortfolioSnapshot stays consistent with all accounts.
                grand_total += _existing_adv.get((account_name, d), 0.0)
                continue

            acct_value = 0.0
            for ticker, shares, mv_today in positions:
                if ticker in price_data:
                    prices = price_data[ticker]
                    if d in prices:
                        if shares > 0:
                            acct_value += shares * prices[d]
                        else:
                            # No shares recorded: scale current mv by price ratio
                            latest = prices.get(max(prices))
                            if latest:
                                acct_value += mv_today * (prices[d] / latest)
                    else:
                        # Forward-fill from most recent prior close
                        prev = [pd for pd in prices if pd <= d]
                        if prev:
                            p = prices[max(prev)]
                            acct_value += (shares * p) if shares > 0 else mv_today * (p / prices.get(max(prices), p))
                elif ticker in skipped_set and spy_today and d in spy_prices:
                    # SPY-scale as last resort
                    acct_value += mv_today * (spy_prices[d] / spy_today)

            if acct_value > 0:
                new_account_rows.append(AccountDailyValue(
                    account_name=account_name,
                    total_value=round(acct_value, 2),
                    captured_at=datetime.combine(d, datetime.min.time()),
                ))
                grand_total += acct_value

        # ── Portfolio snapshot (sum of all accounts) ───────────────────────
        if d not in existing_portfolio and grand_total > 0:
            new_portfolio_rows.append(PortfolioSnapshot(
                total_value=round(grand_total, 2),
                cash_balance=0.0,
                day_pnl=None,
                num_positions=sum(len(p) for p in accounts.values()),
                captured_at=datetime.combine(d, datetime.min.time()),
            ))

        # ── Benchmark snapshot ─────────────────────────────────────────────
        if d not in existing_benchmark and d in spy_prices:
            new_benchmark_rows.append(BenchmarkSnapshot(
                ticker="SPY",
                close_price=spy_prices[d],
                captured_at=datetime.combine(d, datetime.min.time()),
            ))

    with get_session() as session:
        for row in new_portfolio_rows + new_benchmark_rows + new_account_rows:
            session.add(row)

    log.info("backfill_complete",
             new_portfolio=len(new_portfolio_rows),
             new_benchmark=len(new_benchmark_rows),
             new_account_days=len(new_account_rows),
             skipped=skipped)

    return {
        "new_portfolio": len(new_portfolio_rows),
        "new_benchmark": len(new_benchmark_rows),
        "new_account_days": len(new_account_rows),
        "skipped_tickers": skipped,
    }
