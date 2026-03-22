"""
scraper.py – Financial data scraping from stockanalysis.com.

Fetches income statement, balance sheet, cash flow, and ratios pages,
parses HTML tables, and returns data in the common format used by metrics.py.
"""

import re
import time
import threading

import pandas as pd
import requests
import streamlit as st
from bs4 import BeautifulSoup

BASE_URL = "https://stockanalysis.com"
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    ),
}
REQUEST_DELAY = 2.0  # seconds between requests (SA rate-limits aggressively)
REQUEST_TIMEOUT = 15  # seconds

# Global rate limiter – ensures minimum delay between ANY two SA requests,
# even when called from multiple threads.
_request_lock = threading.Lock()
_last_request_time = 0.0


def _rate_limited_get(url: str) -> requests.Response:
    """Thread-safe rate-limited GET request to StockAnalysis."""
    global _last_request_time
    with _request_lock:
        now = time.monotonic()
        elapsed = now - _last_request_time
        if elapsed < REQUEST_DELAY:
            time.sleep(REQUEST_DELAY - elapsed)
        _last_request_time = time.monotonic()
    return requests.get(url, headers=HEADERS, timeout=REQUEST_TIMEOUT)


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
    _NAN = float("nan")
    if not text:
        return _NAN
    text = text.strip()
    if text in ("-", "—", "–", "N/A", "n/a", ""):
        return _NAN

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
        return _NAN


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
    """Fetch a single page with error handling, rate limiting, and retry on 403/429."""
    max_retries = 3
    for attempt in range(max_retries):
        try:
            resp = _rate_limited_get(url)
            resp.raise_for_status()
            return resp.text
        except requests.exceptions.HTTPError as e:
            status = e.response.status_code if e.response is not None else 0
            if status in (403, 429) and attempt < max_retries - 1:
                # Rate limited or blocked – back off and retry
                backoff = 10 * (attempt + 1)  # 10s, 20s
                time.sleep(backoff)
                continue
            raise
    return ""  # unreachable but satisfies type checker


# ---------------------------------------------------------------------------
# Live price scraping
# ---------------------------------------------------------------------------

def _scrape_live_price(slug: str) -> float | None:
    """Scrape the current live stock price from the main StockAnalysis page."""
    if "/" in slug:
        url = f"{BASE_URL}/quote/{slug}/"
    else:
        url = f"{BASE_URL}/stocks/{slug}/"
    try:
        resp = _rate_limited_get(url)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "html.parser")
        # Price is in the first div with 'text-4xl' in its class
        tag = soup.find("div", class_=re.compile(r"text-4xl"))
        if tag:
            match = re.search(r"[\d,]+\.\d+", tag.get_text(strip=True))
            if match:
                return float(match.group().replace(",", ""))
    except Exception:
        pass
    return None


# ---------------------------------------------------------------------------
# URL construction
# ---------------------------------------------------------------------------

def _build_urls(slug: str) -> dict[str, str]:
    """
    Build the 4 financial page URLs from a StockAnalysis slug.

    US stocks (no slash):   slug="MSFT"     → /stocks/MSFT/financials/...
    International (slash):  slug="tsx/CSU"   → /quote/tsx/CSU/financials/...
    """
    if "/" in slug:
        # International: /quote/{exchange}/{ticker}/
        base = f"{BASE_URL}/quote/{slug}"
    else:
        # US stock: /stocks/{ticker}/
        base = f"{BASE_URL}/stocks/{slug}"

    return {
        "income": f"{base}/financials/",
        "balance": f"{base}/financials/balance-sheet/",
        "cashflow": f"{base}/financials/cash-flow-statement/",
        "ratios": f"{base}/financials/ratios/",
    }


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

@st.cache_data(ttl=3600, show_spinner=False)
def fetch_stockanalysis(slug: str) -> dict:
    """
    Scrape financial data from stockanalysis.com for a given ticker.

    Args:
        slug: StockAnalysis URL slug. US stocks: "MSFT".
              International: "tsx/CSU", "ams/ADYEN", "sto/EVO", etc.

    Fetches 4 pages: income statement, balance sheet, cash flow, ratios.
    Returns data in the common format compatible with compute_all_metrics().
    """
    pages = _build_urls(slug)

    raw_tables = {}
    for key, url in pages.items():
        html = _fetch_page(url)
        raw_tables[key] = _parse_financial_table(html)

    if not raw_tables.get("income"):
        raise ValueError(
            f"No financial data found for '{slug}' on StockAnalysis.com"
        )

    # Convert to DataFrames (rows=years, columns=financial line items)
    income_df = _dict_to_dataframe(raw_tables["income"])
    balance_df = _dict_to_dataframe(raw_tables["balance"])
    cashflow_df = _dict_to_dataframe(raw_tables["cashflow"])
    ratios_df = _dict_to_dataframe(raw_tables["ratios"])

    # Extract current price: prefer live scrape, fall back to most recent year
    info = {}
    live_price = _scrape_live_price(slug)
    time.sleep(REQUEST_DELAY)
    if live_price:
        info["currentPrice"] = live_price
    elif "Last Close Price" in raw_tables.get("ratios", {}):
        prices = raw_tables["ratios"]["Last Close Price"]
        # Filter to 4-digit year keys only (exclude "Period Ending", "TTM", etc.)
        year_keys = [k for k in prices if re.match(r"^\d{4}$", k)]
        if year_keys:
            latest = sorted(year_keys, reverse=True)[0]
            info["currentPrice"] = prices[latest]

    # Derive the display symbol from the slug
    display_symbol = slug.split("/")[-1].upper() if "/" in slug else slug.upper()

    return {
        "income": income_df,
        "balance": balance_df,
        "cashflow": cashflow_df,
        "ratios": ratios_df,
        "info": info,
        "history": pd.DataFrame(),  # Not available from scraping
        "symbol": display_symbol,
        "source": "stockanalysis",
    }
