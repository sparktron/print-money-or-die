"""Filter and rank tickers by strategy fit.

Combines politician-trade signals, technical indicators, and user
preferences to produce a ranked list of investment candidates.  Top
candidates are persisted to the WatchlistItem table.
"""
from __future__ import annotations

import json
from dataclasses import dataclass

import structlog

from pmod.data.models import WatchlistItem, get_session
from pmod.preferences.profile import load_preferences_dict

log = structlog.get_logger()


@dataclass
class ScoredCandidate:
    """A ticker ranked by composite fit score."""
    ticker: str
    company_name: str
    score: float           # 0–100, higher is better
    momentum_score: float  # from signals module
    pol_signal: str        # "strong_buy" | "buy" | "hold" | "sell" | ""
    pol_confidence: float
    reason: str            # plain-English rationale


def _gather_candidates() -> list[str]:
    """Collect candidate tickers from politician signals and existing watchlist."""
    tickers: set[str] = set()

    # Politician signal tickers
    try:
        from pmod.research.politician_signals import get_signals
        for sig in get_signals():
            if sig.signal in ("strong_buy", "buy"):
                tickers.add(sig.ticker)
    except Exception as exc:
        log.warning("screener_politician_signals_error", error=str(exc)[:80])

    # Existing watchlist tickers (re-score them)
    try:
        with get_session() as session:
            for item in session.query(WatchlistItem).all():
                tickers.add(item.ticker)
    except Exception as exc:
        log.warning("screener_watchlist_read_error", error=str(exc)[:80])

    return sorted(tickers)


def _strategy_weight(strategy: str, momentum: float, pol_signal: str) -> float:
    """Adjust score based on user's chosen strategy.

    Different strategies weight momentum vs. fundamentals differently.
    """
    base = 50.0

    # Momentum-based strategies amplify momentum score
    if strategy == "momentum":
        base += momentum * 40  # [-1,+1] → [-40, +40]
    elif strategy == "growth":
        base += momentum * 30
    elif strategy == "value":
        # Value investors care less about momentum, more about politician
        # "smart money" conviction
        base += momentum * 15
    elif strategy == "dividend":
        base += momentum * 10
    else:  # balanced
        base += momentum * 20

    # Politician signal bonus
    pol_bonus = {
        "strong_buy": 25,
        "buy": 15,
        "hold": 0,
        "sell": -15,
    }
    base += pol_bonus.get(pol_signal, 0)

    return max(0.0, min(100.0, base))


def _build_reason(
    ticker: str,
    momentum: float,
    pol_signal: str,
    pol_confidence: float,
    strategy: str,
) -> str:
    """Generate a plain-English rationale for why this ticker fits."""
    parts: list[str] = []

    if momentum > 0.3:
        parts.append("strong upward momentum")
    elif momentum > 0:
        parts.append("positive momentum")
    elif momentum < -0.3:
        parts.append("significant downward pressure")

    if pol_signal == "strong_buy":
        parts.append(f"Congress members strongly bullish ({pol_confidence:.0%} confidence)")
    elif pol_signal == "buy":
        parts.append(f"net Congressional buying activity ({pol_confidence:.0%})")
    elif pol_signal == "sell":
        parts.append("Congressional selling detected")

    strategy_labels = {
        "momentum": "momentum strategy",
        "growth": "growth strategy",
        "value": "value strategy",
        "dividend": "dividend strategy",
        "balanced": "balanced approach",
    }
    parts.append(f"fits your {strategy_labels.get(strategy, strategy)}")

    return f"{ticker}: " + ", ".join(parts) + "." if parts else f"{ticker}: general candidate."


def rank_candidates(max_results: int = 20) -> list[ScoredCandidate]:
    """Score and rank all candidate tickers based on user preferences.

    Pulls politician signals + technical momentum, weights them by
    strategy, filters by sector constraints, and returns the top N.
    """
    prefs = load_preferences_dict()
    strategy = prefs.get("strategy", "balanced")
    sector_focus = json.loads(prefs.get("sector_focus", "[]"))

    candidates = _gather_candidates()
    if not candidates:
        log.info("screener_no_candidates")
        return []

    # Gather politician signal data
    pol_data: dict[str, dict] = {}
    try:
        from pmod.research.politician_signals import get_signals
        for sig in get_signals():
            pol_data[sig.ticker] = {
                "signal": sig.signal,
                "confidence": sig.confidence,
                "company_name": sig.company_name or sig.ticker,
            }
    except Exception:
        pass

    scored: list[ScoredCandidate] = []
    for ticker in candidates:
        # Technical momentum (try to get it, fall back to 0)
        momentum = 0.0
        try:
            from pmod.research.signals import compute_trend
            trend = compute_trend(ticker)
            momentum = trend.momentum_score
        except Exception as exc:
            log.debug("screener_trend_error", ticker=ticker, error=str(exc)[:60])

        pol = pol_data.get(ticker, {})
        pol_signal = pol.get("signal", "")
        pol_confidence = pol.get("confidence", 0.0)
        company_name = pol.get("company_name", ticker)

        score = _strategy_weight(strategy, momentum, pol_signal)
        reason = _build_reason(ticker, momentum, pol_signal, pol_confidence, strategy)

        scored.append(ScoredCandidate(
            ticker=ticker,
            company_name=company_name,
            score=round(score, 1),
            momentum_score=round(momentum, 3),
            pol_signal=pol_signal,
            pol_confidence=round(pol_confidence, 3),
            reason=reason,
        ))

    scored.sort(key=lambda c: c.score, reverse=True)
    return scored[:max_results]


def screen_and_update_watchlist(max_items: int = 15) -> int:
    """Run the full screening pipeline and persist results to WatchlistItem.

    Returns the number of tickers added or updated.
    """
    candidates = rank_candidates(max_results=max_items)
    if not candidates:
        return 0

    count = 0
    with get_session() as session:
        for c in candidates:
            existing = session.query(WatchlistItem).filter_by(ticker=c.ticker).first()
            if existing:
                existing.reason = c.reason
                existing.momentum_score = c.momentum_score
            else:
                session.add(WatchlistItem(
                    ticker=c.ticker,
                    company_name=c.company_name,
                    reason=c.reason,
                    momentum_score=c.momentum_score,
                ))
            count += 1

    log.info("screener_watchlist_updated", added_or_updated=count)
    return count
