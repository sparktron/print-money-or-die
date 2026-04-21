"""Reusable Dash/Plotly components — design system tokens and shared elements."""

import os

from dash import html

# ── Design Tokens ──────────────────────────────────────────────────────────
COLORS = {
    "bg": "#0a0a0f",
    "surface": "#12121a",
    "surface_elevated": "#1a1a26",
    "surface_hover": "#22222f",
    "border": "rgba(255, 255, 255, 0.06)",
    "border_accent": "rgba(255, 255, 255, 0.10)",
    "text_primary": "#f5f5f7",
    "text_secondary": "#8e8e93",
    "text_tertiary": "#636366",
    "accent": "#0a84ff",
    "accent_glow": "rgba(10, 132, 255, 0.15)",
    "green": "#30d158",
    "green_bg": "rgba(48, 209, 88, 0.10)",
    "red": "#ff453a",
    "red_bg": "rgba(255, 69, 58, 0.10)",
    "orange": "#ff9f0a",
    "orange_bg": "rgba(255, 159, 10, 0.10)",
    "purple": "#bf5af2",
    "chart_line": "#0a84ff",
    "chart_area": "rgba(10, 132, 255, 0.08)",
    "chart_grid": "rgba(255, 255, 255, 0.04)",
}

FONT = (
    "-apple-system, BlinkMacSystemFont, 'SF Pro Display', 'Segoe UI', "
    "Roboto, Helvetica, Arial, sans-serif"
)

MONO = "'SF Mono', 'Fira Code', 'Cascadia Code', 'Consolas', monospace"

# ── Dev mode masking ──────────────────────────────────────────────────────
_DEV_MODE = os.getenv("PMOD_DEV_MASK", "true").lower() in ("true", "1", "yes")


def mask_number(value: float, show_last_n: int = 3, masked: bool | None = None) -> str:
    """Mask a number with asterisks, showing only the last N digits.

    Pass masked=True/False to override the env-var default.
    Example: 12345.67 → $***567 (shows last 3 digits)
    Negative values preserve their sign: -12345.67 → -$***567
    """
    should_mask = _DEV_MODE if masked is None else masked
    if not should_mask:
        if isinstance(value, (int, float)):
            sign = "-" if value < 0 else ""
            return f"{sign}${abs(value):,.2f}"
        return str(value)

    sign = "-" if value < 0 else ""
    int_value = int(abs(value))
    int_str = str(int_value)
    visible_digits = int_str[-show_last_n:] if len(int_str) > show_last_n else int_str
    hidden_count = max(0, len(int_str) - show_last_n)
    return sign + "$" + "*" * hidden_count + visible_digits


def mask_pct(value: float, masked: bool | None = None) -> str:
    """Mask a percentage with asterisks, showing only the last 2 digits + % sign.

    Pass masked=True/False to override the env-var default.
    Example: 45.67% → ***67%
    Negative values preserve their sign: -45.67% → -***67%
    """
    should_mask = _DEV_MODE if masked is None else masked
    if not should_mask:
        return f"{value:.2f}%"

    sign = "-" if value < 0 else ""
    abs_value = abs(value)

    # Handle zero and very small values — just show "0.00%"
    if abs_value < 0.01:
        return "0.00%"

    formatted = f"{abs_value:.2f}"
    digits_only = formatted.replace(",", "").replace(".", "")
    visible_chars = digits_only[-2:] if len(digits_only) > 2 else digits_only
    hidden_count = max(0, len(digits_only) - 2)
    return sign + "*" * hidden_count + visible_chars + "%"


# ── Plotly layout template ────────────────────────────────────────────────
CHART_LAYOUT = dict(
    paper_bgcolor="rgba(0,0,0,0)",
    plot_bgcolor="rgba(0,0,0,0)",
    font=dict(family=FONT, color=COLORS["text_secondary"], size=12),
    margin=dict(l=0, r=0, t=40, b=0),
    xaxis=dict(
        gridcolor=COLORS["chart_grid"],
        zerolinecolor=COLORS["chart_grid"],
        showgrid=True,
        gridwidth=1,
    ),
    yaxis=dict(
        gridcolor=COLORS["chart_grid"],
        zerolinecolor=COLORS["chart_grid"],
        showgrid=True,
        gridwidth=1,
        side="right",
    ),
    legend=dict(
        bgcolor="rgba(0,0,0,0)",
        font=dict(size=11, color=COLORS["text_secondary"]),
    ),
    hoverlabel=dict(
        bgcolor=COLORS["surface_elevated"],
        font_size=13,
        font_family=FONT,
        bordercolor=COLORS["border"],
    ),
)


# ── Reusable Components ──────────────────────────────────────────────────
def kpi_card(
    label: str,
    value: str,
    delta: str = "",
    delta_color: str = "",
    icon: str = "",
) -> html.Div:
    """Render a single KPI metric card."""
    delta_style = {
        "fontSize": "13px",
        "fontWeight": "500",
        "fontFamily": MONO,
        "color": delta_color or COLORS["text_secondary"],
        "marginTop": "4px",
    }

    return html.Div(
        [
            html.Div(
                [
                    html.Span(
                        icon,
                        style={"fontSize": "14px", "marginRight": "6px"},
                    ) if icon else None,
                    html.Span(
                        label,
                        style={
                            "fontSize": "12px",
                            "fontWeight": "500",
                            "color": COLORS["text_tertiary"],
                            "textTransform": "uppercase",
                            "letterSpacing": "0.8px",
                        },
                    ),
                ],
                style={"display": "flex", "alignItems": "center"},
            ),
            html.Div(
                value,
                style={
                    "fontSize": "28px",
                    "fontWeight": "600",
                    "color": COLORS["text_primary"],
                    "fontFamily": FONT,
                    "marginTop": "8px",
                    "letterSpacing": "-0.5px",
                },
            ),
            html.Div(delta, style=delta_style) if delta else None,
        ],
        style={
            "background": COLORS["surface"],
            "border": f"1px solid {COLORS['border']}",
            "borderRadius": "16px",
            "padding": "20px 24px",
            "flex": "1",
            "minWidth": "180px",
            "backdropFilter": "blur(20px)",
        },
    )


def section_header(title: str, subtitle: str = "") -> html.Div:
    """Render a section header with optional subtitle."""
    return html.Div(
        [
            html.H2(
                title,
                style={
                    "fontSize": "20px",
                    "fontWeight": "600",
                    "color": COLORS["text_primary"],
                    "margin": "0",
                    "letterSpacing": "-0.3px",
                },
            ),
            html.Span(
                subtitle,
                style={
                    "fontSize": "13px",
                    "color": COLORS["text_tertiary"],
                },
            ) if subtitle else None,
        ],
        style={
            "display": "flex",
            "alignItems": "baseline",
            "gap": "12px",
            "marginBottom": "16px",
        },
    )


def status_badge(text: str, variant: str = "neutral") -> html.Span:
    """Render a small status badge. variant: 'green', 'red', 'orange', 'neutral'."""
    color_map = {
        "green": (COLORS["green"], COLORS["green_bg"]),
        "red": (COLORS["red"], COLORS["red_bg"]),
        "orange": (COLORS["orange"], COLORS["orange_bg"]),
        "accent": (COLORS["accent"], COLORS["accent_glow"]),
        "neutral": (COLORS["text_secondary"], COLORS["surface_elevated"]),
    }
    fg, bg = color_map.get(variant, color_map["neutral"])
    return html.Span(
        text,
        style={
            "fontSize": "11px",
            "fontWeight": "600",
            "color": fg,
            "background": bg,
            "padding": "3px 10px",
            "borderRadius": "100px",
            "letterSpacing": "0.3px",
            "textTransform": "uppercase",
        },
    )
