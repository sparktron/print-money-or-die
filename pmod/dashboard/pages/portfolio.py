"""Portfolio performance view."""

from dash import dcc, html
import plotly.graph_objects as go


def portfolio_layout() -> html.Div:
    """Return the placeholder portfolio page layout."""
    fig = go.Figure()
    fig.add_trace(
        go.Scatter(
            x=["2024-01", "2024-02", "2024-03", "2024-04"],
            y=[10000, 10250, 10180, 10500],
            mode="lines+markers",
            name="Portfolio Value",
        )
    )
    fig.update_layout(
        title="Portfolio Performance (sample data)",
        xaxis_title="Date",
        yaxis_title="Value ($)",
        template="plotly_dark",
    )

    return html.Div(
        [
            html.H2("Portfolio"),
            dcc.Graph(id="portfolio-chart", figure=fig),
            html.H3("Positions"),
            html.Table(
                [
                    html.Thead(
                        html.Tr(
                            [
                                html.Th("Ticker"),
                                html.Th("Shares"),
                                html.Th("Cost Basis"),
                                html.Th("Current Value"),
                                html.Th("Gain/Loss"),
                            ]
                        )
                    ),
                    html.Tbody(
                        [
                            html.Tr(
                                [
                                    html.Td("—"),
                                    html.Td("—"),
                                    html.Td("—"),
                                    html.Td("—"),
                                    html.Td("—"),
                                ]
                            )
                        ]
                    ),
                ],
                style={"width": "100%", "borderCollapse": "collapse"},
            ),
            html.P(
                "Connect your Schwab account to see real positions.",
                style={"color": "gray", "marginTop": "10px"},
            ),
        ]
    )
