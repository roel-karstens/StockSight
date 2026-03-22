"""
fetcher.py – Raw financial data fetching.

Combines StockAnalysis.com (financials/ratios) with yfinance (live price,
price history, ticker info) to produce a unified data dict for metrics.py.
"""

import pandas as pd
import yfinance as yf
import streamlit as st

from data.scraper import fetch_stockanalysis, _scrape_live_price


@st.cache_data(ttl=3600, show_spinner=False)
def fetch_yfinance(yf_symbol: str) -> dict:
    """
    Fetch yfinance data only: live price, price history, fiscal-year-end dates.

    This is safe to call from multiple threads in parallel (no rate limit needed).
    """
    ticker = yf.Ticker(yf_symbol)

    info: dict = {}
    try:
        info = ticker.info or {}
    except Exception:
        pass

    # Fallback: if .info failed (e.g. on Python 3.14), try fetching
    # market cap from fast_info so allocation at least gets cap data
    if not info.get("marketCap"):
        try:
            fi = ticker.fast_info
            info.setdefault("marketCap", int(getattr(fi, "market_cap", 0) or 0) or None)
        except Exception:
            pass

    history = ticker.history(period="10y", interval="1mo")

    yf_income_raw = ticker.financials
    if yf_income_raw is not None and not yf_income_raw.empty:
        yf_income = yf_income_raw.T.sort_index()
    else:
        yf_income = pd.DataFrame()

    return {
        "info": info,
        "history": history,
        "yf_income": yf_income,
    }


def combine_data(slug: str, yf_symbol: str, sa_data: dict, yf_data: dict) -> dict:
    """
    Merge StockAnalysis and yfinance data into the unified format.

    Called after both sources have been fetched (possibly in parallel).
    """
    info = yf_data["info"]

    # If yfinance has no live price, fall back to SA scrape
    if not info.get("currentPrice") and not info.get("regularMarketPrice"):
        live = _scrape_live_price(slug)
        if live:
            info["currentPrice"] = live

    return {
        "income": sa_data["income"],
        "balance": sa_data["balance"],
        "cashflow": sa_data["cashflow"],
        "ratios": sa_data.get("ratios", pd.DataFrame()),
        "info": info,
        "history": yf_data["history"],
        "yf_income": yf_data["yf_income"],
        "symbol": sa_data.get("symbol", yf_symbol.upper()),
        "source": "combined",
    }


@st.cache_data(ttl=3600, show_spinner=False)
def fetch_combined(slug: str, yf_symbol: str) -> dict:
    """
    Fetch financial data from both sources and merge (sequential fallback).

    For parallel fetching, use fetch_yfinance + fetch_stockanalysis + combine_data
    separately in app.py.
    """
    sa_data = fetch_stockanalysis(slug)
    yf_data = fetch_yfinance(yf_symbol)
    return combine_data(slug, yf_symbol, sa_data, yf_data)


@st.cache_data(ttl=3600, show_spinner=False)
def fetch_financials(symbol: str) -> dict:
    """
    Fetch all raw financial data for a ticker symbol.

    Returns a dict with keys:
        - 'income': annual income statement (DataFrame, rows=years, cols=line items)
        - 'balance': annual balance sheet
        - 'cashflow': annual cash flow statement
        - 'info': ticker info dict
        - 'history': 10-year monthly price history
        - 'symbol': the ticker symbol
    """
    ticker = yf.Ticker(symbol)

    # Fetch financial statements – yfinance returns columns as dates, rows as line items
    # We transpose so rows=dates (fiscal years) and sort ascending
    income = ticker.financials
    balance = ticker.balance_sheet
    cashflow = ticker.cashflow

    if income is None or income.empty:
        raise ValueError(f"No financial data found for ticker '{symbol}'")

    income = income.T.sort_index()
    balance = balance.T.sort_index() if balance is not None and not balance.empty else pd.DataFrame()
    cashflow = cashflow.T.sort_index() if cashflow is not None and not cashflow.empty else pd.DataFrame()

    # Price history (10 years, monthly) for PE / PEG calculations
    history = ticker.history(period="10y", interval="1mo")

    # Ticker info (contains current PE, PEG, market cap, etc.)
    try:
        info = ticker.info
    except Exception:
        info = {}

    return {
        "income": income,
        "balance": balance,
        "cashflow": cashflow,
        "info": info,
        "history": history,
        "symbol": symbol.upper(),
        "source": "yfinance",
    }


def validate_ticker(symbol: str) -> bool:
    """Check if a ticker symbol is valid by attempting a quick fetch."""
    try:
        ticker = yf.Ticker(symbol)
        info = ticker.info
        # yfinance returns info even for invalid tickers, but with limited fields
        return info is not None and info.get("regularMarketPrice") is not None
    except Exception:
        return False
