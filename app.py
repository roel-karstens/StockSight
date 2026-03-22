"""
StockSight – Stock Financial Health Dashboard

Entry point: streamlit run app.py
"""

import streamlit as st
import pandas as pd

from streamlit_searchbox import st_searchbox

from data.fetcher import fetch_combined
from data.search import search_tickers
from data.metrics import compute_all_metrics
from ui.charts import build_all_charts
from ui.indicators import (
    METRIC_ORDER,
    METRIC_FORMULAS,
    SCORECARD_EXCLUDE,
    THRESHOLDS,
    badge_html,
    evaluate,
    format_value,
    rating_emoji,
)

# ---------------------------------------------------------------------------
# Page config
# ---------------------------------------------------------------------------

st.set_page_config(
    page_title="StockSight",
    page_icon="📈",
    layout="wide",
)

# ---------------------------------------------------------------------------
# Session state initialization
# ---------------------------------------------------------------------------

if "tickers" not in st.session_state:
    st.session_state.tickers = []


def _migrate_ticker(ticker) -> dict:
    """Migrate plain-string tickers from old sessions to dict format."""
    if isinstance(ticker, dict):
        return ticker
    # Assume US stock for legacy plain strings
    return {
        "display": ticker,
        "symbol": ticker,
        "slug": ticker,
        "yf_symbol": ticker,
        "exchange": "",
        "name": ticker,
    }


# Auto-migrate any old-format tickers
st.session_state.tickers = [_migrate_ticker(t) for t in st.session_state.tickers]

# ---------------------------------------------------------------------------
# Sidebar
# ---------------------------------------------------------------------------

with st.sidebar:
    st.title("📈 StockSight")
    st.caption("Stock Financial Health Dashboard")
    st.divider()

    def _do_search(query: str) -> list[tuple[str, dict]]:
        return search_tickers(query, source="stockanalysis")

    def _on_select(ticker_info: dict) -> None:
        """Called when the user selects a ticker from the dropdown."""
        if not ticker_info or not isinstance(ticker_info, dict):
            return
        existing_slugs = {t["slug"] for t in st.session_state.tickers}
        if len(st.session_state.tickers) >= 20:
            st.toast("⚠️ Maximum 20 tickers for comparison.")
        elif ticker_info["slug"] in existing_slugs:
            st.toast(f"ℹ️ {ticker_info['display']} is already added.")
        else:
            st.session_state.tickers.append(ticker_info)

    # Autocomplete searchbox – selecting a result immediately adds the ticker
    st_searchbox(
        _do_search,
        placeholder="Search ticker or company name...",
        label="Add a ticker",
        clear_on_submit=True,
        debounce=200,
        key="ticker_search",
        submit_function=_on_select,
    )

    if st.button("🗑️ Clear All", use_container_width=True):
        st.session_state.tickers = []
        st.rerun()

    # Show active tickers with remove buttons
    if st.session_state.tickers:
        st.subheader("Active Tickers")
        for ticker_info in st.session_state.tickers:
            col_name, col_remove = st.columns([3, 1])
            with col_name:
                st.write(f"**{ticker_info['display']}**")
            with col_remove:
                if st.button("✕", key=f"remove_{ticker_info['slug']}"):
                    st.session_state.tickers.remove(ticker_info)
                    st.rerun()

    st.divider()

    # Time range
    years = st.slider("Years of history", min_value=3, max_value=10, value=5)
    st.caption("ℹ️ Up to 6 years of annual data, with today's live price.")

    st.divider()
    st.caption("Thresholds are configurable in `ui/indicators.py`")

# ---------------------------------------------------------------------------
# Main content
# ---------------------------------------------------------------------------

st.title("📈 StockSight")
st.markdown("Visual stock financial health analysis — search, compare, and evaluate.")

if not st.session_state.tickers:
    st.info("👈 Search for a ticker in the sidebar to get started. Try **MSFT**, **AAPL**, or **Constellation Software**.")
    st.stop()

# ---------------------------------------------------------------------------
# Fetch data and compute metrics for all tickers
# ---------------------------------------------------------------------------

all_data: dict[str, pd.DataFrame] = {}
errors: list[str] = []

with st.spinner("Fetching financial data..."):
    for ticker_info in st.session_state.tickers:
        label = ticker_info["symbol"]  # Short label for charts
        try:
            raw = fetch_combined(ticker_info["slug"], ticker_info["yf_symbol"])
            metrics_df = compute_all_metrics(raw, years=years)

            if metrics_df.empty:
                errors.append(f"⚠️ No financial data available for **{ticker_info['display']}**")
            else:
                all_data[label] = metrics_df
        except Exception as e:
            errors.append(f"❌ Error fetching **{ticker_info['display']}**: {e}")

# Show errors
for err in errors:
    st.warning(err)

if not all_data:
    st.error("No data could be loaded for any ticker. Please check the symbols and try again.")
    st.stop()

# ---------------------------------------------------------------------------
# Charts – 1 full-width + 3×3 grid
# ---------------------------------------------------------------------------

# Chart ticker filter – let user choose which tickers to show in charts
all_symbols = list(all_data.keys())

# Auto-update selection when tickers are added/removed
if "chart_filter" not in st.session_state:
    st.session_state.chart_filter = all_symbols[:8]
else:
    # Add any new tickers not yet in the filter (up to 8 shown by default)
    current = st.session_state.chart_filter
    for sym in all_symbols:
        if sym not in current and len(current) < 8:
            current.append(sym)
    # Remove tickers that no longer exist
    st.session_state.chart_filter = [s for s in current if s in all_symbols]

chart_filter = st.multiselect(
    "Show in charts:",
    options=all_symbols,
    key="chart_filter",
)

# Filter data for charts (scorecard always shows all)
chart_data = {s: df for s, df in all_data.items() if s in chart_filter}

if chart_data:
    charts = build_all_charts(chart_data)

    def _render_chart_cell(metric_key: str, charts: dict, data: dict):
        """Render a single chart cell: title + info popover, badges, chart."""
        t = THRESHOLDS[metric_key]
        # Title with compact info popover on the same line
        title_col, info_col = st.columns([8, 1], gap="small")
        with title_col:
            st.markdown(f"**{t['label']} ({t['unit'] or '-'})**")
        with info_col:
            with st.popover("ℹ️"):
                st.markdown(METRIC_FORMULAS.get(metric_key, "_No description available._"))
        # Badges (skip for stock_price — no rating)
        if metric_key not in SCORECARD_EXCLUDE:
            badges = []
            for symbol, df in data.items():
                if metric_key in df.columns and not df[metric_key].dropna().empty:
                    latest = df[metric_key].dropna().iloc[-1]
                    badges.append(badge_html(metric_key, symbol, latest))
            if badges:
                st.markdown(" &nbsp; ".join(badges))
        # Chart
        st.plotly_chart(charts[metric_key], key=f"chart_{metric_key}", width="stretch")

    # Row 1: Stock Price (full width)
    st.divider()
    _render_chart_cell("stock_price", charts, chart_data)

    # Row 2: Gross Margin, ROCE, LT Debt/FCF
    st.divider()
    row2_cols = st.columns(3)
    for i, key in enumerate(["gross_margin", "roce", "ltd_fcf"]):
        with row2_cols[i]:
            _render_chart_cell(key, charts, chart_data)

    # Row 3: Revenue Growth, FCF Growth, PE Ratio
    row3_cols = st.columns(3)
    for i, key in enumerate(["revenue_growth", "fcf_growth", "pe_ratio"]):
        with row3_cols[i]:
            _render_chart_cell(key, charts, chart_data)

    # Row 4: PEG Ratio, DCF MoS, Implied Growth
    row4_cols = st.columns(3)
    for i, key in enumerate(["peg_ratio", "dcf_mos", "implied_growth"]):
        with row4_cols[i]:
            _render_chart_cell(key, charts, chart_data)
else:
    st.info("Select at least one ticker in the chart filter above.")

# ---------------------------------------------------------------------------
# Summary Scorecard Table (always shows ALL tickers)
# ---------------------------------------------------------------------------

st.divider()
st.subheader("📊 Summary Scorecard")

# Build scorecard data
scorecard_metrics = [k for k in METRIC_ORDER if k not in SCORECARD_EXCLUDE]
scorecard_data = []
for symbol, df in all_data.items():
    row = {"Ticker": symbol}
    for metric_key in scorecard_metrics:
        label = THRESHOLDS[metric_key]["label"]
        if metric_key in df.columns and not df[metric_key].dropna().empty:
            latest = df[metric_key].dropna().iloc[-1]
            rating = evaluate(metric_key, latest)
            emoji = rating_emoji(rating)
            formatted = format_value(metric_key, latest)
            row[label] = f"{emoji} {formatted}"
        else:
            row[label] = "⚪ N/A"
    scorecard_data.append(row)

scorecard_df = pd.DataFrame(scorecard_data)
st.dataframe(
    scorecard_df,
    width="stretch",
    hide_index=True,
)
