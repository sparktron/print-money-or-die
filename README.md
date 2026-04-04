<div align="center">

# PrintMoneyOrDie

### AI-powered portfolio optimizer and automated trading system for Charles Schwab

[![Python 3.11+](https://img.shields.io/badge/python-3.11%2B-blue.svg)](https://www.python.org/downloads/)
[![Tests](https://img.shields.io/badge/tests-133%20passing-brightgreen.svg)](tests/)
[![Type checked: mypy](https://img.shields.io/badge/type%20checked-mypy-blue.svg)](https://mypy-lang.org/)
[![Code style: ruff](https://img.shields.io/badge/code%20style-ruff-000000.svg)](https://github.com/astral-sh/ruff)
[![License: MIT](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)

Pull market data from multiple financial APIs. Factor in your personal risk tolerance. Execute trades directly on your Schwab brokerage account. Monitor everything from a real-time dashboard.

</div>

---

> **Financial Disclaimer** — This software is for informational and educational purposes only. It is not financial advice. Automated trading involves significant risk; you may lose money. Always review trades before execution. The authors are not responsible for financial losses resulting from use of this software.

---

## Table of Contents

- [What It Does](#what-it-does)
- [Dashboard](#dashboard)
  - [Placing a Trade](#placing-a-trade)
  - [Performance Tracking & Alpha](#performance-tracking--alpha)
- [Quick Start](#quick-start)
- [CLI Commands](#cli-commands)
- [Scheduler Behavior](#scheduler-behavior)
- [Common Workflows](#common-workflows)
- [Troubleshooting & Tips](#troubleshooting--tips)
- [Architecture](#architecture)
- [User Preferences](#user-preferences)
- [Development](#development)
- [Safety & Guardrails](#safety--guardrails)
- [Tech Stack](#tech-stack)
- [License](#license)

---

## What It Does

`pmod` connects to your Charles Schwab account and builds a personalized, AI-driven investment pipeline:

| Stage | What happens |
|-------|-------------|
| **Research** | Pulls quotes, history, and news from Polygon.io and Alpha Vantage; scores tickers on momentum (RSI, SMA crossover), valuation, and politician trading patterns |
| **Optimize** | Equal-weight optimization with iterative cap enforcement against your risk profile, sector constraints, and position limits — produces a concrete buy/sell diff |
| **Trade** | Places market and limit equity orders through Schwab's API; dry-run previews and confirmation prompts always required; rate-limited with automatic retry |
| **Advise** | Ask Claude questions about your live portfolio; structured recommendations (new tickers, risk changes, strategy shifts) can be applied with one click |
| **Track** | Captures daily portfolio and S&P 500 (SPY) snapshots to calculate alpha (excess return) over time; displays a 1-year performance comparison chart |
| **Schedule** | Background jobs handle token refresh (every 4h), politician trade fetches (6:30 AM ET), daily research (7 AM ET), external account updates (4:25 PM ET), portfolio snapshots (4:30 PM ET), and benchmark snapshots (4:35 PM ET) |
| **Monitor** | Local Dash/Plotly dashboard with portfolio charts, alpha metrics, a curated watchlist, politician trade tracking, and an AI advisor |

---

## Dashboard

Five tabs, all wired to live Schwab data when connected:

| Tab | What it shows |
|-----|---------------|
| **Portfolio** | Live balance and daily P&L across all accounts, alpha vs S&P 500, 1-year performance chart, per-account positions table, account filter dropdown, one-click rebalance diff |
| **Watchlist** | AI-curated picks with plain-English reasoning, momentum scores, valuation and sentiment badges, "Add to Portfolio" trade modal |
| **Politician Trades** | Recent senator/representative stock disclosures with buy/sell consensus signals derived from PTR data |
| **AI Advisor** | Ask Claude anything about your portfolio; Claude responds with analysis and optional one-click actions (add to watchlist, change risk/strategy) |
| **Settings** | Risk tolerance, strategy, sector constraints, max position size, rebalance frequency, trade execution mode |

### Placing a Trade

**From the Watchlist tab** — click **"Add to Portfolio"** on any card.

**From the Portfolio tab** — click **"Suggest Rebalance"** to run the optimizer, then click **"Execute"** on any row.

Both open the same trade modal: set shares, choose market or limit order, review the estimated total, and click **Confirm Order**. The order goes directly to Schwab.

### Performance Tracking & Alpha

The **Portfolio** tab shows an **"Alpha vs S&P"** metric and a 1-year performance chart:

- **Alpha** — Your portfolio's excess return vs SPY (S&P 500 ETF)
  - Positive alpha = beating the market
  - Negative alpha = underperforming the market
  - Calculated from daily portfolio and S&P 500 snapshots

- **Real data** appears once you have at least 2 daily snapshots
  - Portfolio snapshots: **4:30 PM ET** (after market close)
  - S&P 500 snapshots: **4:35 PM ET**
  - "Insufficient data" shows until day 2 — give it 2 market closes

- **Simulated mode** — Until snapshots are captured, the dashboard renders simulated 1-year returns for visualization

**Getting real data:**
1. **Schwab accounts** — Live data from the API automatically
2. **External accounts** (401k, IRA, etc.) — edit `external_positions_config.csv` and run `pmod external import`; prices update daily at 4:25 PM ET
3. Start the dashboard: `pmod dashboard`
4. After your second market close, real alpha and chart data appear

---

## Quick Start

### Prerequisites

- Python 3.11+
- A [Schwab Developer](https://developer.schwab.com) account (app key + secret)
- A [Polygon.io](https://polygon.io) API key (free tier works)
- An [Anthropic](https://console.anthropic.com) API key (for AI Advisor)
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
# Edit .env with your API keys
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

> **Security** — `.env` and all token files are gitignored. Never commit credentials.

### First-time Setup

```bash
# Authenticate with Schwab (opens browser once; tokens saved locally)
pmod auth login

# Interactive wizard: risk profile, strategy, position limits, sectors
pmod setup
```

### Launch the Dashboard

```bash
pmod dashboard
# Opens at http://localhost:8050
```

---

## CLI Commands

### Portfolio

| Command | Description |
|---------|-------------|
| `pmod portfolio status` | Live snapshot: positions, balances, P&L |
| `pmod portfolio rebalance --dry-run` | Preview optimizer output — **no orders placed** |
| `pmod portfolio rebalance` | Execute rebalance (confirmation prompt per trade) |

### Research

| Command | Description |
|---------|-------------|
| `pmod research run` | Full research pass: quotes, technicals, strategy scoring, watchlist refresh |

### Politician Trades

| Command | Description |
|---------|-------------|
| `pmod politicians fetch` | Pull latest Senate PTR disclosures from efdsearch.senate.gov |
| `pmod politicians signals` | Compute buy/sell consensus signals from aggregated disclosures |
| `pmod politicians list [--ticker X] [--days N]` | Print recent trades to terminal with optional filters |

### External Accounts

`pmod` tracks external accounts (401k, 529, IRA at other custodians) via manual CSV imports. The Schwab API only returns accounts held directly at Schwab.

| Command | Description |
|---------|-------------|
| `pmod external import <file.csv> --account "Name" [--account-type TYPE] [--dry-run]` | Import positions from CSV (replaces existing on re-import) |
| `pmod external list` | Show all external accounts with position counts and values |
| `pmod external show "Account Name"` | Print all positions for a named account |
| `pmod external clear "Account Name"` | Delete account and all positions (confirmation required) |
| `pmod external update` | Refresh prices for all external positions from Polygon |

**CSV column mapping** — common headers from Schwab, Fidelity, Vanguard exports are recognised automatically:

| Your CSV header | Maps to |
|-----------------|---------|
| Symbol, Ticker | ticker |
| Description, Name, Security | company name |
| Quantity, Units, Shares | shares |
| Average Cost, Avg Cost, Cost Basis | avg cost |
| Price, Current Price, Last Price, NAV | price |
| Market Value, Value, Total Value | market value |

**Share configuration file** (`external_positions_config.csv`):

```csv
account_name,ticker,shares
ADP,VBILX,1000.00
Start Right,FXAIX,1000.00
Schwab,BTC,0.5
```

Edit this file to keep share counts current. External accounts will have daily price updates at 4:25 PM ET.

```bash
# Preview parse (nothing written)
pmod external import adp.csv --account "ADP 401k" --account-type 401k --dry-run

# Import for real
pmod external import adp.csv --account "ADP 401k" --account-type 401k

# Re-import after updating the file (fully replaces previous positions)
pmod external import adp_updated.csv --account "ADP 401k" --account-type 401k
```

### Auth & Setup

| Command | Description |
|---------|-------------|
| `pmod auth login` | Schwab OAuth2 browser flow — run once; tokens auto-refresh every 4h |
| `pmod setup` | Interactive wizard to configure your risk profile and preferences |
| `pmod dashboard` | Launch the Dash/Plotly dashboard at `http://localhost:8050` |

---

## Scheduler Behavior

When the dashboard is running, background jobs execute automatically:

| Job | Schedule | Description |
|-----|----------|-------------|
| Token Refresh | Every 4 hours | Silently refreshes Schwab OAuth tokens |
| Politician Trades Fetch | Daily 6:30 AM ET | Pulls latest Senate PTR disclosures |
| Research Pass | Daily 7:00 AM ET | Scores tickers, refreshes watchlist, updates signals |
| External Account Update | Daily 4:25 PM ET | Fetches prices for external positions, stores snapshots |
| Portfolio Snapshot | Daily 4:30 PM ET | Captures portfolio value for alpha calculation |
| Benchmark Snapshot | Daily 4:35 PM ET | Captures S&P 500 (SPY) closing price |
| Rebalance | Per preference | Auto-runs optimizer when execution mode is set to `auto` |

External accounts also update at dashboard startup (in a background thread) so you see current prices immediately.

---

## Common Workflows

### First-Time Setup

```bash
git clone https://github.com/sparktron/print-money-or-die.git
cd print-money-or-die
pip install -e ".[dev]"
cp .env.example .env          # then fill in your API keys

pmod auth login               # browser opens, approve access
pmod setup                    # set risk, strategy, max position %, etc.
pmod dashboard                # http://localhost:8050
```

Alpha metrics appear after 2 market closes (4:30 PM ET daily). Until then, the chart shows simulated returns.

---

### Adding a Stock

**Via Watchlist tab:**
1. Find a card that matches your strategy
2. Read the "WHY THIS FITS YOU" explanation
3. Click **"Add to Portfolio"** → enter shares, choose order type, confirm

**Via rebalancer:**
1. Portfolio tab → **"Suggest Rebalance"**
2. Review the buy/sell diff, optionally click **"Dry Run"**
3. Click **"Execute"** to place all trades

**Via CLI:**
```bash
pmod portfolio rebalance --dry-run    # preview first
pmod portfolio rebalance              # then execute
```

---

### Adjusting Your Risk Profile

**Dashboard:** Settings tab → change Risk Tolerance or Strategy → **"Save Settings"**

**CLI:** `pmod setup` (re-run the interactive wizard)

Changes take effect at the next research pass. Run `pmod research run` immediately to rescore the watchlist.

---

### Tracking Performance vs the Market

1. Dashboard → Portfolio tab → **"Alpha vs S&P"** KPI card
2. Positive % = beating S&P 500; negative % = underperforming
3. The 1-year chart shows your portfolio (blue) vs S&P 500 (dotted)
4. Data accumulates automatically — keep the dashboard running through market closes

---

### Getting AI Advice

1. Dashboard → AI Advisor tab
2. Ask anything, for example:
   - *"Should I trim my XYZ position?"*
   - *"What's my biggest concentration risk?"*
   - *"Explain my sector exposure"*
3. Claude responds with analysis and optional one-click actions:
   - **"Add TICKER to watchlist"**
   - **"Change risk to HIGH"**
   - **"Change strategy to DIVIDEND"**

Requires `ANTHROPIC_API_KEY` in `.env`. No persistent memory between sessions.

---

### Monitoring Politician Trades

1. Dashboard → Politician Trades tab
2. Check the Signal column:
   - **STRONG_BUY** (green) — strong buying consensus, high confidence
   - **BUY** (light green) — positive signals
   - **HOLD** (yellow) — mixed or no recent activity
   - **SELL** (red) — politicians exiting positions
3. Use as a research signal, not a guarantee — cross-check with technicals and fundamentals

```bash
# CLI: all Apple trades by politicians in the last 90 days
pmod politicians list --ticker AAPL --days 90
```

---

## Troubleshooting & Tips

### Dashboard

| Symptom | Fix |
|---------|-----|
| Won't start | Check port 8050 isn't in use: `lsof -i :8050` (macOS/Linux) or `netstat -ano \| findstr :8050` (Windows) |
| "Insufficient data" for alpha | Normal — need 2 daily snapshots. Check machine timezone is correct (scheduler uses US/Eastern) |
| Watchlist empty | Run `pmod research run`; verify `POLYGON_API_KEY` is set |
| Shows "SAMPLE DATA" not "LIVE" | Run `pmod auth login`; verify `~/.pmod/schwab_tokens.json` exists and `.env` keys are correct |
| AI Advisor not responding | Check `ANTHROPIC_API_KEY` in `.env`; verify Anthropic account has credits |

### Trading

| Symptom | Fix |
|---------|-----|
| Order rejected | Insufficient buying power; fractional shares not allowed; market must be open (9:30 AM–4:00 PM ET); check for PDT restrictions |
| Dry-run passes but execute fails | Prices moved between preview and execution; check Schwab account for order details |
| Rebalance didn't execute | Verify trade execution setting — `manual-confirm` needs a dialog click per trade; `auto` only runs on schedule |

### API & Data

| Symptom | Fix |
|---------|-----|
| `POLYGON_API_KEY is not set` | Add to `.env`; free key at polygon.io; 5 req/min rate limit applied automatically |
| Stale market data | Polygon updates during market hours + ~5 min post-close; run `pmod research run` to refresh |
| Politician trades not updating | Senate PTR database has 1–2 week disclosure lag; run `pmod politicians fetch` manually |
| External accounts not in portfolio | Run `pmod external import`; verify with `pmod external list`; check `external_positions_config.csv` has correct share counts |

### Authentication

**"Schwab access token expired"** — Tokens refresh automatically every 4h. If you see auth errors:

```bash
# Ctrl+C to stop dashboard, then:
pmod auth login
pmod dashboard
```

This happens naturally every 7 days (refresh token expiry).

**OAuth callback mismatch** — `SCHWAB_CALLBACK_URL` in `.env` must exactly match your Schwab Developer app registration (default: `https://127.0.0.1:8182/callback`).

### Performance

- **Optimizer slow** — First run may take 30+ seconds (scipy is CPU-bound); subsequent runs are faster
- **Research pass slow** — Polygon free tier is 5 req/min; 100+ tickers ≈ 20 min; consider off-peak runs or a premium tier
- **Dashboard laggy** — Reduce other browser tabs; check `tail -f pmod.log` for warnings

### Best Practices

- Always dry-run before rebalancing: `pmod portfolio rebalance --dry-run`
- Use **"Hide $"** button (top-right) to mask balances during screen shares
- Monitor alpha trend: +5% over 1 year is solid; sustained negative alpha = consider strategy review
- Ask the AI Advisor when something looks off — it has full access to your live positions

---

## Architecture

```
pmod/
├── main.py                    # CLI entry point (Click)
├── config.py                  # Settings via pydantic-settings + .env
├── exceptions.py              # Typed exception hierarchy (AuthError, BrokerError, …)
├── auth/
│   └── schwab.py              # OAuth2 flow + token refresh
├── broker/
│   └── schwab.py              # Order placement, positions, account data (rate-limited)
├── advisor/
│   └── claude.py              # Claude API — portfolio Q&A + strategy actions
├── analytics/
│   └── alpha.py               # Alpha calculation vs S&P 500 benchmark
├── data/
│   ├── market.py              # Market data ingestion (Polygon.io, rate-limited + retried)
│   ├── models.py              # SQLAlchemy models
│   ├── external_accounts.py   # CSV import + query helpers for manually-tracked accounts
│   └── politician_trades.py   # Senate EFD scraper + disclosure ingestion
├── research/
│   ├── signals.py             # Technical indicators (RSI, SMA crossover, volatility)
│   ├── screener.py            # Score + rank tickers by strategy fit
│   └── politician_signals.py  # Aggregate buy/sell signals from politician trades
├── optimizer/
│   └── portfolio.py           # Equal-weight rebalance with iterative position-cap enforcement
├── preferences/
│   └── profile.py             # Risk tolerance + strategy management
├── utils/
│   └── retry.py               # Exponential backoff decorator + token-bucket rate limiter
├── dashboard/
│   ├── app.py                 # Dash app setup, tab routing, all callbacks
│   ├── pages/                 # Portfolio, watchlist, advisor, politician trades, settings views
│   └── components/            # Design tokens + reusable Plotly components
└── scheduler/
    └── jobs.py                # APScheduler: token refresh, research, snapshots, rebalance
```

---

## User Preferences

All preferences persist in SQLite and are editable from the Settings tab or via `pmod setup`:

| Setting | Options | Default |
|---------|---------|---------|
| Risk tolerance | `low` · `medium` · `high` · `degen` | `medium` |
| Strategy | `growth` · `value` · `dividend` · `momentum` · `balanced` | `balanced` |
| Max position size | 1–100% of portfolio per ticker | `5%` |
| Rebalance frequency | `manual` · `daily` · `weekly` | `manual` |
| Trade execution | `manual-confirm` · `auto` | `manual-confirm` |
| Sector constraints | whitelist / blacklist | none |

The AI Advisor can also suggest and apply risk and strategy changes directly from a chat response.

---

## Development

```bash
pytest                 # Run all 133 tests
mypy pmod/             # Type check
ruff check pmod/       # Lint
ruff format pmod/      # Format
```

---

## Safety & Guardrails

- **Dry-run first** — `pmod portfolio rebalance --dry-run` previews every trade before anything is placed
- **Confirmation prompts** — Rebalance and all destructive actions prompt before executing; no silent auto-confirm
- **Rate limiting** — Thread-safe token-bucket limiters for Schwab (120 req/min) and Polygon (5 req/min free tier)
- **Retry with backoff** — Transient API failures retry automatically with exponential backoff
- **Token management** — Schwab refresh tokens expire in 7 days; scheduler refreshes every 4h and alerts on expiry
- **Typed exceptions** — Structured hierarchy (`AuthError`, `BrokerError`, `RateLimitError`, …) for precise error handling
- **Input validation** — All API responses validated through Pydantic before use
- **Credentials** — `.env`, token files, and the SQLite DB are gitignored from day one

---

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Language | Python 3.11+ |
| Brokerage | schwab-py (OAuth2 + trading) |
| Market data | Polygon.io, Alpha Vantage |
| AI advisor | Anthropic SDK (Claude) |
| Optimization | SciPy |
| Dashboard | Dash + Plotly |
| Scheduling | APScheduler |
| Database | SQLite via SQLAlchemy |
| Config | pydantic-settings |
| Logging | structlog |
| Testing | pytest + pytest-mock (133 tests) |

---

## License

MIT © [sparktron](https://github.com/sparktron)
