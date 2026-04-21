"""Periodic research, rebalance, and token refresh jobs.

Uses APScheduler to run background tasks on configurable intervals.
Jobs are designed to be idempotent and resilient — failures are logged
but never crash the scheduler.
"""
from __future__ import annotations

import structlog
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger

log = structlog.get_logger()

_scheduler: BackgroundScheduler | None = None


def _refresh_token() -> None:
    """Silently refresh the Schwab access token.

    schwab-py handles the actual refresh internally, but we need to
    trigger a client instantiation to force the check.  If the refresh
    token itself has expired (>7 days), log an alert.
    """
    try:
        from pmod.auth.schwab import auth_status, get_client

        status = auth_status()
        if not status["connected"]:
            log.error("token_refresh_failed", reason=status["reason"])
            return

        # Force a client load — schwab-py auto-refreshes the access token
        get_client()
        log.info("token_refresh_ok")
    except Exception as exc:
        log.error("token_refresh_error", error=str(exc)[:120])


def _run_research() -> None:
    """Execute a full research pass: politician signals → screener → watchlist."""
    try:
        from pmod.research.politician_signals import generate_signals
        from pmod.research.screener import screen_and_update_watchlist

        signals = generate_signals()
        count = screen_and_update_watchlist()
        log.info(
            "scheduled_research_complete",
            signals=len(signals),
            watchlist_updated=count,
        )
    except Exception as exc:
        log.error("scheduled_research_failed", error=str(exc)[:120])


def _fetch_congress_trades() -> None:
    """Fetch the latest congressional trade disclosures.

    Runs daily to keep politician trades database up-to-date.
    """
    try:
        from pmod.data.politician_trades import fetch_and_store_trades

        counts = fetch_and_store_trades()
        log.info(
            "congress_trades_fetched",
            senate=counts.get("senate", 0),
            errors=counts.get("errors", 0),
        )
    except Exception as exc:
        log.error("congress_trades_fetch_failed", error=str(exc)[:120])


def _run_rebalance() -> None:
    """Preview a portfolio-wide rebalance and execute if user has opted into auto-execution.

    Considers all accounts (Schwab + external) and respects the trade_execution preference.
    Only places orders to Schwab account (external accounts require manual rebalancing).
    """
    try:
        from pmod.optimizer.portfolio import compute_rebalance
        from pmod.preferences.profile import load_preferences_dict

        prefs = load_preferences_dict()
        max_pos = float(prefs.get("max_position_pct", 5.0))
        execution = prefs.get("trade_execution", "manual-confirm")

        holistic_plan = compute_rebalance(max_position_pct=max_pos)

        # Collect all actionable trades from all accounts
        all_actionable = []
        schwab_actionable = []

        for acct_rebalance in holistic_plan.account_rebalances:
            actionable = [t for t in acct_rebalance.trades if t.action != "hold"]
            all_actionable.extend(actionable)
            if "Schwab" in acct_rebalance.account_name:
                schwab_actionable.extend(actionable)

        if not all_actionable:
            log.info("scheduled_rebalance_no_action")
            return

        log.info(
            "scheduled_rebalance_preview",
            accounts=len(holistic_plan.account_rebalances),
            portfolio_trades=len(all_actionable),
            schwab_trades=len(schwab_actionable),
            net_cash=round(holistic_plan.portfolio_net_cash_change, 2),
            portfolio_value=round(holistic_plan.portfolio_total_value, 2),
        )

        if execution != "auto":
            log.info("scheduled_rebalance_skipped_manual_mode")
            return

        from pmod.broker.schwab import OrderRequest, place_order

        # Execute only Schwab trades (other accounts require manual rebalancing)
        for t in schwab_actionable:
            if t.shares_delta == 0:
                continue
            req = OrderRequest(
                ticker=t.ticker,
                instruction=t.action,
                quantity=abs(t.shares_delta),
                order_type="market",
            )
            result = place_order(req)
            log.info(
                "scheduled_trade",
                ticker=t.ticker,
                action=t.action,
                shares=abs(t.shares_delta),
                success=result.success,
                message=result.message,
            )
    except Exception as exc:
        log.error("scheduled_rebalance_failed", error=str(exc)[:120])


def _capture_snapshot() -> None:
    """Record a daily portfolio snapshot for historical tracking.

    Sums all accounts — Schwab brokerage + external accounts — so the
    stored total_value matches what the dashboard shows.
    """
    try:
        from pmod.broker.schwab import get_all_account_summaries
        from pmod.data.external_accounts import list_accounts
        from pmod.data.models import PortfolioSnapshot, get_session

        total_value = 0.0
        cash_balance = 0.0
        day_pnl = 0.0
        num_positions = 0

        try:
            schwab_summaries = get_all_account_summaries()
            for s in schwab_summaries:
                total_value += s.total_value
                cash_balance += s.cash_balance
                day_pnl += s.day_pnl
                num_positions += len(s.positions)
        except Exception as exc:
            log.warning("snapshot_schwab_fetch_failed", error=str(exc)[:120])

        try:
            for ext in list_accounts():
                total_value += ext["total_value"]
        except Exception as exc:
            log.warning("snapshot_external_fetch_failed", error=str(exc)[:120])

        if total_value == 0.0:
            log.debug("snapshot_skipped_no_data")
            return

        from datetime import datetime, timedelta
        today_start = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)

        with get_session() as session:
            already = (
                session.query(PortfolioSnapshot)
                .filter(PortfolioSnapshot.captured_at >= today_start)
                .first()
            )
            if already is not None:
                log.debug("portfolio_snapshot_already_captured_today")
                return
            snapshot = PortfolioSnapshot(
                total_value=total_value,
                cash_balance=cash_balance,
                day_pnl=day_pnl,
                num_positions=num_positions,
            )
            session.add(snapshot)

        log.info(
            "portfolio_snapshot_captured",
            total_value=round(total_value, 2),
            positions=num_positions,
        )
    except Exception as exc:
        log.error("snapshot_capture_failed", error=str(exc)[:120])


def _cache_closing_prices() -> None:
    """Cache historical closing prices from Yahoo Finance for all portfolio tickers.

    Stores closing prices in the database so trend analysis doesn't need to
    fetch from external APIs. Runs nightly to keep data fresh.
    """
    try:
        from pmod.broker.schwab import get_account_summary
        from pmod.data.external_accounts import list_accounts, get_positions as get_ext_positions
        from pmod.data.models import ClosingPrice, get_session
        from pmod.data.yahoo_finance import get_closing_prices

        # Collect all unique tickers from Schwab + external accounts
        tickers = set()

        # Schwab positions
        schwab = get_account_summary()
        if schwab and schwab.positions:
            for pos in schwab.positions:
                tickers.add(pos.ticker)

        # External positions
        for ext_acct in list_accounts():
            for pos in get_ext_positions(ext_acct["name"]):
                tickers.add(pos.ticker)

        if not tickers:
            log.debug("cache_closing_prices_no_tickers")
            return

        cached_count = 0
        failed_count = 0

        with get_session() as session:
            # Pre-load every (ticker, date) pair already in the DB for these
            # tickers in a single query rather than one SELECT per bar (which
            # would be ~1,800 round-trips for 15 tickers × 120 days).
            from datetime import date as _date, datetime as _dt
            existing_rows = (
                session.query(ClosingPrice.ticker, ClosingPrice.date)
                .filter(ClosingPrice.ticker.in_(tickers))
                .all()
            )
            # Normalise to date objects regardless of whether the column stores
            # datetime (old schema) or date (new schema) values.
            seen: set[tuple[str, _date]] = {
                (t, d.date() if isinstance(d, _dt) else d)
                for t, d in existing_rows
            }

            for ticker in sorted(tickers):
                closes = get_closing_prices(ticker, days=120)
                if not closes:
                    failed_count += 1
                    continue

                for bar_date, close_price in closes.items():
                    key = (ticker, bar_date if isinstance(bar_date, _date) else bar_date.date())
                    if key not in seen:
                        session.add(
                            ClosingPrice(
                                ticker=ticker,
                                date=bar_date,
                                close=close_price,
                            )
                        )
                        seen.add(key)
                        cached_count += 1

        log.info(
            "closing_prices_cached",
            tickers=len(tickers),
            prices_stored=cached_count,
            fetch_failures=failed_count,
        )
    except Exception as exc:
        log.error("cache_closing_prices_failed", error=str(exc)[:120])


def _update_external_accounts() -> None:
    """Update external account positions with current market prices.

    Reads share counts from external_positions_config.csv, fetches prices,
    and stores daily snapshots.
    """
    try:
        from pmod.analytics.external_updates import update_external_account_daily_values

        update_external_account_daily_values()
    except Exception as exc:
        log.error("external_accounts_update_failed", error=str(exc)[:120])


def _capture_benchmark_snapshot() -> None:
    """Record daily S&P 500 closing price for alpha calculation."""
    try:
        from pmod.data.market import get_quote
        from pmod.data.models import BenchmarkSnapshot, get_session

        quote = get_quote("SPY")
        if quote is None:
            log.debug("benchmark_snapshot_skipped_no_quote")
            return

        from datetime import datetime
        today_start = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)

        with get_session() as session:
            already = (
                session.query(BenchmarkSnapshot)
                .filter(BenchmarkSnapshot.captured_at >= today_start)
                .first()
            )
            if already is not None:
                log.debug("benchmark_snapshot_already_captured_today")
                return
            snapshot = BenchmarkSnapshot(
                ticker="SPY",
                close_price=quote.price,
            )
            session.add(snapshot)

        log.info(
            "benchmark_snapshot_captured",
            ticker="SPY",
            price=round(quote.price, 2),
        )
    except Exception as exc:
        log.error("benchmark_snapshot_failed", error=str(exc)[:120])


def _is_price_cache_stale() -> bool:
    """Return True if no closing prices have been cached in the last 24 hours.

    Uses cached_at (the wall-clock insertion time) rather than date (the
    trading day the price belongs to) so weekends and holidays — where the
    most recent price date is legitimately in the past — don't trigger a
    spurious re-fetch every startup.
    """
    try:
        from datetime import datetime, timedelta

        from pmod.data.models import ClosingPrice, get_session

        cutoff = datetime.utcnow() - timedelta(hours=24)
        with get_session() as session:
            row = session.query(ClosingPrice).filter(ClosingPrice.cached_at >= cutoff).first()
            return row is None
    except Exception:
        return True  # Assume stale if we can't check


def start_scheduler() -> BackgroundScheduler:
    """Start the background scheduler with all configured jobs.

    Job schedule:
      - Token refresh: every 4 hours (Schwab access tokens expire frequently)
      - Research pass: daily at 6:00 AM ET (before market open)
      - Portfolio snapshot: daily at 4:30 PM ET (after market close)
      - Rebalance: per user preference (daily or weekly)

    Returns the scheduler instance so callers can shut it down.
    """
    global _scheduler

    if _scheduler is not None and _scheduler.running:
        log.warning("scheduler_already_running")
        return _scheduler

    _scheduler = BackgroundScheduler(timezone="US/Eastern")

    # Token refresh — every 4 hours
    _scheduler.add_job(
        _refresh_token,
        trigger=IntervalTrigger(hours=4),
        id="token_refresh",
        name="Schwab token refresh",
        replace_existing=True,
        misfire_grace_time=300,
    )

    # Congress trades fetch — daily at 6:30 AM ET (before market open)
    _scheduler.add_job(
        _fetch_congress_trades,
        trigger=CronTrigger(hour=6, minute=30),
        id="daily_congress_trades",
        name="Daily congress trades fetch",
        replace_existing=True,
        misfire_grace_time=3600,
    )

    # Cache closing prices — daily at 6:45 AM ET (before market open, after congress trades).
    # Also runs immediately at startup if the cache is stale so signals have data on first load.
    from datetime import datetime as _dt

    _startup_run_time = _dt.now() if _is_price_cache_stale() else None
    _scheduler.add_job(
        _cache_closing_prices,
        trigger=CronTrigger(hour=6, minute=45),
        id="daily_cache_prices",
        name="Daily closing prices cache from Yahoo Finance",
        replace_existing=True,
        misfire_grace_time=3600,
        next_run_time=_startup_run_time,
    )

    # Research pass — daily at 7:00 AM ET (before market open, after cache)
    _scheduler.add_job(
        _run_research,
        trigger=CronTrigger(hour=7, minute=0),
        id="daily_research",
        name="Daily research pass",
        replace_existing=True,
        misfire_grace_time=3600,
    )

    # External account update — daily at 4:25 PM ET (after market close, 5 min before portfolio)
    _scheduler.add_job(
        _update_external_accounts,
        trigger=CronTrigger(hour=16, minute=25),
        id="external_accounts_update",
        name="Daily external account price update",
        replace_existing=True,
        misfire_grace_time=3600,
    )

    # Portfolio snapshot — daily at 4:30 PM ET (after market close)
    _scheduler.add_job(
        _capture_snapshot,
        trigger=CronTrigger(hour=16, minute=30),
        id="daily_snapshot",
        name="Daily portfolio snapshot",
        replace_existing=True,
        misfire_grace_time=3600,
    )

    # Benchmark snapshot — daily at 4:35 PM ET (after market close, 5 min after portfolio)
    _scheduler.add_job(
        _capture_benchmark_snapshot,
        trigger=CronTrigger(hour=16, minute=35),
        id="daily_benchmark",
        name="Daily S&P 500 benchmark snapshot",
        replace_existing=True,
        misfire_grace_time=3600,
    )

    # Rebalance — schedule depends on user preference
    try:
        from pmod.preferences.profile import load_preferences_dict

        prefs = load_preferences_dict()
        rebalance_freq = prefs.get("rebalance_frequency", "manual")

        if rebalance_freq == "daily":
            _scheduler.add_job(
                _run_rebalance,
                trigger=CronTrigger(hour=10, minute=0, day_of_week="mon-fri"),
                id="rebalance",
                name="Daily rebalance",
                replace_existing=True,
                misfire_grace_time=3600,
            )
            log.info("rebalance_scheduled", frequency="daily")
        elif rebalance_freq == "weekly":
            _scheduler.add_job(
                _run_rebalance,
                trigger=CronTrigger(hour=10, minute=0, day_of_week="sun"),
                id="rebalance",
                name="Weekly rebalance",
                replace_existing=True,
                misfire_grace_time=3600,
            )
            log.info("rebalance_scheduled", frequency="weekly")
        else:
            log.info("rebalance_manual_mode")
    except Exception as exc:
        log.warning("rebalance_schedule_error", error=str(exc)[:80])

    _scheduler.start()
    log.info("scheduler_started", jobs=len(_scheduler.get_jobs()))
    return _scheduler


def stop_scheduler() -> None:
    """Shut down the scheduler gracefully."""
    global _scheduler
    if _scheduler is not None and _scheduler.running:
        _scheduler.shutdown(wait=False)
        log.info("scheduler_stopped")
    _scheduler = None


def get_scheduler() -> BackgroundScheduler | None:
    """Return the current scheduler instance, or None if not started."""
    return _scheduler
