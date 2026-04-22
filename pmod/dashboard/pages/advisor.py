"""AI Advisor page — ask Claude a question, get portfolio-aware analysis."""
from __future__ import annotations

from dash import dcc, html

from pmod.dashboard.components import COLORS, FONT, MONO, section_header, status_badge

_SUGGESTED_QUESTIONS = [
    "Should I rebalance given current market conditions?",
    "What are the biggest risks in my current portfolio?",
    "Are there any sectors I'm overexposed to?",
    "Given my risk tolerance, what would you add or remove?",
    "How does my portfolio compare to a typical growth strategy?",
]


def _suggestion_chip(text: str) -> html.Button:
    return html.Button(
        text,
        id={"type": "advisor-suggestion", "text": text},
        n_clicks=0,
        style={
            "padding": "7px 14px",
            "fontSize": "12px",
            "fontWeight": "500",
            "color": COLORS["text_secondary"],
            "background": COLORS["surface_hover"],
            "border": f"1px solid {COLORS['border_accent']}",
            "borderRadius": "100px",
            "cursor": "pointer",
            "transition": "all 0.15s ease",
            "textAlign": "left",
            "whiteSpace": "nowrap",
        },
    )


def advisor_layout() -> html.Div:
    """Return the AI Advisor page layout (static shell; callbacks populate content)."""
    textarea_style = {
        "width": "100%",
        "minHeight": "100px",
        "padding": "14px 16px",
        "background": COLORS["surface_hover"],
        "border": f"1px solid {COLORS['border_accent']}",
        "borderRadius": "12px",
        "color": COLORS["text_primary"],
        "fontSize": "14px",
        "fontFamily": FONT,
        "lineHeight": "1.6",
        "resize": "vertical",
        "outline": "none",
        "boxSizing": "border-box",
    }

    return html.Div(
        [
            # Header
            section_header("AI Advisor", "Ask Claude anything about your portfolio"),

            # Suggested questions
            html.Div(
                [
                    html.Div(
                        "Suggested questions",
                        style={
                            "fontSize": "11px",
                            "fontWeight": "600",
                            "color": COLORS["text_tertiary"],
                            "textTransform": "uppercase",
                            "letterSpacing": "0.8px",
                            "marginBottom": "10px",
                        },
                    ),
                    html.Div(
                        [_suggestion_chip(q) for q in _SUGGESTED_QUESTIONS],
                        style={
                            "display": "flex",
                            "flexWrap": "wrap",
                            "gap": "8px",
                        },
                    ),
                ],
                style={"marginBottom": "20px"},
            ),

            # Input card
            html.Div(
                [
                    dcc.Textarea(
                        id="advisor-question-input",
                        placeholder="Ask a question about your portfolio, risk, strategy, or specific tickers…",
                        style=textarea_style,
                    ),
                    html.Div(
                        [
                            html.Div(id="advisor-char-count", style={
                                "fontSize": "12px",
                                "color": COLORS["text_tertiary"],
                            }),
                            html.Button(
                                [
                                    html.Span("Ask Claude", id="advisor-btn-label"),
                                ],
                                id="advisor-submit-btn",
                                n_clicks=0,
                                style={
                                    "padding": "11px 28px",
                                    "fontSize": "14px",
                                    "fontWeight": "700",
                                    "color": COLORS["text_primary"],
                                    "background": COLORS["accent"],
                                    "border": "none",
                                    "borderRadius": "10px",
                                    "cursor": "pointer",
                                },
                            ),
                        ],
                        style={
                            "display": "flex",
                            "justifyContent": "space-between",
                            "alignItems": "center",
                            "marginTop": "12px",
                        },
                    ),
                ],
                style={
                    "background": COLORS["surface"],
                    "border": f"1px solid {COLORS['border']}",
                    "borderRadius": "16px",
                    "padding": "20px",
                    "marginBottom": "24px",
                },
            ),

            # Response area (populated by callback)
            dcc.Loading(
                id="advisor-loading",
                type="dot",
                color=COLORS["accent"],
                children=html.Div(id="advisor-response-area"),
            ),

            # Actions panel (populated by callback after response)
            html.Div(id="advisor-actions-panel"),

            # Hidden store to pass actions between callbacks
            dcc.Store(id="advisor-actions-store", data={}),
        ]
    )


# ── Response rendering helpers (called by app.py callback) ──────────────────

def render_response(text: str) -> html.Div:
    """Render Claude's response text using dcc.Markdown for full CommonMark support."""
    return html.Div(
        [
            html.Div(
                [
                    html.Span("Claude", style={
                        "fontSize": "11px",
                        "fontWeight": "700",
                        "color": COLORS["accent"],
                        "textTransform": "uppercase",
                        "letterSpacing": "1px",
                        "marginRight": "8px",
                    }),
                    html.Span("claude CLI", style={
                        "fontSize": "11px",
                        "color": COLORS["text_tertiary"],
                        "fontFamily": MONO,
                    }),
                ],
                style={"marginBottom": "16px", "display": "flex", "alignItems": "center"},
            ),
            dcc.Markdown(
                text,
                style={
                    "fontSize": "14px",
                    "lineHeight": "1.7",
                    "color": COLORS["text_secondary"],
                },
            ),
        ],
        style={
            "background": COLORS["surface"],
            "border": f"1px solid {COLORS['border']}",
            "borderRadius": "16px",
            "padding": "24px",
            "marginBottom": "20px",
        },
    )


def render_actions(actions: dict) -> html.Div | None:
    """Render clickable action buttons derived from Claude's structured recommendations."""
    watchlist = actions.get("add_to_watchlist") or []
    risk = actions.get("risk_tolerance")
    strategy = actions.get("strategy")

    if not watchlist and not risk and not strategy:
        return None

    items: list = []

    if watchlist:
        items.append(html.Div(
            "Watchlist suggestions",
            style={
                "fontSize": "11px",
                "fontWeight": "700",
                "color": COLORS["text_tertiary"],
                "textTransform": "uppercase",
                "letterSpacing": "0.8px",
                "marginBottom": "12px",
            },
        ))
        for suggestion in watchlist:
            ticker = suggestion.get("ticker", "")
            reason = suggestion.get("reason", "")
            items.append(html.Div(
                [
                    html.Div(
                        [
                            html.Span(ticker, style={
                                "fontWeight": "700",
                                "fontSize": "15px",
                                "color": COLORS["text_primary"],
                                "marginRight": "12px",
                            }),
                            html.Span(reason, style={
                                "fontSize": "13px",
                                "color": COLORS["text_secondary"],
                            }),
                        ],
                        style={"flex": "1"},
                    ),
                    html.Button(
                        "+ Watchlist",
                        id={"type": "advisor-add-watchlist", "ticker": ticker, "reason": reason[:200]},
                        n_clicks=0,
                        style={
                            "padding": "7px 16px",
                            "fontSize": "12px",
                            "fontWeight": "600",
                            "color": COLORS["text_primary"],
                            "background": COLORS["accent"],
                            "border": "none",
                            "borderRadius": "8px",
                            "cursor": "pointer",
                            "whiteSpace": "nowrap",
                        },
                    ),
                ],
                style={
                    "display": "flex",
                    "alignItems": "center",
                    "justifyContent": "space-between",
                    "padding": "10px 0",
                    "borderBottom": f"1px solid {COLORS['border']}",
                },
            ))

    if risk or strategy:
        items.append(html.Div(
            "Strategy recommendations",
            style={
                "fontSize": "11px",
                "fontWeight": "700",
                "color": COLORS["text_tertiary"],
                "textTransform": "uppercase",
                "letterSpacing": "0.8px",
                "marginTop": "18px" if watchlist else "0",
                "marginBottom": "12px",
            },
        ))
        if risk:
            items.append(html.Div(
                [
                    html.Span(f"Change risk tolerance to ", style={"fontSize": "13px", "color": COLORS["text_secondary"]}),
                    status_badge(risk, "orange" if risk in ("high", "degen") else "green"),
                    html.Button(
                        "Apply",
                        id={"type": "advisor-apply-risk", "value": risk},
                        n_clicks=0,
                        style={
                            "marginLeft": "16px",
                            "padding": "7px 16px",
                            "fontSize": "12px",
                            "fontWeight": "600",
                            "color": COLORS["text_primary"],
                            "background": COLORS["surface_hover"],
                            "border": f"1px solid {COLORS['border_accent']}",
                            "borderRadius": "8px",
                            "cursor": "pointer",
                        },
                    ),
                ],
                style={
                    "display": "flex",
                    "alignItems": "center",
                    "padding": "10px 0",
                    "borderBottom": f"1px solid {COLORS['border']}",
                },
            ))
        if strategy:
            items.append(html.Div(
                [
                    html.Span(f"Switch strategy to ", style={"fontSize": "13px", "color": COLORS["text_secondary"]}),
                    status_badge(strategy, "green"),
                    html.Button(
                        "Apply",
                        id={"type": "advisor-apply-strategy", "value": strategy},
                        n_clicks=0,
                        style={
                            "marginLeft": "16px",
                            "padding": "7px 16px",
                            "fontSize": "12px",
                            "fontWeight": "600",
                            "color": COLORS["text_primary"],
                            "background": COLORS["surface_hover"],
                            "border": f"1px solid {COLORS['border_accent']}",
                            "borderRadius": "8px",
                            "cursor": "pointer",
                        },
                    ),
                ],
                style={
                    "display": "flex",
                    "alignItems": "center",
                    "padding": "10px 0",
                },
            ))

    return html.Div(
        [
            html.Div(
                "Suggested actions",
                style={
                    "fontSize": "13px",
                    "fontWeight": "700",
                    "color": COLORS["text_primary"],
                    "marginBottom": "16px",
                },
            ),
            *items,
        ],
        style={
            "background": COLORS["surface"],
            "border": f"1px solid {COLORS['border']}",
            "borderRadius": "16px",
            "padding": "20px 24px",
        },
    )
