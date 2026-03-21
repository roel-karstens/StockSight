# StockSight – POC Design Document

## 1. Vision

**StockSight** is a lightweight stock analysis dashboard that visualizes key financial health metrics for any publicly traded company. Users can search for tickers, compare multiple stocks side-by-side, and instantly see color-coded "good/bad" indicators for each metric.

The goal: in under 30 seconds, get a visual snapshot of whether a company is financially healthy and improving.

---

## 2. Target Metrics

Six financial health metrics plus a DCF valuation, each displayed as a multi-year line/bar chart:

| # | Metric | Unit | Source Calculation | Good Threshold | Bad Threshold |
|---|--------|------|--------------------|----------------|---------------|
| 1 | **Gross Margin** | % | `Gross Profit / Revenue × 100` | ≥ 50% | < 20% |
| 2 | **PEG Ratio** | - | `PE Ratio / EPS Growth Rate` | 0 < PEG ≤ 2.0 | > 3.0 or < 0 |
| 3 | **Revenue Growth** | % | `(Revenue_t − Revenue_t-1) / Revenue_t-1 × 100` | > 10% | < 0% |
| 4 | **ROCE** | - | `EBIT / (Total Assets − Current Liabilities)` | ≥ 15% | < 5% |
| 5 | **Free Cash Flow Growth** | % | `(FCF_t − FCF_t-1) / FCF_t-1 × 100` | > 10% | < 0% |
| 6 | **Long-Term Debt / FCF** | - | `Long-Term Debt / Free Cash Flow` | < 4.0 | > 5.0 |
| 7 | **DCF Margin of Safety** | % | `(Intrinsic Value − Market Price) / Market Price × 100` | ≥ 20% | < −20% |

### Threshold Color Coding
- 🟢 **Green** – metric is in the "good" zone
- 🟡 **Yellow** – metric is in between
- 🔴 **Red** – metric is in the "bad" zone

Applied to the **most recent year's value** as a badge on each chart.

---

## 3. Data Source

### Primary: `yfinance` (Python)
- **Free**, no API key required
- Provides: income statements, balance sheets, cash flow statements (annual & quarterly)
- Covers ~10 years of historical data
- Tickers: any stock on major US exchanges (NYSE, NASDAQ), plus many international

### Derived Calculations
All six metrics are **computed from raw financial statements** pulled via `yfinance`:

```
from yfinance import Ticker

t = Ticker("MSFT")
income   = t.financials          # Annual income statement
balance  = t.balance_sheet       # Annual balance sheet
cashflow = t.cashflow            # Annual cash flow statement
```

| Raw Field (yfinance) | Used For |
|---|---|
| `Total Revenue` | Revenue Growth, Gross Margin |
| `Gross Profit` | Gross Margin |
| `EBIT` | ROCE |
| `Total Assets` | ROCE |
| `Current Liabilities` | ROCE |
| `Free Cash Flow` | FCF Growth, LT Debt / FCF |
| `Long Term Debt` | LT Debt / FCF |
| `Trailing PE` / `EPS` growth | PEG Ratio |

### PEG Ratio – Special Handling
`yfinance` does not always provide a historical PEG ratio directly. Strategy:
1. Use `t.info.get('pegRatio')` for the **current** PEG.
2. For historical PEG: compute `PE_t / EPS_growth_t` where:
   - `PE_t = Price_t / EPS_t` (use year-end close from `t.history()`)
   - `EPS_growth_t = (EPS_t − EPS_t-1) / |EPS_t-1|`

---

## 4. Architecture

```
┌──────────────────────────────────────────────┐
│                 Streamlit App                 │
│                                              │
│  ┌─────────────┐  ┌──────────────────────┐   │
│  │  Search Bar  │  │  Ticker Chips (multi)│   │
│  │  e.g. MSFT   │  │  MSFT ✕  AAPL ✕     │   │
│  └─────────────┘  └──────────────────────┘   │
│                                              │
│  ┌────────────┐ ┌────────────┐ ┌──────────┐  │
│  │Gross Margin│ │ PEG Ratio  │ │Rev Growth│  │
│  │  📈 🟢     │ │  📈 🟡     │ │ 📈 🟢    │  │
│  └────────────┘ └────────────┘ └──────────┘  │
│  ┌────────────┐ ┌────────────┐ ┌──────────┐  │
│  │   ROCE     │ │ FCF Growth │ │LTD / FCF │  │
│  │  📈 🟢     │ │  📈 🔴     │ │ 📈 🟢    │  │
│  └────────────┘ └────────────┘ └──────────┘  │
│                                              │
│  ┌──────────────────────────────────────┐    │
│  │        Summary Scorecard Table       │    │
│  │  Ticker | GM | PEG | RevG | ROCE ... │    │
│  │  MSFT   | 🟢 | 🟡  | 🟢   | 🟢  ... │    │
│  │  AAPL   | 🟢 | 🔴  | 🟡   | 🟢  ... │    │
│  └──────────────────────────────────────┘    │
└──────────────────────────────────────────────┘
        │
        ▼
┌──────────────────┐
│  data/engine.py  │  ← Fetches & computes metrics
│                  │
│  yfinance API    │
└──────────────────┘
```

### Tech Stack
| Layer | Technology | Rationale |
|-------|-----------|-----------|
| **Frontend** | Streamlit | Fastest POC path, built-in widgets, no build step |
| **Charts** | Plotly (via `st.plotly_chart`) | Interactive, zoomable, good multi-series support |
| **Data** | `yfinance` | Free, no API key, good coverage |
| **Language** | Python 3.11+ | Single language for everything |
| **Caching** | `st.cache_data` | Avoid re-fetching on every interaction (TTL: 1 hour) |

---

## 5. Project Structure

```
StockSight/
├── POC.MD                  # This document
├── requirements.txt        # Python dependencies
├── app.py                  # Streamlit entry point (UI)
├── data/
│   ├── __init__.py
│   ├── fetcher.py          # Raw data fetching via yfinance
│   └── metrics.py          # Metric calculations
├── ui/
│   ├── __init__.py
│   ├── charts.py           # Plotly chart builders
│   ├── indicators.py       # Good/bad threshold logic & badges
│   └── layout.py           # Page layout helpers
└── tests/
    ├── test_metrics.py     # Unit tests for metric calculations
    └── test_fetcher.py     # Tests for data fetching
```

---

## 6. Feature Details

### 6.1 Search & Multi-Ticker Support
- **Search bar**: text input, user types a ticker symbol (e.g., `MSFT`)
- **Add button**: adds ticker to the active comparison list
- **Ticker chips**: displayed as removable chips/tags below the search bar
- **Max tickers**: 5 simultaneous (to keep charts readable)
- Each ticker gets its own colored line on every chart

### 6.2 Charts (2×3 Grid)
- Each chart is a **line chart** with years on X-axis
- Multiple tickers shown as separate colored lines with legend
- **Time range**: last 10 fiscal years (configurable via sidebar slider)
- Hover tooltips show exact values
- A **horizontal reference line** at the good/bad thresholds (dashed green/red)

### 6.3 Good/Bad Indicators
- Each chart card shows a **colored badge** per ticker for the most recent value:
  - `🟢 MSFT: 68.8%` – Good
  - `🟡 AAPL: 35.2%` – Neutral
  - `🔴 XYZ: 12.1%` – Bad
- **Summary Scorecard** at the bottom: a table with all tickers × all metrics, each cell colored

### 6.4 Sidebar Controls
- **Time range slider**: 3–10 years
- **Toggle annual / TTM** (trailing twelve months)
- **Theme**: Light / Dark (Streamlit built-in)

---

## 7. Metric Calculation Pseudocode

```python
import pandas as pd
from yfinance import Ticker

def get_metrics(symbol: str, years: int = 10) -> pd.DataFrame:
    t = Ticker(symbol)
    
    inc = t.financials.T.sort_index()           # income statement
    bal = t.balance_sheet.T.sort_index()         # balance sheet
    cf  = t.cashflow.T.sort_index()              # cash flow
    hist = t.history(period="10y", interval="1mo")  # price history
    
    df = pd.DataFrame(index=inc.index[-years:])
    
    # 1. Gross Margin (%)
    df['gross_margin'] = (inc['Gross Profit'] / inc['Total Revenue'] * 100)
    
    # 2. Revenue Growth (%)
    df['revenue_growth'] = inc['Total Revenue'].pct_change() * 100
    
    # 3. ROCE (%)
    capital_employed = bal['Total Assets'] - bal['Current Liabilities']
    df['roce'] = (inc['EBIT'] / capital_employed * 100)
    
    # 4. Free Cash Flow Growth (%)
    df['fcf_growth'] = cf['Free Cash Flow'].pct_change() * 100
    
    # 5. Long-Term Debt / FCF
    df['ltd_fcf'] = bal['Long Term Debt'] / cf['Free Cash Flow']
    
    # 6. PEG Ratio
    eps = inc['Net Income'] / inc['Basic EPS']  # or use diluted
    # ... actually get EPS from income stmt directly
    eps = inc['Diluted EPS'] if 'Diluted EPS' in inc.columns else inc['Basic EPS']
    eps_growth = eps.pct_change()
    # Get year-end prices for PE
    year_end_prices = hist['Close'].resample('Y').last()
    pe = year_end_prices / eps
    df['peg_ratio'] = pe / (eps_growth * 100)
    
    return df
```

> **Note**: Exact column names in `yfinance` may vary slightly. The implementation will handle column name normalization and missing data gracefully.

---

## 8. Threshold Configuration

Thresholds are defined as a config dict, easily adjustable:

```python
THRESHOLDS = {
    'gross_margin':    {'good': 50, 'bad': 20, 'higher_is_better': True,  'unit': '%'},
    'peg_ratio':       {'good': 2.0,'bad': 3.0,'higher_is_better': False, 'unit': ''},
    'revenue_growth':  {'good': 10, 'bad': 0,  'higher_is_better': True,  'unit': '%'},
    'roce':            {'good': 15, 'bad': 5,  'higher_is_better': True,  'unit': '%'},
    'fcf_growth':      {'good': 10, 'bad': 0,  'higher_is_better': True,  'unit': '%'},
    'ltd_fcf':         {'good': 4.0,'bad': 5.0,'higher_is_better': False, 'unit': 'x'},
}
```

---

## 9. Error Handling

| Scenario | Handling |
|----------|----------|
| Invalid ticker | Show warning toast: "Ticker XYZ not found" |
| Partial data (some years missing) | Plot available years, show note |
| yfinance rate limit / timeout | Retry 2× with exponential backoff, then show error |
| Missing field (e.g., no Long-Term Debt) | Show "N/A" for that metric, grey badge |
| Negative FCF (division issues) | Show value but flag as 🔴, handle div-by-zero |

---

## 10. Dependencies

```
streamlit>=1.30
plotly>=5.18
yfinance>=0.2.30
pandas>=2.0
```

---

## 11. Running the POC

```bash
# Install dependencies
pip install -r requirements.txt

# Run the app
streamlit run app.py

# Open in browser
# → http://localhost:8501
```

---

## 12. Future Enhancements (Out of Scope for POC)

- [ ] Quarterly data view
- [ ] Export charts as PNG / PDF
- [ ] Watchlist persistence (save favorite tickers)
- [ ] More metrics (Debt/Equity, Current Ratio, Dividend Yield, etc.)
- [ ] Sector/industry comparison benchmarks
- [ ] Alerting (notify when a metric crosses a threshold)
- [ ] Deploy to Streamlit Cloud for sharing
- [ ] Use a proper financial data API (Financial Modeling Prep, Polygon.io) for reliability
- [ ] Add stock price chart overlay for context

---

## 13. Open Questions

1. **PEG Ratio accuracy**: Historical PEG computed from year-end price and EPS growth may not match analyst-consensus PEG. Acceptable for POC?
2. **Fiscal year alignment**: Different companies have different fiscal year ends (MSFT: Jun, AAPL: Sep). When comparing, we use fiscal year as reported and label charts with actual dates (simple approach).
3. **International stocks**: `yfinance` supports many international tickers (e.g., `ASML`, `TSM`). Include or limit to US only?
   - **POC approach**: Support any ticker `yfinance` supports.

---

*Document created: 2026-03-21*  
*Status: Draft – Ready for implementation*
