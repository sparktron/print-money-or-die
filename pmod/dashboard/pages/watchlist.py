"""Curated picks and watchlist view."""

from dash import html


def watchlist_layout() -> html.Div:
    """Return the placeholder watchlist page layout."""
    return html.Div(
        [
            html.H2("Watchlist"),
            html.P("AI-curated investment opportunities will appear here."),
            html.Div(
                [
                    _placeholder_card("AAPL", "Apple Inc.", "Strong momentum + fits growth strategy"),
                    _placeholder_card("MSFT", "Microsoft Corp.", "Consistent earnings, low volatility"),
                    _placeholder_card("NVDA", "NVIDIA Corp.", "AI tailwind, high momentum score"),
                ],
                style={"display": "flex", "gap": "20px", "flexWrap": "wrap"},
            ),
        ]
    )


def _placeholder_card(ticker: str, name: str, reason: str) -> html.Div:
    """Render a single watchlist card."""
    return html.Div(
        [
            html.H3(f"{ticker}", style={"margin": "0 0 4px 0"}),
            html.P(name, style={"margin": "0 0 8px 0", "color": "gray"}),
            html.P(reason, style={"fontSize": "14px"}),
            html.Div(
                [
                    html.Button("Add to Portfolio", disabled=True),
                    html.Button("Ignore", disabled=True, style={"marginLeft": "8px"}),
                ],
                style={"marginTop": "10px"},
            ),
        ],
        style={
            "border": "1px solid #444",
            "borderRadius": "8px",
            "padding": "16px",
            "width": "280px",
        },
    )
