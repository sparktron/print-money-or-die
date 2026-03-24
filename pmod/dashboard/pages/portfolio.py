"""Portfolio performance view — Bloomberg meets Apple."""

from datetime import datetime, timedelta

from dash import dcc, html
import plotly.graph_objects as go

from pmod.dashboard.components import (
    CHART_LAYOUT,
    COLORS,
    MONO,
    kpi_card,
    section_header,
    status_badge,
)

# ── Sample data (replaced with live data once Schwab is connected) ────────
_DATES = [
    (datetime(2024, 1, 2) + timedelta(days=i)).strftime("%Y-%m-%d")
    for i in range(365)
]

_PORTFOLIO = [
    100_000 + i * 42 + (i % 7 - 3) * 180 + (i % 30 - 15) * 95
    for i in range(365)
]

_SP500 = [
    100_000 + i * 35 + (i % 7 - 3) * 150 + (i % 30 - 15) * 70
    for i in range(365)
]

_POSITIONS = [
    {
        "ticker": "NVDA",
        "name": "NVIDIA Corp.",
        "shares": 45,
        "cost": 487.20,
        "current": 924.80,
        "weight": 24.1,
        "signal": "Strong Buy",
        "signal_variant": "green",
    },
    {
        "ticker": "AAPL",
        "name": "Apple Inc.",
        "shares": 120,
        "cost": 172.50,
        "current": 198.30,
        "weight": 13.8,
        "signal": "Hold",
        "signal_variant": "neutral",
    },
    {
        "ticker": "MSFT",
        "name": "Microsoft Corp.",
        "shares": 55,
        "cost": 378.90,
        "current": 428.60,
        "weight": 13.6,
        "signal": "Buy",
        "signal_variant": "green",
    },
    {
        "ticker": "AMZN",
        "name": "Amazon.com Inc.",
        "shares": 70,
        "cost": 153.20,
        "current": 187.40,
        "weight": 7.6,
        "signal": "Buy",
        "signal_variant": "green",
    },
    {
        "ticker": "GOOGL",
        "name": "Alphabet Inc.",
        "shares": 85,
        "cost": 138.70,
        "current": 164.20,
        "weight": 8.1,
        "signal": "Hold",
        "signal_variant": "neutral",
    },
    {
        "ticker": "META",
        "name": "Meta Platforms",
        "shares": 32,
        "cost": 345.80,
        "current": 512.90,
        "weight": 9.5,
        "signal": "Strong Buy",
        "signal_variant": "green",
    },
    {
        "ticker": "TSLA",
        "name": "Tesla Inc.",
        "shares": 40,
        "cost": 248.60,
        "current": 215.30,
        "weight": 5.0,
        "signal": "Sell",
        "signal_variant": "red",
    },
    {
        "ticker": "JPM",
        "name": "JPMorgan Chase",
        "shares": 60,
        "cost": 172.40,
        "current": 198.70,
        "weight": 6.9,
        "signal": "Buy",
        "signal_variant": "green",
    },
]


def _build_chart() -> dcc.Graph:
    """Build the main portfolio performance chart."""
    fig = go.Figure()

    # Portfolio area fill
    fig.add_trace(
        go.Scatter(
            x=_DATES,
            y=_PORTFOLIO,
            mode="lines",
            name="Portfolio",
            line=dict(color=COLORS["accent"], width=2),
            fill="tozeroy",
            fillcolor=COLORS["chart_area"],
            hovertemplate="<b>Portfolio</b><br>%{x}<br>$%{y:,.0f}<extra></extra>",
        )
    )

    # S&P 500 benchmark
    fig.add_trace(
        go.Scatter(
            x=_DATES,
            y=_SP500,
            mode="lines",
            name="S&P 500",
            line=dict(color=COLORS["text_tertiary"], width=1.5, dash="dot"),
            hovertemplate="<b>S&P 500</b><br>%{x}<br>$%{y:,.0f}<extra></extra>",
        )
    )

    layout = {**CHART_LAYOUT}
    layout["height"] = 380
    layout["margin"] = dict(l=0, r=0, t=10, b=0)
    layout["legend"] = dict(
        **CHART_LAYOUT["legend"],
        orientation="h",
        yanchor="bottom",
        y=1.02,
        xanchor="right",
        x=1,
    )
    layout["xaxis"] = {
        **CHART_LAYOUT["xaxis"],
        "type": "date",
        "tickformat": "%b '%y",
        "dtick": "M2",
    }
    layout["yaxis"] = {
        **CHART_LAYOUT["yaxis"],
        "tickprefix": "$",
        "tickformat": ",.0f",
    }
    fig.update_layout(**layout)

    return dcc.Graph(
        id="portfolio-chart",
        figure=fig,
        config={"displayModeBar": False},
        style={"borderRadius": "12px"},
    )


def _build_positions_table() -> html.Div:
    """Build the positions data table."""
    header_style = {
        "fontSize": "11px",
        "fontWeight": "600",
        "color": COLORS["text_tertiary"],
        "textTransform": "uppercase",
        "letterSpacing": "0.8px",
        "padding": "12px 16px",
        "textAlign": "left",
        "borderBottom": f"1px solid {COLORS['border']}",
    }

    header_style_right = {**header_style, "textAlign": "right"}

    headers = html.Tr(
        [
            html.Th("Asset", style=header_style),
            html.Th("Shares", style=header_style_right),
            html.Th("Avg Cost", style=header_style_right),
            html.Th("Price", style=header_style_right),
            html.Th("Value", style=header_style_right),
            html.Th("P&L", style=header_style_right),
            html.Th("Weight", style=header_style_right),
            html.Th("Signal", style={**header_style, "textAlign": "center"}),
        ]
    )

    rows = []
    for pos in _POSITIONS:
        value = pos["shares"] * pos["current"]
        cost_total = pos["shares"] * pos["cost"]
        pnl = value - cost_total
        pnl_pct = (pnl / cost_total) * 100
        is_positive = pnl >= 0

        cell = {
            "padding": "14px 16px",
            "borderBottom": f"1px solid {COLORS['border']}",
            "fontSize": "14px",
            "color": COLORS["text_primary"],
        }
        cell_right = {**cell, "textAlign": "right", "fontFamily": MONO}
        cell_center = {**cell, "textAlign": "center"}

        pnl_color = COLORS["green"] if is_positive else COLORS["red"]

        rows.append(
            html.Tr(
                [
                    html.Td(
                        html.Div(
                            [
                                html.Span(
                                    pos["ticker"],
                                    style={
                                        "fontWeight": "600",
                                        "fontSize": "14px",
                                        "color": COLORS["text_primary"],
                                    },
                                ),
                                html.Br(),
                                html.Span(
                                    pos["name"],
                                    style={
                                        "fontSize": "12px",
                                        "color": COLORS["text_tertiary"],
                                    },
                                ),
                            ]
                        ),
                        style=cell,
                    ),
                    html.Td(f"{pos['shares']}", style=cell_right),
                    html.Td(f"${pos['cost']:,.2f}", style=cell_right),
                    html.Td(f"${pos['current']:,.2f}", style=cell_right),
                    html.Td(f"${value:,.0f}", style=cell_right),
                    html.Td(
                        html.Span(
                            f"{'+'if is_positive else ''}{pnl_pct:.1f}%",
                            style={"color": pnl_color},
                        ),
                        style=cell_right,
                    ),
                    html.Td(
                        _weight_bar(pos["weight"]),
                        style=cell_right,
                    ),
                    html.Td(
                        status_badge(pos["signal"], pos["signal_variant"]),
                        style=cell_center,
                    ),
                ],
                style={"transition": "background 0.15s ease"},
            )
        )

    return html.Div(
        html.Table(
            [html.Thead(headers), html.Tbody(rows)],
            style={
                "width": "100%",
                "borderCollapse": "collapse",
                "borderSpacing": "0",
            },
        ),
        style={
            "background": COLORS["surface"],
            "border": f"1px solid {COLORS['border']}",
            "borderRadius": "16px",
            "overflow": "hidden",
        },
    )


def _weight_bar(pct: float) -> html.Div:
    """Render a horizontal weight indicator."""
    return html.Div(
        [
            html.Div(
                style={
                    "width": f"{min(pct * 3.5, 100)}%",
                    "height": "4px",
                    "background": COLORS["accent"],
                    "borderRadius": "2px",
                    "transition": "width 0.5s ease",
                },
            ),
            html.Span(
                f"{pct:.1f}%",
                style={
                    "fontSize": "12px",
                    "color": COLORS["text_secondary"],
                    "marginTop": "2px",
                },
            ),
        ],
        style={"display": "flex", "flexDirection": "column", "alignItems": "flex-end"},
    )


def portfolio_layout() -> html.Div:
    """Return the full portfolio page layout."""
    total_value = sum(p["shares"] * p["current"] for p in _POSITIONS)
    total_cost = sum(p["shares"] * p["cost"] for p in _POSITIONS)
    total_pnl = total_value - total_cost
    total_pnl_pct = (total_pnl / total_cost) * 100

    return html.Div(
        [
            # KPI row
            html.Div(
                [
                    kpi_card(
                        "Portfolio Value",
                        f"${total_value:,.0f}",
                        f"+${total_pnl:,.0f} ({total_pnl_pct:+.2f}%)",
                        COLORS["green"],
                    ),
                    kpi_card(
                        "Today's P&L",
                        "+$1,847",
                        "+0.78% vs yesterday",
                        COLORS["green"],
                    ),
                    kpi_card(
                        "Alpha vs S&P",
                        "+4.2%",
                        "Outperforming benchmark",
                        COLORS["accent"],
                    ),
                    kpi_card(
                        "Positions",
                        str(len(_POSITIONS)),
                        "8 active / 0 pending",
                        COLORS["text_secondary"],
                    ),
                ],
                style={
                    "display": "grid",
                    "gridTemplateColumns": "repeat(auto-fit, minmax(220px, 1fr))",
                    "gap": "16px",
                    "marginBottom": "28px",
                },
            ),
            # Chart section
            html.Div(
                [
                    section_header("Performance", "1Y total return vs S&P 500"),
                    html.Div(
                        _build_chart(),
                        style={
                            "background": COLORS["surface"],
                            "border": f"1px solid {COLORS['border']}",
                            "borderRadius": "16px",
                            "padding": "20px",
                        },
                    ),
                ],
                style={"marginBottom": "28px"},
            ),
            # Positions table
            section_header("Positions", "sorted by portfolio weight"),
            _build_positions_table(),
            # Footer note
            html.Div(
                "Sample data shown — connect Schwab account for live positions",
                style={
                    "fontSize": "12px",
                    "color": COLORS["text_tertiary"],
                    "textAlign": "center",
                    "marginTop": "24px",
                    "fontStyle": "italic",
                },
            ),
        ]
    )
