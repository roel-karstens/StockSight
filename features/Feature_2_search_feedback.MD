# Feature 2: Ticker Search Feedback & International Exchange Support

## 1. Summary

Replace the current free-text ticker input with an **autocomplete search** that queries both **StockAnalysis.com** and **yfinance** search APIs. When the user types a ticker or company name, they see a list of matching results showing the **company name, ticker symbol, and exchange**. Selecting a result stores the correct exchange-qualified identifier so that data fetching works seamlessly for international stocks (e.g. `tsx/CSU`, `ams/ADYEN`, `sto/EVO`).

---

## 2. Problem

International tickers don't resolve correctly with the current implementation:

| User types | Current behaviour | Expected behaviour |
|---|---|---|
| `CSU` | Tries `/stocks/csu/financials/` → wrong company or 404 | Search shows **Constellation Software (TSX:CSU)** → uses `/quote/tsx/CSU/financials/` |
| `ADYEN` | Tries `/stocks/adyen/financials/` → 404 | Search shows **Adyen N.V. (AMS:ADYEN)** → uses `/quote/ams/ADYEN/financials/` |
| `EVO` | Tries `/stocks/evo/financials/` → Evotec SE (US-listed) | Search shows **Evolution AB (STO:EVO)** alongside other EVO tickers |
| `KPG` | 404 or wrong stock | Search shows **Kelly Partners (ASX:KPG)** vs **Kiwi Property (NZE:KPG)** |
| `LIFCO` | 404 | Search shows **Lifco AB (STO:LIFCO.B)** |
| `MOHF` | 404 | Search shows **LVMH (FRA:MOHF)** |
| `ROKO` | 404 | Search shows **Röko AB (STO:ROKO.B)** |
| `TOI` | Tries `/stocks/toi/financials/` → The Oncology Institute (US) | Search shows **Topicus.com (TSXV:TOI)** alongside US TOI |
| `MSFT` | ✅ Works (US stock) | Still works — shown as **Microsoft Corporation (MSFT)** |

---

## 3. Data Sources for Search

### 3.1 StockAnalysis.com Search API

**Endpoint:** `GET https://stockanalysis.com/api/search?q={query}`

Returns JSON:
```json
{
  "status": 200,
  "data": [
    {"id": "TSX-CSU",  "s": "tsx/CSU",  "t": "sy", "n": "Constellation Software Inc.", "st": "s"},
    {"id": "MSFT",     "s": "MSFT",     "t": "s",  "n": "Microsoft Corporation"},
    {"id": "AMS-ADYEN","s": "ams/ADYEN","t": "sy", "n": "Adyen N.V.", "st": "s"}
  ]
}
```

**Key fields:**

| Field | Description | Example |
|---|---|---|
| `id` | Unique identifier | `TSX-CSU`, `MSFT` |
| `s` | URL slug — the path segment for constructing URLs | `tsx/CSU` (international), `MSFT` (US) |
| `t` | Type: `"s"` = US stock, `"sy"` = international/exchange-qualified | `s`, `sy` |
| `n` | Company name | `Constellation Software Inc.` |
| `st` | Security type: `"s"` = stock, `"e"` = ETF, `"m"` = mutual fund | `s` |

**URL construction from slug (`s` field):**
- US stocks (`t="s"`): `https://stockanalysis.com/stocks/{s}/financials/`
- International (`t="sy"`): `https://stockanalysis.com/quote/{s}/financials/`

### 3.2 yfinance Search API

**Class:** `yfinance.search.Search(query, max_results=10)`

Returns `.quotes` list:
```python
{
    "symbol": "CSU.TO",
    "shortname": "CONSTELLATION SOFTWARE INC.",
    "longname": "Constellation Software Inc.",
    "exchange": "TOR",
    "exchDisp": "Toronto",
    "quoteType": "EQUITY",
    "sector": "Technology",
    "industry": "Software—Application",
    "score": 20063.0,
    "isYahooFinance": True
}
```

**Key fields:**

| Field | Description | Example |
|---|---|---|
| `symbol` | Yahoo Finance ticker (with exchange suffix) | `CSU.TO`, `EVO.ST`, `ADYEN.AS` |
| `longname` / `shortname` | Company name | `Constellation Software Inc.` |
| `exchDisp` | Human-readable exchange name | `Toronto`, `Stockholm`, `Amsterdam` |
| `quoteType` | `EQUITY`, `ETF`, `MUTUALFUND`, `CRYPTOCURRENCY` | `EQUITY` |
| `score` | Relevance score | `20063.0` |

---

## 4. Exchange Mapping

International stocks live on specific exchanges. Here's the mapping for the user's example tickers:

| Company | SA Exchange Slug | SA URL Path | yfinance Symbol | yfinance Exchange |
|---|---|---|---|---|
| Constellation Software | `tsx/CSU` | `/quote/tsx/CSU/` | `CSU.TO` | Toronto |
| Adyen N.V. | `ams/ADYEN` | `/quote/ams/ADYEN/` | `ADYEN.AS` | Amsterdam |
| Evolution AB | `sto/EVO` | `/quote/sto/EVO/` | `EVO.ST` | Stockholm |
| Kelly Partners | `asx/KPG` | `/quote/asx/KPG/` | `KPG.AX` | Australian |
| Lifco AB | `sto/LIFCO.B` | `/quote/sto/LIFCO.B/` | `LIFCO-B.ST` | Stockholm |
| LVMH | `fra/MOHF` | `/quote/fra/MOHF/` | `MOHF.F` | Frankfurt |
| Röko AB | `sto/ROKO.B` | `/quote/sto/ROKO.B/` | `ROKO-B.ST` | Stockholm |
| Topicus.com | `tsxv/TOI` | `/quote/tsxv/TOI/` | `TOI.V` | CDNX |
| Microsoft (US) | `MSFT` | `/stocks/MSFT/` | `MSFT` | NMS |
| Apple (US) | `AAPL` | `/stocks/AAPL/` | `AAPL` | NMS |

---

## 5. Design

### 5.1 New Module: `data/search.py`

A search module that queries the appropriate API based on the active data source:

```python
def search_tickers(query: str, source: str = "stockanalysis") -> list[dict]:
    """
    Search for tickers matching the query.

    Returns list of dicts:
    [
        {
            "display":  "Constellation Software Inc. (TSX:CSU)",
            "symbol":   "CSU",          # raw ticker
            "slug":     "tsx/CSU",       # SA URL slug (only for SA source)
            "yf_symbol":"CSU.TO",        # yfinance symbol (only for yf source)
            "exchange": "TSX",           # exchange code
            "name":     "Constellation Software Inc.",
            "type":     "stock",         # stock | etf | mutualfund
            "source":   "stockanalysis", # which API provided this result
        },
        ...
    ]
    """
```

**StockAnalysis.com search path:**
1. `GET https://stockanalysis.com/api/search?q={query}`
2. Filter to `st == "s"` (stocks only, exclude ETFs and mutual funds)
3. Build display string: `"{name} ({EXCHANGE}:{TICKER})"` for international, `"{name} ({TICKER})"` for US
4. Store `s` field as `slug` for URL construction

**yfinance search path:**
1. `Search(query, max_results=8).quotes`
2. Filter to `quoteType == "EQUITY"` and `isYahooFinance == True`
3. Build display string: `"{longname} ({exchDisp}:{symbol})"`
4. Store `symbol` field as `yf_symbol`

**Caching:** Results are cached with `@st.cache_data(ttl=300)` (5-minute TTL — shorter than financial data since search is cheap).

### 5.2 Updated Sidebar UX

Replace the current `st.text_input` + `st.button("Add")` with a **real autocomplete searchbox** using the [`streamlit-searchbox`](https://github.com/m-wrzr/streamlit-searchbox) community component. As the user types, a dropdown appears with matching tickers — just like a search engine.

```
┌───────────────────────────────────────┐
│ 🔍 Search ticker or company name      │
│ ┌───────────────────────────────────┐ │
│ │ CSU                             ▾ │ │
│ ├───────────────────────────────────┤ │
│ │ Constellation Software (TSX:CSU)  │ │
│ │ CSU Digital S.A. (BVMF:CSUD3)    │ │
│ │ China Shenhua Energy (OTC:CSUAY)  │ │
│ └───────────────────────────────────┘ │
│                                       │
│ [➕ Add]                              │
└───────────────────────────────────────┘
```

**Component: `streamlit-searchbox` (`st_searchbox`)**

This provides a true type-ahead autocomplete dropdown. The user types, suggestions appear inline, and they click one to select it. No separate radio step needed.

```python
from streamlit_searchbox import st_searchbox

def search_tickers(query: str) -> list[tuple[str, dict]]:
    """Called on every keystroke (debounced). Returns (display_label, data_dict) tuples."""
    if not query:
        return []
    results = search_tickers_api(query, source=data_source)
    return [
        (
            r["display"],  # shown in dropdown: "Constellation Software Inc. (TSX:CSU)"
            r,             # full dict returned on selection
        )
        for r in results
    ]

selected = st_searchbox(
    search_tickers,
    placeholder="Search ticker or company name...",
    label="Add a ticker",
    clear_on_submit=True,
    debounce=200,  # ms – avoid spamming search API on fast typing
    key="ticker_search",
)

# selected is the full dict when the user picks a result, or None
if selected and st.button("➕ Add"):
    st.session_state.tickers.append(selected)
```

**Key `st_searchbox` settings:**

| Parameter | Value | Why |
|---|---|---|
| `clear_on_submit` | `True` | Clears the box after the user selects a result, ready for next search |
| `debounce` | `200` | Waits 200ms after typing stops before calling the search function |
| `rerun_on_update` | `True` (default) | Redraws the page to show new suggestions |

**New dependency:** `streamlit-searchbox>=0.1.24` added to `requirements.txt`.

### 5.3 Internal Ticker Representation

Currently, tickers are stored as plain strings (e.g. `"MSFT"`). After this feature, each ticker in `st.session_state.tickers` becomes a **dict**:

```python
{
    "display":   "Constellation Software Inc. (TSX:CSU)",
    "symbol":    "CSU",
    "slug":      "tsx/CSU",       # StockAnalysis.com URL slug
    "yf_symbol": "CSU.TO",        # yfinance symbol (resolved via cross-search or mapping)
    "exchange":  "TSX",
    "name":      "Constellation Software Inc.",
}
```

This means:
- The **sidebar** shows `display` (human-readable)
- The **StockAnalysis scraper** uses `slug` to construct URLs
- The **yfinance fetcher** uses `yf_symbol` to call `yf.Ticker()`
- **Charts** use `symbol` (short ticker) as the series label

### 5.4 Updated Scraper URL Construction

The scraper currently hard-codes `BASE_URL = "https://stockanalysis.com/stocks"`. This changes to:

```python
BASE_URL = "https://stockanalysis.com"

def _build_urls(slug: str) -> dict:
    """
    Build the 4 financial page URLs from a StockAnalysis slug.

    slug="MSFT"     -> /stocks/MSFT/financials/...
    slug="tsx/CSU"   -> /quote/tsx/CSU/financials/...
    """
    if "/" in slug:
        # International: /quote/{exchange}/{ticker}/
        base = f"{BASE_URL}/quote/{slug}"
    else:
        # US stock: /stocks/{ticker}/
        base = f"{BASE_URL}/stocks/{slug}"

    return {
        "income":   f"{base}/financials/",
        "balance":  f"{base}/financials/balance-sheet/",
        "cashflow": f"{base}/financials/cash-flow-statement/",
        "ratios":   f"{base}/financials/ratios/",
    }
```

`fetch_stockanalysis()` signature changes from `fetch_stockanalysis(symbol)` to `fetch_stockanalysis(slug)` — the slug is the path component from the search result's `s` field.

### 5.5 Updated yfinance Fetcher

`fetch_financials()` already accepts a symbol string. For international stocks, we now pass the full yfinance symbol (e.g. `CSU.TO` instead of `CSU`). No logic change needed in `fetcher.py` — just pass the correct symbol.

### 5.6 Cross-Source Symbol Resolution

When the user switches data sources, we need the symbol for the _other_ source. Name-based cross-search is **unreliable** (tested: searching yfinance for "Lifco AB" returns the Frankfurt listing first instead of Stockholm; "LVMH" returns `MC.PA` instead of `MOHF.F`; "Röko AB" returns nothing at all).

**Solution: Deterministic exchange suffix mapping**

Both sources use a predictable exchange identifier. We maintain a static mapping table to convert between them — no extra API calls needed.

```python
# SA exchange slug ↔ yfinance exchange suffix
EXCHANGE_MAP = {
    #  SA slug   yf suffix
    "tsx":      ".TO",     # Toronto Stock Exchange
    "tsxv":     ".V",      # TSX Venture Exchange
    "ams":      ".AS",     # Euronext Amsterdam
    "sto":      ".ST",     # Stockholm (Nasdaq Nordic)
    "asx":      ".AX",     # Australian Securities Exchange
    "fra":      ".F",      # Frankfurt Stock Exchange
    "lon":      ".L",      # London Stock Exchange
    "epa":      ".PA",     # Euronext Paris
    "nze":      ".NZ",     # New Zealand Exchange
    "bit":      ".MI",     # Borsa Italiana (Milan)
    "hel":      ".HE",     # Helsinki (Nasdaq Nordic)
    "bvmf":     ".SA",     # B3 (Brazil)
    "swx":      ".SW",     # SIX Swiss Exchange
    "vie":      ".VI",     # Vienna Stock Exchange
    "otc":      "",        # OTC Markets (Pink Sheets)
    "snse":     ".SN",     # Santiago Stock Exchange
}
```

**SA → yfinance:** `slug="sto/LIFCO.B"` → exchange=`sto`, ticker=`LIFCO.B` → replace `.` with `-` → `LIFCO-B` + `.ST` = **`LIFCO-B.ST`** ✅

**yfinance → SA:** `symbol="LIFCO-B.ST"` → suffix=`.ST` → exchange=`sto`, ticker=`LIFCO-B` → replace `-` with `.` → **`sto/LIFCO.B`** ✅

**Ticker character differences:**
- StockAnalysis uses **dots** in tickers: `LIFCO.B`, `ROKO.B`
- yfinance uses **dashes**: `LIFCO-B`, `ROKO-B`
- Conversion: simply `replace(".", "-")` and `replace("-", ".")`

**Verified mapping for all example tickers:**

| SA slug | → yfinance symbol | yfinance symbol | → SA slug |
|---|---|---|---|
| `tsx/CSU` | `CSU.TO` ✅ | `CSU.TO` | `tsx/CSU` ✅ |
| `ams/ADYEN` | `ADYEN.AS` ✅ | `ADYEN.AS` | `ams/ADYEN` ✅ |
| `sto/EVO` | `EVO.ST` ✅ | `EVO.ST` | `sto/EVO` ✅ |
| `asx/KPG` | `KPG.AX` ✅ | `KPG.AX` | `asx/KPG` ✅ |
| `sto/LIFCO.B` | `LIFCO-B.ST` ✅ | `LIFCO-B.ST` | `sto/LIFCO.B` ✅ |
| `fra/MOHF` | `MOHF.F` ✅ | `MOHF.F` | `fra/MOHF` ✅ |
| `sto/ROKO.B` | `ROKO-B.ST` ✅ | `ROKO-B.ST` | `sto/ROKO.B` ✅ |
| `tsxv/TOI` | `TOI.V` ✅ | `TOI.V` | `tsxv/TOI` ✅ |
| `MSFT` | `MSFT` ✅ | `MSFT` | `MSFT` ✅ |

**Implementation in `data/search.py`:**

```python
def sa_slug_to_yf_symbol(slug: str) -> str:
    """Convert SA slug 'tsx/CSU' → yfinance symbol 'CSU.TO'."""
    if "/" not in slug:
        return slug  # US stock, same symbol
    exchange, ticker = slug.split("/", 1)
    suffix = EXCHANGE_MAP.get(exchange, "")
    return ticker.replace(".", "-") + suffix

def yf_symbol_to_sa_slug(symbol: str) -> str:
    """Convert yfinance symbol 'CSU.TO' → SA slug 'tsx/CSU'."""
    # Build reverse map: '.TO' → 'tsx'
    for sa_exchange, yf_suffix in EXCHANGE_MAP.items():
        if yf_suffix and symbol.endswith(yf_suffix):
            ticker = symbol[: -len(yf_suffix)]
            return f"{sa_exchange}/{ticker.replace('-', '.')}"
    return symbol  # US stock, same symbol
```

**At add-time:** When the user selects a search result, we immediately compute and store both `slug` and `yf_symbol` using the deterministic mapping — no extra API calls, no latency, 100% reliable for mapped exchanges.

**Unmapped exchanges:** If a user adds a ticker from an exchange not in the map (e.g. `bse/` for Bombay), the cross-resolution gracefully falls back to using the raw ticker. The user can still use the source they searched from; only switching to the other source would fail for that ticker, with a clear error message.

### 5.7 Backward Compatibility

If `st.session_state.tickers` contains plain strings (from a previous session), we detect this and auto-migrate:
```python
# Migration: plain string → ticker dict
if isinstance(ticker, str):
    ticker = {"display": ticker, "symbol": ticker, "slug": ticker.lower(),
              "yf_symbol": ticker, "exchange": "", "name": ticker}
```

---

## 6. Files Changed

| File | Change | Description |
|---|---|---|
| `data/search.py` | **NEW** | Search module with `search_tickers()` function for both SA and yfinance |
| `data/scraper.py` | **MODIFIED** | Updated URL construction to handle international slugs (`/quote/` vs `/stocks/`) |
| `data/fetcher.py` | **MINOR** | No logic change needed — already accepts any symbol string |
| `app.py` | **MODIFIED** | Replace `st.text_input` with `st_searchbox` autocomplete, ticker dict storage, pass correct identifiers to fetchers |
| `requirements.txt` | **MODIFIED** | Add `streamlit-searchbox>=0.1.24` |

---

## 7. Search Result Filtering

Not all search results are useful. We apply filters:

| Filter | StockAnalysis | yfinance |
|---|---|---|
| **Stocks only** | `st == "s"` | `quoteType == "EQUITY"` |
| **Exclude OTC** | Optionally hide `otc/` results | Optionally hide `exchange == "PNK"` |
| **Max results** | Top 8 | Top 8 |
| **Exclude analysts/pages** | Skip entries with `"type": "Analyst"` or missing `s` field | N/A |

---

## 8. Example Flows

### 8.1 International Ticker (StockAnalysis source)

```
User types: "CSU"
  → GET https://stockanalysis.com/api/search?q=CSU
  → Dropdown shows:
      Constellation Software Inc. (TSX:CSU)
      CSU Digital S.A. (BVMF:CSUD3)
      China Shenhua Energy (OTC:CSUAY)
  → User selects first option
  → Deterministic mapping: slug "tsx/CSU" → yf_symbol "CSU.TO"
  → Stored: {slug: "tsx/CSU", yf_symbol: "CSU.TO", ...}
  → Scraper uses: /quote/tsx/CSU/financials/  ✅
  → Switch to yfinance: yf.Ticker("CSU.TO")  ✅
```

### 8.2 International Ticker (yfinance source)

```
User types: "ADYEN"
  → yfinance Search("ADYEN")
  → Dropdown shows:
      Adyen N.V. (Amsterdam: ADYEN.AS)
      Adyen N.V. (OTC Markets: ADYEY)
  → User selects first option
  → Deterministic mapping: yf_symbol "ADYEN.AS" → slug "ams/ADYEN"
  → Stored: {slug: "ams/ADYEN", yf_symbol: "ADYEN.AS", ...}
  → yfinance uses: yf.Ticker("ADYEN.AS")  ✅
  → Switch to SA: /quote/ams/ADYEN/financials/  ✅
```

### 8.3 US Ticker (either source)

```
User types: "MSFT"
  → Search returns: Microsoft Corporation (MSFT)
  → Stored: {slug: "MSFT", yf_symbol: "MSFT", ...}
  → Scraper uses: /stocks/MSFT/financials/  ✅
  → yfinance uses: yf.Ticker("MSFT")  ✅
```

### 8.4 Company Name Search

```
User types: "Constellation Software"
  → SA search returns: Constellation Software Inc. (TSX:CSU)
  → Works just like typing "CSU"
```

### 8.5 Ambiguous Ticker

```
User types: "EVO"
  → SA search returns:
      Evolution AB (STO:EVO)            ← Stockholm
      Embark Early Education (ASX:EVO)  ← Australia
      Evovest Global Equity (TSX:EVO)   ← Canada (ETF, filtered out)
  → User clicks the one they want in the dropdown
```

---

## 9. Edge Cases

| Case | Handling |
|---|---|
| **No results** | Show `st.info("No tickers found for '{query}'")` |
| **Search API down** | Fall back to treating the input as a raw symbol (current behaviour) |
| **Ticker has dots** (e.g. `LIFCO.B`) | Preserved as-is in slug; yfinance uses dash (`LIFCO-B.ST`) |
| **User pastes full yfinance symbol** (e.g. `CSU.TO`) | Search should still find it; store correctly |
| **User pastes SA URL slug** (e.g. `tsx/CSU`) | Detect `/` and try direct lookup |
| **Rate limiting** | SA search API is lightweight (single GET); `st_searchbox` debounce=200ms prevents spamming |
| **Source switching after adding tickers** | Both identifiers stored at add-time via deterministic exchange mapping; no re-search or API call needed |
| **Unmapped exchange** | If exchange not in `EXCHANGE_MAP`, cross-source switch shows a clear warning; ticker still works with the source it was searched from |
| **Session migration** | Old plain-string tickers auto-converted to dict format |

---

## 10. Implementation Plan

| Step | Task | Effort |
|---|---|---|
| 1 | Create `data/search.py` with `search_tickers()` for both sources | Medium |
| 2 | Update `data/scraper.py`: change `BASE_URL`, add `_build_urls(slug)`, update `fetch_stockanalysis(slug)` signature | Small |
| 3 | Update `app.py` sidebar: search input → radio results → add selected | Medium |
| 4 | Update `app.py` main content: pass `slug` to SA scraper, `yf_symbol` to yfinance fetcher | Small |
| 5 | Add cross-source resolution (dual search at add-time) | Medium |
| 6 | Add backward compatibility migration for plain-string tickers | Small |
| 7 | Test with all example tickers (CSU, ADYEN, EVO, KPG, LIFCO.B, MOHF, ROKO.B, TOI, MSFT, AAPL) | Medium |

---

## 11. Testing Checklist

- [ ] Search "CSU" → shows Constellation Software (TSX:CSU) as top result
- [ ] Search "ADYEN" → shows Adyen N.V. (AMS:ADYEN) as top result
- [ ] Search "EVO" → shows Evolution AB (STO:EVO) among results
- [ ] Search "KPG" → shows Kelly Partners (ASX:KPG) among results
- [ ] Search "LIFCO" → shows Lifco AB (STO:LIFCO.B) as top result
- [ ] Search "MOHF" → shows LVMH (FRA:MOHF) as top result
- [ ] Search "ROKO" → shows Röko AB (STO:ROKO.B) as top result
- [ ] Search "TOI" → shows Topicus.com (TSXV:TOI) among results
- [ ] Search "MSFT" → shows Microsoft Corporation (MSFT) — US stock works
- [ ] Search "Constellation Software" → finds by company name
- [ ] Selected SA ticker loads financial data via `/quote/{exchange}/{ticker}/`
- [ ] Selected yfinance ticker loads data via `yf.Ticker("CSU.TO")`
- [ ] Switching data source after adding tickers works without re-search
- [ ] Adding 5 tickers from mixed exchanges works for comparison
- [ ] Old plain-string tickers in session state are auto-migrated
