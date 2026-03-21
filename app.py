"""
StockSight – Stock Financial Health Dashboard

Entry point: streamlit run app.py
"""

import streamlit as st
import pandas as pd

from streamlit_searchbox import st_searchbox

from data.fetcher import fetch_financials
from data.scraper import fetch_stockanalysis
from data.search import search_tickers
from data.metrics import compute_all_metrics
from ui.charts import build_all_charts
from ui.indicators import (
    METRIC_ORDER,
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

    # Data source selector (placed BEFORE search so search uses correct source)
    data_source = st.radio(
        "Data Source",
        options=["StockAnalysis.com", "Yahoo Finance"],
        index=0,
        help="StockAnalysis.com provides ~6 years of data with pre-calculated ratios. Yahoo Finance provides 3–4 years of raw data.",
    )

    st.divider()

    # Determine which search backend to use
    _search_source = "stockanalysis" if data_source == "StockAnalysis.com" else "yfinance"

    def _do_search(query: str) -> list[tuple[str, dict]]:
        return search_tickers(query, source=_search_source)

    def _on_select(ticker_info: dict) -> None:
        """Called when the user selects a ticker from the dropdown."""
        if not ticker_info or not isinstance(ticker_info, dict):
            return
        existing_slugs = {t["slug"] for t in st.session_state.tickers}
        if len(st.session_state.tickers) >= 5:
            st.toast("⚠️ Maximum 5 tickers for comparison.")
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
    if data_source == "Yahoo Finance":
        st.caption("ℹ️ Note: Yahoo Finance typically provides 3–4 years of annual data.")
    else:
        st.caption("ℹ️ StockAnalysis.com typically provides up to 6 years of annual data.")

    st.divider()
    st.caption(f"Data source: {data_source}")
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

with st.spinner(f"Fetching financial data from {data_source}..."):
    for ticker_info in st.session_state.tickers:
        label = ticker_info["symbol"]  # Short label for charts
        try:
            if data_source == "StockAnalysis.com":
                raw = fetch_stockanalysis(ticker_info["slug"])
            else:
                raw = fetch_financials(ticker_info["yf_symbol"])
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
# Charts – 2×3 grid
# ---------------------------------------------------------------------------

charts = build_all_charts(all_data)

# Row 1 (metrics 1-3)
row1_cols = st.columns(3)
for i, metric_key in enumerate(METRIC_ORDER[:3]):
    with row1_cols[i]:
        badges = []
        for symbol, df in all_data.items():
            if metric_key in df.columns and not df[metric_key].dropna().empty:
                latest = df[metric_key].dropna().iloc[-1]
                badges.append(badge_html(metric_key, symbol, latest))
        if badges:
            st.markdown(" &nbsp; ".join(badges))
        st.plotly_chart(charts[metric_key], key=f"chart_{metric_key}", width="stretch")

# Row 2 (metrics 4-6)
row2_cols = st.columns(3)
for i, metric_key in enumerate(METRIC_ORDER[3:6]):
    with row2_cols[i]:
        badges = []
        for symbol, df in all_data.items():
            if metric_key in df.columns and not df[metric_key].dropna().empty:
                latest = df[metric_key].dropna().iloc[-1]
                badges.append(badge_html(metric_key, symbol, latest))
        if badges:
            st.markdown(" &nbsp; ".join(badges))
        st.plotly_chart(charts[metric_key], key=f"chart_{metric_key}", width="stretch")

# Row 3 (DCF Margin of Safety – full width)
if "dcf_mos" in METRIC_ORDER:
    st.divider()
    st.subheader("💰 DCF Valuation")
    st.caption(
        "Margin of Safety = (Intrinsic Value − Market Price) / Market Price. "
        "Positive = undervalued. Uses 10% discount rate, 3% terminal growth, "
        "and FCF growth estimated from trailing data (clamped 2–30%)."
    )
    badges = []
    for symbol, df in all_data.items():
        if "dcf_mos" in df.columns and not df["dcf_mos"].dropna().empty:
            latest = df["dcf_mos"].dropna().iloc[-1]
            badges.append(badge_html("dcf_mos", symbol, latest))
    if badges:
        st.markdown(" &nbsp; ".join(badges))
    st.plotly_chart(charts["dcf_mos"], key="chart_dcf_mos", width="stretch")

# ---------------------------------------------------------------------------
# Summary Scorecard Table
# ---------------------------------------------------------------------------

st.divider()
st.subheader("📊 Summary Scorecard")

# Build scorecard data
scorecard_data = []
for symbol, df in all_data.items():
    row = {"Ticker": symbol}
    for metric_key in METRIC_ORDER:
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
