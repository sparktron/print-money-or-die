"""Alpha calculation — portfolio excess return vs S&P 500 benchmark."""
from __future__ import annotations

import structlog
from datetime import datetime, timedelta

from pmod.data.models import BenchmarkSnapshot, PortfolioSnapshot, get_session

log = structlog.get_logger()


def get_historical_returns(days: int = 365) -> tuple[list[float], list[float], list[str]] | None:
    """Fetch portfolio and benchmark daily returns for the last N days.

    Returns (portfolio_values, benchmark_values, dates) or None if insufficient data.
    """
    try:
        with get_session() as session:
            # Get portfolio snapshots
            cutoff = datetime.utcnow() - timedelta(days=days)
            portfolio_snapshots = (
                session.query(PortfolioSnapshot)
                .filter(PortfolioSnapshot.captured_at >= cutoff)
                .order_by(PortfolioSnapshot.captured_at)
                .all()
            )

            # Get benchmark snapshots
            benchmark_snapshots = (
                session.query(BenchmarkSnapshot)
                .filter(BenchmarkSnapshot.captured_at >= cutoff)
                .order_by(BenchmarkSnapshot.captured_at)
                .all()
            )

        if len(portfolio_snapshots) < 2 or len(benchmark_snapshots) < 2:
            return None

        # Build aligned time series (match dates)
        portfolio_dict = {
            s.captured_at.date(): s.total_value for s in portfolio_snapshots
        }
        benchmark_dict = {
            s.captured_at.date(): s.close_price for s in benchmark_snapshots
        }

        # Get common dates
        common_dates = sorted(set(portfolio_dict.keys()) & set(benchmark_dict.keys()))
        if len(common_dates) < 2:
            return None

        portfolio_values = [portfolio_dict[d] for d in common_dates]
        benchmark_values = [benchmark_dict[d] for d in common_dates]
        date_strs = [d.strftime("%Y-%m-%d") for d in common_dates]

        return portfolio_values, benchmark_values, date_strs

    except Exception as exc:
        log.error("fetch_historical_returns_failed", error=str(exc)[:120])
        return None


def get_account_historical_returns(
    account_name: str,
    days: int = 365,
) -> tuple[list[float], list[float], list[str]] | None:
    """Return per-account historical returns aligned with benchmark.

    Queries AccountDailyValue (populated by ``pmod portfolio backfill``) and
    aligns with BenchmarkSnapshot on common dates.

    Returns (account_values, benchmark_values, dates) or None if insufficient data.
    """
    try:
        from pmod.data.models import AccountDailyValue
        cutoff = datetime.utcnow() - timedelta(days=days)
        with get_session() as session:
            acct_snaps = (
                session.query(AccountDailyValue)
                .filter(
                    AccountDailyValue.account_name == account_name,
                    AccountDailyValue.captured_at >= cutoff,
                )
                .order_by(AccountDailyValue.captured_at)
                .all()
            )
            bench_snaps = (
                session.query(BenchmarkSnapshot)
                .filter(BenchmarkSnapshot.captured_at >= cutoff)
                .order_by(BenchmarkSnapshot.captured_at)
                .all()
            )

        if len(acct_snaps) < 2 or len(bench_snaps) < 2:
            return None

        acct_dict = {s.captured_at.date(): s.total_value for s in acct_snaps}
        bench_dict = {s.captured_at.date(): s.close_price for s in bench_snaps}

        common_dates = sorted(set(acct_dict.keys()) & set(bench_dict.keys()))
        if len(common_dates) < 2:
            return None

        account_values = [acct_dict[d] for d in common_dates]
        benchmark_values = [bench_dict[d] for d in common_dates]
        date_strs = [d.strftime("%Y-%m-%d") for d in common_dates]
        return account_values, benchmark_values, date_strs

    except Exception as exc:
        log.error("get_account_historical_returns_failed", error=str(exc)[:120])
        return None


def calculate_alpha() -> dict | None:
    """Calculate portfolio alpha (annualized excess return vs S&P 500).

    Returns dict with:
      - total_return_pct: portfolio total return %
      - benchmark_return_pct: S&P 500 total return %
      - alpha_pct: excess return (alpha) %
      - days_tracked: number of trading days with data
    """
    result = get_historical_returns(days=365)
    if result is None:
        return None

    portfolio_values, benchmark_values, _ = result

    if len(portfolio_values) < 2:
        return None

    if portfolio_values[0] == 0 or benchmark_values[0] == 0:
        return None

    # Calculate returns
    portfolio_return = (portfolio_values[-1] - portfolio_values[0]) / portfolio_values[0] * 100
    benchmark_return = (benchmark_values[-1] - benchmark_values[0]) / benchmark_values[0] * 100
    alpha = portfolio_return - benchmark_return

    return {
        "total_return_pct": round(portfolio_return, 2),
        "benchmark_return_pct": round(benchmark_return, 2),
        "alpha_pct": round(alpha, 2),
        "days_tracked": len(portfolio_values),
    }
