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


if __name__ == "__main__":
    cli()
