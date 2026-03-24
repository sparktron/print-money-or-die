# PrintMoneyOrDie (pmod)

## What this is
An AI-powered portfolio optimizer and automated trading system that pulls market data from
multiple financial APIs, factors in your personal risk tolerance and investment strategy, and
executes trades directly on your Schwab brokerage account. Includes a graphical dashboard for
monitoring portfolio performance and browsing AI-curated investment opportunities.

## Tech stack
- **Language**: Python 3.11+
- **CLI entry point**: `pmod` (via `pyproject.toml` scripts)
- **Schwab integration**: `schwab-py` (OAuth2, trading, account data, streaming)
- **Market data**: Polygon.io and/or Alpha Vantage (quotes, history, news, options)
- **Portfolio optimization**: `scipy` (mean-variance / risk-parity optimization)
- **Dashboard UI**: `dash` + `plotly` (web-based graphical interface, runs locally)
- **Scheduling**: `apscheduler` (periodic research + rebalance jobs)
- **Storage**: SQLite via `sqlalchemy` (local persistence for preferences, history, signals)
- **Config**: `pydantic-settings` + `.env` file (API keys, risk profile)
- **Testing**: `pytest` + `pytest-mock`

## Directory layout (intended)
```
print-money-or-die/
├── pmod/
│   ├── __init__.py
│   ├── main.py              # CLI entry point
│   ├── auth/
│   │   └── schwab.py        # OAuth2 flow + token refresh logic
│   ├── broker/
│   │   └── schwab.py        # Order placement, account data, positions
│   ├── data/
│   │   ├── market.py        # Market data ingestion (quotes, history, news)
│   │   └── models.py        # SQLAlchemy models
│   ├── research/
│   │   ├── signals.py       # Trend analysis, scoring, signal generation
│   │   └── screener.py      # Filter + rank tickers by strategy fit
│   ├── optimizer/
│   │   └── portfolio.py     # Mean-variance / risk-parity optimization
│   ├── preferences/
│   │   └── profile.py       # Risk tolerance, strategy, sector constraints
│   ├── dashboard/
│   │   ├── app.py           # Dash app setup + layout
│   │   ├── pages/
│   │   │   ├── portfolio.py # Portfolio performance view
│   │   │   └── watchlist.py # Curated picks + "why this fits you" explainer
│   │   └── components/      # Reusable Dash/Plotly components
│   └── scheduler/
│       └── jobs.py          # Periodic research, rebalance, token refresh
├── tests/
│   ├── test_optimizer.py
│   ├── test_screener.py
│   └── test_broker.py
├── .env.example             # Template for secrets (never commit .env)
├── pyproject.toml
├── README.md
└── CLAUDE.md
```

## Key commands
```bash
# Install (editable, with dev deps)
pip install -e ".[dev]"

# First-time Schwab OAuth login (browser required once)
pmod auth login

# Launch the graphical dashboard (opens at http://localhost:8050)
pmod dashboard

# Run a research pass and update watchlist
pmod research run

# Show current portfolio + suggested rebalance
pmod portfolio status

# Execute a rebalance based on optimizer output (confirm prompt required)
pmod portfolio rebalance --dry-run   # preview
pmod portfolio rebalance             # live

# Run tests
pytest

# Typecheck
mypy pmod/

# Lint
ruff check pmod/
```

## Coding conventions
- Type-annotate all functions; use `pydantic` models for structured data
- Prefer explicit over implicit — no silent fallbacks on API errors
- All external API calls go through a thin wrapper in `data/` or `broker/` — never call
  `schwab-py` or requests directly from business logic
- Log with `structlog` at appropriate levels; never print to stdout in library code
- Keep functions under ~40 lines; break anything larger into helpers
- Use `Result`-style returns or raise typed exceptions — never return `None` to signal error
- Dash callbacks must be pure (no side effects beyond DB writes); keep layout and logic separate

## Guardrails — read these first, always
- **NEVER commit `.env`, tokens, or any credentials** — `.gitignore` must cover these from day 1
- **NEVER place a live trade without a `--dry-run` path** tested first in the same session
- **NEVER add a new dependency** without asking the user first
- **NEVER bypass the confirm prompt** on destructive actions (rebalance, sell-all, etc.)
- Treat all API responses as untrusted — validate with pydantic before use
- Schwab refresh tokens expire in 7 days — the scheduler must handle silent re-auth or alert loudly
- Rate limits: Schwab API is 120 req/min; Polygon free tier is 5 req/min — respect both with backoff

## User preferences (persist in DB, editable via dashboard)
- **Risk tolerance**: low / medium / high / degen
- **Strategy**: growth / value / dividend / momentum / balanced
- **Sector constraints**: whitelist/blacklist (e.g. no tobacco, focus on tech)
- **Max position size**: % of portfolio per ticker
- **Rebalance frequency**: manual / daily / weekly
- **Trade execution**: manual-confirm / auto (auto only after explicit opt-in)

## Dashboard features (priority order)
1. Portfolio performance chart (daily P&L, total return, benchmark vs S&P 500)
2. Current positions table (ticker, shares, cost basis, current value, gain/loss)
3. Watchlist / curated picks — each card shows:
   - Ticker + company name
   - Why it fits the user's strategy (plain English, AI-generated)
   - Key signals (momentum score, valuation, analyst sentiment)
   - "Add to portfolio" / "Ignore" actions
4. Rebalance suggestions with diff view (before vs after)
5. Settings page for risk profile and preferences

## Current goal
Scaffold the project skeleton:
1. Set up `pyproject.toml` with all dependencies and the `pmod` CLI entry point
2. Create `.env.example` with all required keys (SCHWAB_APP_KEY, SCHWAB_APP_SECRET,
   SCHWAB_CALLBACK_URL, POLYGON_API_KEY, ALPHA_VANTAGE_API_KEY, DATABASE_URL)
3. Implement `pmod auth login` — the Schwab OAuth2 browser flow using `schwab-py`,
   saving tokens to a local file (never committed)
4. Stub out all module `__init__.py` files so imports resolve cleanly
5. Wire up a "hello world" Dash dashboard that launches with `pmod dashboard` and shows
   a placeholder layout for the portfolio and watchlist pages
6. Add a `pytest` smoke test that imports the top-level package without errors

Do not implement trading logic or real API calls until auth and the dashboard shell are working.
