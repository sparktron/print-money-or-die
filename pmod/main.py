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
    """Show current portfolio and suggested rebalance."""
    click.echo("Portfolio status: not yet implemented.")


@portfolio.command("rebalance")
@click.option("--dry-run", is_flag=True, help="Preview rebalance without executing.")
def portfolio_rebalance(dry_run: bool) -> None:
    """Execute a rebalance based on optimizer output."""
    if dry_run:
        click.echo("Dry-run rebalance: not yet implemented.")
    else:
        if not click.confirm("Execute live rebalance? This will place real trades."):
            click.echo("Aborted.")
            return
        click.echo("Live rebalance: not yet implemented.")


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
