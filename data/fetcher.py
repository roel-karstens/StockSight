"""
fetcher.py – Raw financial data fetching via yfinance.

Fetches income statements, balance sheets, cash flow statements,
price history, and ticker info for a given symbol.
"""

import pandas as pd
import yfinance as yf
import streamlit as st


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
