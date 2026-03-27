"""Mean-variance / risk-parity portfolio optimization."""
from __future__ import annotations

from dataclasses import dataclass, field

import structlog

log = structlog.get_logger()


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

    # Equal-weight target, capped at max_position_pct, then renormalised
    cap = max_position_pct / 100.0
    raw_weights = [min(1.0 / n, cap) for _ in positions]
    total_w = sum(raw_weights)
    weights = [w / total_w for w in raw_weights]

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
