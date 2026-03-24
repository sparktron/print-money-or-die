<div align="center">

# PrintMoneyOrDie

**AI-powered portfolio optimizer and automated trading system**

[![Python 3.10+](https://img.shields.io/badge/python-3.10%2B-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)
[![Code style: ruff](https://img.shields.io/badge/code%20style-ruff-000000.svg)](https://github.com/astral-sh/ruff)

Pull market data from multiple financial APIs. Factor in your personal risk tolerance. Execute trades directly on your Schwab brokerage account. Monitor everything from a real-time dashboard.

</div>

---

## What It Does

PrintMoneyOrDie (`pmod`) connects to your Charles Schwab account and builds a personalized, AI-driven investment pipeline:

- **Research** — Pulls quotes, history, and news from Polygon.io and Alpha Vantage, then scores tickers on momentum, valuation, and analyst sentiment
- **Optimize** — Runs mean-variance and risk-parity optimization against your risk profile, sector constraints, and position limits
- **Trade** — Executes rebalance orders through Schwab's API with mandatory dry-run previews and confirmation prompts
- **Monitor** — Serves a local Dash/Plotly dashboard with portfolio performance charts, position tables, and a curated watchlist

## Dashboard Preview

| Portfolio View | Watchlist |
|:-:|:-:|
| Daily P&L, total return, benchmark vs S&P 500 | AI-curated picks with plain-English reasoning |
| Positions table with cost basis & gain/loss | Momentum scores, valuation metrics, sentiment |
| Rebalance diff view (before → after) | One-click "Add to Portfolio" or "Ignore" |

## Quick Start

### Prerequisites

- Python 3.10+
- A [Schwab Developer](https://developer.schwab.com) account (API key + secret)
- A [Polygon.io](https://polygon.io) API key (free tier works)
- *(Optional)* An [Alpha Vantage](https://www.alphavantage.co) API key

### Installation

```bash
git clone https://github.com/sparktron/print-money-or-die.git
cd print-money-or-die
pip install -e ".[dev]"
```

### Configuration

Copy the example env file and fill in your credentials:

```bash
cp .env.example .env
```

```env
SCHWAB_APP_KEY=your_app_key
SCHWAB_APP_SECRET=your_app_secret
SCHWAB_CALLBACK_URL=https://127.0.0.1:8182/callback
POLYGON_API_KEY=your_polygon_key
ALPHA_VANTAGE_API_KEY=your_alpha_vantage_key
DATABASE_URL=sqlite:///pmod.db
```

> **Security**: `.env` and all token files are gitignored. Never commit credentials.

### Authenticate with Schwab

```bash
pmod auth login
```

This opens your browser for Schwab's OAuth2 flow. Tokens are saved locally and auto-refreshed.

### Launch the Dashboard

```bash
pmod dashboard
```

Opens at [http://localhost:8050](http://localhost:8050) with portfolio, watchlist, and settings views.

## Usage

```bash
# Run a research pass — score tickers and update the watchlist
pmod research run

# View current portfolio and suggested rebalance
pmod portfolio status

# Preview a rebalance (no trades placed)
pmod portfolio rebalance --dry-run

# Execute the rebalance (confirmation prompt required)
pmod portfolio rebalance
```

## Architecture

```
pmod/
├── main.py              # CLI entry point (Click)
├── config.py            # Settings via pydantic-settings + .env
├── auth/schwab.py       # OAuth2 flow + token refresh
├── broker/schwab.py     # Order placement, positions, account data
├── data/
│   ├── market.py        # Market data ingestion (Polygon, Alpha Vantage)
│   └── models.py        # SQLAlchemy models (preferences, watchlist)
├── research/
│   ├── signals.py       # Trend analysis + signal generation
│   └── screener.py      # Ticker filtering + ranking
├── optimizer/
│   └── portfolio.py     # Mean-variance / risk-parity optimization
├── preferences/
│   └── profile.py       # Risk tolerance + strategy management
├── dashboard/
│   ├── app.py           # Dash app setup + tab routing
│   ├── pages/           # Portfolio, watchlist, settings views
│   └── components/      # Reusable Plotly components
└── scheduler/
    └── jobs.py          # APScheduler: research, rebalance, token refresh
```

## User Preferences

All preferences persist in SQLite and are editable from the dashboard settings page:

| Setting | Options | Default |
|---|---|---|
| Risk tolerance | `low` · `medium` · `high` · `degen` | `medium` |
| Strategy | `growth` · `value` · `dividend` · `momentum` · `balanced` | `balanced` |
| Sector constraints | Whitelist / blacklist | None |
| Max position size | 1–100% of portfolio | 5% |
| Rebalance frequency | `manual` · `daily` · `weekly` | `manual` |
| Trade execution | `manual-confirm` · `auto` | `manual-confirm` |

## Development

```bash
# Run tests
pytest

# Type checking
mypy pmod/

# Lint
ruff check pmod/

# Format
ruff format pmod/
```

## Safety & Guardrails

- **Dry-run first** — Every trade path requires `--dry-run` before live execution
- **Confirmation prompts** — Destructive actions (rebalance, sell-all) always ask before proceeding
- **Rate limiting** — Schwab (120 req/min) and Polygon (5 req/min free tier) limits are respected with backoff
- **Token management** — Schwab refresh tokens expire in 7 days; the scheduler handles silent re-auth or alerts loudly
- **Input validation** — All API responses are validated through Pydantic before use

## Tech Stack

| Layer | Technology |
|---|---|
| Language | Python 3.10+ |
| Brokerage | schwab-py (OAuth2 + trading) |
| Market data | Polygon.io, Alpha Vantage |
| Optimization | SciPy |
| Dashboard | Dash + Plotly |
| Scheduling | APScheduler |
| Database | SQLite via SQLAlchemy |
| Config | pydantic-settings |
| Logging | structlog |
| Testing | pytest + pytest-mock |

## License

MIT
