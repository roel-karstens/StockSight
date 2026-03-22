"""
charts.py – Plotly chart builders for the StockSight dashboard.
"""

import plotly.express as px
import plotly.graph_objects as go
import pandas as pd

from ui.indicators import THRESHOLDS, METRIC_ORDER, evaluate, rating_color

# Consistent color palette for up to 20 tickers
TICKER_COLORS = [
    "#3b82f6",  # blue
    "#f97316",  # orange
    "#8b5cf6",  # purple
    "#06b6d4",  # cyan
    "#ec4899",  # pink
    "#10b981",  # emerald
    "#f59e0b",  # amber
    "#ef4444",  # red
    "#6366f1",  # indigo
    "#14b8a6",  # teal
    "#f472b6",  # rose
    "#84cc16",  # lime
    "#a855f7",  # violet
    "#22d3ee",  # sky
    "#fb923c",  # orange-light
    "#4ade80",  # green-light
    "#c084fc",  # purple-light
    "#facc15",  # yellow
    "#2dd4bf",  # teal-light
    "#e879f9",  # fuchsia
]


def build_stock_price_chart(
    all_data: dict[str, pd.DataFrame],
) -> go.Figure:
    """
    Build a stock price chart with a single shared Y-axis.

    All tickers share one USD axis. Hover shows individual prices.
    """
    fig = go.Figure()

    for i, (symbol, df) in enumerate(all_data.items()):
        if "stock_price" not in df.columns:
            continue

        color = TICKER_COLORS[i % len(TICKER_COLORS)]
        x_vals = df.index  # actual datetime values
        values = df["stock_price"]
        labels = df["year"]  # formatted date strings for hover

        fig.add_trace(
            go.Scatter(
                x=x_vals,
                y=values,
                mode="lines+markers",
                name=symbol,
                line=dict(color=color, width=2.5),
                marker=dict(size=7),
                customdata=labels,
                hovertemplate=f"<b>{symbol}</b><br>"
                + "Date: %{customdata}<br>"
                + "Price: $%{y:.2f}"
                + "<extra></extra>",
            )
        )

    fig.update_layout(
        xaxis_title="Fiscal Year",
        yaxis_title="Price ($)",
        height=380,
        margin=dict(l=60, r=60, t=30, b=40),
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


def build_metric_chart(
    metric_key: str,
    all_data: dict[str, pd.DataFrame],
) -> go.Figure:
    """
    Build a single Plotly chart for a given metric across multiple tickers.
    """
    t = THRESHOLDS[metric_key]
    has_thresholds = t["good"] is not None and t["bad"] is not None
    fig = go.Figure()

    all_years = set()

    for i, (symbol, df) in enumerate(all_data.items()):
        if metric_key not in df.columns:
            continue

        color = TICKER_COLORS[i % len(TICKER_COLORS)]
        x_vals = df.index  # actual datetime values
        values = df[metric_key]
        labels = df["year"]  # formatted date strings for hover
        all_years.update(x_vals.tolist())

        fig.add_trace(
            go.Scatter(
                x=x_vals,
                y=values,
                mode="lines+markers",
                name=symbol,
                line=dict(color=color, width=2.5),
                marker=dict(size=7),
                customdata=labels,
                hovertemplate=f"<b>{symbol}</b><br>"
                + "Date: %{customdata}<br>"
                + f"{t['label']}: %{{y:.2f}}{t['unit']}"
                + "<extra></extra>",
            )
        )

    # Add threshold reference lines only for metrics that have them
    if all_years and has_thresholds and metric_key != "dcf_mos":
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
        fig.add_hline(
            y=0, line_dash="solid", line_color="#6b7280", line_width=1.5,
            annotation_text="Fair Value", annotation_position="top left",
            annotation_font_color="#6b7280", annotation_font_size=10,
        )
        fig.add_hline(
            y=t["good"], line_dash="dash", line_color="#22c55e", line_width=1,
            opacity=0.5, annotation_text=f"Undervalued: +{t['good']}%",
            annotation_position="top left", annotation_font_color="#22c55e",
            annotation_font_size=10,
        )
        fig.add_hline(
            y=t["bad"], line_dash="dash", line_color="#ef4444", line_width=1,
            opacity=0.5, annotation_text=f"Overvalued: {t['bad']}%",
            annotation_position="bottom left", annotation_font_color="#ef4444",
            annotation_font_size=10,
        )

    fig.update_layout(
        xaxis_title="Fiscal Year",
        yaxis_title=f"{t['label']}",
        height=320,
        margin=dict(l=50, r=20, t=30, b=40),
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
    """Build all metric charts. Returns dict of {metric_key: Figure}."""
    charts = {}
    for key in METRIC_ORDER:
        if key == "stock_price":
            charts[key] = build_stock_price_chart(all_data)
        else:
            charts[key] = build_metric_chart(key, all_data)
    return charts


# ---------------------------------------------------------------------------
# Allocation treemaps
# ---------------------------------------------------------------------------

# Soft, muted colour palettes for each treemap dimension
_COUNTRY_COLORS = px.colors.qualitative.Pastel
_SECTOR_COLORS = px.colors.qualitative.Set3
_CAP_COLORS = {
    "Mega Cap": "#3b82f6",   # blue
    "Large Cap": "#06b6d4",  # cyan
    "Mid Cap": "#f59e0b",    # amber
    "Small Cap": "#ef4444",  # red
    "Unknown": "#9ca3af",    # gray
}


def _build_treemap(
    df: pd.DataFrame,
    parent_col: str,
    title: str,
    color_sequence: list[str] | None = None,
    color_map: dict[str, str] | None = None,
    path_cols: list[str] | None = None,
) -> go.Figure:
    """
    Build a single Plotly treemap.

    Parameters
    ----------
    df : DataFrame with at least columns: ticker, <parent_col>, weight, cap_label
    parent_col : column name used as the top-level colour grouping
    title : chart title (root node label)
    color_sequence : discrete colour sequence (for country/sector)
    color_map : explicit colour map (for cap buckets)
    path_cols : ordered list of hierarchy columns ending with "ticker".
        Defaults to ``[parent_col, "ticker"]``.
    """
    if path_cols is None:
        path_cols = [parent_col, "ticker"]

    kwargs = dict(
        data_frame=df,
        path=[px.Constant(title)] + path_cols,
        values="weight",
        color=parent_col,
        custom_data=["ticker", parent_col, "weight", "cap_label"],
        hover_data={"weight": ":.1f"},
    )

    if color_map:
        kwargs["color_discrete_map"] = {"(?)": "#e5e7eb", **color_map}
    elif color_sequence:
        kwargs["color_discrete_sequence"] = color_sequence

    fig = px.treemap(**kwargs)

    fig.update_traces(
        hovertemplate=(
            "<b>%{customdata[0]}</b><br>"
            "%{customdata[1]}<br>"
            "Weight: %{customdata[2]:.1f}%<br>"
            "Market Cap: %{customdata[3]}"
            "<extra></extra>"
        ),
        textinfo="label+percent parent",
        textfont_size=13,
    )

    fig.update_layout(
        margin=dict(l=5, r=5, t=35, b=5),
        height=420,
    )

    return fig


def build_allocation_treemaps(
    alloc_df: pd.DataFrame,
) -> dict[str, go.Figure]:
    """
    Build three treemaps: by country, sector, and cap size.

    Parameters
    ----------
    alloc_df : DataFrame from ``data.allocation.build_allocation_df``

    Returns
    -------
    dict with keys ``"country"``, ``"sector"``, ``"cap"`` → Figure
    """
    if alloc_df.empty:
        return {}

    return {
        "country": _build_treemap(
            alloc_df,
            parent_col="country",
            title="Country",
            color_sequence=_COUNTRY_COLORS,
        ),
        "sector": _build_treemap(
            alloc_df,
            parent_col="sector",
            title="Sector / Industry",
            color_sequence=_SECTOR_COLORS,
            path_cols=["sector", "industry", "ticker"],
        ),
        "cap": _build_treemap(
            alloc_df,
            parent_col="cap_bucket",
            title="Cap Size",
            color_map=_CAP_COLORS,
        ),
    }
