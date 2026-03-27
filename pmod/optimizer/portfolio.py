"""Mean-variance / risk-parity portfolio optimization."""
from __future__ import annotations

from dataclasses import dataclass, field

import structlog

log = structlog.get_logger()


def _equal_weight_capped(n: int, cap: float) -> list[float]:
    """Compute equal-weight allocation that respects a hard per-position cap.

    Uses iterative redistribution: any weight exceeding *cap* is pinned to
    *cap*, and the excess is shared equally among uncapped positions.
    Converges in at most *n* iterations (usually 2-3).

    Args:
        n:   number of positions
        cap: maximum weight per position, as a fraction (e.g. 0.05 for 5%)

    Returns:
        List of *n* weights summing to 1.0, each ≤ *cap* (or as close as
        geometrically possible — if ``n * cap < 1`` every position is set
        to ``cap`` and a warning is logged).
    """
    if n == 0:
        return []
    weights = [1.0 / n] * n
    for _ in range(n + 1):
        capped_mask = [w >= cap - 1e-12 for w in weights]
        excess = sum(max(0.0, w - cap) for w in weights)
        if excess < 1e-12:
            break
        uncapped_indices = [i for i, m in enumerate(capped_mask) if not m]
        if not uncapped_indices:
            # Can't honour the cap — every slot is already at the ceiling.
            # Fall back to cap-each and accept the portfolio won't be fully
            # invested.  Logged so the user knows the pref is unsatisfiable.
            log.warning(
                "position_cap_unsatisfiable",
                n=n,
                cap_pct=round(cap * 100, 1),
                shortfall_pct=round((1.0 - n * cap) * 100, 1),
            )
            return [cap] * n
        for i, m in enumerate(capped_mask):
            if m:
                weights[i] = cap
        share = excess / len(uncapped_indices)
        for i in uncapped_indices:
            weights[i] += share
    return weights


@dataclass
class RebalanceTrade:
    ticker: str
    company_name: str
    current_shares: float
    current_price: float
    current_value: float
    current_weight_pct: float
    target_value: float
    target_weight_pct: float
    shares_delta: int          # positive = buy, negative = sell
    dollar_delta: float
    action: str                # "buy" | "sell" | "hold"


@dataclass
class RebalancePlan:
    trades: list[RebalanceTrade] = field(default_factory=list)
    total_value: float = 0.0
    cash_available: float = 0.0
    net_cash_change: float = 0.0   # negative = net buying, positive = net freeing cash


def compute_rebalance(max_position_pct: float = 5.0) -> RebalancePlan:
    """Compute an equal-weight rebalance plan for the current Schwab account.

    Weights are capped at *max_position_pct* and renormalized so they sum to
    100 %.  Only whole shares are traded.  Returns an empty plan if Schwab is
    not connected or the account has no equity positions.
    """
    from pmod.broker.schwab import get_account_summary

    summary = get_account_summary()
    if summary is None or not summary.positions:
        log.warning("rebalance_no_data")
        return RebalancePlan()

    positions = summary.positions
    n = len(positions)
    investable = summary.total_value

    # Equal-weight target, capped at max_position_pct.  Iterative
    # redistribution ensures the cap survives normalisation (see
    # _equal_weight_capped docstring for the algorithm).
    cap = max_position_pct / 100.0
    weights = _equal_weight_capped(n, cap)

    trades: list[RebalanceTrade] = []
    net_cash = 0.0

    for pos, tw in zip(positions, weights):
        target_value = investable * tw
        dollar_delta = target_value - pos.market_value

        if pos.current_price > 0:
            # Truncate toward zero so we never overspend
            shares_delta = int(dollar_delta / pos.current_price)
        else:
            shares_delta = 0

        actual_dollar_delta = shares_delta * pos.current_price
        net_cash -= actual_dollar_delta

        if shares_delta > 0:
            action = "buy"
        elif shares_delta < 0:
            action = "sell"
        else:
            action = "hold"

        trades.append(
            RebalanceTrade(
                ticker=pos.ticker,
                company_name=pos.company_name,
                current_shares=pos.shares,
                current_price=pos.current_price,
                current_value=pos.market_value,
                current_weight_pct=pos.weight,
                target_value=pos.market_value + actual_dollar_delta,
                target_weight_pct=(pos.market_value + actual_dollar_delta) / investable * 100
                if investable
                else 0.0,
                shares_delta=shares_delta,
                dollar_delta=actual_dollar_delta,
                action=action,
            )
        )

    log.info(
        "rebalance_computed",
        positions=n,
        buys=sum(1 for t in trades if t.action == "buy"),
        sells=sum(1 for t in trades if t.action == "sell"),
        net_cash_change=round(net_cash, 2),
    )

    return RebalancePlan(
        trades=trades,
        total_value=investable,
        cash_available=summary.cash_balance,
        net_cash_change=net_cash,
    )
