"""Portfolio performance view — live Schwab data with sample fallback."""
from __future__ import annotations

from datetime import date, datetime, timedelta

import plotly.graph_objects as go
from dash import dcc, html

from pmod.analytics.alpha import calculate_alpha, get_account_historical_returns, get_historical_returns
from pmod.broker.schwab import AccountSummary, Position, get_all_account_summaries
from pmod.data.external_accounts import list_accounts, get_positions
from pmod.dashboard.components import (
    CHART_LAYOUT,
    COLORS,
    MONO,
    kpi_card,
    mask_number,
    mask_pct,
    section_header,
    status_badge,
)

# ── Sample fallback data ───────────────────────────────────────────────────

_SAMPLE_POSITIONS: list[dict] = [
    {"ticker": "NVDA", "name": "NVIDIA Corp.", "shares": 45, "avg_cost": 487.20, "current_price": 924.80, "market_value": 41616.0, "day_pnl": 234.50, "day_pnl_pct": 0.57, "total_pnl": 19701.0, "total_pnl_pct": 89.7, "weight": 24.1},
    {"ticker": "AAPL", "name": "Apple Inc.", "shares": 120, "avg_cost": 172.50, "current_price": 198.30, "market_value": 23796.0, "day_pnl": 42.0, "day_pnl_pct": 0.18, "total_pnl": 3096.0, "total_pnl_pct": 14.9, "weight": 13.8},
    {"ticker": "MSFT", "name": "Microsoft Corp.", "shares": 55, "avg_cost": 378.90, "current_price": 428.60, "market_value": 23573.0, "day_pnl": 110.0, "day_pnl_pct": 0.47, "total_pnl": 2734.5, "total_pnl_pct": 13.1, "weight": 13.6},
    {"ticker": "META", "name": "Meta Platforms", "shares": 32, "avg_cost": 345.80, "current_price": 512.90, "market_value": 16412.8, "day_pnl": 192.0, "day_pnl_pct": 1.18, "total_pnl": 5347.2, "total_pnl_pct": 48.4, "weight": 9.5},
    {"ticker": "GOOGL", "name": "Alphabet Inc.", "shares": 85, "avg_cost": 138.70, "current_price": 164.20, "market_value": 13957.0, "day_pnl": -34.0, "day_pnl_pct": -0.24, "total_pnl": 2167.5, "total_pnl_pct": 18.4, "weight": 8.1},
    {"ticker": "AMZN", "name": "Amazon.com Inc.", "shares": 70, "avg_cost": 153.20, "current_price": 187.40, "market_value": 13118.0, "day_pnl": 56.0, "day_pnl_pct": 0.43, "total_pnl": 2394.0, "total_pnl_pct": 22.3, "weight": 7.6},
    {"ticker": "JPM", "name": "JPMorgan Chase", "shares": 60, "avg_cost": 172.40, "current_price": 198.70, "market_value": 11922.0, "day_pnl": 78.0, "day_pnl_pct": 0.66, "total_pnl": 1578.0, "total_pnl_pct": 15.3, "weight": 6.9},
    {"ticker": "TSLA", "name": "Tesla Inc.", "shares": 40, "avg_cost": 248.60, "current_price": 215.30, "market_value": 8612.0, "day_pnl": -120.0, "day_pnl_pct": -1.37, "total_pnl": -1332.0, "total_pnl_pct": -13.4, "weight": 5.0},
]


def _sample_account() -> dict:
    total_value = sum(p["market_value"] for p in _SAMPLE_POSITIONS) + 5_200
    day_pnl = sum(p["day_pnl"] for p in _SAMPLE_POSITIONS)
    return {"total_value": total_value, "cash_balance": 5_200, "day_pnl": day_pnl}


# ── Chart ──────────────────────────────────────────────────────────────────

def _get_account_total(filter_account: str) -> float:
    """Return total current value for the given account filter (used by the chart callback)."""
    if filter_account == "__all__":
        total = 0.0
        try:
            from pmod.broker.schwab import get_all_account_summaries
            total += sum(s.total_value for s in get_all_account_summaries())
        except Exception:
            pass
        for ext in list_accounts():
            total += ext["total_value"]
        return total
    # External account by name
    for ext in list_accounts():
        if ext["name"] == filter_account:
            return ext["total_value"]
    # Schwab account — match by label "Schwab ···XXXX"
    try:
        from pmod.broker.schwab import get_all_account_summaries
        for s in get_all_account_summaries():
            label = f"Schwab ···{s.account_number[-4:]}" if s.account_number else "Schwab"
            if label == filter_account:
                return s.total_value
    except Exception:
        pass
    return 0.0


_PERIODS = [
    ("1W",  "1 Week"),
    ("1M",  "1 Month"),
    ("YTD", "YTD"),
    ("1Y",  "1 Year"),
]


def _period_cutoff(period: str) -> date:
    today = date.today()
    if period == "1W":
        return today - timedelta(weeks=1)
    if period == "1M":
        return today - timedelta(days=30)
    if period == "YTD":
        return date(today.year, 1, 1)
    return today - timedelta(days=365)  # 1Y default


def build_chart_figure(
    period: str = "1Y",
    total_value: float = 0,
    masked: bool = True,
    filter_account: str = "__all__",
) -> go.Figure:
    """Return a % return from period-start figure.  Called by the Dash callback."""
    cutoff = _period_cutoff(period)
    days_back = (date.today() - cutoff).days + 5

    if filter_account and filter_account != "__all__":
        hist_result = get_account_historical_returns(account_name=filter_account, days=days_back)
    else:
        hist_result = get_historical_returns(days=days_back)

    is_real = False
    if hist_result is not None and len(hist_result[2]) >= 2:
        portfolio_values_all, benchmark_values_all, dates_all = hist_result
        paired = [
            (d, p, b)
            for d, p, b in zip(dates_all, portfolio_values_all, benchmark_values_all)
            if d >= cutoff.strftime("%Y-%m-%d")
        ]
        if len(paired) >= 2:
            dates = [r[0] for r in paired]
            p0, b0 = paired[0][1], paired[0][2]
            # Convert to % return from period start
            portfolio_pct = [(p / p0 - 1) * 100 for _, p, _ in paired]
            benchmark_pct = [(b / b0 - 1) * 100 for _, _, b in paired]
            is_real = True

    if not is_real:
        n = {"1W": 7, "1M": 30, "YTD": max((date.today() - date(date.today().year, 1, 1)).days, 2), "1Y": 365}.get(period, 365)
        dates = [(datetime.now() - timedelta(days=n - 1 - i)).strftime("%Y-%m-%d") for i in range(n)]
        portfolio_pct = [0 + (12 * i / max(n - 1, 1)) + ((i % 7 - 3) * 0.3) for i in range(n)]
        benchmark_pct = [0 + (10 * i / max(n - 1, 1)) + ((i % 7 - 3) * 0.25) for i in range(n)]

    last_p = portfolio_pct[-1]
    last_b = benchmark_pct[-1]
    p_sign = "+" if last_p >= 0 else ""
    b_sign = "+" if last_b >= 0 else ""

    portfolio_color = COLORS["green"] if last_p >= 0 else COLORS["red"]
    chart_fill = COLORS["green_bg"] if last_p >= 0 else "rgba(239,68,68,0.06)"

    hover_p = "<b>masked</b>" if masked else f"%{{y:.2f}}%"
    hover_b = "<b>masked</b>" if masked else f"%{{y:.2f}}%"

    fig = go.Figure()

    # Zero reference line
    fig.add_hline(y=0, line=dict(color=COLORS["border"], width=1, dash="dot"))

    fig.add_trace(go.Scatter(
        x=dates, y=portfolio_pct, mode="lines", name=f"Portfolio ({p_sign}{last_p:.1f}%)",
        line=dict(color=portfolio_color, width=2.5),
        fill="tozeroy", fillcolor=chart_fill,
        hovertemplate=f"<b>Portfolio</b><br>%{{x}}<br>{hover_p}<extra></extra>",
    ))
    fig.add_trace(go.Scatter(
        x=dates, y=benchmark_pct, mode="lines", name=f"S&P 500 ({b_sign}{last_b:.1f}%)",
        line=dict(color=COLORS["text_tertiary"], width=1.5, dash="dot"),
        hovertemplate=f"<b>S&P 500</b><br>%{{x}}<br>{hover_b}<extra></extra>",
    ))

    tick_fmt = "%b %d" if period in ("1W", "1M") else "%b '%y"
    dtick = "D7" if period == "1W" else ("M1" if period == "1M" else "M2")
    layout = {**CHART_LAYOUT, "height": 360, "margin": dict(l=0, r=0, t=10, b=0)}
    layout["legend"] = dict(**CHART_LAYOUT["legend"], orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)
    layout["xaxis"] = {**CHART_LAYOUT["xaxis"], "type": "date", "tickformat": tick_fmt, "dtick": dtick}
    layout["yaxis"] = {**CHART_LAYOUT["yaxis"], "ticksuffix": "%", "tickformat": ".1f", "zeroline": False}
    fig.update_layout(**layout)
    return fig


def _build_chart(total_value: float, masked: bool, period: str = "1Y", filter_account: str = "__all__") -> html.Div:
    """Chart area: period toggle buttons + the Plotly graph."""
    btn_base = {
        "background": "transparent",
        "border": f"1px solid {COLORS['border']}",
        "color": COLORS["text_tertiary"],
        "padding": "5px 14px",
        "fontSize": "12px",
        "fontWeight": "600",
        "borderRadius": "8px",
        "cursor": "pointer",
        "transition": "all 0.15s",
    }
    btn_active = {**btn_base, "background": COLORS["accent"], "color": COLORS["bg"], "borderColor": COLORS["accent"]}

    buttons = html.Div(
        [
            html.Button(
                label,
                id={"type": "period-btn", "index": key},
                style=btn_active if key == period else btn_base,
                n_clicks=0,
            )
            for key, label in _PERIODS
        ],
        style={"display": "flex", "gap": "6px"},
    )

    fig = build_chart_figure(period=period, total_value=total_value, masked=masked, filter_account=filter_account)
    graph = dcc.Graph(id="portfolio-chart", figure=fig, config={"displayModeBar": False})

    return html.Div([buttons, graph], style={"display": "flex", "flexDirection": "column", "gap": "14px"})


# ── Positions table ────────────────────────────────────────────────────────

def _weight_bar(pct: float) -> html.Div:
    return html.Div(
        [
            html.Div(style={"width": f"{min(pct * 3.5, 100)}%", "height": "4px", "background": COLORS["accent"], "borderRadius": "2px"}),
            html.Span(f"{pct:.1f}%", style={"fontSize": "12px", "color": COLORS["text_secondary"], "marginTop": "2px"}),
        ],
        style={"display": "flex", "flexDirection": "column", "alignItems": "flex-end"},
    )


def _positions_table(rows_data: list[dict], masked: bool, show_pnl: bool = True) -> html.Div:
    h = {"fontSize": "11px", "fontWeight": "600", "color": COLORS["text_tertiary"],
         "textTransform": "uppercase", "letterSpacing": "0.8px",
         "padding": "12px 16px", "textAlign": "left", "borderBottom": f"1px solid {COLORS['border']}"}
    hr = {**h, "textAlign": "right"}

    # Fixed column widths for alignment across all tables
    header_cells = [
        html.Th("Asset", style={**h, "width": "28%"}),
        html.Th("Shares", style={**hr, "width": "11%"}),
        html.Th("Avg Cost", style={**hr, "width": "11%"}),
        html.Th("Price", style={**hr, "width": "11%"}),
        html.Th("Value", style={**hr, "width": "12%"}),
    ]
    if show_pnl:
        header_cells += [
            html.Th("Day P&L", style={**hr, "width": "14%"}),
            html.Th("Total P&L", style={**hr, "width": "14%"})
        ]
    header_cells.append(html.Th("Weight", style={**hr, "width": "9%"}))
    headers = html.Tr(header_cells)

    cell = {"padding": "14px 16px", "borderBottom": f"1px solid {COLORS['border']}", "fontSize": "14px", "color": COLORS["text_primary"]}
    cell_r = {**cell, "textAlign": "right", "fontFamily": MONO}
    dash_style = {**cell_r, "color": COLORS["text_tertiary"]}

    # Column width styles for data cells (must match header widths)
    cell_asset = {**cell, "width": "28%"}
    cell_shares = {**cell_r, "width": "11%"}
    cell_avg_cost = {**cell_r, "width": "11%"}
    cell_price = {**cell_r, "width": "11%"}
    cell_value = {**cell_r, "width": "12%"}
    cell_day_pnl = {**cell_r, "width": "14%"}
    cell_total_pnl = {**cell_r, "width": "14%"}
    cell_weight = {**cell_r, "width": "9%"}

    table_rows = []
    for p in rows_data:
        shares = p.get("shares") or 0
        shares_str = (
            f"{shares:.4f}".rstrip("0").rstrip(".")
            if shares and shares != int(shares)
            else (str(int(shares)) if shares else "—")
        )
        avg_cost = p.get("avg_cost") or 0
        current_price = p.get("current_price") or 0
        avg_cost_str = mask_number(avg_cost, masked=masked) if avg_cost else "—"
        current_price_str = mask_number(current_price, masked=masked) if current_price else "—"
        market_value_str = mask_number(p["market_value"], masked=masked)

        row_cells = [
            html.Td(html.Div([
                html.Span(p["ticker"], style={"fontWeight": "600", "fontSize": "14px", "color": COLORS["text_primary"]}),
                html.Br(),
                html.Span(p["name"], style={"fontSize": "12px", "color": COLORS["text_tertiary"]}),
            ]), style=cell_asset),
            html.Td(shares_str, style={**cell_shares, **({} if shares else {"color": COLORS["text_tertiary"]})}),
            html.Td(avg_cost_str, style={**cell_avg_cost, **({} if avg_cost else {"color": COLORS["text_tertiary"]})}),
            html.Td(current_price_str, style={**cell_price, **({} if current_price else {"color": COLORS["text_tertiary"]})}),
            html.Td(market_value_str, style=cell_value),
        ]

        if show_pnl:
            day_pnl = p.get("day_pnl", 0)
            day_pnl_pct = p.get("day_pnl_pct", 0)
            total_pnl = p.get("total_pnl", 0)
            total_pnl_pct = p.get("total_pnl_pct", 0)
            day_color = COLORS["green"] if day_pnl >= 0 else COLORS["red"]
            total_color = COLORS["green"] if total_pnl_pct >= 0 else COLORS["red"]
            day_sign = "+" if day_pnl >= 0 else ""
            total_sign = "+" if total_pnl >= 0 else ""
            day_pnl_str = f"{day_sign}{mask_number(abs(day_pnl), masked=masked)}" if masked else f"{day_sign}${abs(day_pnl):,.0f}"
            day_pnl_pct_str = mask_pct(abs(day_pnl_pct), masked=masked) if masked else f"{day_sign}{day_pnl_pct:.2f}%"
            total_pnl_str = f"{total_sign}{mask_number(abs(total_pnl), masked=masked)}" if masked else f"{total_sign}${abs(total_pnl):,.0f}"
            total_pnl_pct_str = mask_pct(abs(total_pnl_pct), masked=masked) if masked else f"{total_sign}{total_pnl_pct:.1f}%"
            row_cells += [
                html.Td(html.Span(f"{day_pnl_str} ({day_pnl_pct_str})", style={"color": day_color}), style=cell_day_pnl),
                html.Td(html.Span(f"{total_pnl_str} ({total_pnl_pct_str})", style={"color": total_color}), style=cell_total_pnl),
            ]

        row_cells.append(html.Td(_weight_bar(p["weight"]), style=cell_weight))
        table_rows.append(html.Tr(row_cells))

    return html.Div(
        html.Table([html.Thead(headers), html.Tbody(table_rows)],
                   style={
                       "width": "100%",
                       "borderCollapse": "collapse",
                       "borderSpacing": "0",
                       "tableLayout": "fixed"  # Fixed layout ensures column widths are respected
                   }),
        style={"background": COLORS["surface"], "border": f"1px solid {COLORS['border']}", "borderRadius": "16px", "overflow": "hidden"},
    )


def _account_section(name: str, account_type: str | None, total_value: float,
                     rows_data: list[dict], masked: bool, show_pnl: bool) -> html.Div:
    """A labelled section header + positions table for a single account."""
    label = name
    if account_type:
        label += f" ({account_type.upper()})"
    value_str = mask_number(total_value, masked=masked)
    return html.Div([
        html.Div([
            html.Span(label, style={"fontWeight": "600", "fontSize": "15px", "color": COLORS["text_primary"]}),
            html.Span(value_str, style={"fontWeight": "600", "fontSize": "15px", "color": COLORS["text_secondary"], "fontFamily": MONO}),
        ], style={"display": "flex", "justifyContent": "space-between", "alignItems": "center",
                  "marginBottom": "12px", "marginTop": "24px"}),
        _positions_table(rows_data, masked=masked, show_pnl=show_pnl),
    ])


# ── Public layout ──────────────────────────────────────────────────────────

def portfolio_layout(masked: bool = True, filter_account: str = "__all__", chart_period: str = "1Y") -> html.Div:
    """Return the portfolio page, using live Schwab data when available."""
    schwab_summaries: list[AccountSummary] = get_all_account_summaries()
    schwab_live = bool(schwab_summaries) and any(s.total_value > 0 for s in schwab_summaries)

    # ── Collect all named accounts (for dropdown) ──────────────────────────
    all_account_names: list[str] = []

    # ── Calculate full portfolio total FIRST (before filtering) ─────────────
    # This is used to weight positions relative to the entire portfolio
    full_portfolio_total = 0.0
    if schwab_live:
        full_portfolio_total += sum(s.total_value for s in schwab_summaries)
    for ext in list_accounts():
        full_portfolio_total += ext["total_value"]

    # ── Build per-account data ─────────────────────────────────────────────
    # Each entry: (name, account_type, total_value, cash, day_pnl, rows, show_pnl)
    AccountEntry = tuple  # (name, acct_type, total, cash, day_pnl, rows, show_pnl)
    entries: list[AccountEntry] = []

    if schwab_live:
        for s in schwab_summaries:
            label = f"Schwab ···{s.account_number[-4:]}" if s.account_number else "Schwab"
            all_account_names.append(label)
            rows = [
                {
                    "ticker": p.ticker,
                    "name": p.company_name,
                    "shares": p.shares,
                    "avg_cost": p.avg_cost,
                    "current_price": p.current_price,
                    "market_value": p.market_value,
                    "day_pnl": p.day_pnl,
                    "day_pnl_pct": p.day_pnl_pct,
                    "total_pnl": p.total_pnl,
                    "total_pnl_pct": p.total_pnl_pct,
                    "weight": (p.market_value / full_portfolio_total * 100) if full_portfolio_total else 0.0,
                }
                for p in s.positions
            ]
            entries.append((label, "brokerage", s.total_value, s.cash_balance, s.day_pnl, rows, True))

    for ext in list_accounts():
        positions = get_positions(ext["name"])
        acct_total = ext["total_value"]
        all_account_names.append(ext["name"])

        # Calculate P/L for external accounts (no daily snapshots, so day_pnl = 0)
        rows = []
        ext_day_pnl = 0.0
        for p in sorted(positions, key=lambda x: x.market_value or 0, reverse=True):
            shares = p.shares or 0
            current_price = p.current_price or 0
            avg_cost = p.avg_cost or 0
            market_value = p.market_value or 0.0

            # Total P/L: (current_price - avg_cost) * shares
            total_pnl = (current_price - avg_cost) * shares if avg_cost and shares else 0.0
            total_pnl_pct = ((current_price - avg_cost) / avg_cost * 100) if avg_cost and current_price else 0.0

            # Day P/L: external accounts don't track daily, so 0
            day_pnl = 0.0
            day_pnl_pct = 0.0

            rows.append({
                "ticker": p.ticker,
                "name": p.company_name or p.ticker,
                "shares": shares,
                "avg_cost": avg_cost,
                "current_price": current_price,
                "market_value": market_value,
                "day_pnl": day_pnl,
                "day_pnl_pct": day_pnl_pct,
                "total_pnl": total_pnl,
                "total_pnl_pct": total_pnl_pct,
                "weight": (market_value / full_portfolio_total * 100) if full_portfolio_total and market_value else 0.0,
            })

        entries.append((ext["name"], ext["account_type"], acct_total, 0.0, ext_day_pnl, rows, True))

    # ── Apply account filter ───────────────────────────────────────────────
    if filter_account and filter_account != "__all__":
        entries = [e for e in entries if e[0] == filter_account]

    # ── Aggregate summary metrics ──────────────────────────────────────────
    grand_total = sum(e[2] for e in entries)
    grand_cash = sum(e[3] for e in entries)
    grand_day_pnl = sum(e[4] for e in entries)
    total_positions = sum(len(e[5]) for e in entries)

    account_sections: list[html.Div] = [
        _account_section(name, atype, total, rows, masked, show_pnl)
        for name, atype, total, _cash, _dpnl, rows, show_pnl in entries
    ]

    is_live = schwab_live or bool(all_account_names)

    if not is_live:
        # Sample fallback
        sample = _sample_account()
        grand_total = sample["total_value"]
        grand_cash = sample["cash_balance"]
        grand_day_pnl = sample["day_pnl"]
        total_positions = len(_SAMPLE_POSITIONS)
        account_sections = [_account_section("Sample Portfolio", None, grand_total, _SAMPLE_POSITIONS, masked, show_pnl=True)]

    n_accounts = len(account_sections)

    # ── Summary metrics ────────────────────────────────────────────────────
    day_pnl_sign = "+" if grand_day_pnl >= 0 else ""
    day_pnl_color = COLORS["green"] if grand_day_pnl >= 0 else COLORS["red"]

    alpha_data = calculate_alpha()
    hist_result = get_historical_returns(days=365)
    has_history = hist_result is not None and len(hist_result[2]) >= 2

    alpha_str, alpha_desc, alpha_color = "—", "Insufficient data", COLORS["text_tertiary"]
    if alpha_data is not None:
        av = alpha_data["alpha_pct"]
        alpha_str = f"{'+'if av>=0 else ''}{av}%"
        alpha_desc = f"vs S&P 500 ({alpha_data['days_tracked']} days)"
        alpha_color = COLORS["green"] if av >= 0 else COLORS["red"]

    chart_subtitle = f"Real data ({len(hist_result[2])} trading days)" if has_history else "Simulated — enable daily snapshots for real data"

    portfolio_value_str = mask_number(grand_total, masked=masked)
    cash_balance_str = mask_number(grand_cash, masked=masked)
    day_pnl_str = f"{day_pnl_sign}{mask_number(abs(grand_day_pnl), masked=masked)}" if masked else f"{day_pnl_sign}${abs(grand_day_pnl):,.0f}"
    if grand_total:
        day_pnl_pct_str = mask_pct(abs(grand_day_pnl) / grand_total * 100, masked=masked) if masked else f"{day_pnl_sign}{abs(grand_day_pnl) / grand_total * 100:.2f}%"
    else:
        day_pnl_pct_str = "—"

    data_badge = html.Span(
        "● LIVE" if is_live else "● SAMPLE DATA",
        style={
            "fontSize": "10px", "fontWeight": "700",
            "color": COLORS["green"] if is_live else COLORS["orange"],
            "background": COLORS["green_bg"] if is_live else COLORS["orange_bg"],
            "padding": "3px 10px", "borderRadius": "100px",
            "letterSpacing": "1px", "marginLeft": "12px",
        },
    )

    # ── Account filter dropdown ────────────────────────────────────────────
    dropdown_options = [{"label": "All Accounts", "value": "__all__"}] + [
        {"label": name, "value": name} for name in all_account_names
    ]
    filter_bar = html.Div([
        html.Div([
            data_badge,
            dcc.Dropdown(
                id="account-filter-dropdown",
                options=dropdown_options,
                value=filter_account,
                clearable=False,
                style={
                    "width": "260px",
                    "fontSize": "13px",
                    "background": COLORS["surface"],
                    "border": f"1px solid {COLORS['border']}",
                    "borderRadius": "10px",
                    "padding": "8px 12px",
                    "color": COLORS["text_primary"],
                },
            ),
        ], style={"display": "flex", "alignItems": "center", "gap": "16px"}),
    ], style={"marginBottom": "20px"})

    return html.Div([
        # Status badge + account filter
        filter_bar,

        # KPI strip
        html.Div(
            [
                kpi_card("Total Portfolio", portfolio_value_str, f"{n_accounts} account{'s' if n_accounts != 1 else ''}", COLORS["text_secondary"]),
                kpi_card("Today's P&L", day_pnl_str, f"{day_pnl_pct_str} of portfolio" if grand_total else "", day_pnl_color),
                kpi_card("Positions", str(total_positions), f"Cash: {cash_balance_str}", COLORS["text_secondary"]),
                kpi_card("Alpha vs S&P", alpha_str, alpha_desc, alpha_color),
            ],
            style={"display": "grid", "gridTemplateColumns": "repeat(auto-fit, minmax(220px, 1fr))", "gap": "16px", "marginBottom": "28px"},
        ),

        # Chart
        html.Div([
            html.Div([
                section_header("Performance", "1Y total return vs S&P 500"),
                html.Span(chart_subtitle, style={"fontSize": "11px", "color": COLORS["text_tertiary"], "fontStyle": "italic"}),
            ], style={"display": "flex", "justifyContent": "space-between", "alignItems": "baseline", "marginBottom": "16px"}),
            html.Div(
                _build_chart(grand_total, masked=masked, period=chart_period, filter_account=filter_account),
                style={"background": COLORS["surface"], "border": f"1px solid {COLORS['border']}", "borderRadius": "16px", "padding": "20px"},
            ),
        ], style={"marginBottom": "28px"}),

        # Per-account positions
        section_header("Positions", "by account — external accounts show last imported balance"),
        *account_sections,

        # Rebalance section (Schwab only)
        html.Div([
            html.Hr(style={"border": "none", "borderTop": f"1px solid {COLORS['border']}", "margin": "28px 0 24px 0"}),
            html.Div([
                section_header("Rebalance", "signal-driven allocation based on momentum, sentiment, and volatility"),
                html.Button(
                    "Suggest Rebalance",
                    id="portfolio-rebalance-btn",
                    n_clicks=0,
                    style={
                        "padding": "10px 24px", "fontSize": "13px", "fontWeight": "600",
                        "color": COLORS["text_primary"], "background": COLORS["accent"],
                        "border": "none", "borderRadius": "10px",
                        "cursor": "pointer" if schwab_live else "not-allowed",
                        "opacity": "1" if schwab_live else "0.4",
                    },
                    disabled=not schwab_live,
                ),
            ], style={"display": "flex", "justifyContent": "space-between", "alignItems": "center", "marginBottom": "16px"}),
            html.Div(
                "Connect Schwab to enable rebalancing." if not schwab_live else "",
                id="portfolio-rebalance-panel",
                style={"fontSize": "13px", "color": COLORS["text_tertiary"], "fontStyle": "italic"},
            ),
        ]),

        # Footer
        html.Div(
            "Sample data shown — connect Schwab and refresh" if not is_live else f"Live data · {n_accounts} account{'s' if n_accounts != 1 else ''} loaded",
            style={"fontSize": "12px", "color": COLORS["text_tertiary"], "textAlign": "center", "marginTop": "24px", "fontStyle": "italic"},
        ),
    ])
