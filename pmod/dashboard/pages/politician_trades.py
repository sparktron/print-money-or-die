"""Politician Trades dashboard page — congressional stock disclosure tracker."""
from __future__ import annotations

from urllib.parse import quote

from dash import html

from pmod.dashboard.components import COLORS, MONO, section_header, status_badge

# ── External link helpers ──────────────────────────────────────────────────

def _senate_search_url(name: str) -> str:
    """Link to efdsearch.senate.gov filtered by senator name."""
    parts = name.strip().split()
    first = quote(parts[0]) if len(parts) >= 2 else ""
    last = quote(parts[-1]) if parts else quote(name)
    return (
        f"https://efdsearch.senate.gov/search/home/"
        f"?first_name={first}&last_name={last}&filer_type=0&doc_type=ptr&action=search"
    )


# ── Shared badge helpers ───────────────────────────────────────────────────

def _signal_badge(signal: str) -> html.Span:
    variant_map = {
        "strong_buy": ("STRONG BUY", "green"),
        "buy": ("BUY", "green"),
        "hold": ("HOLD", "neutral"),
        "sell": ("SELL", "red"),
    }
    label, variant = variant_map.get(signal, ("UNKNOWN", "neutral"))
    return status_badge(label, variant)


def _trade_type_badge(trade_type: str) -> html.Span:
    if trade_type in ("purchase", "buy"):
        return status_badge("BUY", "green")
    if trade_type in ("sale", "sale_partial", "sell"):
        return status_badge("SELL", "red")
    return status_badge(trade_type.upper(), "neutral")


def _party_badge(party: str) -> html.Span:
    color = COLORS["accent"] if party.upper() in ("D", "DEM", "DEMOCRAT") else COLORS["red"] if party.upper() in ("R", "REP", "REPUBLICAN") else COLORS["text_tertiary"]
    return html.Span(
        party or "?",
        style={"fontSize": "10px", "fontWeight": "700", "color": color,
               "border": f"1px solid {color}", "borderRadius": "4px",
               "padding": "1px 6px", "marginLeft": "6px"},
    )


def _confidence_bar(confidence: float) -> html.Div:
    pct = round(confidence * 100)
    color = COLORS["green"] if confidence >= 0.5 else COLORS["orange"] if confidence >= 0.25 else COLORS["red"]
    return html.Div(
        html.Div(style={"width": f"{pct}%", "height": "4px", "background": color, "borderRadius": "2px"}),
        style={"width": "80px", "height": "4px", "background": COLORS["border"], "borderRadius": "2px", "overflow": "hidden"},
    )


def _ext_link(url: str, label: str = "↗") -> html.A:
    return html.A(
        label,
        href=url,
        target="_blank",
        rel="noopener noreferrer",
        style={
            "fontSize": "12px", "color": COLORS["accent"],
            "textDecoration": "none", "padding": "2px 8px",
            "border": f"1px solid {COLORS['border_accent']}",
            "borderRadius": "6px", "whiteSpace": "nowrap",
        },
    )


# ── Clickable inline button (looks like a link) ────────────────────────────

def _pol_button(name: str, display: str | None = None) -> html.Span:
    """Inline clickable politician name that opens the detail panel."""
    return html.Span(
        display or name,
        id={"type": "pol-btn", "name": name},
        n_clicks=0,
        style={
            "color": COLORS["text_primary"], "cursor": "pointer",
            "borderBottom": f"1px dashed {COLORS['border_accent']}",
            "paddingBottom": "1px",
        },
    )


def _ticker_button(ticker: str, company: str = "") -> html.Span:
    """Clickable company/ticker name that opens the detail panel."""
    return html.Span(
        company or ticker,
        id={"type": "ticker-btn", "ticker": ticker},
        n_clicks=0,
        style={
            "color": COLORS["text_secondary"], "cursor": "pointer",
            "borderBottom": f"1px dashed {COLORS['border_accent']}",
            "paddingBottom": "1px",
        },
    )


# ── Signal card ────────────────────────────────────────────────────────────

def _signal_card(item: dict) -> html.Div:
    buy_pct = round(item["buy_count"] / max(item["buy_count"] + item["sell_count"], 1) * 100)
    return html.Div(
        [
            html.Div(
                [
                    html.Div(
                        [
                            html.Span(item["ticker"], style={"fontFamily": MONO, "fontSize": "18px", "fontWeight": "700", "color": COLORS["text_primary"], "marginRight": "10px"}),
                            _ticker_button(item["ticker"], item["company"]),
                        ],
                        style={"display": "flex", "alignItems": "baseline"},
                    ),
                    _signal_badge(item["signal"]),
                ],
                style={"display": "flex", "justifyContent": "space-between", "alignItems": "flex-start"},
            ),
            html.Div(
                [
                    html.Span("Confidence", style={"fontSize": "11px", "color": COLORS["text_tertiary"]}),
                    _confidence_bar(item["confidence"]),
                    html.Span(f"{round(item['confidence'] * 100)}%", style={"fontSize": "11px", "color": COLORS["text_secondary"], "fontFamily": MONO}),
                ],
                style={"display": "flex", "alignItems": "center", "gap": "10px", "marginTop": "12px"},
            ),
            html.Div(
                [
                    html.Div([html.Span(str(item["buy_count"]), style={"color": COLORS["green"], "fontFamily": MONO, "fontWeight": "600"}), html.Span(" buys", style={"color": COLORS["text_tertiary"], "fontSize": "11px"})]),
                    html.Div([html.Span(str(item["sell_count"]), style={"color": COLORS["red"], "fontFamily": MONO, "fontWeight": "600"}), html.Span(" sells", style={"color": COLORS["text_tertiary"], "fontSize": "11px"})]),
                    html.Div([html.Span(f"{buy_pct}%", style={"color": COLORS["accent"], "fontFamily": MONO, "fontWeight": "600"}), html.Span(" buy rate", style={"color": COLORS["text_tertiary"], "fontSize": "11px"})]),
                    html.Div([html.Span(str(item["politicians"]), style={"color": COLORS["text_primary"], "fontFamily": MONO, "fontWeight": "600"}), html.Span(" members", style={"color": COLORS["text_tertiary"], "fontSize": "11px"})]),
                ],
                style={"display": "flex", "gap": "20px", "marginTop": "10px"},
            ),
            html.P(item["rationale"], style={"fontSize": "12px", "color": COLORS["text_secondary"], "marginTop": "12px", "lineHeight": "1.6", "borderLeft": f"2px solid {COLORS['border_accent']}", "paddingLeft": "10px"}),
        ],
        style={"background": COLORS["surface_elevated"], "border": f"1px solid {COLORS['border']}", "borderRadius": "12px", "padding": "18px 20px"},
    )


# ── Recent disclosures table ───────────────────────────────────────────────

def _recent_trades_table(rows: list[dict]) -> html.Div:
    hs = {"fontSize": "11px", "fontWeight": "600", "color": COLORS["text_tertiary"], "letterSpacing": "0.5px", "textTransform": "uppercase", "padding": "10px 14px", "borderBottom": f"1px solid {COLORS['border']}", "background": COLORS["surface"], "textAlign": "left"}
    cs = {"fontSize": "12px", "color": COLORS["text_secondary"], "padding": "10px 14px", "borderBottom": f"1px solid {COLORS['border']}", "verticalAlign": "middle"}

    header = html.Tr([html.Th("Date", style=hs), html.Th("Member", style=hs), html.Th("Ticker", style=hs), html.Th("Company", style=hs), html.Th("Type", style=hs), html.Th("Amount", style=hs)])

    trade_rows = [
        html.Tr([
            html.Td(row["date"], style=cs),
            html.Td(_pol_button(row["politician"]), style=cs),
            html.Td(html.Span(row["ticker"], style={"fontFamily": MONO, "color": COLORS["accent"], "fontWeight": "600"}), style=cs),
            html.Td(_ticker_button(row["ticker"], row["company"]), style=cs),
            html.Td(_trade_type_badge(row["type"]), style=cs),
            html.Td(row["amount"], style={**cs, "fontFamily": MONO, "fontSize": "11px"}),
        ])
        for row in rows
    ]

    return html.Div(
        html.Table([html.Thead(header), html.Tbody(trade_rows)], style={"width": "100%", "borderCollapse": "collapse"}),
        style={"overflowX": "auto", "overflowY": "hidden", "background": COLORS["surface_elevated"], "border": f"1px solid {COLORS['border']}", "borderRadius": "12px"},
    )


# ── All Members table ──────────────────────────────────────────────────────

def _members_table(politicians: list[dict]) -> html.Div:
    if not politicians:
        return html.Div(
            "No data — run pmod politicians fetch to load congressional trade data",
            style={"fontSize": "13px", "color": COLORS["text_tertiary"], "padding": "24px", "textAlign": "center",
                   "background": COLORS["surface"], "borderRadius": "12px", "border": f"1px solid {COLORS['border']}"},
        )

    hs = {"fontSize": "11px", "fontWeight": "600", "color": COLORS["text_tertiary"], "textTransform": "uppercase",
          "letterSpacing": "0.5px", "padding": "10px 16px", "borderBottom": f"1px solid {COLORS['border']}",
          "background": COLORS["surface"], "textAlign": "left"}
    hsr = {**hs, "textAlign": "right"}
    cs = {"fontSize": "13px", "color": COLORS["text_secondary"], "padding": "10px 16px", "borderBottom": f"1px solid {COLORS['border']}", "verticalAlign": "middle"}
    csr = {**cs, "textAlign": "right", "fontFamily": MONO}

    header = html.Tr([
        html.Th("Member", style=hs), html.Th("Chamber", style=hs),
        html.Th("Trades", style=hsr), html.Th("Buys", style=hsr),
        html.Th("Sells", style=hsr), html.Th("Tickers", style=hsr),
        html.Th("Latest", style=hsr), html.Th("", style=hs),
    ])

    rows = []
    for p in politicians:
        latest = p["latest_date"].strftime("%b %d, %Y") if p.get("latest_date") else "—"
        buy_color = COLORS["green"] if p["buy_count"] > p["sell_count"] else COLORS["red"]
        rows.append(html.Tr([
            html.Td(html.Div([_pol_button(p["name"]), _party_badge(p["party"])], style={"display": "flex", "alignItems": "center"}), style=cs),
            html.Td(p["chamber"].title() if p.get("chamber") else "—", style=cs),
            html.Td(str(p["total_trades"]), style={**csr, "fontWeight": "600", "color": COLORS["text_primary"]}),
            html.Td(str(p["buy_count"]), style={**csr, "color": COLORS["green"]}),
            html.Td(str(p["sell_count"]), style={**csr, "color": COLORS["red"]}),
            html.Td(str(p["unique_tickers"]), style=csr),
            html.Td(latest, style=csr),
            html.Td(_ext_link(_senate_search_url(p["name"]), "View →"), style=cs),
        ]))

    return html.Div(
        html.Table([html.Thead(header), html.Tbody(rows)], style={"width": "100%", "borderCollapse": "collapse"}),
        style={"overflowX": "auto", "overflowY": "hidden", "background": COLORS["surface_elevated"], "border": f"1px solid {COLORS['border']}", "borderRadius": "12px"},
    )


# ── Detail panel content builders (called from app.py callbacks) ───────────

def render_politician_detail(name: str) -> html.Div:
    """Build the detail panel body for a politician."""
    from pmod.data.politician_trades import get_politician_trades_history

    trades = get_politician_trades_history(name)
    buy_count = sum(1 for t in trades if t.trade_type == "purchase")
    sell_count = sum(1 for t in trades if t.trade_type in ("sale", "sale_partial"))
    chamber = trades[0].chamber if trades else ""

    cs = {"fontSize": "12px", "color": COLORS["text_secondary"], "padding": "8px 12px", "borderBottom": f"1px solid {COLORS['border']}", "verticalAlign": "middle"}
    csr = {**cs, "textAlign": "right", "fontFamily": MONO}

    rows = []
    for t in trades:
        amt = f"${t.amount_low:,} – ${t.amount_high:,}" if t.amount_low and t.amount_high else "Undisclosed"
        date_str = t.disclosure_date.strftime("%b %d, %Y") if t.disclosure_date else "N/A"
        link_url = t.report_url or _senate_search_url(name)
        rows.append(html.Tr([
            html.Td(date_str, style=cs),
            html.Td(html.Span(t.ticker, style={"fontFamily": MONO, "fontWeight": "600", "color": COLORS["accent"]}), style=cs),
            html.Td(_ticker_button(t.ticker, t.company_name or t.ticker), style=cs),
            html.Td(_trade_type_badge(t.trade_type), style={**cs, "textAlign": "center"}),
            html.Td(amt, style={**csr, "fontSize": "11px"}),
            html.Td(_ext_link(link_url), style={**cs, "textAlign": "center"}),
        ]))

    hs = {"fontSize": "10px", "fontWeight": "600", "color": COLORS["text_tertiary"], "textTransform": "uppercase",
          "letterSpacing": "0.5px", "padding": "8px 12px", "borderBottom": f"1px solid {COLORS['border']}", "textAlign": "left"}

    return html.Div([
        # Stats strip
        html.Div(
            [
                html.Div([html.Div(str(len(trades)), style={"fontSize": "22px", "fontWeight": "700", "fontFamily": MONO, "color": COLORS["text_primary"]}), html.Div("total trades", style={"fontSize": "11px", "color": COLORS["text_tertiary"]})]),
                html.Div([html.Div(str(buy_count), style={"fontSize": "22px", "fontWeight": "700", "fontFamily": MONO, "color": COLORS["green"]}), html.Div("purchases", style={"fontSize": "11px", "color": COLORS["text_tertiary"]})]),
                html.Div([html.Div(str(sell_count), style={"fontSize": "22px", "fontWeight": "700", "fontFamily": MONO, "color": COLORS["red"]}), html.Div("sales", style={"fontSize": "11px", "color": COLORS["text_tertiary"]})]),
            ],
            style={"display": "flex", "gap": "28px", "padding": "16px 0", "borderBottom": f"1px solid {COLORS['border']}", "marginBottom": "16px"},
        ),
        # Trade history table
        html.Div(
            html.Table(
                [
                    html.Thead(html.Tr([html.Th("Date", style=hs), html.Th("Ticker", style=hs), html.Th("Company", style=hs), html.Th("Type", style={**hs, "textAlign": "center"}), html.Th("Amount", style={**hs, "textAlign": "right"}), html.Th("Filing", style={**hs, "textAlign": "center"})])),
                    html.Tbody(rows if rows else [html.Tr([html.Td("No trades on record", colSpan=6, style={**cs, "textAlign": "center", "fontStyle": "italic"})])]),
                ],
                style={"width": "100%", "borderCollapse": "collapse"},
            ),
            style={"background": COLORS["surface"], "border": f"1px solid {COLORS['border']}", "borderRadius": "10px", "overflow": "hidden"},
        ),
        # External link
        html.Div(
            _ext_link(_senate_search_url(name), f"View all {chamber} filings on efdsearch.senate.gov ↗"),
            style={"marginTop": "16px"},
        ),
    ])


def render_ticker_detail(ticker: str) -> html.Div:
    """Build the detail panel body for a company/ticker."""
    from pmod.data.politician_trades import get_politicians_for_ticker

    trades = get_politicians_for_ticker(ticker)
    buy_count = sum(1 for t in trades if t["trade_type"] == "purchase")
    sell_count = sum(1 for t in trades if t["trade_type"] in ("sale", "sale_partial"))
    unique_pols = len({t["politician_name"] for t in trades})

    cs = {"fontSize": "12px", "color": COLORS["text_secondary"], "padding": "8px 12px", "borderBottom": f"1px solid {COLORS['border']}", "verticalAlign": "middle"}
    hs = {"fontSize": "10px", "fontWeight": "600", "color": COLORS["text_tertiary"], "textTransform": "uppercase",
          "letterSpacing": "0.5px", "padding": "8px 12px", "borderBottom": f"1px solid {COLORS['border']}", "textAlign": "left"}

    rows = [
        html.Tr([
            html.Td(_pol_button(t["politician_name"]), style=cs),
            html.Td(html.Div([_party_badge(t["party"]), html.Span(f" {t['state']}", style={"fontSize": "11px", "color": COLORS["text_tertiary"], "marginLeft": "4px"})]), style=cs),
            html.Td(_trade_type_badge(t["trade_type"]), style={**cs, "textAlign": "center"}),
            html.Td(t["disclosure_date"], style={**cs, "fontFamily": MONO, "fontSize": "11px"}),
            html.Td(t["amount"], style={**cs, "fontFamily": MONO, "fontSize": "11px"}),
            html.Td(_ext_link(t["report_url"] or _senate_search_url(t["politician_name"])), style={**cs, "textAlign": "center"}),
        ])
        for t in trades
    ]

    return html.Div([
        html.Div(
            [
                html.Div([html.Div(str(unique_pols), style={"fontSize": "22px", "fontWeight": "700", "fontFamily": MONO, "color": COLORS["text_primary"]}), html.Div("members", style={"fontSize": "11px", "color": COLORS["text_tertiary"]})]),
                html.Div([html.Div(str(buy_count), style={"fontSize": "22px", "fontWeight": "700", "fontFamily": MONO, "color": COLORS["green"]}), html.Div("purchases", style={"fontSize": "11px", "color": COLORS["text_tertiary"]})]),
                html.Div([html.Div(str(sell_count), style={"fontSize": "22px", "fontWeight": "700", "fontFamily": MONO, "color": COLORS["red"]}), html.Div("sales", style={"fontSize": "11px", "color": COLORS["text_tertiary"]})]),
            ],
            style={"display": "flex", "gap": "28px", "padding": "16px 0", "borderBottom": f"1px solid {COLORS['border']}", "marginBottom": "16px"},
        ),
        html.Div(
            html.Table(
                [
                    html.Thead(html.Tr([html.Th("Member", style=hs), html.Th("Party / State", style=hs), html.Th("Type", style={**hs, "textAlign": "center"}), html.Th("Date", style=hs), html.Th("Amount", style=hs), html.Th("Filing", style={**hs, "textAlign": "center"})])),
                    html.Tbody(rows if rows else [html.Tr([html.Td("No trades on record for this ticker", colSpan=6, style={**cs, "textAlign": "center", "fontStyle": "italic"})])]),
                ],
                style={"width": "100%", "borderCollapse": "collapse"},
            ),
            style={"background": COLORS["surface"], "border": f"1px solid {COLORS['border']}", "borderRadius": "10px", "overflow": "hidden"},
        ),
    ])


# ── Detail drawer shell (always in DOM) ───────────────────────────────────

def _detail_drawer() -> html.Div:
    """Fixed right-side drawer that holds politician/company detail."""
    return html.Div(
        [
            # Semi-transparent backdrop
            html.Div(
                id="congress-panel-backdrop",
                n_clicks=0,
                style={
                    "position": "fixed", "inset": "0",
                    "background": "rgba(0,0,0,0.55)",
                    "zIndex": "1100", "cursor": "pointer",
                },
            ),
            # Drawer panel
            html.Div(
                [
                    # Header
                    html.Div(
                        [
                            html.Div(id="congress-panel-title", style={"fontSize": "16px", "fontWeight": "600", "color": COLORS["text_primary"]}),
                            html.Span("✕", id="congress-panel-close", n_clicks=0, style={"fontSize": "18px", "color": COLORS["text_tertiary"], "cursor": "pointer", "padding": "4px 8px"}),
                        ],
                        style={"display": "flex", "justifyContent": "space-between", "alignItems": "center",
                               "padding": "20px 24px", "borderBottom": f"1px solid {COLORS['border']}"},
                    ),
                    # Body (scrollable)
                    html.Div(
                        id="congress-panel-body",
                        style={"padding": "20px 24px", "overflowY": "auto", "flex": "1"},
                    ),
                ],
                style={
                    "position": "fixed", "top": "0", "right": "0",
                    "width": "min(680px, 95vw)", "height": "100vh",
                    "background": COLORS["surface_elevated"],
                    "borderLeft": f"1px solid {COLORS['border_accent']}",
                    "zIndex": "1101",
                    "display": "flex", "flexDirection": "column",
                    "boxShadow": "-8px 0 32px rgba(0,0,0,0.4)",
                },
            ),
        ],
        id="congress-detail-container",
        style={"display": "none"},
    )


# ── KPI row ────────────────────────────────────────────────────────────────

def _kpi_row(politicians: list[dict], recent: list[dict]) -> html.Div:
    from pmod.research.politician_signals import get_signals
    try:
        signals = get_signals()
        strong_buys = sum(1 for s in signals if s.signal == "strong_buy")
        sells = sum(1 for s in signals if s.signal == "sell")
    except Exception:
        strong_buys, sells = 0, 0

    total_trades = sum(p["total_trades"] for p in politicians) if politicians else len(recent)
    members = len(politicians) if politicians else 0

    def _kpi(label: str, value: str, color: str | None = None) -> html.Div:
        return html.Div(
            [
                html.Div(value, style={"fontSize": "28px", "fontWeight": "700", "fontFamily": MONO, "color": COLORS.get(color, COLORS["text_primary"]) if color else COLORS["text_primary"]}),
                html.Div(label, style={"fontSize": "11px", "color": COLORS["text_tertiary"], "marginTop": "4px"}),
            ],
            style={"background": COLORS["surface_elevated"], "border": f"1px solid {COLORS['border']}", "borderRadius": "12px", "padding": "18px 24px", "flex": "1"},
        )

    return html.Div(
        [
            _kpi("Members Tracked", str(members) if members else "—"),
            _kpi("Trades (365d)", str(total_trades) if total_trades else "—"),
            _kpi("Strong Buy Signals", str(strong_buys), "green" if strong_buys else None),
            _kpi("Sell Signals", str(sells), "red" if sells else None),
        ],
        style={"display": "flex", "gap": "12px", "marginBottom": "24px"},
    )


# ── Disclaimer ─────────────────────────────────────────────────────────────

def _disclaimer() -> html.Div:
    return html.Div(
        "Data sourced from public STOCK Act disclosures via efdsearch.senate.gov. "
        "House PTR data not yet available (individual filings are PDFs only). "
        "Disclosures may lag actual trades by up to 45 days. "
        "This is not financial advice.",
        style={"fontSize": "11px", "color": COLORS["text_tertiary"], "background": COLORS["surface"],
               "border": f"1px solid {COLORS['border']}", "borderRadius": "8px", "padding": "12px 16px",
               "marginTop": "24px", "lineHeight": "1.6"},
    )


# ── Sample fallback data ───────────────────────────────────────────────────

_SAMPLE_SIGNALS = [
    {"ticker": "NVDA", "company": "NVIDIA Corporation", "signal": "strong_buy", "confidence": 0.87, "buy_count": 23, "sell_count": 3, "politicians": 18, "rationale": "18 members of Congress strongly favoured NVDA (23 purchases, 3 sales — 88% buys). Heavy bipartisan buying concentrated in the last 30 days."},
    {"ticker": "LMT", "company": "Lockheed Martin Corp.", "signal": "strong_buy", "confidence": 0.81, "buy_count": 19, "sell_count": 4, "politicians": 14, "rationale": "14 members of Congress strongly favoured LMT (19 purchases, 4 sales — 83% buys). Defense committee members buying ahead of supplemental appropriations."},
    {"ticker": "MSFT", "company": "Microsoft Corporation", "signal": "buy", "confidence": 0.61, "buy_count": 31, "sell_count": 14, "politicians": 27, "rationale": "27 members net bought MSFT (31 purchases, 14 sales — 69% buys). Broad-based accumulation across party lines."},
    {"ticker": "CVX", "company": "Chevron Corporation", "signal": "sell", "confidence": 0.58, "buy_count": 4, "sell_count": 17, "politicians": 13, "rationale": "13 members net sold CVX (4 purchases, 17 sales — 19% buys). Energy committee members reducing ahead of potential carbon regulation."},
]

_SAMPLE_RECENT = [
    {"date": "2026-03-21", "politician": "Nancy Pelosi", "ticker": "NVDA", "company": "NVIDIA Corporation", "type": "purchase", "amount": "$500,001 – $1,000,000"},
    {"date": "2026-03-20", "politician": "Tommy Tuberville", "ticker": "LMT", "company": "Lockheed Martin Corp.", "type": "purchase", "amount": "$100,001 – $250,000"},
    {"date": "2026-03-19", "politician": "Josh Gottheimer", "ticker": "MSFT", "company": "Microsoft Corporation", "type": "purchase", "amount": "$50,001 – $100,000"},
    {"date": "2026-03-18", "politician": "Mark Kelly", "ticker": "GOOGL", "company": "Alphabet Inc.", "type": "sale", "amount": "$250,001 – $500,000"},
    {"date": "2026-03-17", "politician": "Michael McCaul", "ticker": "CVX", "company": "Chevron Corporation", "type": "sale", "amount": "$15,001 – $50,000"},
    {"date": "2026-03-15", "politician": "Jon Ossoff", "ticker": "NVDA", "company": "NVIDIA Corporation", "type": "purchase", "amount": "$50,001 – $100,000"},
]

_SAMPLE_POLITICIANS = [
    {"name": "Nancy Pelosi", "chamber": "house", "party": "D", "state": "CA", "buy_count": 38, "sell_count": 9, "total_trades": 47, "unique_tickers": 22, "latest_date": None},
    {"name": "Tommy Tuberville", "chamber": "senate", "party": "R", "state": "AL", "buy_count": 31, "sell_count": 6, "total_trades": 37, "unique_tickers": 18, "latest_date": None},
    {"name": "Josh Gottheimer", "chamber": "house", "party": "D", "state": "NJ", "buy_count": 28, "sell_count": 4, "total_trades": 32, "unique_tickers": 15, "latest_date": None},
    {"name": "Mark Kelly", "chamber": "senate", "party": "D", "state": "AZ", "buy_count": 12, "sell_count": 14, "total_trades": 26, "unique_tickers": 12, "latest_date": None},
    {"name": "Michael McCaul", "chamber": "house", "party": "R", "state": "TX", "buy_count": 9, "sell_count": 16, "total_trades": 25, "unique_tickers": 10, "latest_date": None},
    {"name": "Jon Ossoff", "chamber": "senate", "party": "D", "state": "GA", "buy_count": 19, "sell_count": 5, "total_trades": 24, "unique_tickers": 14, "latest_date": None},
]


# ── Page layout ────────────────────────────────────────────────────────────

def politician_trades_layout() -> html.Div:
    """Return the full politician trades page layout with live or sample data."""
    from pmod.data.politician_trades import get_all_politician_summaries, get_recent_trades
    from pmod.research.politician_signals import get_signals

    try:
        db_politicians = get_all_politician_summaries(days=365)
        db_recent_raw = get_recent_trades(days=90)
        db_signals = get_signals()
        is_live = bool(db_politicians or db_recent_raw)
    except Exception:
        db_politicians, db_recent_raw, db_signals, is_live = [], [], [], False

    # Build signals list
    if db_signals:
        signals = [
            {"ticker": s.ticker, "company": s.company_name or s.ticker, "signal": s.signal,
             "confidence": s.confidence, "buy_count": s.buy_count, "sell_count": s.sell_count,
             "politicians": s.unique_politicians, "rationale": s.rationale or ""}
            for s in db_signals
        ]
    else:
        signals = _SAMPLE_SIGNALS

    # Build recent trades list
    if db_recent_raw:
        recent = []
        for t in db_recent_raw[:20]:
            amt = f"${t.amount_low:,} – ${t.amount_high:,}" if t.amount_low and t.amount_high else "Undisclosed"
            recent.append({
                "date": t.disclosure_date.strftime("%Y-%m-%d") if t.disclosure_date else "N/A",
                "politician": t.politician_name,
                "ticker": t.ticker,
                "company": t.company_name or t.ticker,
                "type": t.trade_type,
                "amount": amt,
            })
    else:
        recent = _SAMPLE_RECENT

    politicians = db_politicians if db_politicians else _SAMPLE_POLITICIANS

    data_badge = html.Span(
        "● LIVE DATA" if is_live else "● SAMPLE DATA",
        style={"fontSize": "10px", "fontWeight": "700",
               "color": COLORS["green"] if is_live else COLORS["orange"],
               "background": COLORS["green_bg"] if is_live else COLORS["orange_bg"],
               "padding": "3px 10px", "borderRadius": "100px", "letterSpacing": "1px", "marginBottom": "16px", "display": "inline-block"},
    )

    return html.Div([
        data_badge,
        _kpi_row(db_politicians, db_recent_raw),
        section_header("Congressional Trade Signals", subtitle="Recommendations derived from STOCK Act disclosures — last 90 days"),
        html.Div([_signal_card(item) for item in signals],
                 style={"display": "grid", "gridTemplateColumns": "repeat(auto-fill, minmax(420px, 1fr))", "gap": "16px", "marginTop": "16px", "marginBottom": "32px"}),

        section_header("All Members", subtitle=f"{len(politicians)} tracked — click a name to view their trading history"),
        html.Div(style={"height": "12px"}),
        _members_table(politicians),

        html.Div(style={"height": "28px"}),
        section_header("Recent Disclosures", subtitle="Latest trades filed — click a company to see who traded it"),
        html.Div(style={"height": "12px"}),
        _recent_trades_table(recent),

        _disclaimer(),
        _detail_drawer(),
    ])
