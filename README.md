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

- **Research** — Pulls quotes, history, and news from Polygon.io and Alpha Vantage, then scores tickers on momentum (RSI, SMA crossover, composite momentum), valuation, and politician trading patterns
- **Optimize** — Runs equal-weight optimization with iterative cap enforcement against your risk profile, sector constraints, and position limits — produces a concrete buy/sell diff
- **Trade** — Places market and limit equity orders through Schwab's API with dry-run previews and confirmation prompts; rate-limited with automatic retry on transient failures
- **Advise** — Ask Claude questions about your live portfolio; structured recommendations (new tickers, risk changes, strategy shifts) can be applied with one click
- **Track** — Captures daily portfolio and S&P 500 (SPY) snapshots to calculate your alpha (excess return) over time; displays a 1-year performance comparison chart
- **Schedule** — Background jobs handle token refresh (every 4h), politician trade fetches (6:30 AM ET), daily research passes (7 AM ET), external account price updates (4:25 PM ET), portfolio snapshots (4:30 PM ET), benchmark snapshots (4:35 PM ET), and configurable rebalancing
- **Monitor** — Serves a local Dash/Plotly dashboard with portfolio performance charts, alpha metrics, a curated watchlist, politician trade tracking, and an AI advisor

## Dashboard

Five tabs, all wired to live Schwab data when connected:

| Tab | What it shows |
|---|---|
| **Portfolio** | Live balance and daily P&L across all accounts, alpha (excess return vs S&P 500), 1-year performance chart, per-account positions tables, account filter dropdown, one-click rebalance diff |
| **Watchlist** | AI-curated picks with plain-English reasoning, momentum scores, valuation and sentiment badges, "Add to Portfolio" trade modal |
| **Politician Trades** | Recent politician stock disclosures with buy/sell signals derived from politician trading patterns |
| **AI Advisor** | Ask Claude anything about your portfolio; Claude responds with analysis and optional actions (add to watchlist, change risk/strategy) |
| **Settings** | Risk tolerance, strategy, sector constraints, max position size, rebalance frequency, trade execution mode |

### Placing a Trade

**From the Watchlist tab** — click **"Add to Portfolio"** on any card.

**From the Portfolio tab** — click **"Suggest Rebalance"** to run the optimizer, then click **"Execute"** on any row.

Both open the same trade modal: set shares, choose market or limit order, review the estimated total, and click **Confirm Order**. The order goes directly to Schwab.

### Performance Tracking & Alpha

The **Portfolio** tab displays a **"Alpha vs S&P"** metric and a 1-year performance chart comparing your portfolio to the S&P 500:

- **Alpha** — Your portfolio's excess return vs SPY (S&P 500 ETF)
  - Positive alpha = beating the market
  - Negative alpha = underperforming the market
  - Calculated from daily portfolio snapshots and S&P 500 closes

- **Real data** — The chart shows actual historical returns once you have at least 2 daily snapshots
  - Portfolio snapshots captured daily at **4:30 PM ET** (after market close)
  - S&P 500 snapshots captured daily at **4:35 PM ET**
  - Data displayed starting from your second snapshot (minimum 2 days)
  - **Insufficient data** message appears until you have 2+ snapshots (give it 2 market closes)

- **Simulated mode** — Until snapshots are captured, the dashboard shows simulated 1-year returns for visualization

**Getting Real Data:**
1. **Schwab accounts**: Live data from API automatically
2. **External accounts** (401k, IRA, etc.):
   - Edit `external_positions_config.csv` with your account holdings and share counts
   - Run `pmod external import` to import initial positions from CSV
   - Prices update automatically daily at 4:25 PM ET and on dashboard startup
   - After 2+ days, historical data available for performance charts
3. Start the dashboard: `pmod dashboard`
4. The scheduler automatically captures snapshots daily at 4:30 PM & 4:35 PM ET
5. After your first market close, you'll have 1 snapshot; alpha still shows "Insufficient data"
6. After your second market close, real alpha appears! Chart updates with actual returns

## Features & Usage Guide

### 📊 Portfolio Tab

**What you see:**
- **Live portfolio metrics** — Total balance, today's P&L (+/- dollar and %), number of positions
- **Alpha vs S&P** — Your excess return compared to the market (explained above)
- **1-year performance chart** — Portfolio vs S&P 500 side-by-side line chart
- **Positions table** — Each holding with shares, cost basis, current price, gain/loss (total and %), portfolio weight

**Positions table columns:**
- **ASSET** — Stock ticker (clickable to see details)
- **SHARES** — Number of shares you own
- **AVG COST** — Your average purchase price
- **PRICE** — Current market price
- **VALUE** — Total market value (shares × price)
- **DAY P&L** — Today's profit/loss in dollars and %
- **TOTAL P&L** — Total profit/loss since purchase in dollars and %
- **WEIGHT** — % of portfolio this position represents

**Actions:**
- **"Suggest Rebalance"** button — Runs the optimizer against your risk profile and constraints, shows what positions to buy/sell
  - Shows expected vs current allocation
  - Lists specific trades: how many shares to buy/sell per ticker
  - Preview changes with "Dry Run" before committing
  - One-click "Execute" to place all trades (with per-trade confirmation prompts)

**Privacy:**
- Click **"Hide $"** in top-right to mask all dollar amounts on screen (useful if someone is watching)
- Masked view shows sentiment colors and percentages but hides exact dollar values
- Click **"Show $"** to reveal amounts again

---

### 🎯 Watchlist Tab

**What you see:**
- **AI-curated investment opportunities** — Cards with tickers your strategy/signals recommend
- **Why it fits you** — Plain-English explanation of why Claude thinks this matches your preferences
- **Momentum score** — 0–100 technical momentum indicator (RSI, SMA crossover blend)
- **Valuation badge** — Visual indicator of valuation vs historical average
- **Sentiment badge** — "BULLISH", "VERY BULLISH", "HOLD", etc. from politician trading activity
- **Price and change %** — Current quote and today's % move

**Actions:**
- **"Add to Portfolio"** — Opens trade modal to buy shares (see "Placing a Trade" below)
- **"Dismiss"** — Hide this card from your watchlist (useful if you've already added it or not interested)

**How the watchlist is populated:**
- Daily research pass (6 AM ET) scores all tickers against your strategy
  - Momentum-based buys for momentum strategy
  - Dividend stocks for dividend strategy
  - Value plays for value strategy
  - etc.
- Politician trading signals — When politicians are buying, stocks rise to the top
- Only top 15 candidates shown to keep it curated (not overwhelming)

---

### 🏛️ Politician Trades Tab

**What you see:**
- **Recent senator/representative stock trades** — Buy and sell activity disclosed in Senate ETF database
- For each trade:
  - **Politician name** — Who made the trade
  - **Party & state** — Context (D/R, state abbreviation)
  - **Ticker** — Stock traded
  - **Action** — BUY, SELL, EXCHANGE
  - **Amount** — Dollar range (e.g., "$100k–$250k")
  - **Transaction date** — When the trade happened
  - **Disclosure date** — When it was publicly reported (often weeks later)

**Why it matters:**
- Politicians often have better information than the public before trades become public
- Aggregated signals: when many politicians buy the same stock, it's a strong bullish signal
- Helps identify institutional-quality picks early

**Signals shown:**
- **Buy signal** — Multiple politicians buying, strong consensus
- **Sell signal** — Multiple politicians exiting positions
- **Hold** — Mixed activity or no recent trades
- **Confidence score** — How certain the signal is (based on # of politicians, % agreement)

**Actions:**
- Click on any ticker to see the full trading chain
- Filter by ticker, date range, or politician name (if search is enabled)

---

### 🤖 AI Advisor Tab

**What you see:**
- **Text input box** — Ask Claude anything about your portfolio
- **Live Schwab data** — Claude has real-time access to your positions, balances, and performance

**Example questions:**
- "Should I sell XYZ? I'm worried about valuations."
- "What's my biggest position and should I trim it?"
- "Given my risk profile, how much should I keep in cash?"
- "Explain my portfolio's sector exposure"
- "Should I buy more tech given current market conditions?"

**What Claude can do:**
- **Analyze** your portfolio composition, risk, performance
- **Suggest** new tickers to add from the watchlist
- **Recommend** risk tolerance or strategy changes
- **Explain** why a position is in your portfolio
- **Calculate** impact of hypothetical trades

**Actions:**
- Claude can suggest one-click actions:
  - **"Add TICKER to watchlist"** — Instantly adds to your watch list
  - **"Change risk from MEDIUM to HIGH"** — Updates your risk preference
  - **"Change strategy to DIVIDEND"** — Switches your investing strategy
  - Links open modals or apply changes directly

**How it works:**
- Your message and portfolio data sent to Claude API (configured via `ANTHROPIC_API_KEY`)
- Claude analyzes your holdings and responds with actionable advice
- All communication is secure; Claude has no persistent memory between sessions

---

### ⚙️ Settings Tab

**What you see:**
- **Risk tolerance** — low / medium / high / degen (degenerate/aggressive)
- **Strategy** — growth / value / dividend / momentum / balanced
- **Max position size** — Maximum % of portfolio a single position can occupy (1–100%, default 5%)
- **Rebalance frequency** — manual / daily / weekly
- **Trade execution** — manual-confirm (prompt for each trade) / auto (execute without prompt)
- **Sector constraints** — Whitelist or blacklist specific sectors (e.g., "No tobacco, focus on tech")

**What each setting does:**

| Setting | Impact |
|---------|--------|
| **Risk tolerance** | Affects portfolio optimization (high = more aggressive picks, more volatility) |
| **Strategy** | Changes which stocks appear on watchlist (momentum vs value vs dividend, etc.) |
| **Max position size** | Rebalancer won't let any single stock exceed this % (prevents over-concentration) |
| **Rebalance frequency** | manual = you click "Suggest Rebalance" manually; daily = auto-runs at 10 AM ET; weekly = Sundays |
| **Trade execution** | manual-confirm = each trade gets a confirmation dialog; auto = executes silently if rebalance is automated |
| **Sectors** | Screener ignores tickers in blacklisted sectors, or only considers whitelisted ones |

**How to update:**
1. Change a setting in the Settings tab
2. Click **"Save Settings"** at the bottom
3. Settings persist to your local SQLite database
4. Changes take effect immediately for new research passes, watchlist refreshes, or rebalances

---

### 🔄 Trading Workflow (Detailed)

#### Placing a Single Trade

**From Watchlist:**
1. Find a stock card you like
2. Click **"Add to Portfolio"**
3. Trade modal opens:
   - **Ticker** — Pre-filled (e.g., "XOM")
   - **Quantity** — Enter how many shares to buy
   - **Order type** — Market (fills immediately at best price) or Limit (set your price, may not fill)
   - **Limit price** — Only shown if you chose Limit order type
   - **Estimated total** — Shows total cost (quantity × estimated price)
4. Review and click **"Confirm Order"**
5. Order sent to Schwab; you'll see confirmation with order ID

#### Portfolio Rebalancing

**Full rebalance workflow:**
1. Click **"Suggest Rebalance"** on Portfolio tab
2. Optimizer runs:
   - Takes your current holdings
   - Calculates target weights based on your strategy + risk
   - Applies max position size constraints
   - Generates buy/sell list to reach target
3. Modal shows:
   - **Current allocation** — Your actual % per ticker
   - **Target allocation** — Where optimizer thinks you should be
   - **Trades needed** — Specific buy/sell orders
   - **Cash impact** — Net cash freed up or required
4. Options:
   - **"Dry Run"** — Preview without executing (see what would happen)
   - **"Execute"** — Place all trades (get confirmation per trade)
5. Each trade shows:
   - Action (BUY / SELL)
   - Ticker and # shares
   - Order type (Market / Limit)
   - Estimated price and total
   - Confirm / Skip buttons

---

### 🔐 Privacy & Safety Features

**Privacy mask:**
- Click **"Hide $"** button (top right) to mask all dollar amounts
- Useful during screen shares or if someone's watching
- Shows positions, percentages, and sentiment but hides exact balances
- Completely client-side (no data sent)

**Order confirmation:**
- Every trade requires explicit confirmation before being sent to Schwab
- No "auto-confirm" modal dismissal; you must actively click
- Prevents accidental bulk trades

**Dry-run before live:**
- Always run `pmod portfolio rebalance --dry-run` (or use modal "Dry Run") before executing trades
- Lets you verify optimizer logic without placing orders

---

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

## CLI Commands

### Portfolio Commands

**`pmod portfolio status`**
- Shows your current portfolio snapshot (live from Schwab)
- Lists all positions: ticker, shares, cost basis, current price, gain/loss
- Shows account balances and total portfolio value
- Useful for quick command-line check without opening dashboard

**`pmod portfolio rebalance --dry-run`**
- Runs the optimizer against your current holdings
- **DOES NOT place any orders** — just shows what the optimizer would do
- Previews the rebalance plan: target allocation, trades needed, cash impact
- Always run this first to verify the optimizer logic makes sense
- Output includes detailed trade list (BUY/SELL per ticker with share counts)

**`pmod portfolio rebalance`**
- Executes the rebalance live
- Places orders through Schwab for all trades in the plan
- Each trade shows a confirmation prompt (unless you've set trade execution to "auto")
- Only runs if your rebalance frequency allows it (manual, daily, or weekly)
- Respects max position size constraints and sector filters from Settings

---

### Research Commands

**`pmod research run`**
- Executes a full research pass:
  1. Fetches latest quotes and technicals for all tracked tickers
  2. Runs momentum analysis (RSI, SMA crossover, volatility)
  3. Scores tickers against your strategy (growth/value/dividend/momentum/balanced)
  4. Refreshes the watchlist with top 15 candidates
  5. Updates the "Why this fits you" explanations
- Runs automatically every morning at 6 AM ET (before market open)
- Can be triggered manually at any time
- Takes 1–2 minutes (respects Polygon API rate limits: 5 req/min free tier)

---

### Politician Trading Commands

**`pmod politicians fetch`**
- Pulls the latest Senate PTR (Periodic Transaction Report) disclosures
- Scrapes senate.gov EFDS database for recent senator/representative trades
- Updates local database with new buy/sell activity
- Runs automatically daily at 6:30 AM ET (before market open, before research pass)
- Useful for refreshing data if you want the absolute latest disclosures

**`pmod politicians signals`**
- Analyzes all disclosed trades and generates buy/sell consensus signals
- Groups trades by ticker and calculates:
  - # of politicians buying vs selling
  - Confidence score (higher = stronger consensus)
  - Signal: STRONG_BUY, BUY, HOLD, SELL
- Results persist to database and display on Politician Trades tab
- Runs automatically every morning at 6 AM ET with research pass
- Can be run manually to update signals immediately

**`pmod politicians list [--ticker TICKER] [--days N]`**
- Prints recent politician trades to terminal in readable format
- Optional filters:
  - `--ticker XOM` — Show only XOM trades
  - `--days 30` — Show trades from the last 30 days
- Example: `pmod politicians list --ticker AAPL --days 90` shows Apple trades from the last 90 days
- Useful for quick lookup without opening dashboard

---

### External Account Commands

pmod tracks external accounts (401k, 529, IRA at other custodians) via manual CSV imports. The Schwab API only returns accounts held directly at Schwab; externally linked accounts shown in Schwab's web UI are not accessible via their API.

**`pmod external import <file.csv> --account "Account Name" [--account-type TYPE] [--dry-run]`**
- Imports positions from a CSV file into a named external account
- `--account` — Required. Human-readable name (e.g. `"ADP 401k"`, `"Start Right Online"`)
- `--account-type` — Optional label: `529`, `401k`, `IRA`, etc.
- `--dry-run` — Preview parsed rows without writing to the database
- Replaces all existing positions for that account on each import (clean re-import)
- Recognises column names from common export formats (Schwab, Fidelity, Vanguard, generic):

  | Your CSV header | Mapped to |
  |---|---|
  | Symbol, Ticker | ticker |
  | Description, Name, Security | company name |
  | Quantity, Units, Shares | shares |
  | Average Cost, Avg Cost, Cost Basis | avg cost |
  | Price, Current Price, Last Price, NAV | price |
  | Market Value, Value, Total Value | market value |

**`pmod external list`**
- Shows all external accounts with position counts, total values, and last import date

**`pmod external show "Account Name"`**
- Prints all positions for the named account

**`pmod external clear "Account Name"`**
- Deletes all positions and the account record (with confirmation prompt)

**`pmod external update`**
- Updates all external account positions with current market prices
- Reads share counts from `external_positions_config.csv` (you can edit this file manually)
- Fetches latest prices from Polygon.io for each position (ETF proxy mapping for mutual funds)
- Calculates updated market values and stores daily snapshots for performance tracking
- Runs automatically daily at 4:25 PM ET (after market close)
- Also runs automatically when dashboard starts for absolute latest prices
- Takes ~3 minutes for 15 positions (respects Polygon rate limit: 5 req/min)

**Share configuration file (`external_positions_config.csv`):**
```csv
account_name,ticker,shares
ADP,VBILX,1000.00
Start Right,FXAIX,1000.00
Schwab,BTC,0.5
```
Edit this file to add your actual share counts. External accounts will then have daily price updates.

**CSV import workflow:**
```bash
# Preview what will be parsed (nothing written)
pmod external import adp.csv --account "ADP 401k" --account-type 401k --dry-run

# Import for real
pmod external import adp.csv --account "ADP 401k" --account-type 401k

# Re-import after updating the CSV (fully replaces previous positions)
pmod external import adp_updated.csv --account "ADP 401k" --account-type 401k

# See all accounts
pmod external list

# View detail
pmod external show "ADP 401k"
```

Once imported, external accounts appear in the dashboard Portfolio tab alongside your live Schwab data. Use the **account filter dropdown** at the top of the Portfolio tab to view all accounts together or drill into a single account.

---

### Auth & Setup Commands

**`pmod auth login`**
- Initiates Schwab OAuth2 browser flow (one-time setup)
- Opens your browser to Schwab login page
- You approve access; browser redirects to localhost callback
- Tokens saved locally (never committed to git)
- Run once at initial setup; tokens auto-refresh every 4 hours
- If tokens expire (>7 days), run this again to re-authenticate

**`pmod setup`**
- Interactive wizard to configure your profile:
  - Risk tolerance (low/medium/high/degen)
  - Strategy (growth/value/dividend/momentum/balanced)
  - Max position size (% of portfolio)
  - Rebalance frequency (manual/daily/weekly)
  - Trade execution (manual-confirm/auto)
  - Sector constraints (optional)
- Settings saved to local SQLite database
- Can also update in Settings tab on dashboard
- Changes take effect immediately

**`pmod dashboard`**
- Launches the Dash/Plotly web dashboard
- Opens at `http://localhost:8050` (opens automatically in default browser)
- All 5 tabs (Portfolio, Watchlist, Politician Trades, AI Advisor, Settings) available
- Dashboard runs until you press Ctrl+C
- Scheduler jobs (token refresh, research, snapshots) run in background while dashboard is open

---

### Scheduler Behavior

When the dashboard is running, background jobs execute automatically:

| Job | Schedule | What it does |
|-----|----------|---|
| Token Refresh | Every 4 hours | Refreshes Schwab OAuth tokens (silent, no prompt) |
| Politician Trades Fetch | Daily at 6:30 AM ET | Fetches latest Senate PTR disclosures from efdsearch.senate.gov |
| Research Pass | Daily at 7:00 AM ET | Scores tickers, refreshes watchlist, updates signals |
| External Account Update | Daily at 4:25 PM ET | Fetches prices for external account positions, stores daily snapshots |
| Portfolio Snapshot | Daily at 4:30 PM ET | Captures your portfolio value (for alpha calculation) |
| Benchmark Snapshot | Daily at 4:35 PM ET | Captures S&P 500 (SPY) closing price |
| Rebalance | Per preference (daily or weekly) | Auto-runs optimizer if set to "auto" execution mode |

All jobs log their status; check dashboard logs or console output for details.

**Dashboard startup:**
- External accounts also update when you launch `pmod dashboard` (runs in background thread so dashboard starts immediately)
- This ensures you have the latest prices before viewing your portfolio

## Architecture

```
pmod/
├── main.py              # CLI entry point (Click)
├── config.py            # Settings via pydantic-settings + .env
├── exceptions.py        # Typed exception hierarchy (AuthError, BrokerError, etc.)
├── auth/schwab.py       # OAuth2 flow + token refresh
├── broker/schwab.py     # Order placement, positions, account data (rate-limited)
├── advisor/
│   └── claude.py        # Claude API integration — portfolio Q&A + strategy actions
├── analytics/
│   └── alpha.py         # Alpha calculation — portfolio excess return vs S&P 500 benchmark
├── data/
│   ├── market.py        # Market data ingestion (Polygon.io, rate-limited + retried)
│   ├── models.py        # SQLAlchemy models (UserPreference, WatchlistItem, ExternalAccount, ExternalPosition, etc.)
│   ├── external_accounts.py  # CSV import + query helpers for manually-tracked external accounts
│   └── politician_trades.py  # Senate EFD scraper + politician disclosure ingestion
├── research/
│   ├── signals.py       # Technical indicators (RSI, SMA crossover, volatility, momentum)
│   ├── screener.py      # Score + rank tickers by strategy fit, persist to watchlist
│   └── politician_signals.py # Aggregate buy/sell signals from politician trades
├── optimizer/
│   └── portfolio.py     # Equal-weight rebalance with iterative position cap enforcement
├── preferences/
│   └── profile.py       # Risk tolerance + strategy management
├── utils/
│   └── retry.py         # Exponential backoff decorator + token-bucket rate limiter
├── dashboard/
│   ├── app.py           # Dash app setup, tab routing, all callbacks
│   ├── pages/           # Portfolio, watchlist, advisor, congress, settings views
│   └── components/      # Design tokens + reusable Plotly components
└── scheduler/
    └── jobs.py          # APScheduler: token refresh, research, snapshots, benchmark snapshots, rebalance
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

## Common Workflows

### Workflow 1: First-Time Setup

1. **Install and configure**
   ```bash
   git clone https://github.com/sparktron/print-money-or-die.git
   cd print-money-or-die
   pip install -e ".[dev]"
   cp .env.example .env
   # Edit .env with your API keys
   ```

2. **Authenticate with Schwab**
   ```bash
   pmod auth login
   # Browser opens, you approve access, tokens saved locally
   ```

3. **Set your preferences**
   ```bash
   pmod setup
   # Wizard walks you through: risk, strategy, max position %, rebalance frequency, trade execution, sectors
   ```

4. **Launch dashboard**
   ```bash
   pmod dashboard
   # Opens http://localhost:8050 in your browser
   ```

5. **Wait for first snapshot** (important for alpha calculation)
   - Next market close at 4:30 PM ET, scheduler captures your portfolio value
   - After 2nd market close, alpha metrics appear with real data
   - Until then, chart shows simulated 1-year returns for preview

---

### Workflow 2: Adding a Stock to Your Portfolio

**Via Dashboard (Watchlist tab):**
1. Open Dashboard → Watchlist tab
2. Find a stock card that interests you (filtered by your strategy)
3. Read "WHY THIS FITS YOU" explanation
4. Click **"Add to Portfolio"**
5. Modal opens:
   - Enter # of shares to buy
   - Choose Order type (Market = fill now, Limit = set your price)
   - Review estimated cost
6. Click **"Confirm Order"**
7. Order sent to Schwab; you get confirmation with order ID

**Via Dashboard (Rebalance):**
1. Open Portfolio tab
2. Click **"Suggest Rebalance"**
3. Optimizer shows target allocation based on your strategy
4. Review the buy/sell list
5. Click **"Execute"** to place all trades (or **"Dry Run"** first to preview)

**Via CLI (manual rebalance):**
```bash
pmod portfolio rebalance --dry-run    # Preview what will happen
pmod portfolio rebalance              # Execute for real
```

---

### Workflow 3: Adjusting Your Risk Profile

**Via Dashboard:**
1. Go to Settings tab
2. Change "Risk Tolerance" to low/medium/high/degen
3. Optionally change "Strategy" to growth/value/dividend/momentum/balanced
4. Click **"Save Settings"**
5. Settings persist locally
6. Next research pass uses new settings to resccore watchlist

**Via CLI:**
```bash
pmod setup
# Re-run the interactive wizard to update any preference
```

**Effect:**
- Watchlist updates at next research pass (or run `pmod research run` immediately)
- New scores and recommendations reflect your new risk/strategy
- Rebalancer will optimize toward new allocation if you run rebalance again

---

### Workflow 4: Tracking Your Performance vs the Market

**Automatic (happens daily):**
1. At 4:30 PM ET, scheduler captures your portfolio's total value
2. At 4:35 PM ET, scheduler captures S&P 500 (SPY) closing price
3. Dashboard calculates alpha (your return % − S&P return %)
4. Chart updates with real historical data

**Checking your alpha:**
1. Open Dashboard → Portfolio tab
2. Look at **"Alpha vs S&P"** KPI card (top-right area)
3. Shows:
   - Excess return % (positive = beating market, negative = underperforming)
   - "vs S&P 500 (N days)" — how many days of data you have
4. Chart below shows your portfolio (blue line) vs S&P 500 (dotted line)

**Waiting for real data:**
- After 1st market close: "Insufficient data" (need at least 2 snapshots)
- After 2nd market close: Real alpha appears! Chart shows actual returns
- Keep the dashboard running nightly and it auto-captures

---

### Workflow 5: Getting AI Advice on Your Portfolio

1. Open Dashboard → AI Advisor tab
2. Type a question in the text box, e.g.:
   - "Should I sell my XYZ position?"
   - "What's my biggest risk right now?"
   - "Can I afford another $10k position?"
   - "Why do I have so much cash?"
3. Press Enter or click Send
4. Claude responds with analysis and optional actions:
   - **"Add XYZ to watchlist"** — Adds to your curated picks
   - **"Change risk to HIGH"** — Updates your risk profile
   - **"Change strategy to DIVIDEND"** — Switches your strategy
5. Click any action to apply it instantly

**How it works:**
- Your portfolio data (positions, balances, performance) sent to Claude
- Claude analyzes and responds
- No memory between sessions; start fresh each time
- Requires ANTHROPIC_API_KEY in .env

---

### Workflow 6: Monitoring Politician Trading Activity

1. Open Dashboard → Politician Trades tab
2. See recent senator/representative trades:
   - Politician name, party, state
   - Stock ticker, buy/sell action
   - Dollar amount, transaction date, disclosure date
3. Check **Signal** column for consensus:
   - **STRONG_BUY** (green) = many politicians buying, high confidence
   - **BUY** (light green) = positive signals
   - **HOLD** (yellow) = mixed or no recent activity
   - **SELL** (red) = many politicians exiting
4. Use as a signal:
   - Strong buys = good entry candidates (check watchlist or research)
   - Strong sells = watch for profit-taking or insider concerns
   - Neutral signals = check fundamentals before trading

**From CLI:**
```bash
pmod politicians list --ticker AAPL --days 90
# Shows all Apple trades from politicians in the last 90 days
```

---

## Troubleshooting & Tips

### Dashboard Issues

**Dashboard won't start**
- Check that port 8050 is not in use: `lsof -i :8050` (macOS/Linux) or `netstat -ano | findstr :8050` (Windows)
- If in use, kill the process or start with a different port
- Ensure all dependencies installed: `pip install -e ".[dev]"`

**"Insufficient data" for alpha**
- This is normal! You need at least 2 daily snapshots
- Snapshots captured at 4:30 PM ET every trading day
- After 2 market closes, real alpha will appear
- Check that your machine's timezone is correct (scheduler uses US/Eastern)

**Watchlist is empty**
- Run `pmod research run` to score tickers and populate watchlist
- Ensure your Polygon API key is set and valid in .env
- Check that your strategy preference is saved (Settings tab)

**"LIVE" vs "SAMPLE DATA" badge**
- **LIVE** = connected to Schwab account with real data
- **SAMPLE DATA** = no Schwab connection (use for testing without account)
- If seeing sample data:
  - Run `pmod auth login` to re-authenticate
  - Check that `~/.pmod/schwab_tokens.json` exists (contains your OAuth tokens)
  - Verify SCHWAB_APP_KEY and SCHWAB_APP_SECRET in .env

**AI Advisor not responding**
- Check that ANTHROPIC_API_KEY is set in .env
- Verify your Anthropic account has available credits
- Check console for error logs (should show API status)

---

### Trading Issues

**Order rejected by Schwab**
- Insufficient buying power (not enough cash for the trade)
- Fractional shares not allowed (use whole share count)
- Market hours: orders only work during market open (9:30 AM – 4:00 PM ET)
- Check Schwab account for restrictions or pattern day trader rules

**Dry-run shows plan but execute fails**
- Market conditions may have changed between dry-run and execution
- Prices may have moved; limit orders may not fill
- Insufficient cash by execution time
- Check order confirmations on Schwab website for details

**Rebalance didn't execute**
- If trade execution is set to "manual-confirm", each trade needs a confirmation dialog
- If set to "auto", rebalance only runs at scheduled times (daily or weekly, not manual click)
- Check Settings tab to verify your trade execution preference

---

### API & Data Issues

**"POLYGON_API_KEY is not set"**
- Add to .env: `POLYGON_API_KEY=your_key`
- Free tier key available at https://polygon.io
- Rate limit: 5 API calls per minute (respected automatically with backoff)

**Market data is stale or missing**
- Polygon is only updated during market hours + ~5 min after close
- Research pass runs at 6 AM ET (pre-market); data may be yesterday's close
- Quotes refresh after 4 PM ET when market closes
- Run `pmod research run` manually to refresh immediately

**Politician trades not updating**
- Senate PTR database updated daily
- Data often has 1–2 week lag before disclosure
- Run `pmod politicians fetch` to pull latest (automatic daily at 6:30 AM ET)
- Check congress.gov for most recent filings if you need real-time data

**External accounts not showing in portfolio**
- Make sure you've imported the CSV: `pmod external import file.csv --account "Name"`
- Run `pmod external list` to verify accounts were imported
- For daily price updates, edit `external_positions_config.csv` with your share counts
- Then run `pmod external update` (automatic daily at 4:25 PM ET)
- Run `pmod dashboard` to see all accounts on the Portfolio tab

**External account prices not updating**
- Check that `external_positions_config.csv` exists in the project root
- Verify your share counts are correct in the CSV (must be > 0)
- Mutual funds are mapped to equivalent ETFs (VBILX→BND, VIMAX→VO, etc.)
- Run `pmod external update` manually to trigger an immediate update
- Check console logs for rate-limit messages (Polygon: 5 req/min free tier)

---

### Token & Authentication

**"Schwab access token expired"**
- Tokens auto-refresh every 4 hours while dashboard runs
- If you see auth errors:
  1. Close dashboard (`Ctrl+C`)
  2. Run `pmod auth login` again
  3. Restart dashboard
  4. This happens naturally every 7 days (refresh token expiry)

**OAuth callback loop**
- Make sure SCHWAB_CALLBACK_URL in .env matches your app registration
- Default: `https://127.0.0.1:8182/callback`
- If you changed the port, update in Schwab Developer console too

---

### Performance & Optimization

**Optimizer takes too long to run**
- First run may take 30+ seconds (scipy optimization is CPU-bound)
- Subsequent runs cached; faster as you add more positions
- Max position size constraint causes more iterations (if set very low)
- Consider reducing watchlist size or sector filters if very slow

**Research pass is slow**
- Polygon API calls are rate-limited (5 req/min free tier)
- Full scan of 100+ tickers = ~20 minutes
- Run at off-peak times or overnight
- Premium Polygon tier has higher limits

**Dashboard is laggy**
- If dashboard is slow, check that no other heavy processes are running
- Plotly charts can be CPU-intensive; reduce chart update frequency
- Close other browser tabs if memory-constrained
- Check logs for warnings: `tail -f pmod.log`

---

### Tips & Best Practices

**Always dry-run before rebalancing**
```bash
pmod portfolio rebalance --dry-run    # Review plan first
pmod portfolio rebalance              # Then execute
```

**Keep your risk settings realistic**
- "degen" = very aggressive (high volatility, experimental picks)
- "high" = growth-oriented, okay with volatility
- "medium" = balanced growth + stability
- "low" = conservative, prioritize dividends and quality

**Review your positions daily**
- Check Dashboard Portfolio tab for P&L and weightings
- Use **"Hide $"** button if screen is visible to others
- Ask AI Advisor if anything looks off-strategy

**Rebalance regularly**
- Manual: run `pmod portfolio rebalance --dry-run` weekly
- Daily: set rebalance frequency to "daily" in Settings
- Weekly: set to "weekly" and optimizer runs Sundays at 10 AM ET

**Monitor alpha trend**
- Alpha of +5% over 1 year = beating market (good!)
- Alpha of -10% = underperforming (consider strategy review)
- Alpha is cumulative; temporary underperformance is normal
- Use AI Advisor to strategize improvements

**Use Politician Trades as a research signal, not a guarantee**
- Strong politician consensus is bullish but not foolproof
- Always cross-check with technical and fundamental analysis
- Insider trades can signal early exits (profit-taking, not always bearish)
- Combine with watchlist signals and your own research

---

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
- **Rate limiting** — Thread-safe token-bucket limiters for Schwab (120 req/min) and Polygon (5 req/min free tier)
- **Retry with backoff** — Transient API failures automatically retry with exponential backoff (configurable max retries, delay ceiling)
- **Token management** — Schwab refresh tokens expire in 7 days; the scheduler refreshes every 4 hours and alerts on expiry
- **Typed exceptions** — Structured error hierarchy (`AuthError`, `BrokerError`, `RateLimitError`, etc.) for precise error handling
- **Input validation** — All API responses are validated through Pydantic before use
- **Credentials** — `.env`, token files, and the SQLite DB are gitignored from day one

## Tech Stack

| Layer | Technology |
|---|---|
| Language | Python 3.10+ |
| Brokerage | schwab-py (OAuth2 + trading) |
| Market data | Polygon.io, Alpha Vantage |
| AI advisor | Anthropic SDK (Claude) |
| Optimization | SciPy |
| Dashboard | Dash + Plotly |
| Scheduling | APScheduler (background jobs) |
| Database | SQLite via SQLAlchemy |
| Config | pydantic-settings |
| Logging | structlog |
| Testing | pytest + pytest-mock (133 tests) |

## License

MIT
