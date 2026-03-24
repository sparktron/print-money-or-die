"""Dash app setup and layout."""

import dash
from dash import dcc, html

from pmod.dashboard.pages.portfolio import portfolio_layout
from pmod.dashboard.pages.watchlist import watchlist_layout


def create_app() -> dash.Dash:
    """Create and configure the Dash application."""
    app = dash.Dash(
        __name__,
        suppress_callback_exceptions=True,
        title="PrintMoneyOrDie",
    )

    app.layout = html.Div(
        [
            html.H1("PrintMoneyOrDie", style={"textAlign": "center", "padding": "20px"}),
            dcc.Tabs(
                id="main-tabs",
                value="portfolio",
                children=[
                    dcc.Tab(label="Portfolio", value="portfolio"),
                    dcc.Tab(label="Watchlist", value="watchlist"),
                    dcc.Tab(label="Settings", value="settings"),
                ],
            ),
            html.Div(id="tab-content", style={"padding": "20px"}),
        ]
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
        if tab == "settings":
            return html.Div(
                [
                    html.H2("Settings"),
                    html.P("Risk profile and preferences — coming soon."),
                ]
            )
        return html.Div("Unknown tab.")

    return app
