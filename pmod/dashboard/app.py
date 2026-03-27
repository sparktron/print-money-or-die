"""Dash app setup and layout — Bloomberg meets Apple."""
from __future__ import annotations

import dash
from dash import ALL, Input, Output, State, ctx, dcc, html, no_update

from pmod.dashboard.components import COLORS, FONT
from pmod.dashboard.pages.politician_trades import politician_trades_layout
from pmod.dashboard.pages.portfolio import portfolio_layout
from pmod.dashboard.pages.settings import settings_layout
from pmod.dashboard.pages.setup import setup_layout, wizard_step_layout
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

    ::-webkit-scrollbar { width: 6px; height: 6px; }
    ::-webkit-scrollbar-track { background: transparent; }
    ::-webkit-scrollbar-thumb { background: rgba(255,255,255,0.08); border-radius: 3px; }
    ::-webkit-scrollbar-thumb:hover { background: rgba(255,255,255,0.14); }

    .tab-container .tab {
        background: transparent !important; border: none !important;
        color: %(text_tertiary)s !important; font-size: 13px !important;
        font-weight: 500 !important; padding: 12px 20px !important;
        letter-spacing: 0.2px; transition: all 0.2s ease; cursor: pointer;
    }
    .tab-container .tab:hover { color: %(text_secondary)s !important; }
    .tab-container .tab--selected {
        color: %(text_primary)s !important;
        border-bottom: 2px solid %(accent)s !important;
        background: transparent !important;
    }

    /* Dark dropdown overrides */
    .dark-dropdown .Select-control {
        background: %(surface_hover)s !important;
        border-color: %(border_accent)s !important;
    }
    .dark-dropdown .Select-menu-outer {
        background: %(surface_elevated)s !important;
        border-color: %(border_accent)s !important;
    }
    .dark-dropdown .Select-option { background: %(surface_elevated)s !important; color: %(text_primary)s !important; }
    .dark-dropdown .Select-option:hover { background: %(surface_hover)s !important; }
    .dark-dropdown .Select-value-label { color: %(accent)s !important; font-weight: 500 !important; }
    .dark-dropdown .Select-arrow { border-top-color: %(text_tertiary)s !important; }
""" % {**COLORS, "font": FONT}

_WIZARD_INIT: dict = {
    "step": 1,
    "risk": None,
    "strategy": None,
    "sectors": [],
    "max_pos": 5.0,
    "rebalance": "manual",
    "execution": "manual-confirm",
}


def _build_nav() -> html.Div:
    """Top navigation bar."""
    return html.Div(
        [
            html.Div(
                [
                    html.Span("PMOD", style={
                        "fontSize": "18px", "fontWeight": "700",
                        "color": COLORS["text_primary"], "letterSpacing": "1.5px",
                    }),
                    html.Span("PrintMoneyOrDie", style={
                        "fontSize": "12px", "color": COLORS["text_tertiary"],
                        "marginLeft": "12px", "fontWeight": "400", "letterSpacing": "0.5px",
                    }),
                ],
                style={"display": "flex", "alignItems": "baseline"},
            ),
            html.Div(
                dcc.Tabs(
                    id="main-tabs",
                    value="portfolio",
                    className="tab-container",
                    children=[
                        dcc.Tab(label="Portfolio", value="portfolio", className="tab", selected_className="tab--selected"),
                        dcc.Tab(label="Watchlist", value="watchlist", className="tab", selected_className="tab--selected"),
                        dcc.Tab(label="Congress Trades", value="politician_trades", className="tab", selected_className="tab--selected"),
                        dcc.Tab(label="Settings", value="settings", className="tab", selected_className="tab--selected"),
                    ],
                    style={"border": "none"},
                ),
            ),
            html.Div(
                html.Span("LIVE", style={
                    "fontSize": "10px", "fontWeight": "700", "color": COLORS["green"],
                    "background": COLORS["green_bg"], "padding": "3px 10px",
                    "borderRadius": "100px", "letterSpacing": "1.2px",
                }),
                style={"display": "flex", "alignItems": "center", "gap": "12px"},
            ),
        ],
        style={
            "display": "flex", "justifyContent": "space-between", "alignItems": "center",
            "padding": "12px 32px", "borderBottom": f"1px solid {COLORS['border']}",
            "background": COLORS["surface"], "backdropFilter": "blur(30px)",
            "position": "sticky", "top": "0", "zIndex": "1000",
        },
    )


def _main_layout() -> html.Div:
    """Return the main app shell (nav + tab content)."""
    return html.Div(
        [
            _build_nav(),
            html.Div(
                id="tab-content",
                style={"padding": "28px 32px 60px 32px", "maxWidth": "1440px", "margin": "0 auto", "width": "100%"},
            ),
            dcc.Interval(id="live-refresh", interval=60_000, n_intervals=0),
        ],
        style={"background": COLORS["bg"], "minHeight": "100vh"},
    )


def create_app() -> dash.Dash:
    """Create and configure the Dash application."""
    app = dash.Dash(
        __name__,
        suppress_callback_exceptions=True,
        title="PMOD — PrintMoneyOrDie",
    )

    app.index_string = (
        "<!DOCTYPE html><html><head>{%metas%}<title>{%title%}</title>"
        "{%favicon%}{%css%}<style>" + GLOBAL_CSS + "</style></head>"
        "<body>{%app_entry%}<footer>{%config%}{%scripts%}{%renderer%}</footer></body></html>"
    )

    app.layout = html.Div(
        [
            # Init trigger: fires once on page load
            dcc.Store(id="init-data", storage_type="session"),
            # Set by wizard on completion
            dcc.Store(id="setup-complete-flag", storage_type="session"),
            # Wizard form state
            dcc.Store(id="wizard-state", data=dict(_WIZARD_INIT)),
            # Page content: either setup wizard or main app
            html.Div(id="page-content"),
        ],
        style={"background": COLORS["bg"], "minHeight": "100vh"},
    )

    # ── Routing ────────────────────────────────────────────────────────────

    @app.callback(Output("init-data", "data"), Input("init-data", "id"))
    def check_setup_on_load(_: str) -> dict:
        from pmod.preferences.profile import has_completed_setup
        return {"setup_complete": has_completed_setup()}

    @app.callback(
        Output("page-content", "children"),
        Input("init-data", "data"),
        Input("setup-complete-flag", "data"),
    )
    def route_page(init_data: dict | None, complete_flag: dict | None) -> html.Div:
        if complete_flag and complete_flag.get("complete"):
            return _main_layout()
        if init_data and init_data.get("setup_complete"):
            return _main_layout()
        return setup_layout()

    # ── Main tab rendering ─────────────────────────────────────────────────

    @app.callback(Output("tab-content", "children"), Input("main-tabs", "value"))
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

    # ── Settings save ──────────────────────────────────────────────────────

    @app.callback(
        Output("settings-saved-msg", "children"),
        Input("settings-save-btn", "n_clicks"),
        State("settings-risk", "value"),
        State("settings-strategy", "value"),
        State("settings-maxpos", "value"),
        State("settings-rebalance", "value"),
        State("settings-execution", "value"),
        State("settings-sectors", "value"),
        prevent_initial_call=True,
    )
    def save_settings(
        n_clicks: int,
        risk: str,
        strategy: str,
        max_pos: float,
        rebalance: str,
        execution: str,
        sectors: list[str] | None,
    ) -> str:
        if not n_clicks:
            return no_update
        from pmod.preferences.profile import save_preferences
        save_preferences(
            risk_tolerance=risk,
            strategy=strategy,
            max_position_pct=float(max_pos),
            rebalance_frequency=rebalance,
            trade_execution=execution,
            sector_focus=sectors or [],
        )
        return "✓ Saved"

    # ── Wizard: option selection ───────────────────────────────────────────

    @app.callback(
        Output("wizard-state", "data", allow_duplicate=True),
        Input({"type": "wizard-opt", "field": ALL, "val": ALL}, "n_clicks"),
        State("wizard-state", "data"),
        prevent_initial_call=True,
    )
    def handle_wizard_option(n_clicks_list: list[int], state: dict) -> dict:
        if not any(n_clicks_list):
            return no_update
        trigger = ctx.triggered_id
        if trigger is None:
            return no_update
        field_map = {"risk": "risk", "strategy": "strategy", "rebalance": "rebalance", "execution": "execution"}
        key = field_map.get(trigger["field"])
        if key:
            state[key] = trigger["val"]
        return state

    @app.callback(
        Output("wizard-state", "data", allow_duplicate=True),
        Input({"type": "wizard-sector", "val": ALL}, "n_clicks"),
        State("wizard-state", "data"),
        prevent_initial_call=True,
    )
    def handle_wizard_sector(n_clicks_list: list[int], state: dict) -> dict:
        if not any(n_clicks_list):
            return no_update
        trigger = ctx.triggered_id
        if trigger is None:
            return no_update
        sector = trigger["val"]
        sectors: list[str] = list(state.get("sectors", []))
        if sector in sectors:
            sectors.remove(sector)
        else:
            sectors.append(sector)
        state["sectors"] = sectors
        return state

    @app.callback(
        Output("wizard-state", "data", allow_duplicate=True),
        Input({"type": "wizard-maxpos", "val": ALL}, "n_clicks"),
        State("wizard-state", "data"),
        prevent_initial_call=True,
    )
    def handle_wizard_maxpos(n_clicks_list: list[int], state: dict) -> dict:
        if not any(n_clicks_list):
            return no_update
        trigger = ctx.triggered_id
        if trigger is None:
            return no_update
        state["max_pos"] = trigger["val"]
        return state

    # ── Wizard: navigation ─────────────────────────────────────────────────

    @app.callback(
        Output("wizard-state", "data", allow_duplicate=True),
        Input("wizard-next", "n_clicks"),
        Input("wizard-back", "n_clicks"),
        State("wizard-state", "data"),
        prevent_initial_call=True,
    )
    def handle_wizard_nav(next_clicks: int, back_clicks: int, state: dict) -> dict:
        trigger_id = ctx.triggered_id
        if trigger_id == "wizard-next":
            state["step"] = min(state.get("step", 1) + 1, 5)
        elif trigger_id == "wizard-back":
            state["step"] = max(state.get("step", 1) - 1, 1)
        return state

    # ── Wizard: render current step ────────────────────────────────────────

    @app.callback(Output("wizard-content", "children"), Input("wizard-state", "data"))
    def render_wizard_step(state: dict) -> html.Div:
        return wizard_step_layout(state)

    # ── Wizard: complete setup ─────────────────────────────────────────────

    @app.callback(
        Output("setup-complete-flag", "data"),
        Input("wizard-complete", "n_clicks"),
        State("wizard-state", "data"),
        prevent_initial_call=True,
    )
    def complete_setup(n_clicks: int, state: dict) -> dict:
        if not n_clicks:
            return no_update
        from pmod.preferences.profile import save_preferences
        save_preferences(
            risk_tolerance=state.get("risk") or "medium",
            strategy=state.get("strategy") or "balanced",
            max_position_pct=float(state.get("max_pos") or 5.0),
            rebalance_frequency=state.get("rebalance") or "manual",
            trade_execution=state.get("execution") or "manual-confirm",
            sector_focus=state.get("sectors") or [],
        )
        return {"complete": True}

    return app
