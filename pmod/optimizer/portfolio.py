"""Signal-driven portfolio optimization based on momentum, sentiment, and fundamentals."""
from __future__ import annotations

import math
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


def _compute_position_signal_score(
    ticker: str,
    momentum_score: float,
    volatility_pct: float | None,
) -> float:
    """Compute composite signal score for a ticker based on all market signals.

    Returns a score in [-1.0, +1.0] where:
      +1.0 = strong buy signal (low volatility, positive momentum, strong buy from politicians)
      -1.0 = strong sell signal (negative momentum, selling pressure from politicians)
      0.0  = neutral / hold signal
    """
    try:
        from pmod.research.politician_signals import get_signals

        # Get political signals (already cached, fast)
        pol_signals = {s.ticker: (s.signal, s.confidence) for s in get_signals()}
        pol_signal, pol_confidence = pol_signals.get(ticker, ("hold", 0.0))

        # Map political signal to numeric score
        pol_score_map = {
            "strong_buy": 0.8,
            "buy": 0.4,
            "hold": 0.0,
            "sell": -0.4,
        }
        pol_score = pol_score_map.get(pol_signal, 0.0)

        # Combine momentum and political signals (equal weight)
        combined = 0.6 * momentum_score + 0.4 * pol_score

        # Volatility adjustment: high volatility = reduce position size (shift negative)
        # This prevents over-concentration in volatile assets
        vol_adjustment = 0.0
        if volatility_pct is not None:
            if volatility_pct > 60:  # Very high volatility
                vol_adjustment = -0.2
            elif volatility_pct > 40:  # High volatility
                vol_adjustment = -0.1

        final_score = combined + vol_adjustment
        return max(-1.0, min(1.0, round(final_score, 3)))
    except Exception as exc:
        log.debug("signal_score_error", ticker=ticker, error=str(exc)[:60])
        return 0.0


def _softmax_weights(scores: dict[str, float]) -> dict[str, float]:
    """Convert signal scores to portfolio weights using softmax.

    This maps scores in [-1, +1] to weights proportional to exp(score * scale).
    Negative scores still get some weight (never zero), but positive scores
    get preferentially higher allocation.
    """
    if not scores:
        return {}

    # Shift scores to be non-negative for softmax
    # Map [-1, +1] → [0, 2] for more numerical stability
    shifted = {t: s + 1.0 for t, s in scores.items()}
    scale = 2.0  # Temperature factor: higher = more conservative distribution

    # Compute exp(score / temp) for each position
    exp_scores = {}
    for ticker, shifted_score in shifted.items():
        exp_scores[ticker] = math.exp(shifted_score / scale)

    # Normalize to sum to 1.0
    total = sum(exp_scores.values())
    if total == 0:
        # Fallback to equal weight if all exp values are somehow zero
        n = len(exp_scores)
        return {t: 1.0 / n for t in exp_scores.keys()}

    return {t: w / total for t, w in exp_scores.items()}


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


@dataclass
class AccountRebalance:
    """Per-account rebalance suggestions as part of a holistic portfolio rebalance."""
    account_name: str
    account_type: str  # "brokerage" | "401k" | "ira" | etc
    trades: list[RebalanceTrade] = field(default_factory=list)
    account_value: float = 0.0
    account_cash: float = 0.0
    net_cash_change: float = 0.0


@dataclass
class HolisticRebalancePlan:
    """Portfolio-wide rebalance across all accounts."""
    account_rebalances: list[AccountRebalance] = field(default_factory=list)
    portfolio_total_value: float = 0.0
    portfolio_cash_available: float = 0.0
    portfolio_net_cash_change: float = 0.0


def compute_rebalance(max_position_pct: float = 5.0) -> HolisticRebalancePlan | RebalancePlan:
    """Compute signal-driven rebalance across ALL accounts.

    Instead of equal-weighting, this analyzes:
      - Technical momentum (RSI, SMA, 1m/3m returns)
      - Political sentiment (Congressional buy/sell signals)
      - Risk (volatility) — high volatility reduces position size

    Sizes trades proportionally to signal strength. No fixed position caps.
    Considers positions from Schwab account + all external accounts (401k, IRA, etc).

    Returns:
        HolisticRebalancePlan with per-account rebalance suggestions.
    """
    log.info("rebalance_starting", max_position_pct=max_position_pct)
    from pmod.broker.schwab import get_account_summary
    from pmod.data.external_accounts import list_accounts, get_positions as get_ext_positions
    from pmod.research.signals import compute_trend

    # ─── Collect all positions from all accounts ───────────────────────────────
    log.info("loading_accounts")
    all_positions: dict[str, list] = {}  # {account_name: [positions...]}
    account_info: dict[str, dict] = {}  # {account_name: {account_type, total_value, cash}}
    portfolio_total = 0.0
    portfolio_cash = 0.0

    # Schwab account
    log.info("loading_schwab_account")
    schwab_summary = get_account_summary()
    if schwab_summary and schwab_summary.positions:
        account_label = f"Schwab ···{schwab_summary.account_number[-4:]}" if schwab_summary.account_number else "Schwab"
        all_positions[account_label] = schwab_summary.positions
        account_info[account_label] = {
            "account_type": "brokerage",
            "total_value": schwab_summary.total_value,
            "cash": schwab_summary.cash_balance,
        }
        portfolio_total += schwab_summary.total_value
        portfolio_cash += schwab_summary.cash_balance
        positions_sum = sum(p.market_value for p in schwab_summary.positions)
        log.debug(
            "account_value_detail",
            account=account_label,
            account_total=round(schwab_summary.total_value, 2),
            positions_sum=round(positions_sum, 2),
            cash=round(schwab_summary.cash_balance, 2),
        )

    # External accounts
    log.info("loading_external_accounts")
    for ext in list_accounts():
        positions = get_ext_positions(ext["name"])
        if positions:
            positions_sum = sum(p.market_value or 0 for p in positions)
            log.info(
                "external_account_loaded",
                name=ext["name"],
                positions=len(positions),
                stored_total=round(ext["total_value"], 2),
                positions_sum=round(positions_sum, 2),
            )
            all_positions[ext["name"]] = positions
            account_info[ext["name"]] = {
                "account_type": ext.get("account_type", "external"),
                "total_value": ext["total_value"],
                "cash": 0.0,  # External accounts typically don't have cash
            }
            portfolio_total += ext["total_value"]

    if not all_positions:
        log.error("rebalance_no_data")
        return HolisticRebalancePlan()

    # ─── Build portfolio-wide ticker list with aggregated positions ──────────
    ticker_totals: dict[str, dict] = {}  # {ticker: {current_value, volatility, momentum, positions_by_account}}
    for account_name, positions in all_positions.items():
        for pos in positions:
            if pos.ticker not in ticker_totals:
                # Compute technical signals (including volatility & momentum) — graceful degradation on failure
                volatility = None
                momentum = 0.0
                try:
                    trend = compute_trend(pos.ticker)
                    volatility = trend.volatility_pct
                    momentum = trend.momentum_score
                    log.info("trend_computed", ticker=pos.ticker, momentum=momentum, volatility=volatility)
                except Exception as exc:
                    log.error("trend_compute_failed", ticker=pos.ticker, error=str(exc)[:60])

                ticker_totals[pos.ticker] = {
                    "company_name": pos.company_name,
                    "current_price": pos.current_price,
                    "current_value": 0.0,
                    "volatility_pct": volatility,
                    "momentum_score": momentum,
                    "by_account": {},
                }
            ticker_totals[pos.ticker]["current_value"] += pos.market_value or 0.0
            ticker_totals[pos.ticker]["by_account"][account_name] = pos

    # ─── Compute signal scores and target weights ──────────────────────────
    log.info("computing_signal_scores", tickers=len(ticker_totals))
    signal_scores: dict[str, float] = {}
    for ticker, data in ticker_totals.items():
        signal_scores[ticker] = _compute_position_signal_score(
            ticker, data["momentum_score"], data["volatility_pct"]
        )
        log.info("signal_score_computed", ticker=ticker, score=signal_scores[ticker])

    # Convert scores to target weights using softmax
    target_weights_map = _softmax_weights(signal_scores)

    # ─── Generate per-account rebalance suggestions ──────────────────────────
    account_rebalances: list[AccountRebalance] = []

    for account_name in sorted(all_positions.keys()):
        positions = all_positions[account_name]
        acct_info = account_info[account_name]
        acct_value = acct_info["total_value"]
        acct_cash = acct_info["cash"]

        trades: list[RebalanceTrade] = []
        net_cash = 0.0

        for pos in positions:
            target_weight = target_weights_map.get(pos.ticker, 0.0)
            target_weight_pct = target_weight * 100
            # Target value is per-account: each account independently rebalances
            # to the target weights using its own capital.  Using portfolio_total
            # here would subtract only this account's position from a
            # portfolio-wide target, causing a massive over-buy when positions
            # are spread across multiple accounts.
            target_value = acct_value * target_weight
            dollar_delta = target_value - (pos.market_value or 0.0)

            current_price = pos.current_price or 0.0
            if current_price > 0:
                shares_delta = int(dollar_delta / current_price)
            else:
                shares_delta = 0

            actual_dollar_delta = shares_delta * current_price
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
                    current_shares=pos.shares or 0.0,
                    current_price=current_price,
                    current_value=pos.market_value or 0.0,
                    current_weight_pct=((pos.market_value or 0.0) / portfolio_total * 100) if portfolio_total else 0.0,
                    target_value=target_value,
                    target_weight_pct=target_weight_pct,
                    shares_delta=shares_delta,
                    dollar_delta=actual_dollar_delta,
                    action=action,
                )
            )

        account_rebalances.append(
            AccountRebalance(
                account_name=account_name,
                account_type=acct_info["account_type"],
                trades=trades,
                account_value=acct_value,
                account_cash=acct_cash,
                net_cash_change=net_cash,
            )
        )

    total_buys = sum(sum(1 for t in ar.trades if t.action == "buy") for ar in account_rebalances)
    total_sells = sum(sum(1 for t in ar.trades if t.action == "sell") for ar in account_rebalances)
    log.info(
        "rebalance_computed_signal_driven",
        accounts=len(account_rebalances),
        tickers=len(ticker_totals),
        portfolio_total=round(portfolio_total, 2),
        total_buys=total_buys,
        total_sells=total_sells,
    )
    log.info("rebalance_complete")

    plan = HolisticRebalancePlan(
        account_rebalances=account_rebalances,
        portfolio_total_value=portfolio_total,
        portfolio_cash_available=portfolio_cash,
        portfolio_net_cash_change=sum(ar.net_cash_change for ar in account_rebalances),
    )
    log.info("rebalance_plan_returned")
    return plan
