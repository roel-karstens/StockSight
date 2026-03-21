"""
StockSight – Stock Financial Health Dashboard

Entry point: streamlit run app.py
"""

import streamlit as st
import pandas as pd

from data.fetcher import fetch_financials
from data.scraper import fetch_stockanalysis
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

# ---------------------------------------------------------------------------
# Sidebar
# ---------------------------------------------------------------------------

with st.sidebar:
    st.title("📈 StockSight")
    st.caption("Stock Financial Health Dashboard")
    st.divider()

    # Search / add ticker
    new_ticker = st.text_input(
        "Add a ticker symbol",
        placeholder="e.g. MSFT, AAPL, GOOG",
        key="ticker_input",
    ).upper().strip()

    col_add, col_clear = st.columns(2)
    with col_add:
        add_clicked = st.button("➕ Add", use_container_width=True)
    with col_clear:
        clear_clicked = st.button("🗑️ Clear All", use_container_width=True)

    if add_clicked and new_ticker:
        if len(st.session_state.tickers) >= 5:
            st.warning("Maximum 5 tickers for comparison.")
        elif new_ticker in st.session_state.tickers:
            st.warning(f"{new_ticker} is already added.")
        else:
            st.session_state.tickers.append(new_ticker)
            st.rerun()

    if clear_clicked:
        st.session_state.tickers = []
        st.rerun()

    # Show active tickers with remove buttons
    if st.session_state.tickers:
        st.subheader("Active Tickers")
        for ticker in st.session_state.tickers:
            col_name, col_remove = st.columns([3, 1])
            with col_name:
                st.write(f"**{ticker}**")
            with col_remove:
                if st.button("✕", key=f"remove_{ticker}"):
                    st.session_state.tickers.remove(ticker)
                    st.rerun()

    st.divider()

    # Data source selector
    data_source = st.radio(
        "Data Source",
        options=["StockAnalysis.com", "Yahoo Finance"],
        index=0,
        help="StockAnalysis.com provides ~6 years of data with pre-calculated ratios. Yahoo Finance provides 3–4 years of raw data.",
    )

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
    st.info("👈 Add a ticker symbol in the sidebar to get started. Try **MSFT**, **AAPL**, or **GOOG**.")
    st.stop()

# ---------------------------------------------------------------------------
# Fetch data and compute metrics for all tickers
# ---------------------------------------------------------------------------

all_data: dict[str, pd.DataFrame] = {}
errors: list[str] = []

with st.spinner(f"Fetching financial data from {data_source}..."):
    for symbol in st.session_state.tickers:
        try:
            if data_source == "StockAnalysis.com":
                raw = fetch_stockanalysis(symbol)
            else:
                raw = fetch_financials(symbol)
            metrics_df = compute_all_metrics(raw, years=years)

            if metrics_df.empty:
                errors.append(f"⚠️ No financial data available for **{symbol}**")
            else:
                all_data[symbol] = metrics_df
        except Exception as e:
            errors.append(f"❌ Error fetching **{symbol}**: {e}")

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
