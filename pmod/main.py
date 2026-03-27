"""CLI entry point for pmod."""

import click
import structlog

log = structlog.get_logger()


@click.group()
def cli() -> None:
    """PrintMoneyOrDie — AI-powered portfolio optimizer."""
    structlog.configure(
        processors=[
            structlog.dev.ConsoleRenderer(),
        ],
        wrapper_class=structlog.make_filtering_bound_logger(0),
    )


@cli.group()
def auth() -> None:
    """Schwab authentication commands."""


@auth.command("login")
def auth_login() -> None:
    """Run the Schwab OAuth2 browser login flow."""
    from pmod.auth.schwab import run_oauth_flow

    run_oauth_flow()


@cli.command("setup")
def setup() -> None:
    """Run the interactive trading profile setup wizard."""
    import json

    import click

    from pmod.preferences.profile import has_completed_setup, save_preferences

    if has_completed_setup():
        if not click.confirm("A profile already exists. Re-run setup and overwrite it?"):
            click.echo("Aborted.")
            return

    click.echo("\n  PrintMoneyOrDie — Trading Profile Setup\n")

    risk_choices = {"1": "low", "2": "medium", "3": "high", "4": "degen"}
    click.echo("  Risk Tolerance:")
    click.echo("    1) Conservative  — capital preservation first")
    click.echo("    2) Moderate      — balanced growth and safety")
    click.echo("    3) Aggressive    — high returns, high volatility")
    click.echo("    4) Full Degen    — max risk, max potential")
    risk_input = click.prompt("  Choice", type=click.Choice(list(risk_choices)), show_choices=False)
    risk = risk_choices[risk_input]

    strategy_choices = {"1": "growth", "2": "value", "3": "dividend", "4": "momentum", "5": "balanced"}
    click.echo("\n  Investment Strategy:")
    click.echo("    1) Growth    — high-revenue momentum, tech/biotech")
    click.echo("    2) Value     — undervalued companies, Buffett-style")
    click.echo("    3) Dividend  — steady income, REITs, utilities")
    click.echo("    4) Momentum  — trade what's working now")
    click.echo("    5) Balanced  — diversified mix of styles")
    strat_input = click.prompt("  Choice", type=click.Choice(list(strategy_choices)), show_choices=False)
    strategy = strategy_choices[strat_input]

    all_sectors = [
        "Technology", "Healthcare", "Financials", "Energy",
        "Consumer Discretionary", "Consumer Staples", "Industrials",
        "Materials", "Utilities", "Real Estate", "Communication Services",
    ]
    click.echo("\n  Sector Focus (comma-separated numbers, or Enter to skip):")
    for i, s in enumerate(all_sectors, 1):
        click.echo(f"    {i:>2}) {s}")
    raw = click.prompt("  Selection", default="")
    sectors: list[str] = []
    if raw.strip():
        for tok in raw.split(","):
            try:
                idx = int(tok.strip()) - 1
                if 0 <= idx < len(all_sectors):
                    sectors.append(all_sectors[idx])
            except ValueError:
                pass

    max_pos = click.prompt(
        "\n  Max position size per ticker (%)", type=float, default=5.0
    )

    rebalance_choices = {"1": "manual", "2": "weekly", "3": "daily"}
    click.echo("\n  Rebalance frequency:")
    click.echo("    1) Manual  — I'll trigger it myself")
    click.echo("    2) Weekly  — every Sunday")
    click.echo("    3) Daily   — every market day")
    reb_input = click.prompt("  Choice", type=click.Choice(list(rebalance_choices)), show_choices=False)
    rebalance = rebalance_choices[reb_input]

    exec_choices = {"1": "manual-confirm", "2": "auto"}
    click.echo("\n  Trade execution:")
    click.echo("    1) Manual Confirm — review each trade before it runs")
    click.echo("    2) Auto-Execute   — optimizer runs trades automatically")
    exec_input = click.prompt("  Choice", type=click.Choice(list(exec_choices)), show_choices=False, default="1")
    execution = exec_choices[exec_input]

    click.echo("\n  Summary:")
    click.echo(f"    Risk:        {risk}")
    click.echo(f"    Strategy:    {strategy}")
    click.echo(f"    Sectors:     {', '.join(sectors) if sectors else 'All'}")
    click.echo(f"    Max pos:     {max_pos}%")
    click.echo(f"    Rebalance:   {rebalance}")
    click.echo(f"    Execution:   {execution}\n")

    if click.confirm("  Save this profile?"):
        save_preferences(
            risk_tolerance=risk,
            strategy=strategy,
            max_position_pct=max_pos,
            rebalance_frequency=rebalance,
            trade_execution=execution,
            sector_focus=sectors,
        )
        click.echo("  Profile saved. Run `pmod dashboard` to launch the UI.\n")
    else:
        click.echo("  Aborted — no changes saved.\n")


@cli.command("dashboard")
def dashboard() -> None:
    """Launch the graphical dashboard."""
    from pmod.dashboard.app import create_app

    app = create_app()
    log.info("starting dashboard", url="http://localhost:8050")
    app.run(debug=True, host="0.0.0.0", port=8050)


@cli.group()
def portfolio() -> None:
    """Portfolio management commands."""


@portfolio.command("status")
def portfolio_status() -> None:
    """Show current portfolio positions and balances."""
    from pmod.broker.schwab import get_account_summary

    summary = get_account_summary()
    if summary is None:
        click.echo("Could not retrieve account — run `pmod auth login` first.")
        return

    click.echo(f"\n  Account  ···{summary.account_number[-4:] if summary.account_number else 'N/A'}")
    click.echo(f"  Value    ${summary.total_value:>14,.2f}")
    click.echo(f"  Cash     ${summary.cash_balance:>14,.2f}")
    day_sign = "+" if summary.day_pnl >= 0 else ""
    click.echo(f"  Day P&L  {day_sign}${abs(summary.day_pnl):>13,.2f}\n")

    if not summary.positions:
        click.echo("  No equity positions.")
        return

    click.echo(f"  {'Ticker':<8} {'Shares':>10} {'Price':>10} {'Value':>12} {'Day P&L':>10} {'Total':>8}")
    click.echo("  " + "-" * 62)
    for p in summary.positions:
        day = f"{'+' if p.day_pnl >= 0 else ''}{p.day_pnl:,.0f}"
        total = f"{'+' if p.total_pnl_pct >= 0 else ''}{p.total_pnl_pct:.1f}%"
        shares_str = (
            f"{p.shares:.4f}".rstrip("0").rstrip(".")
            if p.shares != int(p.shares)
            else str(int(p.shares))
        )
        click.echo(
            f"  {p.ticker:<8} {shares_str:>10} ${p.current_price:>9,.2f} ${p.market_value:>11,.0f} {day:>10} {total:>8}"
        )
    click.echo()


@portfolio.command("rebalance")
@click.option("--dry-run", is_flag=True, help="Preview rebalance without executing.")
def portfolio_rebalance(dry_run: bool) -> None:
    """Rebalance the portfolio using equal-weight optimization."""
    from pmod.optimizer.portfolio import compute_rebalance
    from pmod.preferences.profile import load_preferences_dict

    prefs = load_preferences_dict()
    max_pos = float(prefs.get("max_position_pct", 5.0))

    click.echo(f"\n  Computing rebalance (max position: {max_pos}%)…\n")
    plan = compute_rebalance(max_position_pct=max_pos)

    if not plan.trades:
        click.echo("  No rebalance data — connect Schwab first.")
        return

    click.echo(f"  {'Ticker':<8} {'Action':<6} {'Shares Δ':>10} {'$ Δ':>12}  {'Cur %':>7}  {'Tgt %':>7}")
    click.echo("  " + "-" * 58)
    for t in sorted(plan.trades, key=lambda x: abs(x.dollar_delta), reverse=True):
        sign = "+" if t.shares_delta >= 0 else ""
        dsign = "+" if t.dollar_delta >= 0 else ""
        click.echo(
            f"  {t.ticker:<8} {t.action:<6} {sign}{t.shares_delta:>9}  {dsign}${abs(t.dollar_delta):>10,.0f}"
            f"  {t.current_weight_pct:>6.1f}%  {t.target_weight_pct:>6.1f}%"
        )

    cash_sign = "+" if plan.net_cash_change >= 0 else ""
    click.echo(f"\n  Net cash impact: {cash_sign}${plan.net_cash_change:,.0f}")
    click.echo(f"  Cash available:  ${plan.cash_available:,.0f}\n")

    if dry_run:
        click.echo("  Dry run — no trades placed.\n")
        return

    actionable = [t for t in plan.trades if t.action != "hold"]
    if not actionable:
        click.echo("  Portfolio is already balanced.\n")
        return

    if not click.confirm(f"  Execute {len(actionable)} trade(s)? This will place real orders."):
        click.echo("  Aborted.\n")
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
        status = "OK" if result.success else "FAIL"
        sign = "+" if t.shares_delta > 0 else ""
        click.echo(f"  [{status}] {t.action.upper()} {abs(t.shares_delta)} {t.ticker} — {result.message}")

    click.echo()


@cli.group()
def research() -> None:
    """Research and screening commands."""


@research.command("run")
def research_run() -> None:
    """Run a research pass and update watchlist."""
    click.echo("Research pass: not yet implemented.")


@cli.group()
def politicians() -> None:
    """Congressional trade disclosure tracking commands."""


@politicians.command("fetch")
def politicians_fetch() -> None:
    """Fetch the latest congressional trade disclosures and store them."""
    from pmod.data.politician_trades import fetch_and_store_trades

    click.echo("Fetching Senate PTR disclosures from efdsearch.senate.gov…")
    click.echo("(House PTR data not yet available — individual filings are PDFs only)")
    counts = fetch_and_store_trades()
    click.echo(
        f"Done — Senate: {counts['senate']}, Skipped: {counts['errors']}"
    )


@politicians.command("signals")
@click.option("--days", default=90, show_default=True, help="Rolling window in days.")
@click.option("--min-trades", default=2, show_default=True, help="Minimum trades to signal.")
def politicians_signals(days: int, min_trades: int) -> None:
    """Generate buy/sell signals from congressional trade data."""
    from pmod.research.politician_signals import generate_signals

    click.echo(f"Generating signals from last {days} days of disclosures…")
    signals = generate_signals(window_days=days, min_trades=min_trades)
    if not signals:
        click.echo("No signals generated — run `pmod politicians fetch` first.")
        return

    strong_buys = [s for s in signals if s.signal == "strong_buy"]
    buys = [s for s in signals if s.signal == "buy"]
    sells = [s for s in signals if s.signal == "sell"]

    click.echo(f"\nGenerated {len(signals)} signals:")
    click.echo(f"  Strong Buy : {len(strong_buys)}")
    click.echo(f"  Buy        : {len(buys)}")
    click.echo(f"  Sell       : {len(sells)}")

    if strong_buys:
        click.echo("\nTop Strong Buy signals:")
        for s in sorted(strong_buys, key=lambda x: x.confidence, reverse=True)[:5]:
            click.echo(
                f"  {s.ticker:<6} {round(s.confidence * 100):>3}% confidence — {s.rationale}"
            )


@politicians.command("list")
@click.option("--ticker", default=None, help="Filter by ticker symbol.")
@click.option("--days", default=90, show_default=True, help="Look-back window in days.")
@click.option("--limit", default=20, show_default=True, help="Max rows to display.")
def politicians_list(ticker: str | None, days: int, limit: int) -> None:
    """List recent congressional trade disclosures."""
    from pmod.data.politician_trades import get_recent_trades

    trades = get_recent_trades(days=days, ticker=ticker)[:limit]
    if not trades:
        click.echo("No trades found — run `pmod politicians fetch` first.")
        return

    click.echo(f"\n{'Date':<12} {'Politician':<35} {'Ticker':<8} {'Type':<10} {'Amount Range'}")
    click.echo("-" * 90)
    for t in trades:
        date_str = t.disclosure_date.strftime("%Y-%m-%d") if t.disclosure_date else "N/A"
        amount = (
            f"${t.amount_low:,} – ${t.amount_high:,}"
            if t.amount_low and t.amount_high
            else "Undisclosed"
        )
        click.echo(
            f"{date_str:<12} {t.politician_name[:34]:<35} {t.ticker:<8} {t.trade_type:<10} {amount}"
        )


if __name__ == "__main__":
    cli()
