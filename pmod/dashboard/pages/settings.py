"""Settings page — interactive risk profile and preferences editor."""
from __future__ import annotations

import json

from dash import dcc, html

from pmod.dashboard.components import COLORS, FONT, MONO, section_header, status_badge
from pmod.preferences.profile import load_preferences_dict


def _connection_statuses() -> dict:
    """Return live connection status for each integration."""
    from pmod.auth.schwab import auth_status
    from pmod.config import get_settings

    settings = get_settings()
    schwab = auth_status()

    polygon_ok = bool(settings.polygon_api_key)
    av_ok = bool(settings.alpha_vantage_api_key)

    return {
        "schwab": schwab,
        "polygon": {
            "connected": polygon_ok,
            "reason": "API key configured" if polygon_ok else "Set POLYGON_API_KEY in .env",
        },
        "alpha_vantage": {
            "connected": av_ok,
            "reason": "API key configured" if av_ok else "Set ALPHA_VANTAGE_API_KEY in .env",
        },
    }

# ── Human-readable label maps ──────────────────────────────────────────────

_RISK_LABELS = {
    "low": "Conservative",
    "medium": "Moderate",
    "high": "Aggressive",
    "degen": "Full Degen",
}
_STRATEGY_LABELS = {
    "growth": "Growth",
    "value": "Value",
    "dividend": "Dividend Income",
    "momentum": "Momentum",
    "balanced": "Balanced",
}
_REBALANCE_LABELS = {"manual": "Manual", "weekly": "Weekly", "daily": "Daily"}
_EXECUTION_LABELS = {"manual-confirm": "Manual Confirm", "auto": "Auto-Execute"}

_RISK_VARIANT = {"low": "green", "medium": "orange", "high": "red", "degen": "red"}
_EXEC_VARIANT = {"manual-confirm": "green", "auto": "orange"}


# ── Layout helpers ─────────────────────────────────────────────────────────


def _connection_card(name: str, description: str, connected: bool, reason: str = "") -> html.Div:
    dot_color = COLORS["green"] if connected else COLORS["red"]
    status_text = reason if reason else ("Connected" if connected else "Not configured")
    status_color = COLORS["green"] if connected else COLORS["text_secondary"]
    return html.Div(
        [
            html.Div(
                [
                    html.Div(name, style={
                        "fontSize": "15px", "fontWeight": "600", "color": COLORS["text_primary"],
                    }),
                    html.Div(description, style={
                        "fontSize": "13px", "color": COLORS["text_tertiary"], "marginTop": "2px",
                    }),
                ],
                style={"flex": "1"},
            ),
            html.Div(
                [
                    html.Span(style={
                        "width": "8px", "height": "8px", "borderRadius": "50%",
                        "background": dot_color, "display": "inline-block",
                        "marginRight": "8px", "flexShrink": "0",
                        # Pulse animation on connected
                        "boxShadow": f"0 0 0 2px {COLORS['green_bg']}" if connected else "none",
                    }),
                    html.Span(status_text, style={"fontSize": "13px", "color": status_color}),
                ],
                style={"display": "flex", "alignItems": "center"},
            ),
        ],
        style={
            "display": "flex", "justifyContent": "space-between", "alignItems": "center",
            "padding": "18px 24px", "borderBottom": f"1px solid {COLORS['border']}",
        },
    )


def _current_value_badge(text: str, variant: str = "neutral") -> html.Div:
    """Prominent pill showing the active setting value."""
    color_map = {
        "green": COLORS["green"],
        "red": COLORS["red"],
        "orange": COLORS["orange"],
        "neutral": COLORS["accent"],
    }
    color = color_map.get(variant, COLORS["accent"])
    return html.Div(
        text,
        style={
            "fontSize": "13px",
            "fontWeight": "700",
            "color": color,
            "background": f"rgba({_hex_to_rgb(color)}, 0.12)",
            "border": f"1px solid rgba({_hex_to_rgb(color)}, 0.30)",
            "borderRadius": "100px",
            "padding": "4px 14px",
            "letterSpacing": "0.2px",
            "whiteSpace": "nowrap",
        },
    )


def _hex_to_rgb(hex_color: str) -> str:
    """Convert #rrggbb to 'r, g, b' string for rgba() CSS."""
    h = hex_color.lstrip("#")
    r, g, b = int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
    return f"{r}, {g}, {b}"


def _setting_row(
    label: str,
    description: str,
    current_text: str,
    current_variant: str,
    control: html.Div,
    last: bool = False,
) -> html.Div:
    """One settings row: label/description | current value badge | dropdown."""
    return html.Div(
        [
            # Left — label + description
            html.Div(
                [
                    html.Div(label, style={
                        "fontSize": "15px", "fontWeight": "600", "color": COLORS["text_primary"],
                    }),
                    html.Div(description, style={
                        "fontSize": "13px", "color": COLORS["text_tertiary"], "marginTop": "2px",
                    }),
                ],
                style={"flex": "1", "minWidth": "0"},
            ),
            # Middle — current value (always visible)
            html.Div(
                _current_value_badge(current_text, current_variant),
                style={"display": "flex", "alignItems": "center", "margin": "0 24px"},
            ),
            # Right — dropdown to change
            html.Div(control, style={"width": "200px", "flexShrink": "0"}),
        ],
        style={
            "display": "flex",
            "justifyContent": "space-between",
            "alignItems": "center",
            "padding": "18px 24px",
            **({"borderBottom": f"1px solid {COLORS['border']}"} if not last else {}),
        },
    )


_DD = {
    "backgroundColor": COLORS["surface_elevated"],
    "color": COLORS["text_primary"],
    "border": f"1px solid {COLORS['border_accent']}",
    "borderRadius": "10px",
    "fontFamily": FONT,
    "fontSize": "14px",
}


def settings_layout() -> html.Div:
    """Return the settings page layout with current values loaded from DB."""
    prefs = load_preferences_dict()
    sectors = json.loads(prefs.get("sector_focus", "[]"))
    max_pos = prefs["max_position_pct"]
    max_pos_label = f"{int(max_pos)}%" if max_pos == int(max_pos) else f"{max_pos}%"
    conn = _connection_statuses()

    return html.Div(
        [
            # ── Connections ───────────────────────────────────────────────
            section_header("Connections", "API integrations"),
            html.Div(
                [
                    _connection_card(
                        "Charles Schwab",
                        "Brokerage account for live trading and portfolio data",
                        conn["schwab"]["connected"],
                        conn["schwab"]["reason"],
                    ),
                    _connection_card(
                        "Polygon.io",
                        "Real-time and historical market data",
                        conn["polygon"]["connected"],
                        conn["polygon"]["reason"],
                    ),
                    _connection_card(
                        "Alpha Vantage",
                        "Fundamental data, earnings, and news",
                        conn["alpha_vantage"]["connected"],
                        conn["alpha_vantage"]["reason"],
                    ),
                ],
                style={
                    "background": COLORS["surface"], "border": f"1px solid {COLORS['border']}",
                    "borderRadius": "16px", "overflow": "hidden", "marginBottom": "32px",
                },
            ),

            # ── Risk Profile ──────────────────────────────────────────────
            section_header("Risk Profile", "controls portfolio optimization"),
            html.Div(
                [
                    _setting_row(
                        "Risk Tolerance", "How much volatility you can stomach",
                        _RISK_LABELS.get(prefs["risk_tolerance"], prefs["risk_tolerance"]),
                        _RISK_VARIANT.get(prefs["risk_tolerance"], "neutral"),
                        dcc.Dropdown(
                            id="settings-risk",
                            options=[
                                {"label": "Conservative", "value": "low"},
                                {"label": "Moderate", "value": "medium"},
                                {"label": "Aggressive", "value": "high"},
                                {"label": "Full Degen", "value": "degen"},
                            ],
                            value=prefs["risk_tolerance"],
                            clearable=False,
                            style=_DD,
                        ),
                    ),
                    _setting_row(
                        "Strategy", "Primary investment approach",
                        _STRATEGY_LABELS.get(prefs["strategy"], prefs["strategy"]),
                        "neutral",
                        dcc.Dropdown(
                            id="settings-strategy",
                            options=[
                                {"label": "Growth", "value": "growth"},
                                {"label": "Value", "value": "value"},
                                {"label": "Dividend Income", "value": "dividend"},
                                {"label": "Momentum", "value": "momentum"},
                                {"label": "Balanced", "value": "balanced"},
                            ],
                            value=prefs["strategy"],
                            clearable=False,
                            style=_DD,
                        ),
                    ),
                    _setting_row(
                        "Max Position Size", "Maximum allocation per ticker",
                        max_pos_label,
                        "neutral",
                        dcc.Dropdown(
                            id="settings-maxpos",
                            options=[
                                {"label": "2%", "value": 2.0},
                                {"label": "5%", "value": 5.0},
                                {"label": "10%", "value": 10.0},
                                {"label": "15%", "value": 15.0},
                                {"label": "20%", "value": 20.0},
                            ],
                            value=prefs["max_position_pct"],
                            clearable=False,
                            style=_DD,
                        ),
                        last=True,
                    ),
                ],
                style={
                    "background": COLORS["surface"], "border": f"1px solid {COLORS['border']}",
                    "borderRadius": "16px", "overflow": "hidden", "marginBottom": "32px",
                },
            ),

            # ── Automation ────────────────────────────────────────────────
            section_header("Automation", "trading and rebalancing behavior"),
            html.Div(
                [
                    _setting_row(
                        "Rebalance Frequency", "How often the optimizer runs",
                        _REBALANCE_LABELS.get(prefs["rebalance_frequency"], prefs["rebalance_frequency"]),
                        "neutral",
                        dcc.Dropdown(
                            id="settings-rebalance",
                            options=[
                                {"label": "Manual", "value": "manual"},
                                {"label": "Weekly", "value": "weekly"},
                                {"label": "Daily", "value": "daily"},
                            ],
                            value=prefs["rebalance_frequency"],
                            clearable=False,
                            style=_DD,
                        ),
                    ),
                    _setting_row(
                        "Trade Execution", "Confirm before every trade or auto-execute",
                        _EXECUTION_LABELS.get(prefs["trade_execution"], prefs["trade_execution"]),
                        _EXEC_VARIANT.get(prefs["trade_execution"], "neutral"),
                        dcc.Dropdown(
                            id="settings-execution",
                            options=[
                                {"label": "Manual Confirm", "value": "manual-confirm"},
                                {"label": "Auto-Execute", "value": "auto"},
                            ],
                            value=prefs["trade_execution"],
                            clearable=False,
                            style=_DD,
                        ),
                        last=True,
                    ),
                ],
                style={
                    "background": COLORS["surface"], "border": f"1px solid {COLORS['border']}",
                    "borderRadius": "16px", "overflow": "hidden", "marginBottom": "32px",
                },
            ),

            # ── Sector Focus ──────────────────────────────────────────────
            section_header("Sector Focus", "guide the screener toward preferred sectors"),
            html.Div(
                [
                    # Active sectors summary strip
                    html.Div(
                        [
                            html.Span("Active: ", style={
                                "fontSize": "13px", "color": COLORS["text_tertiary"],
                                "marginRight": "8px", "fontWeight": "500",
                            }),
                            html.Span(
                                ", ".join(sectors) if sectors else "All sectors (no filter)",
                                style={
                                    "fontSize": "13px", "fontWeight": "600",
                                    "color": COLORS["accent"] if sectors else COLORS["text_secondary"],
                                },
                            ),
                        ],
                        style={
                            "padding": "14px 24px",
                            "borderBottom": f"1px solid {COLORS['border']}",
                            "background": COLORS["surface_elevated"],
                        },
                    ),
                    html.Div(
                        dcc.Checklist(
                            id="settings-sectors",
                            options=[{"label": f"  {s}", "value": s} for s in [
                                "Technology", "Healthcare", "Financials", "Energy",
                                "Consumer Discretionary", "Consumer Staples", "Industrials",
                                "Materials", "Utilities", "Real Estate", "Communication Services",
                            ]],
                            value=sectors,
                            inline=True,
                            inputStyle={"marginRight": "6px", "accentColor": COLORS["accent"]},
                            labelStyle={
                                "fontSize": "13px",
                                "color": COLORS["text_secondary"],
                                "marginRight": "16px",
                                "marginBottom": "10px",
                            },
                        ),
                        style={"padding": "20px 24px"},
                    ),
                ],
                style={
                    "background": COLORS["surface"], "border": f"1px solid {COLORS['border']}",
                    "borderRadius": "16px", "overflow": "hidden", "marginBottom": "32px",
                },
            ),

            # ── Save ──────────────────────────────────────────────────────
            html.Div(
                [
                    html.Div(
                        "Save Settings",
                        id="settings-save-btn",
                        n_clicks=0,
                        style={
                            "padding": "12px 32px", "borderRadius": "10px",
                            "background": COLORS["accent"], "color": "#fff",
                            "fontSize": "14px", "fontWeight": "600",
                            "cursor": "pointer", "display": "inline-block",
                        },
                    ),
                    html.Div(
                        id="settings-saved-msg",
                        style={"fontSize": "13px", "color": COLORS["green"], "marginLeft": "16px"},
                    ),
                ],
                style={"display": "flex", "alignItems": "center", "marginBottom": "8px"},
            ),

            # ── Footer ────────────────────────────────────────────────────
            html.Div(
                [
                    html.Span("Re-run the onboarding wizard: ", style={"fontSize": "12px", "color": COLORS["text_tertiary"]}),
                    html.Code("pmod setup", style={
                        "fontSize": "12px", "color": COLORS["accent"],
                        "fontFamily": MONO, "background": COLORS["surface_elevated"],
                        "padding": "2px 8px", "borderRadius": "4px",
                    }),
                    html.Span("  ·  Connect Schwab: ", style={"fontSize": "12px", "color": COLORS["text_tertiary"]}),
                    html.Code("pmod auth login", style={
                        "fontSize": "12px", "color": COLORS["accent"],
                        "fontFamily": MONO, "background": COLORS["surface_elevated"],
                        "padding": "2px 8px", "borderRadius": "4px",
                    }),
                ],
                style={"textAlign": "center", "marginTop": "8px"},
            ),
        ]
    )
