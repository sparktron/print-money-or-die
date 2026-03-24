"""Settings page — risk profile and preferences."""

from dash import html

from pmod.dashboard.components import COLORS, MONO, section_header


def _setting_row(label: str, description: str, current: str) -> html.Div:
    """Render a single settings row."""
    return html.Div(
        [
            html.Div(
                [
                    html.Div(label, style={
                        "fontSize": "15px",
                        "fontWeight": "600",
                        "color": COLORS["text_primary"],
                    }),
                    html.Div(description, style={
                        "fontSize": "13px",
                        "color": COLORS["text_tertiary"],
                        "marginTop": "2px",
                    }),
                ],
                style={"flex": "1"},
            ),
            html.Div(
                current,
                style={
                    "fontSize": "14px",
                    "fontWeight": "500",
                    "fontFamily": MONO,
                    "color": COLORS["accent"],
                    "background": COLORS["surface_hover"],
                    "padding": "8px 16px",
                    "borderRadius": "10px",
                    "border": f"1px solid {COLORS['border']}",
                },
            ),
        ],
        style={
            "display": "flex",
            "justifyContent": "space-between",
            "alignItems": "center",
            "padding": "18px 24px",
            "borderBottom": f"1px solid {COLORS['border']}",
        },
    )


def _connection_card(
    name: str,
    description: str,
    connected: bool,
) -> html.Div:
    """Render a service connection card."""
    dot_color = COLORS["green"] if connected else COLORS["text_tertiary"]
    status_text = "Connected" if connected else "Not configured"

    return html.Div(
        [
            html.Div(
                [
                    html.Div(name, style={
                        "fontSize": "15px",
                        "fontWeight": "600",
                        "color": COLORS["text_primary"],
                    }),
                    html.Div(description, style={
                        "fontSize": "13px",
                        "color": COLORS["text_tertiary"],
                        "marginTop": "2px",
                    }),
                ],
                style={"flex": "1"},
            ),
            html.Div(
                [
                    html.Span(style={
                        "width": "8px",
                        "height": "8px",
                        "borderRadius": "50%",
                        "background": dot_color,
                        "display": "inline-block",
                        "marginRight": "8px",
                    }),
                    html.Span(status_text, style={
                        "fontSize": "13px",
                        "color": COLORS["text_secondary"],
                    }),
                ],
                style={"display": "flex", "alignItems": "center"},
            ),
        ],
        style={
            "display": "flex",
            "justifyContent": "space-between",
            "alignItems": "center",
            "padding": "18px 24px",
            "borderBottom": f"1px solid {COLORS['border']}",
        },
    )


def settings_layout() -> html.Div:
    """Return the settings page layout."""
    return html.Div(
        [
            # Connections section
            section_header("Connections", "API integrations"),
            html.Div(
                [
                    _connection_card(
                        "Charles Schwab",
                        "Brokerage account for live trading and portfolio data",
                        connected=False,
                    ),
                    _connection_card(
                        "Polygon.io",
                        "Real-time and historical market data",
                        connected=False,
                    ),
                    _connection_card(
                        "Alpha Vantage",
                        "Fundamental data, earnings, and news",
                        connected=False,
                    ),
                ],
                style={
                    "background": COLORS["surface"],
                    "border": f"1px solid {COLORS['border']}",
                    "borderRadius": "16px",
                    "overflow": "hidden",
                    "marginBottom": "32px",
                },
            ),
            # Risk profile section
            section_header("Risk Profile", "controls portfolio optimization"),
            html.Div(
                [
                    _setting_row(
                        "Risk Tolerance",
                        "How much volatility you can stomach",
                        "Medium",
                    ),
                    _setting_row(
                        "Strategy",
                        "Primary investment approach",
                        "Growth",
                    ),
                    _setting_row(
                        "Max Position Size",
                        "Maximum allocation per ticker",
                        "5.0%",
                    ),
                ],
                style={
                    "background": COLORS["surface"],
                    "border": f"1px solid {COLORS['border']}",
                    "borderRadius": "16px",
                    "overflow": "hidden",
                    "marginBottom": "32px",
                },
            ),
            # Automation section
            section_header("Automation", "trading and rebalancing behavior"),
            html.Div(
                [
                    _setting_row(
                        "Rebalance Frequency",
                        "How often the optimizer runs",
                        "Manual",
                    ),
                    _setting_row(
                        "Trade Execution",
                        "Confirm before every trade or auto-execute",
                        "Manual Confirm",
                    ),
                ],
                style={
                    "background": COLORS["surface"],
                    "border": f"1px solid {COLORS['border']}",
                    "borderRadius": "16px",
                    "overflow": "hidden",
                    "marginBottom": "32px",
                },
            ),
            # Footer
            html.Div(
                [
                    html.Span(
                        "Settings are persisted locally — run ",
                        style={"fontSize": "12px", "color": COLORS["text_tertiary"]},
                    ),
                    html.Code(
                        "pmod auth login",
                        style={
                            "fontSize": "12px",
                            "color": COLORS["accent"],
                            "fontFamily": MONO,
                            "background": COLORS["surface_elevated"],
                            "padding": "2px 8px",
                            "borderRadius": "4px",
                        },
                    ),
                    html.Span(
                        " to connect Schwab",
                        style={"fontSize": "12px", "color": COLORS["text_tertiary"]},
                    ),
                ],
                style={"textAlign": "center", "marginTop": "8px"},
            ),
        ]
    )
