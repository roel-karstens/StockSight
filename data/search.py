"""
search.py – Ticker search and cross-source symbol resolution.

Provides autocomplete search via StockAnalysis.com API and yfinance Search,
plus deterministic exchange-suffix mapping so tickers work across both sources.
"""

import requests
import streamlit as st

# ---------------------------------------------------------------------------
# Exchange mapping: StockAnalysis slug ↔ yfinance suffix
# ---------------------------------------------------------------------------

EXCHANGE_MAP = {
    # SA slug : yfinance suffix
    "tsx": ".TO",       # Toronto Stock Exchange
    "tsxv": ".V",       # TSX Venture Exchange
    "ams": ".AS",       # Euronext Amsterdam
    "sto": ".ST",       # Stockholm (Nasdaq Nordic)
    "asx": ".AX",       # Australian Securities Exchange
    "fra": ".F",        # Frankfurt Stock Exchange
    "lon": ".L",        # London Stock Exchange
    "epa": ".PA",       # Euronext Paris
    "nze": ".NZ",       # New Zealand Exchange
    "bit": ".MI",       # Borsa Italiana (Milan)
    "hel": ".HE",       # Helsinki (Nasdaq Nordic)
    "bvmf": ".SA",      # B3 (Brazil)
    "swx": ".SW",       # SIX Swiss Exchange
    "vie": ".VI",       # Vienna Stock Exchange
    "otc": "",          # OTC Markets (Pink Sheets)
    "snse": ".SN",      # Santiago Stock Exchange
    "wse": ".WA",       # Warsaw Stock Exchange
    "bcba": ".BA",      # Buenos Aires Stock Exchange
    "ksc": ".KS",       # Korea Stock Exchange
    "koe": ".KS",       # Korea Exchange (alias)
    "hkse": ".HK",      # Hong Kong Stock Exchange
    "sse": ".SS",       # Shanghai Stock Exchange
    "szse": ".SZ",      # Shenzhen Stock Exchange
    "tse": ".T",        # Tokyo Stock Exchange
    "nse": ".NS",       # National Stock Exchange of India
    "bse": ".BO",       # Bombay Stock Exchange
}

# Reverse map: yfinance suffix → SA slug (built from EXCHANGE_MAP)
_REVERSE_MAP = {v: k for k, v in EXCHANGE_MAP.items() if v}

SA_SEARCH_URL = "https://stockanalysis.com/api/search"
SA_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    ),
}


# ---------------------------------------------------------------------------
# Cross-source symbol conversion
# ---------------------------------------------------------------------------

def sa_slug_to_yf_symbol(slug: str) -> str:
    """Convert SA slug 'tsx/CSU' → yfinance symbol 'CSU.TO'.

    US stocks (no slash): 'MSFT' → 'MSFT'.
    SA uses dots in tickers (LIFCO.B), yfinance uses dashes (LIFCO-B).
    """
    if "/" not in slug:
        return slug  # US stock
    exchange, ticker = slug.split("/", 1)
    suffix = EXCHANGE_MAP.get(exchange.lower(), "")
    return ticker.replace(".", "-") + suffix


def yf_symbol_to_sa_slug(symbol: str) -> str:
    """Convert yfinance symbol 'CSU.TO' → SA slug 'tsx/CSU'.

    US stocks (no matching suffix): 'MSFT' → 'MSFT'.
    yfinance uses dashes (LIFCO-B), SA uses dots (LIFCO.B).
    """
    # Try matching longest suffix first to avoid partial matches
    for yf_suffix in sorted(_REVERSE_MAP, key=len, reverse=True):
        if yf_suffix and symbol.endswith(yf_suffix):
            ticker = symbol[: -len(yf_suffix)]
            sa_exchange = _REVERSE_MAP[yf_suffix]
            return f"{sa_exchange}/{ticker.replace('-', '.')}"
    return symbol  # US stock


def _extract_exchange_label(slug: str) -> str:
    """Extract human-readable exchange label from SA slug.

    'tsx/CSU' → 'TSX', 'MSFT' → '' (US).
    """
    if "/" in slug:
        return slug.split("/", 1)[0].upper()
    return ""


# ---------------------------------------------------------------------------
# Search functions
# ---------------------------------------------------------------------------

@st.cache_data(ttl=300, show_spinner=False)
def _search_stockanalysis(query: str) -> list[dict]:
    """Search StockAnalysis.com API for matching tickers."""
    try:
        resp = requests.get(
            SA_SEARCH_URL,
            params={"q": query},
            headers=SA_HEADERS,
            timeout=10,
        )
        resp.raise_for_status()
        data = resp.json().get("data", [])
    except Exception:
        return []

    results = []
    for item in data:
        # Must have an 's' (slug) field
        slug = item.get("s", "")
        if not slug:
            continue

        # Filter: stocks only (st='s' or t='s' for US stocks)
        item_type = item.get("st", item.get("t", ""))
        if item_type not in ("s",):
            # US stocks have t='s' and no 'st' field
            if item.get("t") != "s":
                continue

        name = item.get("n", slug)
        exchange = _extract_exchange_label(slug)
        ticker = slug.split("/")[-1] if "/" in slug else slug

        if exchange:
            display = f"{name} ({exchange}:{ticker})"
        else:
            display = f"{name} ({ticker})"

        results.append({
            "display": display,
            "symbol": ticker,
            "slug": slug,
            "yf_symbol": sa_slug_to_yf_symbol(slug),
            "exchange": exchange,
            "name": name,
        })

    return results[:8]


@st.cache_data(ttl=300, show_spinner=False)
def _search_yfinance(query: str) -> list[dict]:
    """Search yfinance for matching tickers."""
    try:
        from yfinance.search import Search as YFSearch
        search = YFSearch(query, max_results=10)
        quotes = search.quotes
    except Exception:
        return []

    results = []
    for q in quotes:
        # Filter: equities only
        if q.get("quoteType") != "EQUITY":
            continue

        symbol = q.get("symbol", "")
        if not symbol:
            continue

        name = q.get("longname") or q.get("shortname") or symbol
        exch_disp = q.get("exchDisp", "")

        if exch_disp:
            display = f"{name} ({exch_disp}: {symbol})"
        else:
            display = f"{name} ({symbol})"

        results.append({
            "display": display,
            "symbol": symbol.split(".")[0] if "." in symbol else symbol,
            "slug": yf_symbol_to_sa_slug(symbol),
            "yf_symbol": symbol,
            "exchange": exch_disp,
            "name": name,
        })

    return results[:8]


def search_tickers(query: str, source: str = "stockanalysis") -> list[tuple[str, dict]]:
    """
    Search for tickers matching the query.

    Returns list of (display_label, ticker_dict) tuples for st_searchbox.
    The ticker_dict contains all fields needed for both data sources.
    """
    if not query or len(query) < 1:
        return []

    if source == "stockanalysis":
        results = _search_stockanalysis(query)
    else:
        results = _search_yfinance(query)

    if not results:
        return []

    return [(r["display"], r) for r in results]
