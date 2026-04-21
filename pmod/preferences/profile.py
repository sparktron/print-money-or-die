"""Risk tolerance, strategy, and sector constraint management."""
from __future__ import annotations

import structlog

from pmod.data.models import UserPreference, get_session

log = structlog.get_logger()

_DEFAULTS: dict = {
    "risk_tolerance": "medium",
    "strategy": "balanced",
    "max_position_pct": 5.0,
    "rebalance_frequency": "manual",
    "trade_execution": "manual-confirm",
    "sector_focus": [],
}


def get_preferences() -> UserPreference | None:
    """Return the current user preference record, or None if not yet set up.

    The returned object is expunged from the session so attribute access is
    safe after the context exits regardless of lazy-load relationships added
    in the future.
    """
    with get_session() as session:
        prefs = session.query(UserPreference).first()
        if prefs is not None:
            session.expunge(prefs)
        return prefs


def has_completed_setup() -> bool:
    """Return True if the user has saved preferences at least once."""
    try:
        return get_preferences() is not None
    except Exception:
        return False


def load_preferences_dict() -> dict:
    """Return preferences as a plain dict, falling back to defaults if not set."""
    prefs = get_preferences()
    if prefs is None:
        return dict(_DEFAULTS)
    return {
        "risk_tolerance": prefs.risk_tolerance,
        "strategy": prefs.strategy,
        "max_position_pct": prefs.max_position_pct,
        "rebalance_frequency": prefs.rebalance_frequency,
        "trade_execution": prefs.trade_execution,
        "sector_focus": prefs.sector_focus or [],
    }


def save_preferences(
    risk_tolerance: str,
    strategy: str,
    max_position_pct: float,
    rebalance_frequency: str,
    trade_execution: str,
    sector_focus: list[str] | None = None,
) -> UserPreference:
    """Upsert the user preference record."""
    with get_session() as session:
        prefs = session.query(UserPreference).first()
        if prefs is None:
            prefs = UserPreference()
            session.add(prefs)
        prefs.risk_tolerance = risk_tolerance
        prefs.strategy = strategy
        prefs.max_position_pct = float(max_position_pct)
        prefs.rebalance_frequency = rebalance_frequency
        prefs.trade_execution = trade_execution
        prefs.sector_focus = sector_focus or []
        log.info(
            "preferences_saved",
            risk=risk_tolerance,
            strategy=strategy,
            max_pos=max_position_pct,
            rebalance=rebalance_frequency,
            execution=trade_execution,
        )
        return prefs
