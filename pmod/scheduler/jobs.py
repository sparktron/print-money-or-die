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


def _run_rebalance() -> None:
    """Preview a rebalance and execute if user has opted into auto-execution.

    Respects the trade_execution preference — only places orders when set
    to 'auto'.  Otherwise just logs the suggested trades.
    """
    try:
        from pmod.optimizer.portfolio import compute_rebalance
        from pmod.preferences.profile import load_preferences_dict

        prefs = load_preferences_dict()
        max_pos = float(prefs.get("max_position_pct", 5.0))
        execution = prefs.get("trade_execution", "manual-confirm")

        plan = compute_rebalance(max_position_pct=max_pos)
        actionable = [t for t in plan.trades if t.action != "hold"]

        if not actionable:
            log.info("scheduled_rebalance_no_action")
            return

        log.info(
            "scheduled_rebalance_preview",
            trades=len(actionable),
            net_cash=round(plan.net_cash_change, 2),
        )

        if execution != "auto":
            log.info("scheduled_rebalance_skipped_manual_mode")
            return

        from pmod.broker.schwab import OrderRequest, place_order

        for t in actionable:
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
    """Record a daily portfolio snapshot for historical tracking."""
    try:
        from pmod.broker.schwab import get_account_summary
        from pmod.data.models import PortfolioSnapshot, get_session

        summary = get_account_summary()
        if summary is None:
            log.debug("snapshot_skipped_no_account")
            return

        with get_session() as session:
            snapshot = PortfolioSnapshot(
                total_value=summary.total_value,
                cash_balance=summary.cash_balance,
                day_pnl=summary.day_pnl,
                num_positions=len(summary.positions),
            )
            session.add(snapshot)

        log.info(
            "portfolio_snapshot_captured",
            total_value=round(summary.total_value, 2),
            positions=len(summary.positions),
        )
    except Exception as exc:
        log.error("snapshot_capture_failed", error=str(exc)[:120])


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

    # Research pass — daily at 6:00 AM ET (before market open)
    _scheduler.add_job(
        _run_research,
        trigger=CronTrigger(hour=6, minute=0),
        id="daily_research",
        name="Daily research pass",
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
