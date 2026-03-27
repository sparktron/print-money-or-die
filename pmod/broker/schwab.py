"""Account data and position retrieval via the Schwab Trader API."""
from __future__ import annotations

from dataclasses import dataclass, field

import structlog

log = structlog.get_logger()


@dataclass
class OrderRequest:
    ticker: str
    instruction: str  # "buy" | "sell"
    quantity: int  # whole shares only
    order_type: str = "market"  # "market" | "limit"
    limit_price: float | None = None


@dataclass
class OrderResult:
    success: bool
    order_id: str | None = None
    message: str = ""


@dataclass
class Position:
    ticker: str
    company_name: str
    shares: float
    avg_cost: float
    current_price: float
    market_value: float
    cost_basis: float
    day_pnl: float
    day_pnl_pct: float
    total_pnl: float
    total_pnl_pct: float
    weight: float  # % of total portfolio value


@dataclass
class AccountSummary:
    account_number: str
    total_value: float
    cash_balance: float
    day_pnl: float
    positions: list[Position] = field(default_factory=list)


def _unwrap_account(raw: dict) -> dict:
    """Schwab wraps account data in a 'securitiesAccount' key; normalise it."""
    return raw.get("securitiesAccount", raw)


def _parse_positions(raw_positions: list[dict], total_value: float) -> list[Position]:
    """Convert raw Schwab position dicts into typed Position objects."""
    results: list[Position] = []

    for raw in raw_positions:
        instrument = raw.get("instrument", {})
        if instrument.get("assetType") not in ("EQUITY", "ETF", "EQUITY_ETF"):
            continue

        ticker = instrument.get("symbol", "").strip()
        if not ticker:
            continue

        shares = float(raw.get("longQuantity", 0))
        if shares <= 0:
            continue

        avg_cost = float(raw.get("averagePrice", 0))
        market_value = float(raw.get("marketValue", 0))
        day_pnl = float(raw.get("currentDayProfitLoss", 0))
        # Schwab field name varies slightly across account types
        day_pnl_pct = float(
            raw.get("currentDayProfitLossPercent")
            or raw.get("currentDayProfitLossPercentage")
            or 0
        )

        cost_basis = avg_cost * shares
        current_price = market_value / shares if shares else 0.0
        total_pnl = market_value - cost_basis
        total_pnl_pct = (total_pnl / cost_basis * 100) if cost_basis else 0.0
        weight = (market_value / total_value * 100) if total_value else 0.0

        results.append(
            Position(
                ticker=ticker,
                company_name=instrument.get("description", ticker),
                shares=shares,
                avg_cost=avg_cost,
                current_price=current_price,
                market_value=market_value,
                cost_basis=cost_basis,
                day_pnl=day_pnl,
                day_pnl_pct=day_pnl_pct,
                total_pnl=total_pnl,
                total_pnl_pct=total_pnl_pct,
                weight=weight,
            )
        )

    return sorted(results, key=lambda p: p.market_value, reverse=True)


def get_account_summary() -> AccountSummary | None:
    """Fetch live balances and positions for the first linked Schwab account.

    Returns None on any API or auth failure so callers can fall back gracefully.
    """
    from schwab.client import Client

    from pmod.auth.schwab import get_client

    try:
        client = get_client()
        resp = client.get_accounts(fields=[Client.Account.Fields.POSITIONS])
        resp.raise_for_status()
        accounts: list[dict] = resp.json()
    except Exception as exc:
        log.error("schwab_get_accounts_failed", error=str(exc))
        return None

    if not accounts:
        log.warning("schwab_no_accounts_returned")
        return None

    acct = _unwrap_account(accounts[0])
    balances = acct.get("currentBalances", {})

    total_value = float(
        balances.get("liquidationValue")
        or balances.get("equity")
        or 0
    )
    cash_balance = float(balances.get("cashBalance", 0))

    raw_positions = acct.get("positions", [])
    positions = _parse_positions(raw_positions, total_value)
    day_pnl = sum(p.day_pnl for p in positions)

    log.info(
        "schwab_account_loaded",
        positions=len(positions),
        total_value=total_value,
    )

    return AccountSummary(
        account_number=str(acct.get("accountNumber", "")),
        total_value=total_value,
        cash_balance=cash_balance,
        day_pnl=day_pnl,
        positions=positions,
    )


def place_order(request: OrderRequest) -> OrderResult:
    """Place a market or limit equity order on the first linked Schwab account."""
    from schwab.orders.equities import (
        equity_buy_limit,
        equity_buy_market,
        equity_sell_limit,
        equity_sell_market,
    )

    from pmod.auth.schwab import get_client

    if request.quantity <= 0:
        return OrderResult(success=False, message="Quantity must be a positive integer.")

    try:
        client = get_client()

        if request.instruction == "buy":
            if request.order_type == "limit" and request.limit_price:
                order = equity_buy_limit(request.ticker, request.quantity, request.limit_price)
            else:
                order = equity_buy_market(request.ticker, request.quantity)
        elif request.instruction == "sell":
            if request.order_type == "limit" and request.limit_price:
                order = equity_sell_limit(request.ticker, request.quantity, request.limit_price)
            else:
                order = equity_sell_market(request.ticker, request.quantity)
        else:
            return OrderResult(success=False, message=f"Unknown instruction: {request.instruction!r}")

        resp_accts = client.get_accounts()
        resp_accts.raise_for_status()
        accounts: list[dict] = resp_accts.json()
        if not accounts:
            return OrderResult(success=False, message="No Schwab accounts found.")

        acct = _unwrap_account(accounts[0])
        account_number = str(acct.get("accountNumber", ""))

        resp = client.place_order(account_number, order)
        if resp.status_code in (200, 201):
            location = resp.headers.get("Location", "")
            order_id = location.rsplit("/", 1)[-1] if "/" in location else None
            log.info(
                "order_placed",
                ticker=request.ticker,
                instruction=request.instruction,
                quantity=request.quantity,
                order_id=order_id,
            )
            return OrderResult(success=True, order_id=order_id, message="Order placed successfully.")
        else:
            log.error("order_rejected", status=resp.status_code, body=resp.text[:300])
            return OrderResult(success=False, message=f"Order rejected ({resp.status_code}).")

    except Exception as exc:
        log.error("place_order_error", error=str(exc))
        return OrderResult(success=False, message=str(exc))
