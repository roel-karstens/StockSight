"""
charts.py – Plotly chart builders for the StockSight dashboard.
"""

import plotly.graph_objects as go
import pandas as pd

from ui.indicators import THRESHOLDS, METRIC_ORDER, evaluate, rating_color

# Consistent color palette for up to 5 tickers
TICKER_COLORS = [
    "#3b82f6",  # blue
    "#f97316",  # orange
    "#8b5cf6",  # purple
    "#06b6d4",  # cyan
    "#ec4899",  # pink
]


def build_metric_chart(
    metric_key: str,
    all_data: dict[str, pd.DataFrame],
) -> go.Figure:
    """
    Build a single Plotly chart for a given metric across multiple tickers.

    Args:
        metric_key: one of METRIC_ORDER keys
        all_data: dict of {symbol: metrics_df} from compute_all_metrics()

    Returns:
        A Plotly Figure
    """
    t = THRESHOLDS[metric_key]
    fig = go.Figure()

    all_years = set()

    for i, (symbol, df) in enumerate(all_data.items()):
        if metric_key not in df.columns:
            continue

        color = TICKER_COLORS[i % len(TICKER_COLORS)]
        years = df["year"]
        values = df[metric_key]
        all_years.update(years.tolist())

        fig.add_trace(
            go.Scatter(
                x=years,
                y=values,
                mode="lines+markers",
                name=symbol,
                line=dict(color=color, width=2.5),
                marker=dict(size=7),
                hovertemplate=f"<b>{symbol}</b><br>"
                + "Year: %{x}<br>"
                + f"{t['label']}: %{{y:.2f}}{t['unit']}"
                + "<extra></extra>",
            )
        )

    # Add threshold reference lines (skip for dcf_mos — handled separately)
    if all_years and metric_key != "dcf_mos":
        sorted_years = sorted(all_years)

        # Good threshold (green dashed)
        fig.add_hline(
            y=t["good"],
            line_dash="dash",
            line_color="#22c55e",
            line_width=1,
            opacity=0.6,
            annotation_text=f"Good: {t['good']}{t['unit']}",
            annotation_position="top left",
            annotation_font_color="#22c55e",
            annotation_font_size=10,
        )

        # Bad threshold (red dashed)
        fig.add_hline(
            y=t["bad"],
            line_dash="dash",
            line_color="#ef4444",
            line_width=1,
            opacity=0.6,
            annotation_text=f"Bad: {t['bad']}{t['unit']}",
            annotation_position="bottom left",
            annotation_font_color="#ef4444",
            annotation_font_size=10,
        )
    elif all_years and metric_key == "dcf_mos":
        # DCF: show fair value line at 0%, and shaded regions
        fig.add_hline(
            y=0,
            line_dash="solid",
            line_color="#6b7280",
            line_width=1.5,
            annotation_text="Fair Value",
            annotation_position="top left",
            annotation_font_color="#6b7280",
            annotation_font_size=10,
        )
        fig.add_hline(
            y=t["good"],
            line_dash="dash",
            line_color="#22c55e",
            line_width=1,
            opacity=0.5,
            annotation_text=f"Undervalued: +{t['good']}%",
            annotation_position="top left",
            annotation_font_color="#22c55e",
            annotation_font_size=10,
        )
        fig.add_hline(
            y=t["bad"],
            line_dash="dash",
            line_color="#ef4444",
            line_width=1,
            opacity=0.5,
            annotation_text=f"Overvalued: {t['bad']}%",
            annotation_position="bottom left",
            annotation_font_color="#ef4444",
            annotation_font_size=10,
        )

    fig.update_layout(
        title=dict(
            text=f"{t['label']} ({t['unit'] or '-'})",
            font=dict(size=16),
        ),
        xaxis_title="Fiscal Year",
        yaxis_title=f"{t['label']}",
        height=320,
        margin=dict(l=50, r=20, t=50, b=40),
        legend=dict(
            orientation="h",
            yanchor="bottom",
            y=1.02,
            xanchor="right",
            x=1,
            font=dict(size=11),
        ),
        hovermode="x unified",
        template="plotly_white",
    )

    return fig


def build_all_charts(all_data: dict[str, pd.DataFrame]) -> dict[str, go.Figure]:
    """Build all 6 metric charts. Returns dict of {metric_key: Figure}."""
    return {key: build_metric_chart(key, all_data) for key in METRIC_ORDER}
