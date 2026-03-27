"""First-run onboarding wizard — collects user preferences in 5 steps."""
from __future__ import annotations

from dash import html

from pmod.dashboard.components import COLORS, FONT, MONO

# ── Constants ──────────────────────────────────────────────────────────────

TOTAL_STEPS = 5

RISK_OPTIONS = [
    {
        "value": "low",
        "label": "Conservative",
        "icon": "🛡️",
        "desc": "Capital preservation first. I'd rather miss a rally than watch my portfolio drop 20%.",
    },
    {
        "value": "medium",
        "label": "Moderate",
        "icon": "⚖️",
        "desc": "I can handle some dips for reasonable upside. Balanced growth over time.",
    },
    {
        "value": "high",
        "label": "Aggressive",
        "icon": "🚀",
        "desc": "I'm here for big returns and accept higher volatility. Short-term pain is fine.",
    },
    {
        "value": "degen",
        "label": "Full Degen",
        "icon": "💀",
        "desc": "Max risk, max potential. I live for the dopamine. YOLO is a strategy.",
    },
]

STRATEGY_OPTIONS = [
    {
        "value": "growth",
        "label": "Growth",
        "icon": "📈",
        "desc": "High-growth companies with strong revenue momentum. Tech, biotech, disruptors.",
    },
    {
        "value": "value",
        "label": "Value",
        "icon": "💎",
        "desc": "Undervalued companies trading below intrinsic worth. Buffett-style patience.",
    },
    {
        "value": "dividend",
        "label": "Dividend Income",
        "icon": "💰",
        "desc": "Steady cash flow through dividends. REITs, utilities, mature blue chips.",
    },
    {
        "value": "momentum",
        "label": "Momentum",
        "icon": "⚡",
        "desc": "Trade what's working right now. Buy strength, rotate away from weakness.",
    },
    {
        "value": "balanced",
        "label": "Balanced",
        "icon": "🎯",
        "desc": "Mix of growth and stability across investment styles. Diversified by default.",
    },
]

SECTOR_OPTIONS = [
    "Technology",
    "Healthcare",
    "Financials",
    "Energy",
    "Consumer Discretionary",
    "Consumer Staples",
    "Industrials",
    "Materials",
    "Utilities",
    "Real Estate",
    "Communication Services",
]

MAX_POS_OPTIONS = [2.0, 5.0, 10.0, 15.0, 20.0]

REBALANCE_OPTIONS = [
    {"value": "manual", "label": "Manual", "desc": "I'll trigger rebalancing myself."},
    {"value": "weekly", "label": "Weekly", "desc": "Automatically rebalance every Sunday."},
    {"value": "daily", "label": "Daily", "desc": "Rebalance every market day (active management)."},
]

EXECUTION_OPTIONS = [
    {
        "value": "manual-confirm",
        "label": "Manual Confirm",
        "icon": "👁️",
        "desc": "Review and approve every trade before it executes. Recommended for most users.",
    },
    {
        "value": "auto",
        "label": "Auto-Execute",
        "icon": "⚡",
        "desc": "Let the optimizer run automatically. Enable only after you trust the system's output.",
    },
]

# ── Shared style helpers ───────────────────────────────────────────────────


def _card_style(selected: bool) -> dict:
    return {
        "background": COLORS["surface_elevated"] if selected else COLORS["surface"],
        "border": f"2px solid {COLORS['accent']}" if selected else f"1px solid {COLORS['border_accent']}",
        "borderRadius": "14px",
        "padding": "18px 20px",
        "cursor": "pointer",
        "transition": "all 0.15s ease",
        "flex": "1",
        "minWidth": "200px",
    }


def _chip_style(selected: bool) -> dict:
    return {
        "background": COLORS["accent_glow"] if selected else COLORS["surface"],
        "border": f"1px solid {COLORS['accent']}" if selected else f"1px solid {COLORS['border_accent']}",
        "borderRadius": "100px",
        "padding": "8px 18px",
        "cursor": "pointer",
        "fontSize": "13px",
        "fontWeight": "500",
        "color": COLORS["accent"] if selected else COLORS["text_secondary"],
        "transition": "all 0.15s ease",
        "display": "inline-block",
    }


def _option_card(opts: dict, field: str, selected_value: str | None) -> html.Div:
    """Render a single radio-style option card."""
    selected = opts["value"] == selected_value
    return html.Div(
        [
            html.Div(
                [
                    html.Span(opts["icon"], style={"fontSize": "22px", "marginRight": "10px"}),
                    html.Span(
                        opts["label"],
                        style={
                            "fontSize": "15px",
                            "fontWeight": "600",
                            "color": COLORS["accent"] if selected else COLORS["text_primary"],
                        },
                    ),
                ],
                style={"display": "flex", "alignItems": "center", "marginBottom": "8px"},
            ),
            html.Div(
                opts["desc"],
                style={
                    "fontSize": "13px",
                    "color": COLORS["text_secondary"],
                    "lineHeight": "1.5",
                },
            ),
        ],
        id={"type": "wizard-opt", "field": field, "val": opts["value"]},
        n_clicks=0,
        style=_card_style(selected),
    )


# ── Step renderers ─────────────────────────────────────────────────────────


def _step_risk(state: dict) -> html.Div:
    return html.Div(
        [
            html.Div("How do you handle market volatility?", style=_question_style()),
            html.Div(
                "This shapes how aggressively the optimizer pursues returns versus safety.",
                style=_sub_style(),
            ),
            html.Div(
                [_option_card(o, "risk", state.get("risk")) for o in RISK_OPTIONS],
                style={"display": "flex", "gap": "12px", "flexWrap": "wrap"},
            ),
        ]
    )


def _step_strategy(state: dict) -> html.Div:
    return html.Div(
        [
            html.Div("What's your primary investment philosophy?", style=_question_style()),
            html.Div(
                "The screener and optimizer weight signals differently based on your style.",
                style=_sub_style(),
            ),
            html.Div(
                [_option_card(o, "strategy", state.get("strategy")) for o in STRATEGY_OPTIONS],
                style={"display": "flex", "gap": "12px", "flexWrap": "wrap"},
            ),
        ]
    )


def _step_sectors(state: dict) -> html.Div:
    selected = set(state.get("sectors", []))
    chips = [
        html.Div(
            sector,
            id={"type": "wizard-sector", "val": sector},
            n_clicks=0,
            style=_chip_style(sector in selected),
        )
        for sector in SECTOR_OPTIONS
    ]
    return html.Div(
        [
            html.Div("Which sectors should the system prioritize?", style=_question_style()),
            html.Div(
                "Select any that interest you. Leave blank to cover all sectors equally.",
                style=_sub_style(),
            ),
            html.Div(chips, style={"display": "flex", "flexWrap": "wrap", "gap": "10px"}),
        ]
    )


def _step_sizing(state: dict) -> html.Div:
    cur_pos = state.get("max_pos", 5.0)
    cur_reb = state.get("rebalance", "manual")

    pos_buttons = [
        html.Div(
            f"{int(v)}%",
            id={"type": "wizard-maxpos", "val": v},
            n_clicks=0,
            style={
                "background": COLORS["accent_glow"] if v == cur_pos else COLORS["surface"],
                "border": f"1px solid {COLORS['accent']}" if v == cur_pos else f"1px solid {COLORS['border_accent']}",
                "borderRadius": "10px",
                "padding": "12px 20px",
                "cursor": "pointer",
                "fontSize": "16px",
                "fontWeight": "600",
                "color": COLORS["accent"] if v == cur_pos else COLORS["text_primary"],
                "fontFamily": MONO,
                "minWidth": "64px",
                "textAlign": "center",
            },
        )
        for v in MAX_POS_OPTIONS
    ]

    reb_cards = [
        html.Div(
            [
                html.Div(o["label"], style={
                    "fontSize": "14px", "fontWeight": "600",
                    "color": COLORS["accent"] if o["value"] == cur_reb else COLORS["text_primary"],
                }),
                html.Div(o["desc"], style={"fontSize": "12px", "color": COLORS["text_secondary"], "marginTop": "4px"}),
            ],
            id={"type": "wizard-opt", "field": "rebalance", "val": o["value"]},
            n_clicks=0,
            style={**_card_style(o["value"] == cur_reb), "minWidth": "160px"},
        )
        for o in REBALANCE_OPTIONS
    ]

    return html.Div(
        [
            html.Div("Position sizing & rebalancing", style=_question_style()),
            html.Div("Max allocation per ticker:", style=_sub_style()),
            html.Div(pos_buttons, style={"display": "flex", "gap": "10px", "marginBottom": "32px"}),
            html.Div("How often should the portfolio rebalance?", style=_sub_style()),
            html.Div(reb_cards, style={"display": "flex", "gap": "12px", "flexWrap": "wrap"}),
        ]
    )


def _step_execution(state: dict) -> html.Div:
    cur_exec = state.get("execution", "manual-confirm")
    labels = {
        "low": "Conservative", "medium": "Moderate", "high": "Aggressive", "degen": "Full Degen",
    }
    strat_labels = {
        "growth": "Growth", "value": "Value", "dividend": "Dividend Income",
        "momentum": "Momentum", "balanced": "Balanced",
    }
    rebal_labels = {"manual": "Manual", "weekly": "Weekly", "daily": "Daily"}

    sectors = state.get("sectors", [])
    sector_str = ", ".join(sectors) if sectors else "All sectors"

    summary_rows = [
        ("Risk Tolerance", labels.get(state.get("risk", ""), "—")),
        ("Strategy", strat_labels.get(state.get("strategy", ""), "—")),
        ("Sector Focus", sector_str),
        ("Max Position", f"{state.get('max_pos', 5.0):.0f}%"),
        ("Rebalance", rebal_labels.get(state.get("rebalance", ""), "—")),
    ]

    return html.Div(
        [
            html.Div("How should trades be executed?", style=_question_style()),
            html.Div(
                [_option_card(o, "execution", cur_exec) for o in EXECUTION_OPTIONS],
                style={"display": "flex", "gap": "12px", "flexWrap": "wrap", "marginBottom": "32px"},
            ),
            html.Div("Your configuration summary", style={
                "fontSize": "13px", "fontWeight": "600",
                "color": COLORS["text_tertiary"],
                "textTransform": "uppercase",
                "letterSpacing": "0.8px",
                "marginBottom": "12px",
            }),
            html.Div(
                [
                    html.Div(
                        [
                            html.Span(label, style={"color": COLORS["text_tertiary"], "fontSize": "13px"}),
                            html.Span(value, style={
                                "color": COLORS["text_primary"],
                                "fontSize": "13px",
                                "fontWeight": "600",
                                "fontFamily": MONO,
                            }),
                        ],
                        style={
                            "display": "flex",
                            "justifyContent": "space-between",
                            "padding": "10px 0",
                            "borderBottom": f"1px solid {COLORS['border']}",
                        },
                    )
                    for label, value in summary_rows
                ],
                style={
                    "background": COLORS["surface_elevated"],
                    "border": f"1px solid {COLORS['border']}",
                    "borderRadius": "12px",
                    "padding": "4px 18px",
                },
            ),
        ]
    )


# ── Progress indicator ─────────────────────────────────────────────────────


def _progress_bar(step: int) -> html.Div:
    circles = []
    for i in range(1, TOTAL_STEPS + 1):
        if i < step:
            color, bg, text_color = COLORS["accent"], COLORS["accent"], "#fff"
            label = "✓"
        elif i == step:
            color, bg, text_color = COLORS["accent"], COLORS["accent_glow"], COLORS["accent"]
            label = str(i)
        else:
            color, bg, text_color = COLORS["border_accent"], "transparent", COLORS["text_tertiary"]
            label = str(i)

        circles.append(html.Div(
            [
                html.Div(
                    label,
                    style={
                        "width": "28px",
                        "height": "28px",
                        "borderRadius": "50%",
                        "background": bg,
                        "border": f"2px solid {color}",
                        "display": "flex",
                        "alignItems": "center",
                        "justifyContent": "center",
                        "fontSize": "11px",
                        "fontWeight": "700",
                        "color": text_color,
                    },
                ),
                html.Div(
                    _STEP_LABELS[i - 1],
                    style={"fontSize": "11px", "color": COLORS["text_tertiary"], "marginTop": "4px"},
                ),
            ],
            style={"display": "flex", "flexDirection": "column", "alignItems": "center"},
        ))

        if i < TOTAL_STEPS:
            circles.append(html.Div(
                style={
                    "flex": "1",
                    "height": "2px",
                    "background": COLORS["accent"] if i < step else COLORS["border"],
                    "marginBottom": "18px",
                }
            ))

    return html.Div(
        circles,
        style={"display": "flex", "alignItems": "center", "marginBottom": "40px"},
    )


_STEP_LABELS = ["Risk", "Strategy", "Sectors", "Sizing", "Execute"]


def _question_style() -> dict:
    return {
        "fontSize": "22px",
        "fontWeight": "600",
        "color": COLORS["text_primary"],
        "marginBottom": "8px",
        "letterSpacing": "-0.3px",
    }


def _sub_style() -> dict:
    return {
        "fontSize": "14px",
        "color": COLORS["text_tertiary"],
        "marginBottom": "24px",
    }


# ── Navigation buttons ─────────────────────────────────────────────────────


def _nav_buttons(step: int, can_advance: bool) -> html.Div:
    back_btn = html.Div(
        "← Back",
        id="wizard-back",
        n_clicks=0,
        style={
            "padding": "12px 28px",
            "borderRadius": "10px",
            "background": "transparent",
            "border": f"1px solid {COLORS['border_accent']}",
            "color": COLORS["text_secondary"],
            "fontSize": "14px",
            "fontWeight": "500",
            "cursor": "pointer",
        },
    ) if step > 1 else html.Div()

    if step < TOTAL_STEPS:
        next_label = "Next →"
        next_id = "wizard-next"
    else:
        next_label = "Complete Setup ✓"
        next_id = "wizard-complete"

    next_btn = html.Div(
        next_label,
        id=next_id,
        n_clicks=0,
        style={
            "padding": "12px 28px",
            "borderRadius": "10px",
            "background": COLORS["accent"] if can_advance else COLORS["surface_elevated"],
            "border": "none",
            "color": "#fff" if can_advance else COLORS["text_tertiary"],
            "fontSize": "14px",
            "fontWeight": "600",
            "cursor": "pointer" if can_advance else "not-allowed",
        },
    )

    return html.Div(
        [back_btn, next_btn],
        style={
            "display": "flex",
            "justifyContent": "space-between",
            "alignItems": "center",
            "marginTop": "36px",
        },
    )


# ── Public layout function ─────────────────────────────────────────────────

_STEP_RENDERERS = [_step_risk, _step_strategy, _step_sectors, _step_sizing, _step_execution]

_CAN_ADVANCE_KEYS = ["risk", "strategy", None, "max_pos", "execution"]


def _can_advance(step: int, state: dict) -> bool:
    """Return True if the user has made the required selection for the current step."""
    key = _CAN_ADVANCE_KEYS[step - 1]
    if key is None:
        return True  # sectors are optional
    return bool(state.get(key))


def wizard_step_layout(state: dict) -> html.Div:
    """Render the content area for the current wizard step."""
    step = state.get("step", 1)
    renderer = _STEP_RENDERERS[step - 1]
    return html.Div(
        [
            _progress_bar(step),
            renderer(state),
            _nav_buttons(step, _can_advance(step, state)),
        ]
    )


def setup_layout() -> html.Div:
    """Full-page onboarding wizard shell."""
    return html.Div(
        [
            # Header
            html.Div(
                [
                    html.Span("PMOD", style={
                        "fontSize": "18px", "fontWeight": "700",
                        "color": COLORS["text_primary"], "letterSpacing": "1.5px",
                    }),
                    html.Span("Setup", style={
                        "fontSize": "12px", "color": COLORS["text_tertiary"],
                        "marginLeft": "12px", "letterSpacing": "0.5px",
                    }),
                ],
                style={
                    "display": "flex",
                    "alignItems": "baseline",
                    "padding": "20px 32px",
                    "borderBottom": f"1px solid {COLORS['border']}",
                    "background": COLORS["surface"],
                },
            ),
            # Wizard body
            html.Div(
                [
                    html.Div(
                        "Let's configure your trading profile",
                        style={
                            "fontSize": "13px",
                            "color": COLORS["text_tertiary"],
                            "textAlign": "center",
                            "marginBottom": "36px",
                            "letterSpacing": "0.3px",
                        },
                    ),
                    html.Div(id="wizard-content"),
                ],
                style={
                    "maxWidth": "760px",
                    "margin": "0 auto",
                    "padding": "48px 32px 80px",
                    "fontFamily": FONT,
                },
            ),
        ],
        style={"minHeight": "100vh", "background": COLORS["bg"]},
    )
