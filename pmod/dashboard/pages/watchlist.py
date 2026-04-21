"""Curated picks and watchlist view — Bloomberg meets Apple.

Reads from the WatchlistItem table first; falls back to demo data when
the DB is empty (e.g. before the first ``pmod research run``).
"""
from __future__ import annotations

import structlog
from dash import html

from pmod.dashboard.components import COLORS, MONO, section_header, status_badge

log = structlog.get_logger()


def _load_picks() -> list[dict]:
    """Load watchlist items from the DB and enrich with live signals.

    Returns a list of pick dicts ready for ``_pick_card()``.  Falls back
    to a small set of demo picks when the DB is empty.
    """
    try:
        from pmod.data.models import WatchlistItem, get_session

        with get_session() as session:
            items = session.query(WatchlistItem).order_by(
                WatchlistItem.momentum_score.desc().nullslast()
            ).all()

        if not items:
            return _demo_picks()

        # Build politician signal lookup
        pol_data: dict[str, dict] = {}
        try:
            from pmod.research.politician_signals import get_signals
            for sig in get_signals():
                pol_data[sig.ticker] = {
                    "signal": sig.signal,
                    "confidence": sig.confidence,
                }
        except Exception:
            pass

        picks: list[dict] = []
        for item in items:
            mom = int(((item.momentum_score or 0) + 1.0) * 50)  # map [-1,1] → [0,100]
            mom = max(0, min(100, mom))

            pol = pol_data.get(item.ticker, {})
            pol_signal = pol.get("signal", "")
            sentiment_map = {
                "strong_buy": ("Very Bullish", "green"),
                "buy": ("Bullish", "green"),
                "hold": ("Neutral", "neutral"),
                "sell": ("Bearish", "red"),
            }
            sentiment_text, sentiment_var = sentiment_map.get(
                pol_signal, ("—", "neutral")
            )

            picks.append({
                "ticker": item.ticker,
                "name": item.company_name or item.ticker,
                "price": "—",
                "change": "—",
                "change_positive": True,
                "momentum": mom,
                "valuation": "—",
                "valuation_variant": "neutral",
                "sentiment": sentiment_text,
                "sentiment_variant": sentiment_var,
                "reason": item.reason or "Added to watchlist.",
                "tags": [],
            })

        # Try to enrich with live quotes — parallel, 3-second hard cap.
        # Quotes are cosmetic; any slowness or rate-limit just shows "—".
        try:
            import httpx
            from concurrent.futures import ThreadPoolExecutor, as_completed

            from pmod.config import get_settings

            api_key = get_settings().polygon_api_key

            def _fetch_quote(ticker: str) -> tuple[str, dict | None]:
                if not api_key:
                    return ticker, None
                try:
                    from pmod.utils.retry import polygon_limiter
                    polygon_limiter.acquire()
                    # Snapshot endpoint gives today's price and true day-change %
                    # (today's close vs previous close), unlike /prev which only
                    # has the prior session's bar and would compute open→close.
                    resp = httpx.get(
                        f"https://api.polygon.io/v2/snapshot/locale/us/markets/stocks/tickers/{ticker}",
                        params={"apiKey": api_key},
                        timeout=2.5,
                    )
                    resp.raise_for_status()
                    ticker_data = resp.json().get("ticker", {})
                    if not ticker_data:
                        return ticker, None
                    price = float(ticker_data.get("day", {}).get("c", 0) or ticker_data.get("lastTrade", {}).get("p", 0))
                    change_pct = float(ticker_data.get("todaysChangePerc", 0))
                    if not price:
                        return ticker, None
                    return ticker, {"price": price, "change_pct": round(change_pct, 2)}
                except Exception:
                    return ticker, None

            enrich_picks = picks[:5]
            with ThreadPoolExecutor(max_workers=5) as pool:
                futures = {pool.submit(_fetch_quote, p["ticker"]): p for p in enrich_picks}
                for future in as_completed(futures, timeout=3.0):
                    try:
                        ticker, data = future.result()
                        if data:
                            pick = futures[future]
                            pick["price"] = f"${data['price']:,.2f}"
                            sign = "+" if data["change_pct"] >= 0 else ""
                            pick["change"] = f"{sign}{data['change_pct']:.1f}%"
                            pick["change_positive"] = data["change_pct"] >= 0
                    except Exception:
                        pass
        except Exception as exc:
            log.debug("watchlist_quote_enrich_failed", error=str(exc)[:60])

        return picks

    except Exception as exc:
        log.warning("watchlist_db_load_failed", error=str(exc)[:80])
        return _demo_picks()


def _demo_picks() -> list[dict]:
    """Hardcoded demo picks shown before the first research pass."""
    return [
        {
            "ticker": "NVDA", "name": "NVIDIA Corp.",
            "price": "—", "change": "—", "change_positive": True,
            "momentum": 85, "valuation": "Premium", "valuation_variant": "orange",
            "sentiment": "Very Bullish", "sentiment_variant": "green",
            "reason": "Run `pmod research run` to generate personalised picks. "
                      "This is demo data showing the card layout.",
            "tags": ["Demo"],
        },
    ]


def _momentum_bar(score: int) -> html.Div:
    """Render a horizontal momentum score bar."""
    if score >= 80:
        color = COLORS["green"]
    elif score >= 60:
        color = COLORS["accent"]
    else:
        color = COLORS["orange"]

    return html.Div(
        [
            html.Div(
                [
                    html.Span("Momentum", style={
                        "fontSize": "11px",
                        "color": COLORS["text_tertiary"],
                        "textTransform": "uppercase",
                        "letterSpacing": "0.5px",
                    }),
                    html.Span(str(score), style={
                        "fontSize": "13px",
                        "fontWeight": "600",
                        "fontFamily": MONO,
                        "color": color,
                    }),
                ],
                style={
                    "display": "flex",
                    "justifyContent": "space-between",
                    "marginBottom": "6px",
                },
            ),
            html.Div(
                html.Div(
                    style={
                        "width": f"{score}%",
                        "height": "4px",
                        "background": f"linear-gradient(90deg, {color}, {color}88)",
                        "borderRadius": "2px",
                        "transition": "width 0.8s ease",
                    },
                ),
                style={
                    "width": "100%",
                    "height": "4px",
                    "background": COLORS["surface_hover"],
                    "borderRadius": "2px",
                },
            ),
        ],
    )


def _pick_card(pick: dict) -> html.Div:  # type: ignore[type-arg]
    """Render a single curated pick card."""
    change_color = COLORS["green"] if pick["change_positive"] else COLORS["red"]

    return html.Div(
        [
            # Header row — ticker + price
            html.Div(
                [
                    html.Div(
                        [
                            html.Span(pick["ticker"], style={
                                "fontSize": "20px",
                                "fontWeight": "700",
                                "color": COLORS["text_primary"],
                                "letterSpacing": "-0.3px",
                            }),
                            html.Span(pick["change"], style={
                                "fontSize": "13px",
                                "fontWeight": "600",
                                "fontFamily": MONO,
                                "color": change_color,
                                "marginLeft": "10px",
                            }),
                        ],
                        style={"display": "flex", "alignItems": "baseline"},
                    ),
                    html.Span(pick["price"], style={
                        "fontSize": "16px",
                        "fontWeight": "500",
                        "fontFamily": MONO,
                        "color": COLORS["text_primary"],
                    }),
                ],
                style={
                    "display": "flex",
                    "justifyContent": "space-between",
                    "alignItems": "baseline",
                },
            ),
            html.Div(pick["name"], style={
                "fontSize": "13px",
                "color": COLORS["text_tertiary"],
                "marginTop": "2px",
            }),

            # Divider
            html.Hr(style={
                "border": "none",
                "borderTop": f"1px solid {COLORS['border']}",
                "margin": "14px 0",
            }),

            # Why it fits
            html.Div(
                [
                    html.Div("Why this fits you", style={
                        "fontSize": "11px",
                        "fontWeight": "600",
                        "color": COLORS["text_tertiary"],
                        "textTransform": "uppercase",
                        "letterSpacing": "0.8px",
                        "marginBottom": "6px",
                    }),
                    html.P(pick["reason"], style={
                        "fontSize": "13px",
                        "lineHeight": "1.55",
                        "color": COLORS["text_secondary"],
                        "margin": "0",
                    }),
                ],
            ),

            # Signals row
            html.Div(
                [
                    _momentum_bar(pick["momentum"]),
                    html.Div(
                        [
                            html.Div(
                                [
                                    html.Span("Valuation", style={
                                        "fontSize": "11px",
                                        "color": COLORS["text_tertiary"],
                                        "marginRight": "8px",
                                    }),
                                    status_badge(pick["valuation"], pick["valuation_variant"]),
                                ],
                                style={"display": "flex", "alignItems": "center"},
                            ),
                            html.Div(
                                [
                                    html.Span("Sentiment", style={
                                        "fontSize": "11px",
                                        "color": COLORS["text_tertiary"],
                                        "marginRight": "8px",
                                    }),
                                    status_badge(pick["sentiment"], pick["sentiment_variant"]),
                                ],
                                style={
                                    "display": "flex",
                                    "alignItems": "center",
                                    "marginTop": "8px",
                                },
                            ),
                        ],
                        style={"marginTop": "12px"},
                    ),
                ],
                style={"marginTop": "14px"},
            ),

            # Tags
            html.Div(
                [
                    html.Span(tag, style={
                        "fontSize": "11px",
                        "color": COLORS["text_tertiary"],
                        "background": COLORS["surface_hover"],
                        "padding": "3px 10px",
                        "borderRadius": "100px",
                        "fontWeight": "500",
                    })
                    for tag in pick["tags"]
                ],
                style={
                    "display": "flex",
                    "gap": "6px",
                    "flexWrap": "wrap",
                    "marginTop": "14px",
                },
            ),

            # Action buttons
            html.Div(
                [
                    html.Button(
                        "Add to Portfolio",
                        id={"type": "watchlist-buy", "ticker": pick["ticker"], "name": pick["name"], "price": pick["price"]},
                        n_clicks=0,
                        style={
                            "flex": "1",
                            "padding": "10px",
                            "fontSize": "13px",
                            "fontWeight": "600",
                            "color": COLORS["text_primary"],
                            "background": COLORS["accent"],
                            "border": "none",
                            "borderRadius": "10px",
                            "cursor": "pointer",
                        },
                    ),
                    html.Button(
                        "Dismiss",
                        id={"type": "watchlist-dismiss", "ticker": pick["ticker"]},
                        n_clicks=0,
                        style={
                            "padding": "10px 20px",
                            "fontSize": "13px",
                            "fontWeight": "500",
                            "color": COLORS["text_tertiary"],
                            "background": COLORS["surface_hover"],
                            "border": f"1px solid {COLORS['border']}",
                            "borderRadius": "10px",
                            "cursor": "pointer",
                        },
                    ),
                ],
                style={
                    "display": "flex",
                    "gap": "10px",
                    "marginTop": "16px",
                },
            ),
        ],
        style={
            "background": COLORS["surface"],
            "border": f"1px solid {COLORS['border']}",
            "borderRadius": "16px",
            "padding": "24px",
            "transition": "border-color 0.2s ease, box-shadow 0.2s ease",
        },
    )


def watchlist_layout() -> html.Div:
    """Return the watchlist page layout."""
    picks = _load_picks()

    # Pull user strategy/risk for the header badges
    try:
        from pmod.preferences.profile import load_preferences_dict

        prefs = load_preferences_dict()
        strategy = prefs.get("strategy", "balanced").capitalize()
        risk = prefs.get("risk_tolerance", "medium").capitalize()
    except Exception:
        strategy, risk = "Balanced", "Medium"

    strategy_variant = {
        "Growth": "green", "Momentum": "green",
        "Value": "accent", "Dividend": "accent",
    }.get(strategy, "neutral")
    risk_variant = {
        "Low": "green", "Medium": "orange",
        "High": "red", "Degen": "red",
    }.get(risk, "neutral")

    return html.Div(
        [
            # Header with count
            html.Div(
                [
                    section_header(
                        "Watchlist",
                        f"{len(picks)} AI-curated opportunities",
                    ),
                    html.Div(
                        [
                            html.Span("Strategy: ", style={
                                "fontSize": "12px",
                                "color": COLORS["text_tertiary"],
                            }),
                            status_badge(strategy, strategy_variant),
                            html.Span(
                                " | Risk: ",
                                style={
                                    "fontSize": "12px",
                                    "color": COLORS["text_tertiary"],
                                    "marginLeft": "8px",
                                },
                            ),
                            status_badge(risk, risk_variant),
                        ],
                        style={
                            "display": "flex",
                            "alignItems": "center",
                            "marginBottom": "16px",
                        },
                    ),
                ],
            ),
            # Cards grid
            html.Div(
                [_pick_card(pick) for pick in picks],
                style={
                    "display": "grid",
                    "gridTemplateColumns": "repeat(auto-fill, minmax(380px, 1fr))",
                    "gap": "20px",
                },
            ),
        ]
    )
