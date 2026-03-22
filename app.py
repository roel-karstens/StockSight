"""
StockSight – Stock Financial Health Dashboard

Entry point: streamlit run app.py
"""

from concurrent.futures import ThreadPoolExecutor, as_completed

import streamlit as st
import pandas as pd

from streamlit_searchbox import st_searchbox

from data.fetcher import fetch_yfinance, combine_data
from data.scraper import fetch_stockanalysis
from data.portfolio import DEFAULT_PORTFOLIO
from data.search import search_tickers
from data.metrics import compute_all_metrics
from data.allocation import build_allocation_df
from ui.charts import build_all_charts, build_allocation_treemaps
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


def _load_portfolio():
    """Add default portfolio tickers, skipping duplicates and respecting the 20-ticker limit."""
    existing_slugs = {t["slug"] for t in st.session_state.tickers}
    added = 0
    skipped = 0
    for ticker in DEFAULT_PORTFOLIO:
        if len(st.session_state.tickers) >= 20:
            remaining = len(DEFAULT_PORTFOLIO) - added - skipped
            st.toast(f"⚠️ Hit 20-ticker limit. {remaining} stocks not added.")
            break
        if ticker["slug"] in existing_slugs:
            skipped += 1
            continue
        st.session_state.tickers.append(ticker)
        existing_slugs.add(ticker["slug"])
        added += 1
    if skipped:
        st.toast(f"✅ Loaded {added} portfolio stocks ({skipped} already active)")
    else:
        st.toast(f"✅ Loaded {added} portfolio stocks")


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

    if st.button("📋 Load Default Portfolio", use_container_width=True):
        _load_portfolio()
        st.rerun()

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
    st.info("👈 Search for a ticker in the sidebar to get started, or click **Load Default Portfolio**.")
    st.stop()

# ---------------------------------------------------------------------------
# Fetch data and compute metrics for all tickers
# ---------------------------------------------------------------------------

all_data: dict[str, pd.DataFrame] = {}
errors: list[str] = []

tickers = st.session_state.tickers
n = len(tickers)

with st.status(f"Fetching financial data for {n} stocks...", expanded=False) as status:
    # Phase 1: Fetch all yfinance data in parallel (no rate limit needed)
    status.update(label=f"Fetching price data (0/{n})...")
    yf_results: dict[str, dict] = {}
    yf_done = 0
    with ThreadPoolExecutor(max_workers=8) as pool:
        yf_futures = {
            pool.submit(fetch_yfinance, ti["yf_symbol"]): ti
            for ti in tickers
        }
        for future in as_completed(yf_futures):
            ti = yf_futures[future]
            try:
                yf_results[ti["slug"]] = future.result()
                yf_done += 1
                status.update(label=f"Fetching price data ({yf_done}/{n})...")
            except Exception as e:
                yf_done += 1
                errors.append(f"❌ Error fetching yfinance data for **{ti['display']}**: {e}")

    # Phase 2: Fetch SA data with rate limiting (global lock serialises requests)
    sa_results: dict[str, dict] = {}
    sa_done = 0
    status.update(label=f"Fetching financial statements (0/{n})...")
    with ThreadPoolExecutor(max_workers=2) as pool:
        sa_futures = {
            pool.submit(fetch_stockanalysis, ti["slug"]): ti
            for ti in tickers
        }
        for future in as_completed(sa_futures):
            ti = sa_futures[future]
            sa_done += 1
            try:
                sa_results[ti["slug"]] = future.result()
                status.update(label=f"Fetching financial statements ({sa_done}/{n})...")
            except Exception as e:
                status.update(label=f"Fetching financial statements ({sa_done}/{n})...")
                errors.append(f"❌ Error fetching **{ti['display']}**: {e}")

    # Phase 3: Combine and compute metrics
    status.update(label="Computing metrics...")
    ticker_infos: dict[str, dict] = {}  # symbol → yfinance info (for allocation)
    for ti in tickers:
        slug = ti["slug"]
        label = ti["symbol"]
        if slug not in sa_results or slug not in yf_results:
            continue
        try:
            raw = combine_data(slug, ti["yf_symbol"], sa_results[slug], yf_results[slug])
            df = compute_all_metrics(raw, years=years)
            if df.empty:
                errors.append(f"⚠️ No financial data available for **{ti['display']}**")
            else:
                all_data[label] = df
                ticker_infos[label] = yf_results[slug].get("info", {})
        except Exception as e:
            errors.append(f"❌ Error computing metrics for **{ti['display']}**: {e}")

    status.update(label=f"Done — loaded {len(all_data)}/{n} stocks.", state="complete")

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
    st.session_state.chart_filter = all_symbols[:3]
else:
    # Add any new tickers not yet in the filter (up to 3 shown by default)
    current = st.session_state.chart_filter
    for sym in all_symbols:
        if sym not in current and len(current) < 3:
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
# Dynamic height: 35px per data row + 45px for header/padding, so all rows visible without scrolling
scorecard_height = len(scorecard_df) * 35 + 45
st.dataframe(
    scorecard_df,
    width="stretch",
    height=scorecard_height,
    hide_index=True,
)

# ---------------------------------------------------------------------------
# Portfolio Allocation Treemaps
# ---------------------------------------------------------------------------

if len(ticker_infos) >= 2:
    st.divider()
    with st.expander("📊 Portfolio Allocation", expanded=False):
        # Filter out tickers with no useful info (e.g. yfinance .info failed)
        valid_infos = {
            sym: info for sym, info in ticker_infos.items()
            if info.get("country") or info.get("sector") or info.get("marketCap")
        }
        if len(valid_infos) >= 2:
            alloc_df = build_allocation_df(valid_infos)
            treemaps = build_allocation_treemaps(alloc_df)
            tm_cols = st.columns(3)
            for col, (key, label) in zip(
                tm_cols,
                [("country", "Country"), ("sector", "Sector / Industry"), ("cap", "Cap Size")],
            ):
                with col:
                    st.markdown(f"**{label}**")
                    st.plotly_chart(
                        treemaps[key],
                        key=f"treemap_{key}",
                        width="stretch",
                    )
            missing = len(ticker_infos) - len(valid_infos)
            if missing:
                st.caption(f"⚠️ {missing} ticker(s) excluded — no profile data available.")
        else:
            st.info("Profile data unavailable — allocation breakdown requires country/sector info from Yahoo Finance.")
