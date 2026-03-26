"""Dash app setup and layout — Bloomberg meets Apple."""

import dash
from dash import dcc, html

from pmod.dashboard.components import COLORS, FONT
from pmod.dashboard.pages.politician_trades import politician_trades_layout
from pmod.dashboard.pages.portfolio import portfolio_layout
from pmod.dashboard.pages.settings import settings_layout
from pmod.dashboard.pages.watchlist import watchlist_layout

# ── Global CSS ────────────────────────────────────────────────────────────
GLOBAL_CSS = """
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap');

    * { box-sizing: border-box; }

    body {
        margin: 0;
        padding: 0;
        background: %(bg)s;
        color: %(text_primary)s;
        font-family: %(font)s;
        -webkit-font-smoothing: antialiased;
        -moz-osx-font-smoothing: grayscale;
    }

    ::-webkit-scrollbar {
        width: 6px;
        height: 6px;
    }
    ::-webkit-scrollbar-track {
        background: transparent;
    }
    ::-webkit-scrollbar-thumb {
        background: rgba(255,255,255,0.08);
        border-radius: 3px;
    }
    ::-webkit-scrollbar-thumb:hover {
        background: rgba(255,255,255,0.14);
    }

    /* Tab overrides */
    .tab-container .tab {
        background: transparent !important;
        border: none !important;
        color: %(text_tertiary)s !important;
        font-size: 13px !important;
        font-weight: 500 !important;
        padding: 12px 20px !important;
        letter-spacing: 0.2px;
        transition: all 0.2s ease;
        cursor: pointer;
    }
    .tab-container .tab:hover {
        color: %(text_secondary)s !important;
    }
    .tab-container .tab--selected {
        color: %(text_primary)s !important;
        border-bottom: 2px solid %(accent)s !important;
        background: transparent !important;
    }
""" % {**COLORS, "font": FONT}


def _build_nav() -> html.Div:
    """Top navigation bar."""
    return html.Div(
        [
            # Left — brand
            html.Div(
                [
                    html.Span(
                        "PMOD",
                        style={
                            "fontSize": "18px",
                            "fontWeight": "700",
                            "color": COLORS["text_primary"],
                            "letterSpacing": "1.5px",
                        },
                    ),
                    html.Span(
                        "PrintMoneyOrDie",
                        style={
                            "fontSize": "12px",
                            "color": COLORS["text_tertiary"],
                            "marginLeft": "12px",
                            "fontWeight": "400",
                            "letterSpacing": "0.5px",
                        },
                    ),
                ],
                style={"display": "flex", "alignItems": "baseline"},
            ),
            # Center — tabs
            html.Div(
                dcc.Tabs(
                    id="main-tabs",
                    value="portfolio",
                    className="tab-container",
                    children=[
                        dcc.Tab(
                            label="Portfolio",
                            value="portfolio",
                            className="tab",
                            selected_className="tab--selected",
                        ),
                        dcc.Tab(
                            label="Watchlist",
                            value="watchlist",
                            className="tab",
                            selected_className="tab--selected",
                        ),
                        dcc.Tab(
                            label="Congress Trades",
                            value="politician_trades",
                            className="tab",
                            selected_className="tab--selected",
                        ),
                        dcc.Tab(
                            label="Settings",
                            value="settings",
                            className="tab",
                            selected_className="tab--selected",
                        ),
                    ],
                    style={"border": "none"},
                ),
            ),
            # Right — status
            html.Div(
                [
                    html.Span(
                        "LIVE",
                        style={
                            "fontSize": "10px",
                            "fontWeight": "700",
                            "color": COLORS["green"],
                            "background": COLORS["green_bg"],
                            "padding": "3px 10px",
                            "borderRadius": "100px",
                            "letterSpacing": "1.2px",
                        },
                    ),
                ],
                style={"display": "flex", "alignItems": "center", "gap": "12px"},
            ),
        ],
        style={
            "display": "flex",
            "justifyContent": "space-between",
            "alignItems": "center",
            "padding": "12px 32px",
            "borderBottom": f"1px solid {COLORS['border']}",
            "background": COLORS["surface"],
            "backdropFilter": "blur(30px)",
            "position": "sticky",
            "top": "0",
            "zIndex": "1000",
        },
    )


def create_app() -> dash.Dash:
    """Create and configure the Dash application."""
    app = dash.Dash(
        __name__,
        suppress_callback_exceptions=True,
        title="PMOD — PrintMoneyOrDie",
    )

    app.index_string = """<!DOCTYPE html>
<html>
    <head>
        {%metas%}
        <title>{%title%}</title>
        {%favicon%}
        {%css%}
        <style>""" + GLOBAL_CSS + """</style>
    </head>
    <body>
        {%app_entry%}
        <footer>
            {%config%}
            {%scripts%}
            {%renderer%}
        </footer>
    </body>
</html>"""

    app.layout = html.Div(
        [
            _build_nav(),
            html.Div(
                id="tab-content",
                style={
                    "padding": "28px 32px 60px 32px",
                    "maxWidth": "1440px",
                    "margin": "0 auto",
                    "width": "100%",
                },
            ),
            # Auto-refresh every 60s
            dcc.Interval(id="live-refresh", interval=60_000, n_intervals=0),
        ],
        style={
            "background": COLORS["bg"],
            "minHeight": "100vh",
        },
    )

    @app.callback(
        dash.Output("tab-content", "children"),
        dash.Input("main-tabs", "value"),
    )
    def render_tab(tab: str) -> html.Div:
        if tab == "portfolio":
            return portfolio_layout()
        if tab == "watchlist":
            return watchlist_layout()
        if tab == "politician_trades":
            return politician_trades_layout()
        if tab == "settings":
            return settings_layout()
        return html.Div("Unknown tab.")

    return app
