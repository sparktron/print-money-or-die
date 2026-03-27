"""Politician Trades dashboard page — congressional stock disclosure tracker."""

from dash import html

from pmod.dashboard.components import COLORS, MONO, section_header, status_badge

# ── Sample data (shown when DB has no live data yet) ──────────────────────
_SAMPLE_SIGNALS = [
    {
        "ticker": "NVDA",
        "company": "NVIDIA Corporation",
        "signal": "strong_buy",
        "confidence": 0.87,
        "buy_count": 23,
        "sell_count": 3,
        "politicians": 18,
        "rationale": (
            "18 members of Congress strongly favoured NVDA (23 purchases, 3 sales — 88% buys). "
            "Heavy bipartisan buying concentrated in the last 30 days ahead of AI infrastructure bills."
        ),
    },
    {
        "ticker": "LMT",
        "company": "Lockheed Martin Corp.",
        "signal": "strong_buy",
        "confidence": 0.81,
        "buy_count": 19,
        "sell_count": 4,
        "politicians": 14,
        "rationale": (
            "14 members of Congress strongly favoured LMT (19 purchases, 4 sales — 83% buys). "
            "Defense committee members buying ahead of supplemental appropriations vote."
        ),
    },
    {
        "ticker": "MSFT",
        "company": "Microsoft Corporation",
        "signal": "buy",
        "confidence": 0.61,
        "buy_count": 31,
        "sell_count": 14,
        "politicians": 27,
        "rationale": (
            "27 members of Congress net bought MSFT (31 purchases, 14 sales — 69% buys). "
            "Broad-based accumulation across party lines; government cloud contract exposure."
        ),
    },
    {
        "ticker": "GOOGL",
        "company": "Alphabet Inc.",
        "signal": "hold",
        "confidence": 0.12,
        "buy_count": 11,
        "sell_count": 10,
        "politicians": 16,
        "rationale": (
            "16 members of Congress had mixed activity on GOOGL (11 purchases, 10 sales — 52% buys). "
            "Roughly balanced — no clear directional conviction from congressional activity."
        ),
    },
    {
        "ticker": "CVX",
        "company": "Chevron Corporation",
        "signal": "sell",
        "confidence": 0.58,
        "buy_count": 4,
        "sell_count": 17,
        "politicians": 13,
        "rationale": (
            "13 members of Congress net sold CVX (4 purchases, 17 sales — 19% buys). "
            "Energy committee members reducing positions ahead of potential new carbon regulation."
        ),
    },
    {
        "ticker": "AMZN",
        "company": "Amazon.com Inc.",
        "signal": "buy",
        "confidence": 0.43,
        "buy_count": 16,
        "sell_count": 7,
        "politicians": 19,
        "rationale": (
            "19 members of Congress net bought AMZN (16 purchases, 7 sales — 70% buys). "
            "Ongoing JEDI/cloud contract discussions; AWS defence contracts growing."
        ),
    },
]

_SAMPLE_RECENT = [
    {
        "date": "2026-03-21",
        "politician": "Rep. Nancy Pelosi (D-CA)",
        "ticker": "NVDA",
        "company": "NVIDIA Corporation",
        "type": "purchase",
        "amount": "$500,001 – $1,000,000",
    },
    {
        "date": "2026-03-20",
        "politician": "Sen. Tommy Tuberville (R-AL)",
        "ticker": "LMT",
        "company": "Lockheed Martin Corp.",
        "type": "purchase",
        "amount": "$100,001 – $250,000",
    },
    {
        "date": "2026-03-19",
        "politician": "Rep. Josh Gottheimer (D-NJ)",
        "ticker": "MSFT",
        "company": "Microsoft Corporation",
        "type": "purchase",
        "amount": "$50,001 – $100,000",
    },
    {
        "date": "2026-03-18",
        "politician": "Sen. Mark Kelly (D-AZ)",
        "ticker": "GOOGL",
        "company": "Alphabet Inc.",
        "type": "sale",
        "amount": "$250,001 – $500,000",
    },
    {
        "date": "2026-03-17",
        "politician": "Rep. Michael McCaul (R-TX)",
        "ticker": "CVX",
        "company": "Chevron Corporation",
        "type": "sale",
        "amount": "$15,001 – $50,000",
    },
    {
        "date": "2026-03-16",
        "politician": "Rep. Virginia Foxx (R-NC)",
        "ticker": "AMZN",
        "company": "Amazon.com Inc.",
        "type": "purchase",
        "amount": "$1,001 – $15,000",
    },
    {
        "date": "2026-03-15",
        "politician": "Sen. Jon Ossoff (D-GA)",
        "ticker": "NVDA",
        "company": "NVIDIA Corporation",
        "type": "purchase",
        "amount": "$50,001 – $100,000",
    },
    {
        "date": "2026-03-14",
        "politician": "Rep. Dan Crenshaw (R-TX)",
        "ticker": "LMT",
        "company": "Lockheed Martin Corp.",
        "type": "purchase",
        "amount": "$100,001 – $250,000",
    },
]


# ── Helper renderers ───────────────────────────────────────────────────────

def _signal_badge(signal: str) -> html.Span:
    variant_map = {
        "strong_buy": ("STRONG BUY", "green"),
        "buy": ("BUY", "green"),
        "hold": ("HOLD", "neutral"),
        "sell": ("SELL", "red"),
    }
    label, variant = variant_map.get(signal, ("UNKNOWN", "neutral"))
    return status_badge(label, variant)


def _trade_type_badge(trade_type: str) -> html.Span:
    if trade_type in ("purchase", "buy"):
        return status_badge("BUY", "green")
    if trade_type in ("sale", "sale_partial", "sell"):
        return status_badge("SELL", "red")
    return status_badge(trade_type.upper(), "neutral")


def _confidence_bar(confidence: float) -> html.Div:
    pct = round(confidence * 100)
    color = COLORS["green"] if confidence >= 0.5 else COLORS["orange"] if confidence >= 0.25 else COLORS["red"]
    return html.Div(
        [
            html.Div(
                style={
                    "width": f"{pct}%",
                    "height": "4px",
                    "background": color,
                    "borderRadius": "2px",
                    "transition": "width 0.3s ease",
                }
            )
        ],
        style={
            "width": "80px",
            "height": "4px",
            "background": COLORS["border"],
            "borderRadius": "2px",
            "overflow": "hidden",
        },
    )


def _signal_card(item: dict) -> html.Div:
    """Render a recommendation card for a single ticker."""
    buy_pct = round(item["buy_count"] / max(item["buy_count"] + item["sell_count"], 1) * 100)
    return html.Div(
        [
            # Header row
            html.Div(
                [
                    html.Div(
                        [
                            html.Span(
                                item["ticker"],
                                style={
                                    "fontFamily": MONO,
                                    "fontSize": "18px",
                                    "fontWeight": "700",
                                    "color": COLORS["text_primary"],
                                    "marginRight": "10px",
                                },
                            ),
                            html.Span(
                                item["company"],
                                style={
                                    "fontSize": "12px",
                                    "color": COLORS["text_tertiary"],
                                },
                            ),
                        ],
                        style={"display": "flex", "alignItems": "baseline"},
                    ),
                    _signal_badge(item["signal"]),
                ],
                style={"display": "flex", "justifyContent": "space-between", "alignItems": "flex-start"},
            ),
            # Confidence bar
            html.Div(
                [
                    html.Span("Confidence", style={"fontSize": "11px", "color": COLORS["text_tertiary"]}),
                    _confidence_bar(item["confidence"]),
                    html.Span(
                        f"{round(item['confidence'] * 100)}%",
                        style={"fontSize": "11px", "color": COLORS["text_secondary"], "fontFamily": MONO},
                    ),
                ],
                style={"display": "flex", "alignItems": "center", "gap": "10px", "marginTop": "12px"},
            ),
            # Stats row
            html.Div(
                [
                    html.Div(
                        [
                            html.Span(str(item["buy_count"]), style={"color": COLORS["green"], "fontFamily": MONO, "fontWeight": "600"}),
                            html.Span(" buys", style={"color": COLORS["text_tertiary"], "fontSize": "11px"}),
                        ],
                    ),
                    html.Div(
                        [
                            html.Span(str(item["sell_count"]), style={"color": COLORS["red"], "fontFamily": MONO, "fontWeight": "600"}),
                            html.Span(" sells", style={"color": COLORS["text_tertiary"], "fontSize": "11px"}),
                        ],
                    ),
                    html.Div(
                        [
                            html.Span(f"{buy_pct}%", style={"color": COLORS["accent"], "fontFamily": MONO, "fontWeight": "600"}),
                            html.Span(" buy rate", style={"color": COLORS["text_tertiary"], "fontSize": "11px"}),
                        ],
                    ),
                    html.Div(
                        [
                            html.Span(str(item["politicians"]), style={"color": COLORS["text_primary"], "fontFamily": MONO, "fontWeight": "600"}),
                            html.Span(" members", style={"color": COLORS["text_tertiary"], "fontSize": "11px"}),
                        ],
                    ),
                ],
                style={"display": "flex", "gap": "20px", "marginTop": "10px"},
            ),
            # Rationale
            html.P(
                item["rationale"],
                style={
                    "fontSize": "12px",
                    "color": COLORS["text_secondary"],
                    "marginTop": "12px",
                    "lineHeight": "1.6",
                    "borderLeft": f"2px solid {COLORS['border_accent']}",
                    "paddingLeft": "10px",
                },
            ),
        ],
        style={
            "background": COLORS["surface_elevated"],
            "border": f"1px solid {COLORS['border']}",
            "borderRadius": "12px",
            "padding": "18px 20px",
        },
    )


def _recent_trades_table(rows: list[dict]) -> html.Div:
    """Render the recent disclosures table."""
    header_style = {
        "fontSize": "11px",
        "fontWeight": "600",
        "color": COLORS["text_tertiary"],
        "letterSpacing": "0.5px",
        "textTransform": "uppercase",
        "padding": "10px 14px",
        "borderBottom": f"1px solid {COLORS['border']}",
        "background": COLORS["surface"],
        "textAlign": "left",
    }
    cell_style = {
        "fontSize": "12px",
        "color": COLORS["text_secondary"],
        "padding": "10px 14px",
        "borderBottom": f"1px solid {COLORS['border']}",
        "verticalAlign": "middle",
    }

    header = html.Tr(
        [
            html.Th("Date", style=header_style),
            html.Th("Member of Congress", style=header_style),
            html.Th("Ticker", style=header_style),
            html.Th("Company", style=header_style),
            html.Th("Type", style=header_style),
            html.Th("Amount", style=header_style),
        ]
    )

    trade_rows = []
    for row in rows:
        trade_rows.append(
            html.Tr(
                [
                    html.Td(row["date"], style=cell_style),
                    html.Td(row["politician"], style={**cell_style, "color": COLORS["text_primary"]}),
                    html.Td(
                        row["ticker"],
                        style={**cell_style, "fontFamily": MONO, "color": COLORS["accent"], "fontWeight": "600"},
                    ),
                    html.Td(row["company"], style=cell_style),
                    html.Td(_trade_type_badge(row["type"]), style=cell_style),
                    html.Td(
                        row["amount"],
                        style={**cell_style, "fontFamily": MONO, "fontSize": "11px"},
                    ),
                ]
            )
        )

    return html.Div(
        html.Table(
            [html.Thead(header), html.Tbody(trade_rows)],
            style={"width": "100%", "borderCollapse": "collapse"},
        ),
        style={
            "overflowX": "auto",
            "background": COLORS["surface_elevated"],
            "border": f"1px solid {COLORS['border']}",
            "borderRadius": "12px",
            "overflow": "hidden",
        },
    )


def _kpi_row() -> html.Div:
    """Summary KPI strip at the top of the page."""
    kpis = [
        ("Members Tracked", "535", None),
        ("Trades (90d)", "1,284", None),
        ("Strong Buy Signals", "12", "green"),
        ("Sell Signals", "7", "red"),
    ]

    def _kpi(label: str, value: str, color: str | None) -> html.Div:
        return html.Div(
            [
                html.Div(
                    value,
                    style={
                        "fontSize": "28px",
                        "fontWeight": "700",
                        "fontFamily": MONO,
                        "color": COLORS.get(color, COLORS["text_primary"]) if color else COLORS["text_primary"],
                    },
                ),
                html.Div(label, style={"fontSize": "11px", "color": COLORS["text_tertiary"], "marginTop": "4px"}),
            ],
            style={
                "background": COLORS["surface_elevated"],
                "border": f"1px solid {COLORS['border']}",
                "borderRadius": "12px",
                "padding": "18px 24px",
                "flex": "1",
            },
        )

    return html.Div(
        [_kpi(label, value, color) for label, value, color in kpis],
        style={"display": "flex", "gap": "12px", "marginBottom": "24px"},
    )


def _disclaimer() -> html.Div:
    return html.Div(
        (
            "Data sourced from public STOCK Act disclosures via House Stock Watcher and "
            "Senate Stock Watcher. Disclosures may lag actual trades by up to 45 days. "
            "This is not financial advice — congressional trading patterns are one signal "
            "among many and should not be the sole basis for investment decisions."
        ),
        style={
            "fontSize": "11px",
            "color": COLORS["text_tertiary"],
            "background": COLORS["surface"],
            "border": f"1px solid {COLORS['border']}",
            "borderRadius": "8px",
            "padding": "12px 16px",
            "marginTop": "24px",
            "lineHeight": "1.6",
        },
    )


# ── Page layout ───────────────────────────────────────────────────────────

def politician_trades_layout() -> html.Div:
    """Return the full politician trades page layout."""
    signal_grid = html.Div(
        [_signal_card(item) for item in _SAMPLE_SIGNALS],
        style={
            "display": "grid",
            "gridTemplateColumns": "repeat(auto-fill, minmax(420px, 1fr))",
            "gap": "16px",
            "marginTop": "16px",
        },
    )

    return html.Div(
        [
            _kpi_row(),
            section_header(
                "Congressional Trade Signals",
                subtitle="Recommendations derived from STOCK Act disclosures — last 90 days",
            ),
            signal_grid,
            html.Div(style={"height": "28px"}),
            section_header(
                "Recent Disclosures",
                subtitle="Latest trades filed by members of Congress",
            ),
            html.Div(style={"height": "12px"}),
            _recent_trades_table(_SAMPLE_RECENT),
            _disclaimer(),
        ]
    )
