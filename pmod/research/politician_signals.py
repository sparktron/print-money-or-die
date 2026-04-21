"""Generate trade signals from congressional disclosure data.

Logic:
- Look at all trades in a configurable rolling window (default 90 days)
- For each ticker, count purchases vs sales by unique politicians
- Weight by recency (trades in the last 30 days score 2x vs older)
- Weight by amount (larger disclosed ranges add more signal weight)
- Derive a confidence score and map to: strong_buy / buy / hold / sell
- Persist results as PoliticianSignal rows
"""

import math
from collections import defaultdict
from datetime import datetime, timedelta
from typing import Any

import structlog

from pmod.data.models import PoliticianSignal, PoliticianTrade, get_session

log = structlog.get_logger()

# Dollar midpoints for each disclosed amount range (used for weighting)
_AMOUNT_MIDPOINTS: dict[tuple[int | None, int | None], float] = {
    (1_001, 15_000): 8_000,
    (15_001, 50_000): 32_500,
    (50_001, 100_000): 75_000,
    (100_001, 250_000): 175_000,
    (250_001, 500_000): 375_000,
    (500_001, 1_000_000): 750_000,
    (1_000_001, 5_000_000): 3_000_000,
    (5_000_001, 25_000_000): 15_000_000,
    (25_000_001, 50_000_000): 37_500_000,
    (50_000_001, None): 75_000_000,
}
_DEFAULT_MIDPOINT = 8_000.0
_MAX_MIDPOINT = 75_000_000.0


def _amount_weight(low: int | None, high: int | None) -> float:
    """Return a normalised 0.5–2.0 weight based on trade size."""
    midpoint = _AMOUNT_MIDPOINTS.get((low, high), _DEFAULT_MIDPOINT)
    raw = math.log1p(midpoint) / math.log1p(_MAX_MIDPOINT)
    return 0.5 + raw * 1.5  # maps [0,1] → [0.5, 2.0]


def _recency_multiplier(trade_date: datetime | None, now: datetime, recent_days: int = 30) -> float:
    """Return 2.0 for trades within recent_days, 1.0 otherwise."""
    if trade_date is None:
        return 1.0
    return 2.0 if (now - trade_date).days <= recent_days else 1.0


def _score_to_signal(net_score: float, total_weight: float) -> tuple[str, float]:
    """Map a net weighted score to (signal, confidence).

    net_score = sum of signed weighted votes (positive = buy, negative = sell)
    total_weight = sum of absolute weights (used for normalisation)
    """
    if total_weight == 0:
        return "hold", 0.0
    ratio = net_score / total_weight  # -1.0 to +1.0
    if ratio >= 0.6:
        return "strong_buy", min(ratio, 1.0)
    if ratio >= 0.2:
        return "buy", ratio
    if ratio <= -0.2:
        return "sell", abs(ratio)
    return "hold", abs(ratio)


def _build_rationale(
    ticker: str,
    buy_count: int,
    sell_count: int,
    unique_pols: int,
    signal: str,
) -> str:
    """Generate a plain-English rationale string."""
    total = buy_count + sell_count
    pct_buy = round(buy_count / total * 100) if total else 0
    verb = {
        "strong_buy": "strongly favoured",
        "buy": "net bought",
        "sell": "net sold",
        "hold": "had mixed activity on",
    }[signal]
    return (
        f"{unique_pols} member{'s' if unique_pols != 1 else ''} of Congress "
        f"{verb} {ticker} ({buy_count} purchase{'s' if buy_count != 1 else ''}, "
        f"{sell_count} sale{'s' if sell_count != 1 else ''} — {pct_buy}% buys)."
    )


def _aggregate_trades(
    trades: list[PoliticianTrade], now: datetime
) -> dict[str, dict[str, Any]]:
    """Group trades by ticker and accumulate weighted scores."""
    agg: dict[str, dict[str, Any]] = defaultdict(
        lambda: {
            "net_score": 0.0,
            "total_weight": 0.0,
            "buy_count": 0,
            "sell_count": 0,
            "politicians": set(),
            "company_name": None,
        }
    )
    for trade in trades:
        ticker = trade.ticker
        entry = agg[ticker]

        if entry["company_name"] is None and trade.company_name:
            entry["company_name"] = trade.company_name

        weight = _amount_weight(trade.amount_low, trade.amount_high)
        weight *= _recency_multiplier(trade.disclosure_date, now)
        entry["politicians"].add(trade.politician_name)

        if trade.trade_type == "purchase":
            entry["net_score"] += weight
            entry["total_weight"] += weight
            entry["buy_count"] += 1
        elif trade.trade_type in ("sale", "sale_partial"):
            entry["net_score"] -= weight
            entry["total_weight"] += weight
            entry["sell_count"] += 1
        # exchange: ignore for signal purposes

    return agg


def generate_signals(window_days: int = 90, min_trades: int = 2) -> list[PoliticianSignal]:
    """Compute and persist PoliticianSignal rows from recent trade data.

    Args:
        window_days: How many days back to include trades.
        min_trades: Minimum total trades for a ticker to be signalled.

    Returns:
        The list of generated PoliticianSignal objects.
    """
    now = datetime.utcnow()
    cutoff = now - timedelta(days=window_days)

    with get_session() as session:
        trades = (
            session.query(PoliticianTrade)
            .filter(PoliticianTrade.disclosure_date >= cutoff)
            .all()
        )

        agg = _aggregate_trades(trades, now)

        # Insert new signals first so readers never see an empty table.
        # generated_at is set to `now` on all new rows; after the flush we
        # delete any rows whose generated_at predates this batch.
        signals: list[PoliticianSignal] = []
        for ticker, data in agg.items():
            total = data["buy_count"] + data["sell_count"]
            if total < min_trades:
                continue

            signal, confidence = _score_to_signal(data["net_score"], data["total_weight"])
            unique_pols = len(data["politicians"])
            rationale = _build_rationale(
                ticker, data["buy_count"], data["sell_count"], unique_pols, signal
            )

            row = PoliticianSignal(
                ticker=ticker,
                company_name=data["company_name"],
                signal=signal,
                confidence=round(confidence, 3),
                buy_count=data["buy_count"],
                sell_count=data["sell_count"],
                unique_politicians=unique_pols,
                rationale=rationale,
                generated_at=now,
            )
            session.add(row)
            signals.append(row)

        # Flush so the new rows have persisted IDs, then evict stale signals
        # (any row written before this batch started).
        session.flush()
        session.query(PoliticianSignal).filter(
            PoliticianSignal.generated_at < now
        ).delete(synchronize_session=False)

        log.info("politician signals generated", count=len(signals))
        return signals


def get_signals(signal_type: str | None = None) -> list[PoliticianSignal]:
    """Load persisted signals, optionally filtered by type."""
    with get_session() as session:
        q = session.query(PoliticianSignal)
        if signal_type:
            q = q.filter(PoliticianSignal.signal == signal_type)
        return (
            q.order_by(
                PoliticianSignal.confidence.desc(),
                PoliticianSignal.buy_count.desc(),
            )
            .all()
        )
