"""Curated picks and watchlist view — Bloomberg meets Apple."""

from dash import html

from pmod.dashboard.components import COLORS, MONO, section_header, status_badge

# ── Sample watchlist data ─────────────────────────────────────────────────
_PICKS = [
    {
        "ticker": "NVDA",
        "name": "NVIDIA Corp.",
        "price": "$924.80",
        "change": "+3.2%",
        "change_positive": True,
        "momentum": 94,
        "valuation": "Premium",
        "valuation_variant": "orange",
        "sentiment": "Very Bullish",
        "sentiment_variant": "green",
        "reason": (
            "Dominant AI/ML chip supplier with 80%+ data center GPU market share. "
            "Massive earnings beats driven by explosive demand for H100/B100 GPUs. "
            "Fits your growth strategy with exceptional revenue acceleration."
        ),
        "tags": ["AI/ML", "Semiconductors", "Growth"],
    },
    {
        "ticker": "PLTR",
        "name": "Palantir Technologies",
        "price": "$24.60",
        "change": "+1.8%",
        "change_positive": True,
        "momentum": 82,
        "valuation": "Fair",
        "valuation_variant": "green",
        "sentiment": "Bullish",
        "sentiment_variant": "green",
        "reason": (
            "Leading AI platform for government and enterprise analytics. "
            "AIP platform driving commercial segment growth at 40%+ YoY. "
            "Expanding margins with sticky, high-value contracts."
        ),
        "tags": ["AI/ML", "Software", "Defense"],
    },
    {
        "ticker": "AVGO",
        "name": "Broadcom Inc.",
        "price": "$168.40",
        "change": "+0.9%",
        "change_positive": True,
        "momentum": 78,
        "valuation": "Fair",
        "valuation_variant": "green",
        "sentiment": "Bullish",
        "sentiment_variant": "green",
        "reason": (
            "Custom AI chip partnerships with major hyperscalers. "
            "VMware acquisition creates recurring software revenue stream. "
            "Strong dividend history supports your balanced strategy."
        ),
        "tags": ["Semiconductors", "Infrastructure", "Dividend"],
    },
    {
        "ticker": "CRWD",
        "name": "CrowdStrike Holdings",
        "price": "$342.10",
        "change": "-0.4%",
        "change_positive": False,
        "momentum": 71,
        "valuation": "Premium",
        "valuation_variant": "orange",
        "sentiment": "Neutral",
        "sentiment_variant": "neutral",
        "reason": (
            "Cybersecurity leader with best-in-class Falcon platform. "
            "Recovering well from July outage incident with improved processes. "
            "88% gross retention — extremely sticky enterprise customer base."
        ),
        "tags": ["Cybersecurity", "Cloud", "SaaS"],
    },
    {
        "ticker": "LLY",
        "name": "Eli Lilly & Co.",
        "price": "$782.50",
        "change": "+2.1%",
        "change_positive": True,
        "momentum": 88,
        "valuation": "Premium",
        "valuation_variant": "orange",
        "sentiment": "Very Bullish",
        "sentiment_variant": "green",
        "reason": (
            "GLP-1 pipeline with Mounjaro/Zepbound driving massive revenue growth. "
            "Tirzepatide supply ramp-up unlocking TAM worth $100B+. "
            "Strong momentum score with consistent analyst upgrades."
        ),
        "tags": ["Pharma", "GLP-1", "Growth"],
    },
    {
        "ticker": "COIN",
        "name": "Coinbase Global",
        "price": "$267.30",
        "change": "+4.5%",
        "change_positive": True,
        "momentum": 76,
        "valuation": "Fair",
        "valuation_variant": "green",
        "sentiment": "Bullish",
        "sentiment_variant": "green",
        "reason": (
            "Dominant US crypto exchange benefiting from Bitcoin ETF volumes. "
            "Diversifying revenue with staking, Base L2, and institutional custody. "
            "Positive regulatory tailwinds with increased crypto policy clarity."
        ),
        "tags": ["Crypto", "Fintech", "High Volatility"],
    },
]


def _momentum_bar(score: int) -> html.Div:
    """Render a horizontal momentum score bar."""
    if score >= 80:
        color = COLORS["green"]
    elif score >= 60:
        color = COLORS["accent"]
    else:
        color = COLORS["orange"]

    return html.Div(
        [
            html.Div(
                [
                    html.Span("Momentum", style={
                        "fontSize": "11px",
                        "color": COLORS["text_tertiary"],
                        "textTransform": "uppercase",
                        "letterSpacing": "0.5px",
                    }),
                    html.Span(str(score), style={
                        "fontSize": "13px",
                        "fontWeight": "600",
                        "fontFamily": MONO,
                        "color": color,
                    }),
                ],
                style={
                    "display": "flex",
                    "justifyContent": "space-between",
                    "marginBottom": "6px",
                },
            ),
            html.Div(
                html.Div(
                    style={
                        "width": f"{score}%",
                        "height": "4px",
                        "background": f"linear-gradient(90deg, {color}, {color}88)",
                        "borderRadius": "2px",
                        "transition": "width 0.8s ease",
                    },
                ),
                style={
                    "width": "100%",
                    "height": "4px",
                    "background": COLORS["surface_hover"],
                    "borderRadius": "2px",
                },
            ),
        ],
    )


def _pick_card(pick: dict) -> html.Div:  # type: ignore[type-arg]
    """Render a single curated pick card."""
    change_color = COLORS["green"] if pick["change_positive"] else COLORS["red"]

    return html.Div(
        [
            # Header row — ticker + price
            html.Div(
                [
                    html.Div(
                        [
                            html.Span(pick["ticker"], style={
                                "fontSize": "20px",
                                "fontWeight": "700",
                                "color": COLORS["text_primary"],
                                "letterSpacing": "-0.3px",
                            }),
                            html.Span(pick["change"], style={
                                "fontSize": "13px",
                                "fontWeight": "600",
                                "fontFamily": MONO,
                                "color": change_color,
                                "marginLeft": "10px",
                            }),
                        ],
                        style={"display": "flex", "alignItems": "baseline"},
                    ),
                    html.Span(pick["price"], style={
                        "fontSize": "16px",
                        "fontWeight": "500",
                        "fontFamily": MONO,
                        "color": COLORS["text_primary"],
                    }),
                ],
                style={
                    "display": "flex",
                    "justifyContent": "space-between",
                    "alignItems": "baseline",
                },
            ),
            html.Div(pick["name"], style={
                "fontSize": "13px",
                "color": COLORS["text_tertiary"],
                "marginTop": "2px",
            }),

            # Divider
            html.Hr(style={
                "border": "none",
                "borderTop": f"1px solid {COLORS['border']}",
                "margin": "14px 0",
            }),

            # Why it fits
            html.Div(
                [
                    html.Div("Why this fits you", style={
                        "fontSize": "11px",
                        "fontWeight": "600",
                        "color": COLORS["text_tertiary"],
                        "textTransform": "uppercase",
                        "letterSpacing": "0.8px",
                        "marginBottom": "6px",
                    }),
                    html.P(pick["reason"], style={
                        "fontSize": "13px",
                        "lineHeight": "1.55",
                        "color": COLORS["text_secondary"],
                        "margin": "0",
                    }),
                ],
            ),

            # Signals row
            html.Div(
                [
                    _momentum_bar(pick["momentum"]),
                    html.Div(
                        [
                            html.Div(
                                [
                                    html.Span("Valuation", style={
                                        "fontSize": "11px",
                                        "color": COLORS["text_tertiary"],
                                        "marginRight": "8px",
                                    }),
                                    status_badge(pick["valuation"], pick["valuation_variant"]),
                                ],
                                style={"display": "flex", "alignItems": "center"},
                            ),
                            html.Div(
                                [
                                    html.Span("Sentiment", style={
                                        "fontSize": "11px",
                                        "color": COLORS["text_tertiary"],
                                        "marginRight": "8px",
                                    }),
                                    status_badge(pick["sentiment"], pick["sentiment_variant"]),
                                ],
                                style={
                                    "display": "flex",
                                    "alignItems": "center",
                                    "marginTop": "8px",
                                },
                            ),
                        ],
                        style={"marginTop": "12px"},
                    ),
                ],
                style={"marginTop": "14px"},
            ),

            # Tags
            html.Div(
                [
                    html.Span(tag, style={
                        "fontSize": "11px",
                        "color": COLORS["text_tertiary"],
                        "background": COLORS["surface_hover"],
                        "padding": "3px 10px",
                        "borderRadius": "100px",
                        "fontWeight": "500",
                    })
                    for tag in pick["tags"]
                ],
                style={
                    "display": "flex",
                    "gap": "6px",
                    "flexWrap": "wrap",
                    "marginTop": "14px",
                },
            ),

            # Action buttons
            html.Div(
                [
                    html.Button(
                        "Add to Portfolio",
                        id={"type": "watchlist-buy", "ticker": pick["ticker"], "name": pick["name"], "price": pick["price"]},
                        n_clicks=0,
                        style={
                            "flex": "1",
                            "padding": "10px",
                            "fontSize": "13px",
                            "fontWeight": "600",
                            "color": COLORS["text_primary"],
                            "background": COLORS["accent"],
                            "border": "none",
                            "borderRadius": "10px",
                            "cursor": "pointer",
                        },
                    ),
                    html.Button(
                        "Dismiss",
                        id={"type": "watchlist-dismiss", "ticker": pick["ticker"]},
                        n_clicks=0,
                        style={
                            "padding": "10px 20px",
                            "fontSize": "13px",
                            "fontWeight": "500",
                            "color": COLORS["text_tertiary"],
                            "background": COLORS["surface_hover"],
                            "border": f"1px solid {COLORS['border']}",
                            "borderRadius": "10px",
                            "cursor": "pointer",
                        },
                    ),
                ],
                style={
                    "display": "flex",
                    "gap": "10px",
                    "marginTop": "16px",
                },
            ),
        ],
        style={
            "background": COLORS["surface"],
            "border": f"1px solid {COLORS['border']}",
            "borderRadius": "16px",
            "padding": "24px",
            "transition": "border-color 0.2s ease, box-shadow 0.2s ease",
        },
    )


def watchlist_layout() -> html.Div:
    """Return the watchlist page layout."""
    return html.Div(
        [
            # Header with count
            html.Div(
                [
                    section_header(
                        "Watchlist",
                        f"{len(_PICKS)} AI-curated opportunities",
                    ),
                    html.Div(
                        [
                            html.Span("Strategy: ", style={
                                "fontSize": "12px",
                                "color": COLORS["text_tertiary"],
                            }),
                            status_badge("Growth", "green"),
                            html.Span(
                                " | Risk: ",
                                style={
                                    "fontSize": "12px",
                                    "color": COLORS["text_tertiary"],
                                    "marginLeft": "8px",
                                },
                            ),
                            status_badge("Medium", "orange"),
                        ],
                        style={
                            "display": "flex",
                            "alignItems": "center",
                            "marginBottom": "16px",
                        },
                    ),
                ],
            ),
            # Cards grid
            html.Div(
                [_pick_card(pick) for pick in _PICKS],
                style={
                    "display": "grid",
                    "gridTemplateColumns": "repeat(auto-fill, minmax(380px, 1fr))",
                    "gap": "20px",
                },
            ),
        ]
    )
