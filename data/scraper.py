"""
scraper.py – Financial data scraping from stockanalysis.com.

Fetches income statement, balance sheet, cash flow, and ratios pages,
parses HTML tables, and returns data in the common format used by metrics.py.
"""

import re
import time

import numpy as np
import pandas as pd
import requests
import streamlit as st
from bs4 import BeautifulSoup

BASE_URL = "https://stockanalysis.com/stocks"
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    ),
}
REQUEST_DELAY = 0.5  # seconds between requests
REQUEST_TIMEOUT = 15  # seconds


# ---------------------------------------------------------------------------
# Value parsing
# ---------------------------------------------------------------------------

def _parse_value(text: str) -> float:
    """Parse a formatted value string from stockanalysis.com to float.

    Examples:
        "35,425"   → 35425.0
        "68.59%"   → 68.59
        "-3.32%"   → -3.32
        "-"        → NaN
        "0"        → 0.0
        ""         → NaN
    """
    if not text:
        return np.nan
    text = text.strip()
    if text in ("-", "—", "–", "N/A", "n/a", ""):
        return np.nan

    # Remove percentage sign (we keep the numeric value, e.g., 68.59% → 68.59)
    text = text.replace("%", "")
    # Remove commas
    text = text.replace(",", "")
    # Handle parenthetical negatives: (123) → -123
    if text.startswith("(") and text.endswith(")"):
        text = "-" + text[1:-1]

    try:
        return float(text)
    except ValueError:
        return np.nan


# ---------------------------------------------------------------------------
# HTML table parsing
# ---------------------------------------------------------------------------

def _parse_financial_table(html: str) -> dict[str, dict[str, float]]:
    """
    Parse a stockanalysis.com financial data table from HTML.

    Returns:
        {row_label: {year_str: value, ...}, ...}
        Example: {"Revenue": {"2025": 305453.0, "2024": 281724.0, ...}}
    """
    soup = BeautifulSoup(html, "html.parser")

    # Find the main data table – it's typically inside a <table> tag
    table = soup.find("table")
    if table is None:
        return {}

    # Extract column headers (fiscal years)
    headers = []
    thead = table.find("thead")
    if thead:
        header_cells = thead.find_all("th")
        for cell in header_cells[1:]:  # skip first (row label column)
            text = cell.get_text(strip=True)
            # Extract year: might be "2025", "FY 2025", "Jun 2025", etc.
            year_match = re.search(r"(\d{4})", text)
            if year_match:
                headers.append(year_match.group(1))
            elif text and text.lower() not in ("current", "ttm"):
                headers.append(text)

    if not headers:
        return {}

    # Extract data rows
    data = {}
    tbody = table.find("tbody")
    rows = tbody.find_all("tr") if tbody else table.find_all("tr")[1:]

    for row in rows:
        cells = row.find_all(["td", "th"])
        if len(cells) < 2:
            continue

        # First cell is the row label
        label = cells[0].get_text(strip=True)
        if not label:
            continue

        # Remaining cells are values, aligned with headers
        row_data = {}
        for j, cell in enumerate(cells[1:]):
            if j < len(headers):
                row_data[headers[j]] = _parse_value(cell.get_text(strip=True))

        data[label] = row_data

    return data


def _dict_to_dataframe(data: dict[str, dict[str, float]]) -> pd.DataFrame:
    """Convert parsed table dict to DataFrame with years as index, labels as columns."""
    if not data:
        return pd.DataFrame()

    df = pd.DataFrame(data)
    # Index is year strings – filter to only valid 4-digit years
    # (removes "Period Ending", "Current", "TTM", etc.)
    df = df[df.index.str.match(r"^\d{4}$", na=False)]
    df.index.name = "year"
    # Sort ascending
    df = df.sort_index()
    return df


# ---------------------------------------------------------------------------
# Page fetching
# ---------------------------------------------------------------------------

def _fetch_page(url: str) -> str:
    """Fetch a single page with error handling and rate limiting."""
    try:
        resp = requests.get(url, headers=HEADERS, timeout=REQUEST_TIMEOUT)
        resp.raise_for_status()
        return resp.text
    except requests.exceptions.HTTPError as e:
        if e.response is not None and e.response.status_code == 429:
            # Rate limited – retry once after delay
            time.sleep(3)
            resp = requests.get(url, headers=HEADERS, timeout=REQUEST_TIMEOUT)
            resp.raise_for_status()
            return resp.text
        raise
    except requests.exceptions.RequestException:
        raise


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

@st.cache_data(ttl=3600, show_spinner=False)
def fetch_stockanalysis(symbol: str) -> dict:
    """
    Scrape financial data from stockanalysis.com for a given ticker.

    Fetches 4 pages: income statement, balance sheet, cash flow, ratios.
    Returns data in the common format compatible with compute_all_metrics().
    """
    symbol_lower = symbol.lower()
    pages = {
        "income": f"{BASE_URL}/{symbol_lower}/financials/",
        "balance": f"{BASE_URL}/{symbol_lower}/financials/balance-sheet/",
        "cashflow": f"{BASE_URL}/{symbol_lower}/financials/cash-flow-statement/",
        "ratios": f"{BASE_URL}/{symbol_lower}/financials/ratios/",
    }

    raw_tables = {}
    for key, url in pages.items():
        html = _fetch_page(url)
        raw_tables[key] = _parse_financial_table(html)
        time.sleep(REQUEST_DELAY)

    if not raw_tables.get("income"):
        raise ValueError(
            f"No financial data found for ticker '{symbol}' on StockAnalysis.com"
        )

    # Convert to DataFrames (rows=years, columns=financial line items)
    income_df = _dict_to_dataframe(raw_tables["income"])
    balance_df = _dict_to_dataframe(raw_tables["balance"])
    cashflow_df = _dict_to_dataframe(raw_tables["cashflow"])
    ratios_df = _dict_to_dataframe(raw_tables["ratios"])

    # Extract some info-level fields from ratios for DCF
    info = {}
    if "Last Close Price" in raw_tables.get("ratios", {}):
        prices = raw_tables["ratios"]["Last Close Price"]
        # Get the most recent year's price
        sorted_years = sorted(prices.keys(), reverse=True)
        if sorted_years:
            info["currentPrice"] = prices[sorted_years[0]]

    return {
        "income": income_df,
        "balance": balance_df,
        "cashflow": cashflow_df,
        "ratios": ratios_df,
        "info": info,
        "history": pd.DataFrame(),  # Not available from scraping
        "symbol": symbol.upper(),
        "source": "stockanalysis",
    }
