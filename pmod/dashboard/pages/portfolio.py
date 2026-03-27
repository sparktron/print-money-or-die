"""Portfolio performance view — live Schwab data with sample fallback."""
from __future__ import annotations

from datetime import datetime, timedelta

import plotly.graph_objects as go
from dash import dcc, html

from pmod.broker.schwab import AccountSummary, Position, get_account_summary
from pmod.dashboard.components import (
    CHART_LAYOUT,
    COLORS,
    MONO,
    kpi_card,
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

def _build_chart(total_value: float) -> dcc.Graph:
    """Simulated 1-year performance chart (historical snapshots not yet tracked)."""
    dates = [
        (datetime(2025, 3, 26) - timedelta(days=364 - i)).strftime("%Y-%m-%d")
        for i in range(365)
    ]
    start = total_value * 0.78
    portfolio = [start + (total_value - start) * (i / 364) + ((i % 7 - 3) * start * 0.002) for i in range(365)]
    sp500 = [start * 0.97 + (total_value * 0.93 - start * 0.97) * (i / 364) + ((i % 7 - 3) * start * 0.0015) for i in range(365)]

    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=dates, y=portfolio, mode="lines", name="Portfolio",
        line=dict(color=COLORS["accent"], width=2),
        fill="tozeroy", fillcolor=COLORS["chart_area"],
        hovertemplate="<b>Portfolio</b><br>%{x}<br>$%{y:,.0f}<extra></extra>",
    ))
    fig.add_trace(go.Scatter(
        x=dates, y=sp500, mode="lines", name="S&P 500",
        line=dict(color=COLORS["text_tertiary"], width=1.5, dash="dot"),
        hovertemplate="<b>S&P 500</b><br>%{x}<br>$%{y:,.0f}<extra></extra>",
    ))

    layout = {**CHART_LAYOUT, "height": 380, "margin": dict(l=0, r=0, t=10, b=0)}
    layout["legend"] = dict(**CHART_LAYOUT["legend"], orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)
    layout["xaxis"] = {**CHART_LAYOUT["xaxis"], "type": "date", "tickformat": "%b '%y", "dtick": "M2"}
    layout["yaxis"] = {**CHART_LAYOUT["yaxis"], "tickprefix": "$", "tickformat": ",.0f"}
    fig.update_layout(**layout)

    return dcc.Graph(id="portfolio-chart", figure=fig, config={"displayModeBar": False}, style={"borderRadius": "12px"})


# ── Positions table ────────────────────────────────────────────────────────

def _weight_bar(pct: float) -> html.Div:
    return html.Div(
        [
            html.Div(style={"width": f"{min(pct * 3.5, 100)}%", "height": "4px", "background": COLORS["accent"], "borderRadius": "2px"}),
            html.Span(f"{pct:.1f}%", style={"fontSize": "12px", "color": COLORS["text_secondary"], "marginTop": "2px"}),
        ],
        style={"display": "flex", "flexDirection": "column", "alignItems": "flex-end"},
    )


def _positions_table(rows_data: list[dict]) -> html.Div:
    h = {"fontSize": "11px", "fontWeight": "600", "color": COLORS["text_tertiary"],
         "textTransform": "uppercase", "letterSpacing": "0.8px",
         "padding": "12px 16px", "textAlign": "left", "borderBottom": f"1px solid {COLORS['border']}"}
    hr = {**h, "textAlign": "right"}

    headers = html.Tr([
        html.Th("Asset", style=h),
        html.Th("Shares", style=hr),
        html.Th("Avg Cost", style=hr),
        html.Th("Price", style=hr),
        html.Th("Value", style=hr),
        html.Th("Day P&L", style=hr),
        html.Th("Total P&L", style=hr),
        html.Th("Weight", style=hr),
    ])

    cell = {"padding": "14px 16px", "borderBottom": f"1px solid {COLORS['border']}", "fontSize": "14px", "color": COLORS["text_primary"]}
    cell_r = {**cell, "textAlign": "right", "fontFamily": MONO}

    table_rows = []
    for p in rows_data:
        day_color = COLORS["green"] if p["day_pnl"] >= 0 else COLORS["red"]
        total_color = COLORS["green"] if p["total_pnl"] >= 0 else COLORS["red"]
        day_sign = "+" if p["day_pnl"] >= 0 else ""
        total_sign = "+" if p["total_pnl"] >= 0 else ""

        shares_str = f"{p['shares']:.4f}".rstrip("0").rstrip(".") if p["shares"] != int(p["shares"]) else str(int(p["shares"]))

        table_rows.append(html.Tr([
            html.Td(html.Div([
                html.Span(p["ticker"], style={"fontWeight": "600", "fontSize": "14px", "color": COLORS["text_primary"]}),
                html.Br(),
                html.Span(p["name"], style={"fontSize": "12px", "color": COLORS["text_tertiary"]}),
            ]), style=cell),
            html.Td(shares_str, style=cell_r),
            html.Td(f"${p['avg_cost']:,.2f}", style=cell_r),
            html.Td(f"${p['current_price']:,.2f}", style=cell_r),
            html.Td(f"${p['market_value']:,.0f}", style=cell_r),
            html.Td(html.Span(f"{day_sign}{p['day_pnl']:,.0f} ({day_sign}{p['day_pnl_pct']:.2f}%)", style={"color": day_color}), style=cell_r),
            html.Td(html.Span(f"{total_sign}{p['total_pnl_pct']:.1f}%", style={"color": total_color}), style=cell_r),
            html.Td(_weight_bar(p["weight"]), style=cell_r),
        ]))

    return html.Div(
        html.Table([html.Thead(headers), html.Tbody(table_rows)],
                   style={"width": "100%", "borderCollapse": "collapse", "borderSpacing": "0"}),
        style={"background": COLORS["surface"], "border": f"1px solid {COLORS['border']}", "borderRadius": "16px", "overflow": "hidden"},
    )


# ── Public layout ──────────────────────────────────────────────────────────

def portfolio_layout() -> html.Div:
    """Return the portfolio page, using live Schwab data when available."""
    summary: AccountSummary | None = get_account_summary()
    is_live = summary is not None and summary.total_value > 0

    if is_live:
        assert summary is not None
        rows_data = [
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
                "weight": p.weight,
            }
            for p in summary.positions
        ]
        total_value = summary.total_value
        cash_balance = summary.cash_balance
        day_pnl = summary.day_pnl
    else:
        rows_data = _SAMPLE_POSITIONS
        sample = _sample_account()
        total_value = sample["total_value"]
        cash_balance = sample["cash_balance"]
        day_pnl = sample["day_pnl"]

    day_pnl_sign = "+" if day_pnl >= 0 else ""
    day_pnl_color = COLORS["green"] if day_pnl >= 0 else COLORS["red"]
    n_positions = len(rows_data)

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

    return html.Div([
        # Status badge row
        html.Div([data_badge], style={"marginBottom": "20px"}),

        # KPI strip
        html.Div(
            [
                kpi_card("Portfolio Value", f"${total_value:,.0f}", f"Cash: ${cash_balance:,.0f}", COLORS["text_secondary"]),
                kpi_card("Today's P&L", f"{day_pnl_sign}${abs(day_pnl):,.0f}", f"{day_pnl_sign}{abs(day_pnl) / total_value * 100:.2f}% of portfolio" if total_value else "", day_pnl_color),
                kpi_card("Positions", str(n_positions), f"{n_positions} equity / cash: ${cash_balance:,.0f}", COLORS["text_secondary"]),
                kpi_card("Alpha vs S&P", "—", "Enable market data for benchmark", COLORS["text_tertiary"]),
            ],
            style={"display": "grid", "gridTemplateColumns": "repeat(auto-fit, minmax(220px, 1fr))", "gap": "16px", "marginBottom": "28px"},
        ),

        # Chart (simulated until daily snapshots are implemented)
        html.Div([
            html.Div([
                section_header("Performance", "1Y total return vs S&P 500"),
                html.Span("Simulated — historical snapshots not yet tracked", style={
                    "fontSize": "11px", "color": COLORS["text_tertiary"], "fontStyle": "italic",
                }),
            ], style={"display": "flex", "justifyContent": "space-between", "alignItems": "baseline", "marginBottom": "16px"}),
            html.Div(
                _build_chart(total_value),
                style={"background": COLORS["surface"], "border": f"1px solid {COLORS['border']}", "borderRadius": "16px", "padding": "20px"},
            ),
        ], style={"marginBottom": "28px"}),

        # Positions table
        section_header("Positions", "sorted by market value"),
        _positions_table(rows_data),

        # Footer
        html.Div(
            "Sample data shown — connect Schwab and refresh" if not is_live else f"Live data from account ···{summary.account_number[-4:] if summary and summary.account_number else ''}",  # type: ignore[union-attr]
            style={"fontSize": "12px", "color": COLORS["text_tertiary"], "textAlign": "center", "marginTop": "24px", "fontStyle": "italic"},
        ),
    ])
