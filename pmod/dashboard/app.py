"""Dash app setup and layout — Bloomberg meets Apple."""
from __future__ import annotations

import dash
from dash import ALL, Input, Output, State, ctx, dcc, html, no_update, MATCH

from pmod.dashboard.components import COLORS, FONT
from pmod.dashboard.pages.advisor import advisor_layout, render_actions, render_response
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
                        dcc.Tab(label="AI Advisor", value="advisor", className="tab", selected_className="tab--selected"),
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


def _trade_modal() -> html.Div:
    """Global trade confirmation modal overlay."""
    input_style = {
        "width": "100%",
        "padding": "10px 14px",
        "background": COLORS["surface_hover"],
        "border": f"1px solid {COLORS['border_accent']}",
        "borderRadius": "10px",
        "color": COLORS["text_primary"],
        "fontSize": "14px",
        "fontFamily": FONT,
        "outline": "none",
    }
    label_style = {
        "fontSize": "11px",
        "fontWeight": "600",
        "color": COLORS["text_tertiary"],
        "textTransform": "uppercase",
        "letterSpacing": "0.8px",
        "marginBottom": "6px",
        "display": "block",
    }

    return html.Div(
        id="trade-modal",
        style={"display": "none"},
        children=[
            # Backdrop
            html.Div(
                id="trade-modal-backdrop",
                style={
                    "position": "fixed", "top": "0", "left": "0", "right": "0", "bottom": "0",
                    "background": "rgba(0,0,0,0.72)", "zIndex": "2000",
                },
            ),
            # Card
            html.Div(
                [
                    # Title row
                    html.Div(
                        [
                            html.Div(id="trade-modal-title", style={
                                "fontSize": "18px", "fontWeight": "700",
                                "color": COLORS["text_primary"], "letterSpacing": "-0.3px",
                            }),
                            html.Button(
                                "✕",
                                id="trade-cancel-btn",
                                n_clicks=0,
                                style={
                                    "background": "none", "border": "none",
                                    "color": COLORS["text_tertiary"], "fontSize": "18px",
                                    "cursor": "pointer", "padding": "0",
                                },
                            ),
                        ],
                        style={"display": "flex", "justifyContent": "space-between", "alignItems": "center", "marginBottom": "20px"},
                    ),

                    # Shares
                    html.Div(
                        [
                            html.Label("Shares", style=label_style),
                            dcc.Input(
                                id="trade-shares-input",
                                type="number", min=1, step=1, value=1,
                                style=input_style,
                            ),
                        ],
                        style={"marginBottom": "16px"},
                    ),

                    # Order type
                    html.Div(
                        [
                            html.Label("Order Type", style=label_style),
                            dcc.Dropdown(
                                id="trade-order-type",
                                options=[
                                    {"label": "Market", "value": "market"},
                                    {"label": "Limit", "value": "limit"},
                                ],
                                value="market",
                                clearable=False,
                                className="dark-dropdown",
                            ),
                        ],
                        style={"marginBottom": "16px"},
                    ),

                    # Limit price (shown only for limit orders)
                    html.Div(
                        id="trade-limit-price-row",
                        style={"display": "none", "marginBottom": "16px"},
                        children=[
                            html.Label("Limit Price ($)", style=label_style),
                            dcc.Input(
                                id="trade-limit-price",
                                type="number", min=0.01, step=0.01,
                                style=input_style,
                            ),
                        ],
                    ),

                    # Estimated total
                    html.Div(id="trade-estimated-total", style={
                        "fontSize": "13px", "color": COLORS["text_secondary"],
                        "marginBottom": "20px", "fontStyle": "italic",
                    }),

                    # Confirm button
                    html.Button(
                        "Confirm Order",
                        id="trade-confirm-btn",
                        n_clicks=0,
                        style={
                            "width": "100%",
                            "padding": "13px",
                            "fontSize": "14px",
                            "fontWeight": "700",
                            "color": COLORS["text_primary"],
                            "background": COLORS["accent"],
                            "border": "none",
                            "borderRadius": "12px",
                            "cursor": "pointer",
                            "marginBottom": "10px",
                        },
                    ),

                    # Result / error message
                    html.Div(id="trade-result-msg", style={
                        "fontSize": "13px",
                        "textAlign": "center",
                        "minHeight": "20px",
                    }),
                ],
                style={
                    "position": "fixed", "top": "50%", "left": "50%",
                    "transform": "translate(-50%, -50%)",
                    "background": COLORS["surface_elevated"],
                    "border": f"1px solid {COLORS['border_accent']}",
                    "borderRadius": "20px",
                    "padding": "28px 32px",
                    "zIndex": "2001",
                    "width": "420px",
                    "maxWidth": "92vw",
                    "boxShadow": "0 32px 80px rgba(0,0,0,0.6)",
                },
            ),
        ],
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
            # Global trade modal + its backing store
            dcc.Store(id="trade-pending-store", data={}),
            _trade_modal(),
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
        if tab == "advisor":
            return advisor_layout()
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

    # ── Congress detail drawer ─────────────────────────────────────────────

    @app.callback(
        Output("congress-detail-container", "style"),
        Output("congress-panel-title", "children"),
        Output("congress-panel-body", "children"),
        Input({"type": "pol-btn", "name": ALL}, "n_clicks"),
        Input({"type": "ticker-btn", "ticker": ALL}, "n_clicks"),
        Input("congress-panel-close", "n_clicks"),
        Input("congress-panel-backdrop", "n_clicks"),
        prevent_initial_call=True,
    )
    def handle_congress_panel(
        pol_clicks: list[int],
        ticker_clicks: list[int],
        _close: int,
        _backdrop: int,
    ) -> tuple:
        from pmod.dashboard.pages.politician_trades import render_politician_detail, render_ticker_detail

        hidden = {"display": "none"}
        visible = {"display": "block"}
        trigger = ctx.triggered_id

        if trigger in ("congress-panel-close", "congress-panel-backdrop"):
            return hidden, no_update, no_update

        if not any(pol_clicks) and not any(ticker_clicks):
            return no_update, no_update, no_update

        if isinstance(trigger, dict) and trigger.get("type") == "pol-btn":
            name: str = trigger["name"]
            return visible, name, render_politician_detail(name)

        if isinstance(trigger, dict) and trigger.get("type") == "ticker-btn":
            ticker: str = trigger["ticker"]
            return visible, ticker, render_ticker_detail(ticker)

        return no_update, no_update, no_update

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

    # ── Trade modal: open from watchlist ───────────────────────────────────

    @app.callback(
        Output("trade-pending-store", "data"),
        Input({"type": "watchlist-buy", "ticker": ALL, "name": ALL, "price": ALL}, "n_clicks"),
        Input({"type": "rebalance-execute", "ticker": ALL}, "n_clicks"),
        State("trade-pending-store", "data"),
        prevent_initial_call=True,
    )
    def open_trade_modal(
        watchlist_clicks: list[int],
        rebalance_clicks: list[int],
        current_store: dict,
    ) -> dict:
        if not any(watchlist_clicks) and not any(rebalance_clicks):
            return no_update
        trigger = ctx.triggered_id
        if trigger is None:
            return no_update

        if isinstance(trigger, dict) and trigger.get("type") == "watchlist-buy":
            price_str: str = trigger.get("price", "$0")
            price = float(price_str.replace("$", "").replace(",", ""))
            return {
                "ticker": trigger["ticker"],
                "name": trigger["name"],
                "price": price,
                "instruction": "buy",
                "source": "watchlist",
            }

        if isinstance(trigger, dict) and trigger.get("type") == "rebalance-execute":
            ticker = trigger["ticker"]
            # Pull trade details from the rebalance panel's hidden store
            plan = current_store.get("_rebalance_plan", {})
            trade = next((t for t in plan.get("trades", []) if t["ticker"] == ticker), None)
            if trade:
                return {
                    "ticker": ticker,
                    "name": trade.get("company_name", ticker),
                    "price": trade.get("current_price", 0),
                    "instruction": trade.get("action", "buy"),
                    "quantity": abs(trade.get("shares_delta", 1)),
                    "source": "rebalance",
                }

        return no_update

    # ── Trade modal: show/hide ─────────────────────────────────────────────

    @app.callback(
        Output("trade-modal", "style"),
        Output("trade-modal-title", "children"),
        Output("trade-shares-input", "value"),
        Output("trade-limit-price", "value"),
        Output("trade-result-msg", "children"),
        Input("trade-pending-store", "data"),
        Input("trade-cancel-btn", "n_clicks"),
        Input("trade-modal-backdrop", "n_clicks"),
        Input("trade-confirm-btn", "n_clicks"),
        prevent_initial_call=True,
    )
    def toggle_trade_modal(
        store: dict,
        cancel: int,
        backdrop: int,
        confirm: int,
    ) -> tuple:
        hidden = {"display": "none"}
        visible = {"display": "block"}
        trigger = ctx.triggered_id

        if trigger in ("trade-cancel-btn", "trade-modal-backdrop", "trade-confirm-btn"):
            return hidden, no_update, no_update, no_update, ""

        if store and store.get("ticker"):
            ticker = store["ticker"]
            name = store.get("name", ticker)
            instruction = store.get("instruction", "buy").upper()
            price = store.get("price", 0)
            qty = store.get("quantity", 1)
            title = f"{instruction}  {ticker} — {name}"
            price_str = f"${price:,.2f}" if price else "market price"
            return visible, title, qty, price, ""

        return hidden, no_update, no_update, no_update, ""

    # ── Trade modal: limit price row visibility ────────────────────────────

    @app.callback(
        Output("trade-limit-price-row", "style"),
        Input("trade-order-type", "value"),
    )
    def toggle_limit_row(order_type: str) -> dict:
        if order_type == "limit":
            return {"display": "block", "marginBottom": "16px"}
        return {"display": "none"}

    # ── Trade modal: estimated total ───────────────────────────────────────

    @app.callback(
        Output("trade-estimated-total", "children"),
        Input("trade-shares-input", "value"),
        Input("trade-order-type", "value"),
        Input("trade-limit-price", "value"),
        State("trade-pending-store", "data"),
    )
    def update_estimated_total(
        shares: int | None,
        order_type: str,
        limit_price: float | None,
        store: dict,
    ) -> str:
        if not shares or shares <= 0 or not store:
            return ""
        price = limit_price if order_type == "limit" and limit_price else store.get("price", 0)
        if not price:
            return "Market order — price determined at execution"
        total = shares * price
        return f"Estimated total: {shares} × ${price:,.2f} = ${total:,.2f}"

    # ── Trade modal: confirm / execute ────────────────────────────────────

    @app.callback(
        Output("trade-result-msg", "children", allow_duplicate=True),
        Input("trade-confirm-btn", "n_clicks"),
        State("trade-pending-store", "data"),
        State("trade-shares-input", "value"),
        State("trade-order-type", "value"),
        State("trade-limit-price", "value"),
        prevent_initial_call=True,
    )
    def execute_trade(
        n_clicks: int,
        store: dict,
        shares: int | None,
        order_type: str,
        limit_price: float | None,
    ) -> str:
        if not n_clicks or not store or not store.get("ticker"):
            return no_update

        from pmod.broker.schwab import OrderRequest, place_order

        qty = int(shares) if shares and shares > 0 else 1
        request = OrderRequest(
            ticker=store["ticker"],
            instruction=store.get("instruction", "buy"),
            quantity=qty,
            order_type=order_type or "market",
            limit_price=float(limit_price) if order_type == "limit" and limit_price else None,
        )
        result = place_order(request)

        if result.success:
            order_ref = f" (ID {result.order_id})" if result.order_id else ""
            return html.Span(
                f"✓ {result.message}{order_ref}",
                style={"color": COLORS["green"]},
            )
        return html.Span(
            f"✗ {result.message}",
            style={"color": COLORS["red"]},
        )

    # ── Portfolio: rebalance panel ─────────────────────────────────────────

    @app.callback(
        Output("portfolio-rebalance-panel", "children"),
        Output("trade-pending-store", "data", allow_duplicate=True),
        Input("portfolio-rebalance-btn", "n_clicks"),
        State("trade-pending-store", "data"),
        prevent_initial_call=True,
    )
    def render_rebalance_panel(n_clicks: int, store: dict) -> tuple:
        if not n_clicks:
            return no_update, no_update

        from pmod.optimizer.portfolio import compute_rebalance
        from pmod.preferences.profile import load_preferences_dict

        prefs = load_preferences_dict()
        plan = compute_rebalance(max_position_pct=float(prefs.get("max_position_pct", 5.0)))

        if not plan.trades:
            return html.Span(
                "No positions to rebalance — connect Schwab first.",
                style={"color": COLORS["text_tertiary"], "fontSize": "13px", "fontStyle": "italic"},
            ), no_update

        action_color = {"buy": COLORS["green"], "sell": COLORS["red"], "hold": COLORS["text_tertiary"]}
        h_style = {
            "fontSize": "11px", "fontWeight": "600", "color": COLORS["text_tertiary"],
            "textTransform": "uppercase", "letterSpacing": "0.8px",
            "padding": "10px 14px", "borderBottom": f"1px solid {COLORS['border']}",
            "textAlign": "left",
        }
        h_style_r = {**h_style, "textAlign": "right"}
        c_style = {
            "padding": "12px 14px", "borderBottom": f"1px solid {COLORS['border']}",
            "fontSize": "13px", "color": COLORS["text_primary"],
        }
        c_style_r = {**c_style, "textAlign": "right", "fontFamily": "'SF Mono','Fira Code',monospace"}

        rows = []
        for t in sorted(plan.trades, key=lambda x: abs(x.dollar_delta), reverse=True):
            color = action_color.get(t.action, COLORS["text_tertiary"])
            sign = "+" if t.shares_delta > 0 else ""
            execute_btn = html.Button(
                "Execute",
                id={"type": "rebalance-execute", "ticker": t.ticker},
                n_clicks=0,
                style={
                    "padding": "6px 14px", "fontSize": "12px", "fontWeight": "600",
                    "color": COLORS["text_primary"], "background": color,
                    "border": "none", "borderRadius": "8px", "cursor": "pointer",
                    "opacity": "0.9",
                },
            ) if t.action != "hold" else html.Span("—", style={"color": COLORS["text_tertiary"]})

            rows.append(html.Tr([
                html.Td(html.Div([
                    html.Span(t.ticker, style={"fontWeight": "600"}),
                    html.Span(f" {t.company_name}", style={"color": COLORS["text_tertiary"], "fontSize": "12px"}),
                ]), style=c_style),
                html.Td(f"{t.current_weight_pct:.1f}%", style=c_style_r),
                html.Td(f"{t.target_weight_pct:.1f}%", style=c_style_r),
                html.Td(
                    html.Span(t.action.upper(), style={"color": color, "fontWeight": "700"}),
                    style=c_style_r,
                ),
                html.Td(
                    f"{sign}{t.shares_delta} shares",
                    style={**c_style_r, "color": color},
                ),
                html.Td(
                    f"{'+' if t.dollar_delta >= 0 else ''}${t.dollar_delta:,.0f}",
                    style={**c_style_r, "color": color},
                ),
                html.Td(execute_btn, style={**c_style, "textAlign": "right"}),
            ]))

        cash_sign = "+" if plan.net_cash_change >= 0 else ""
        summary_row = html.Tr([
            html.Td(html.Span("Net cash impact", style={"fontWeight": "600", "color": COLORS["text_secondary"]}), style={**c_style, "borderBottom": "none"}),
            html.Td("", style={**c_style, "borderBottom": "none"}),
            html.Td("", style={**c_style, "borderBottom": "none"}),
            html.Td("", style={**c_style, "borderBottom": "none"}),
            html.Td("", style={**c_style, "borderBottom": "none"}),
            html.Td(
                f"{cash_sign}${plan.net_cash_change:,.0f}",
                style={**c_style_r, "borderBottom": "none",
                       "color": COLORS["green"] if plan.net_cash_change >= 0 else COLORS["red"]},
            ),
            html.Td("", style={**c_style, "borderBottom": "none"}),
        ])

        table = html.Div(
            html.Table(
                [
                    html.Thead(html.Tr([
                        html.Th("Asset", style=h_style),
                        html.Th("Current %", style=h_style_r),
                        html.Th("Target %", style=h_style_r),
                        html.Th("Action", style=h_style_r),
                        html.Th("Shares Δ", style=h_style_r),
                        html.Th("$ Δ", style=h_style_r),
                        html.Th("", style=h_style_r),
                    ])),
                    html.Tbody(rows + [summary_row]),
                ],
                style={"width": "100%", "borderCollapse": "collapse"},
            ),
            style={
                "background": COLORS["surface"],
                "border": f"1px solid {COLORS['border']}",
                "borderRadius": "16px",
                "overflow": "hidden",
            },
        )

        # Cache the plan in the store so rebalance-execute buttons can read trade details
        trades_serialised = [
            {
                "ticker": t.ticker,
                "company_name": t.company_name,
                "current_price": t.current_price,
                "action": t.action,
                "shares_delta": t.shares_delta,
            }
            for t in plan.trades
        ]
        updated_store = {**store, "_rebalance_plan": {"trades": trades_serialised}}

        return table, updated_store

    # ── Advisor: populate textarea from suggestion chips ───────────────────

    @app.callback(
        Output("advisor-question-input", "value"),
        Input({"type": "advisor-suggestion", "text": ALL}, "n_clicks"),
        prevent_initial_call=True,
    )
    def fill_suggestion(n_clicks_list: list[int]) -> str:
        if not any(n_clicks_list):
            return no_update
        trigger = ctx.triggered_id
        if trigger is None:
            return no_update
        return trigger["text"]

    # ── Advisor: char count ────────────────────────────────────────────────

    @app.callback(
        Output("advisor-char-count", "children"),
        Input("advisor-question-input", "value"),
    )
    def update_char_count(value: str | None) -> str:
        n = len(value or "")
        return f"{n} / 1000"

    # ── Advisor: submit question → call Claude ─────────────────────────────

    @app.callback(
        Output("advisor-response-area", "children"),
        Output("advisor-actions-store", "data"),
        Input("advisor-submit-btn", "n_clicks"),
        State("advisor-question-input", "value"),
        prevent_initial_call=True,
    )
    def ask_advisor(n_clicks: int, question: str | None) -> tuple:
        if not n_clicks or not question or not question.strip():
            return no_update, no_update

        from pmod.advisor.claude import ask_claude

        text, actions = ask_claude(question.strip())
        return render_response(text), actions

    # ── Advisor: render actions panel from store ───────────────────────────

    @app.callback(
        Output("advisor-actions-panel", "children"),
        Input("advisor-actions-store", "data"),
        prevent_initial_call=True,
    )
    def show_actions_panel(actions: dict) -> html.Div | str:
        if not actions:
            return ""
        panel = render_actions(actions)
        return panel or ""

    # ── Advisor: add ticker to watchlist ───────────────────────────────────

    @app.callback(
        Output({"type": "advisor-add-watchlist", "ticker": MATCH, "reason": MATCH}, "children"),
        Output({"type": "advisor-add-watchlist", "ticker": MATCH, "reason": MATCH}, "disabled"),
        Input({"type": "advisor-add-watchlist", "ticker": MATCH, "reason": MATCH}, "n_clicks"),
        prevent_initial_call=True,
    )
    def add_to_watchlist(n_clicks: int) -> tuple:
        if not n_clicks:
            return no_update, no_update
        trigger = ctx.triggered_id
        if trigger is None:
            return no_update, no_update

        ticker: str = trigger["ticker"]
        reason: str = trigger.get("reason", "")

        try:
            from pmod.data.models import WatchlistItem, get_session
            session = get_session()
            try:
                existing = session.query(WatchlistItem).filter_by(ticker=ticker).first()
                if not existing:
                    session.add(WatchlistItem(
                        ticker=ticker,
                        company_name=ticker,
                        reason=reason,
                    ))
                    session.commit()
            finally:
                session.close()
            return "✓ Added", True
        except Exception as exc:
            return f"Error: {str(exc)[:40]}", False

    # ── Advisor: apply risk tolerance from suggestion ──────────────────────

    @app.callback(
        Output({"type": "advisor-apply-risk", "value": MATCH}, "children"),
        Output({"type": "advisor-apply-risk", "value": MATCH}, "disabled"),
        Input({"type": "advisor-apply-risk", "value": MATCH}, "n_clicks"),
        prevent_initial_call=True,
    )
    def apply_risk(n_clicks: int) -> tuple:
        if not n_clicks:
            return no_update, no_update
        trigger = ctx.triggered_id
        if trigger is None:
            return no_update, no_update

        try:
            import json
            from pmod.preferences.profile import load_preferences_dict, save_preferences
            prefs = load_preferences_dict()
            save_preferences(
                risk_tolerance=trigger["value"],
                strategy=prefs.get("strategy", "balanced"),
                max_position_pct=float(prefs.get("max_position_pct", 5.0)),
                rebalance_frequency=prefs.get("rebalance_frequency", "manual"),
                trade_execution=prefs.get("trade_execution", "manual-confirm"),
                sector_focus=json.loads(prefs.get("sector_focus", "[]")),
            )
            return "✓ Applied", True
        except Exception as exc:
            return f"Error: {str(exc)[:40]}", False

    # ── Advisor: apply strategy suggestion ────────────────────────────────

    @app.callback(
        Output({"type": "advisor-apply-strategy", "value": MATCH}, "children"),
        Output({"type": "advisor-apply-strategy", "value": MATCH}, "disabled"),
        Input({"type": "advisor-apply-strategy", "value": MATCH}, "n_clicks"),
        prevent_initial_call=True,
    )
    def apply_strategy(n_clicks: int) -> tuple:
        if not n_clicks:
            return no_update, no_update
        trigger = ctx.triggered_id
        if trigger is None:
            return no_update, no_update

        try:
            import json
            from pmod.preferences.profile import load_preferences_dict, save_preferences
            prefs = load_preferences_dict()
            save_preferences(
                risk_tolerance=prefs.get("risk_tolerance", "medium"),
                strategy=trigger["value"],
                max_position_pct=float(prefs.get("max_position_pct", 5.0)),
                rebalance_frequency=prefs.get("rebalance_frequency", "manual"),
                trade_execution=prefs.get("trade_execution", "manual-confirm"),
                sector_focus=json.loads(prefs.get("sector_focus", "[]")),
            )
            return "✓ Applied", True
        except Exception as exc:
            return f"Error: {str(exc)[:40]}", False

    return app
