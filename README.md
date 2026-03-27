<div align="center">

# PrintMoneyOrDie

**AI-powered portfolio optimizer and automated trading system**

[![Python 3.10+](https://img.shields.io/badge/python-3.10%2B-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)
[![Code style: ruff](https://img.shields.io/badge/code%20style-ruff-000000.svg)](https://github.com/astral-sh/ruff)

Pull market data from multiple financial APIs. Factor in your personal risk tolerance. Execute trades directly on your Schwab brokerage account. Get AI-powered portfolio advice. Monitor everything from a real-time dashboard.

</div>

---

## What It Does

PrintMoneyOrDie (`pmod`) connects to your Charles Schwab account and builds a personalized, AI-driven investment pipeline:

- **Research** — Pulls quotes, history, and news from Polygon.io and Alpha Vantage, then scores tickers on momentum, valuation, and analyst sentiment
- **Optimize** — Runs equal-weight optimization against your risk profile, sector constraints, and position limits — produces a concrete buy/sell diff
- **Trade** — Places market and limit equity orders through Schwab's API with dry-run previews and confirmation prompts
- **Advise** — Asks Claude questions about your live portfolio; structured recommendations (new tickers, risk changes, strategy shifts) can be applied with one click
- **Monitor** — Serves a local Dash/Plotly dashboard with portfolio performance charts, a curated watchlist, congressional trade tracking, and an AI advisor

## Dashboard

Five tabs, all wired to live Schwab data when connected:

| Tab | What it shows |
|---|---|
| **Portfolio** | Daily P&L, total return vs S&P 500, positions table with cost basis and gain/loss, one-click rebalance diff |
| **Watchlist** | AI-curated picks with plain-English reasoning, momentum scores, valuation and sentiment badges, "Add to Portfolio" trade modal |
| **Congress Trades** | Recent congressional stock disclosures with buy/sell signals derived from politician trading patterns |
| **AI Advisor** | Ask Claude anything about your portfolio; Claude responds with analysis and optional actions (add to watchlist, change risk/strategy) |
| **Settings** | Risk tolerance, strategy, sector constraints, max position size, rebalance frequency, trade execution mode |

### Placing a Trade

**From the Watchlist tab** — click **"Add to Portfolio"** on any card.

**From the Portfolio tab** — click **"Suggest Rebalance"** to run the optimizer, then click **"Execute"** on any row.

Both open the same trade modal: set shares, choose market or limit order, review the estimated total, and click **Confirm Order**. The order goes directly to Schwab.

## Quick Start

### Prerequisites

- Python 3.10+
- A [Schwab Developer](https://developer.schwab.com) account (API key + secret)
- A [Polygon.io](https://polygon.io) API key (free tier works)
- An [Anthropic](https://console.anthropic.com) API key for the AI Advisor
- *(Optional)* An [Alpha Vantage](https://www.alphavantage.co) API key

### Installation

```bash
git clone https://github.com/sparktron/print-money-or-die.git
cd print-money-or-die
pip install -e ".[dev]"
```

### Configuration

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
ANTHROPIC_API_KEY=your_anthropic_key
```

> **Security**: `.env` and all token files are gitignored. Never commit credentials.

### First-time Setup

```bash
# Authenticate with Schwab (opens browser once)
pmod auth login

# Set your risk profile and strategy
pmod setup
```

### Launch the Dashboard

```bash
pmod dashboard
```

Opens at [http://localhost:8050](http://localhost:8050).

## CLI Reference

```bash
# Portfolio
pmod portfolio status                   # Live positions and balances
pmod portfolio rebalance --dry-run      # Preview optimizer output, no trades placed
pmod portfolio rebalance                # Execute rebalance (confirmation prompt per trade)

# Research
pmod research run                       # Score tickers and refresh watchlist

# Congressional trades
pmod politicians fetch                  # Pull latest Senate PTR disclosures
pmod politicians signals                # Generate buy/sell signals from disclosure data
pmod politicians list                   # Print recent disclosures (--ticker, --days filters)

# Auth
pmod auth login                         # Schwab OAuth2 browser flow
pmod setup                              # Interactive profile setup wizard
pmod dashboard                          # Launch the web dashboard
```

## Architecture

```
pmod/
├── main.py              # CLI entry point (Click)
├── config.py            # Settings via pydantic-settings + .env
├── auth/schwab.py       # OAuth2 flow + token refresh
├── broker/schwab.py     # Order placement, positions, account data
├── advisor/
│   └── claude.py        # Claude API integration — portfolio Q&A + strategy actions
├── data/
│   ├── market.py        # Market data ingestion (Polygon, Alpha Vantage)
│   ├── models.py        # SQLAlchemy models
│   └── politician_trades.py  # Congressional disclosure ingestion
├── research/
│   ├── signals.py       # Trend analysis + signal generation
│   ├── screener.py      # Ticker filtering + ranking
│   └── politician_signals.py # Buy/sell signals from politician trades
├── optimizer/
│   └── portfolio.py     # Equal-weight rebalance optimization
├── preferences/
│   └── profile.py       # Risk tolerance + strategy management
├── dashboard/
│   ├── app.py           # Dash app setup, tab routing, all callbacks
│   ├── pages/           # Portfolio, watchlist, advisor, congress, settings views
│   └── components/      # Design tokens + reusable Plotly components
└── scheduler/
    └── jobs.py          # APScheduler: research, rebalance, token refresh
```

## User Preferences

All preferences persist in SQLite and are editable from the dashboard Settings tab or by running `pmod setup`:

| Setting | Options | Default |
|---|---|---|
| Risk tolerance | `low` · `medium` · `high` · `degen` | `medium` |
| Strategy | `growth` · `value` · `dividend` · `momentum` · `balanced` | `balanced` |
| Sector constraints | Whitelist / blacklist | None |
| Max position size | 1–100% of portfolio | 5% |
| Rebalance frequency | `manual` · `daily` · `weekly` | `manual` |
| Trade execution | `manual-confirm` · `auto` | `manual-confirm` |

The AI Advisor can also suggest and apply risk and strategy changes directly from its response.

## Development

```bash
pytest          # Run tests
mypy pmod/      # Type checking
ruff check pmod/   # Lint
ruff format pmod/  # Format
```

## Safety & Guardrails

- **Dry-run first** — `pmod portfolio rebalance --dry-run` previews all trades before anything is placed
- **Confirmation prompts** — Rebalance and other destructive actions always prompt before executing
- **Rate limiting** — Schwab (120 req/min) and Polygon (5 req/min free tier) limits are respected with backoff
- **Token management** — Schwab refresh tokens expire in 7 days; the scheduler handles silent re-auth or alerts loudly
- **Input validation** — All API responses are validated through Pydantic before use
- **Credentials** — `.env`, token files, and the SQLite DB are gitignored from day one

## Tech Stack

| Layer | Technology |
|---|---|
| Language | Python 3.10+ |
| Brokerage | schwab-py (OAuth2 + trading) |
| Market data | Polygon.io, Alpha Vantage |
| AI advisor | Anthropic SDK (claude-opus-4-6) |
| Optimization | SciPy |
| Dashboard | Dash + Plotly |
| Scheduling | APScheduler |
| Database | SQLite via SQLAlchemy |
| Config | pydantic-settings |
| Logging | structlog |
| Testing | pytest + pytest-mock |

## License

MIT
