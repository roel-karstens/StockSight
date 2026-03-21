# Feature 1: StockAnalysis.com as Second Data Source

## 1. Summary

Add **stockanalysis.com** as an alternative data source alongside yfinance. Users can switch between sources via a sidebar radio button (applies globally to all tickers). The stockanalysis.com source provides **6 years** of historical data (vs. yfinance's 3–4) and offers many metrics **pre-calculated**, reducing computation errors.

---

## 2. Motivation

| Aspect | yfinance (current) | StockAnalysis.com (new) |
|--------|-------------------|------------------------|
| **Years of data** | 3–4 | 6 |
| **Pre-calculated metrics** | Few (must derive ROCE, PEG, etc.) | Most metrics pre-calculated |
| **Reliability** | API can change without notice | HTML structure more stable |
| **Rate limits** | Occasional throttling | Unknown, respect via delays |
| **API key** | None needed | None needed |
| **Speed** | Fast (~1s per ticker) | Slower (~2-4s, 4 HTTP requests) |
| **Risk** | API deprecation | HTML structure changes, ToS |

---

## 3. Pages to Scrape

For a given ticker `{TICKER}`, we scrape 4 pages:

| Page | URL | Data Extracted |
|------|-----|---------------|
| **Income Statement** | `/stocks/{ticker}/financials/` | Revenue, Gross Profit, Gross Margin, Revenue Growth, FCF, FCF Growth |
| **Balance Sheet** | `/stocks/{ticker}/financials/balance-sheet/` | Long-Term Debt, Total Assets, Current Liabilities, Cash & Equivalents |
| **Cash Flow** | `/stocks/{ticker}/financials/cash-flow-statement/` | Free Cash Flow, Operating Cash Flow, CapEx |
| **Ratios** | `/stocks/{ticker}/financials/ratios/` | PEG Ratio, ROCE, Debt/FCF |

Base URL: `https://stockanalysis.com`

---

## 4. Metric Mapping

### 4.1 Direct from StockAnalysis.com (pre-calculated)

| Our Metric | Page | Row Label | Example |
|---|---|---|---|
| **Gross Margin (%)** | `/financials/` | `Gross Margin` | `68.59%` |
| **PEG Ratio** | `/financials/ratios/` | `PEG Ratio` | `1.61` |
| **Revenue Growth (%)** | `/financials/` | `Revenue Growth (YoY)` | `16.67%` |
| **ROCE (%)** | `/financials/ratios/` | `Return on Capital Employed (ROCE)` | `29.69%` |
| **FCF Growth (%)** | `/financials/` | `Free Cash Flow Growth` | `8.10%` |

### 4.2 Computed from scraped raw data

| Our Metric | Scraped Fields | Calculation |
|---|---|---|
| **LT Debt / FCF** | `Long-Term Debt` (balance sheet), `Free Cash Flow` (income/cash flow) | `LT Debt / FCF` |
| **DCF Margin of Safety** | `Free Cash Flow` (cash flow), `Shares Outstanding` (income), `Total Debt` (balance sheet), `Cash & Equivalents` (balance sheet), `Last Close Price` (ratios) | Same two-stage DCF model as current |

---

## 5. Scraping Strategy

### 5.1 Approach: `requests` + `BeautifulSoup`

The stockanalysis.com pages render financial data in HTML tables that are accessible via standard HTTP requests (server-side rendered). No headless browser needed.

```
GET https://stockanalysis.com/stocks/msft/financials/
→ Parse HTML tables → Extract rows by label → Build DataFrame
```

### 5.2 Table Structure

Each page has a table with:
- **Column headers**: fiscal year dates (e.g., `2025`, `2024`, `2023`, ...)
- **Rows**: labeled financial line items
- **Values**: formatted numbers (e.g., `35,425`, `68.59%`, `-3.32%`)

### 5.3 Parsing Logic

```python
def parse_table(html: str) -> dict[str, dict[str, float]]:
    """
    Parse a stockanalysis.com financial table.
    
    Returns: {row_label: {year: value, ...}, ...}
    Example: {"Gross Margin": {"2025": 68.59, "2024": 68.82, ...}}
    """
    # 1. Find the main data table in the HTML
    # 2. Extract column headers (years)
    # 3. For each row, extract the label and values
    # 4. Parse values: remove commas, handle %, handle "-" as NaN
```

### 5.4 Value Parsing

| Format | Example | Parsed |
|--------|---------|--------|
| Number | `35,425` | `35425.0` |
| Percentage | `68.59%` | `68.59` |
| Negative | `-3.32%` | `-3.32` |
| Missing | `-` | `NaN` |
| Zero | `0` | `0.0` |

### 5.5 Rate Limiting & Caching

- **Delay**: 0.5s between HTTP requests (4 pages → ~2s total)
- **Caching**: Same `st.cache_data(ttl=3600)` as yfinance (1 hour)
- **User-Agent**: Set a reasonable user-agent string
- **Error handling**: Graceful fallback on HTTP 429/403/timeout

---

## 6. Architecture Changes

### 6.1 New File: `data/scraper.py`

```
data/
├── __init__.py
├── fetcher.py          # yfinance fetcher (unchanged)
├── scraper.py          # NEW: stockanalysis.com scraper
└── metrics.py          # Updated: accept data from either source
```

### 6.2 Data Source Abstraction

Both sources will return data in a **common format** so `metrics.py` can work with either:

```python
# Common data dict structure (returned by both fetcher.py and scraper.py)
{
    "symbol": "MSFT",
    "source": "yfinance" | "stockanalysis",
    "income": pd.DataFrame,    # rows=years, cols=line items
    "balance": pd.DataFrame,
    "cashflow": pd.DataFrame,
    "ratios": pd.DataFrame,    # NEW: pre-calculated ratios (stockanalysis only)
    "info": dict,              # current price, shares, etc.
    "history": pd.DataFrame,   # price history (yfinance only, for PEG/DCF)
}
```

### 6.3 Metrics Computation Strategy

When source is **stockanalysis.com**:
1. **Use pre-calculated metrics directly** for: Gross Margin, PEG Ratio, Revenue Growth, ROCE, FCF Growth
2. **Compute from raw scraped data** for: LT Debt / FCF
3. **Compute DCF** using: FCF, shares, debt, cash, and stock price from scraped data

When source is **yfinance** (unchanged):
- All metrics computed from raw financials as today

```python
def compute_all_metrics(data: dict, years: int = 10) -> pd.DataFrame:
    if data["source"] == "stockanalysis":
        return _compute_from_stockanalysis(data, years)
    else:
        return _compute_from_yfinance(data, years)
```

### 6.4 UI Changes

Sidebar addition:

```
┌─────────────────────────┐
│  📈 StockSight          │
│                         │
│  Add a ticker: [____]   │
│  [➕ Add] [🗑️ Clear All] │
│                         │
│  Active Tickers         │
│  MSFT ✕                 │
│                         │
│  ─────────────────────  │
│  Data Source            │
│  ⦿ StockAnalysis.com   │  ← NEW
│  ○ Yahoo Finance        │
│  ─────────────────────  │
│                         │
│  Years of history [5]   │
│  ...                    │
└─────────────────────────┘
```

---

## 7. Scraper Module Design

### 7.1 `data/scraper.py` – Public API

```python
@st.cache_data(ttl=3600, show_spinner=False)
def fetch_stockanalysis(symbol: str) -> dict:
    """
    Scrape financial data from stockanalysis.com.
    
    Fetches 4 pages: income statement, balance sheet, cash flow, ratios.
    Returns data in the common format (same structure as fetch_financials).
    """

def _scrape_page(url: str) -> pd.DataFrame:
    """Fetch a single page and parse the financial table."""

def _parse_value(text: str) -> float:
    """Parse a formatted value string to float."""
```

### 7.2 Column Name Normalization

Stockanalysis.com uses display-friendly names. We normalize to match our internal names:

```python
STOCKANALYSIS_COLUMN_MAP = {
    # Income Statement
    "Revenue": "Total Revenue",
    "Gross Profit": "Gross Profit",
    "Gross Margin": "Gross Margin",
    "Revenue Growth (YoY)": "Revenue Growth",
    "Free Cash Flow": "Free Cash Flow",
    "Free Cash Flow Growth": "FCF Growth",
    "Operating Income": "EBIT",
    "Shares Outstanding (Diluted)": "Diluted Average Shares",
    "EPS (Diluted)": "Diluted EPS",
    
    # Balance Sheet
    "Long-Term Debt": "Long Term Debt",
    "Total Assets": "Total Assets",
    "Total Current Liabilities": "Current Liabilities",  
    "Cash & Equivalents": "Cash And Cash Equivalents",
    "Total Debt": "Total Debt",
    
    # Ratios
    "PEG Ratio": "PEG Ratio",
    "Return on Capital Employed (ROCE)": "ROCE",
    "PE Ratio": "PE Ratio",
    "Last Close Price": "Close Price",
}
```

---

## 8. Error Handling

| Scenario | Handling |
|----------|----------|
| HTTP 403 / blocked | Show warning, suggest switching to yfinance |
| HTTP 429 (rate limit) | Retry once after 3s, then fail gracefully |
| Table structure changed | Log error, return NaN for affected metrics |
| Ticker not found (404) | Show "Ticker not found on StockAnalysis.com" |
| Partial data (some pages fail) | Return available data, NaN for missing |
| Network timeout | 10s timeout, retry once |

---

## 9. New Dependency

```
beautifulsoup4>=4.12
```

> Note: `beautifulsoup4` is already installed as a transitive dependency of `yfinance`, so no new installation needed. We add it explicitly to `requirements.txt` for clarity.

---

## 10. Testing Plan

### 10.1 Scraper Tests (`tests/test_scraper.py`)

- Parse a saved HTML fixture for MSFT income statement
- Verify all expected rows are extracted
- Verify value parsing (numbers, percentages, negatives, missing)
- Test with different tickers (AAPL, GOOG) for structural consistency

### 10.2 Integration Tests

- Compare yfinance vs. stockanalysis.com output for MSFT
- Verify metric values are in the same ballpark (not identical — different data sources)
- Verify DCF works with stockanalysis.com data

---

## 11. Implementation Steps

1. **Add `beautifulsoup4`** to `requirements.txt` (explicit)
2. **Create `data/scraper.py`** — page fetching, HTML parsing, value extraction
3. **Update `data/metrics.py`** — branch on source, use pre-calculated ratios when available
4. **Update `app.py`** — add data source radio button in sidebar, route to correct fetcher
5. **Test with MSFT, AAPL, GOOG** — verify all 7 metrics render correctly from both sources
6. **Commit & push**

---

## 12. Risks & Mitigations

| Risk | Impact | Mitigation |
|------|--------|------------|
| **HTML structure changes** | Scraper breaks | Version-pin parsing logic, add fallback patterns |
| **ToS enforcement** | IP block | Rate limiting, caching, personal use only |
| **Data discrepancies** | Metrics differ between sources | Expected — note source in UI, don't cross-compare |
| **JS-only rendering** | Empty tables | Fall back to Playwright (out of scope for v1) |

### ToS Note
StockAnalysis.com ToS states: *"It is not allowed to republish our content in full without our explicit permission."* This tool is for **personal financial analysis** only, not republishing. Data is cached locally and not redistributed.

---

*Document created: 2026-03-21*
*Status: Draft — Ready for implementation*
