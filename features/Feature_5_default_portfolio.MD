# Feature 5: Default Portfolio

## 1. Summary

Add a **pre-configured default portfolio** of 16 quality/growth stocks that loads instantly on first visit, so new users see a fully populated scorecard without having to search for tickers one by one.

A sidebar button lets users load the portfolio at any time. Tickers that are already active are skipped (no duplicates).

---

## 2. Motivation

- **First-visit experience** — today the app opens with an empty state and a "search to get started" message. A curated portfolio gives users an immediate feel for what StockSight does.
- **Scorecard showcase** — the Summary Scorecard only becomes useful when comparing multiple stocks. Preloading 16 tickers demonstrates the value proposition straight away.
- **Personal use** — this is the owner's watchlist, so it doubles as a quick-access portfolio.

---

## 3. Default Portfolio

16 stocks, spanning US, Canadian, European, and Australian exchanges:

| # | Ticker | SA Slug | yfinance Symbol | Company | Exchange |
|---|--------|---------|-----------------|---------|----------|
| 1 | ADBE | `ADBE` | `ADBE` | Adobe | NASDAQ |
| 2 | ASML | `ASML` | `ASML` | ASML Holding | NASDAQ (ADR) |
| 3 | CSU | `tsx/CSU` | `CSU.TO` | Constellation Software | TSX |
| 4 | FICO | `FICO` | `FICO` | Fair Isaac Corporation | NYSE |
| 5 | GOOG | `GOOG` | `GOOG` | Alphabet | NASDAQ |
| 6 | INTU | `INTU` | `INTU` | Intuit | NASDAQ |
| 7 | KPG | `asx/KPG` | `KPG.AX` | Kelly Partners Group | ASX |
| 8 | LIFCO.B | `sto/LIFCO.B` | `LIFCO-B.ST` | Lifco AB | STO |
| 9 | MA | `MA` | `MA` | Mastercard | NYSE |
| 10 | META | `META` | `META` | Meta Platforms | NASDAQ |
| 11 | MSFT | `MSFT` | `MSFT` | Microsoft | NASDAQ |
| 12 | NVDA | `NVDA` | `NVDA` | NVIDIA | NASDAQ |
| 13 | NVO | `NVO` | `NVO` | Novo Nordisk | NYSE (ADR) |
| 14 | RACE | `RACE` | `RACE` | Ferrari | NYSE |
| 15 | TSM | `TSM` | `TSM` | Taiwan Semiconductor | NYSE (ADR) |
| 16 | V | `V` | `V` | Visa | NYSE |

The portfolio is defined as a constant list in a new module `data/portfolio.py`, using the same ticker-dict format that `search.py` produces. This makes it trivial to edit or extend the list later.

---

## 4. UX Design

### 4.1 First Visit (Empty State)

When `st.session_state.tickers` is empty (first visit or after "Clear All"):

- Replace the current `st.info("👈 Search for a ticker...")` with a **call-to-action** that includes a "Load Default Portfolio" button.
- Clicking the button populates `st.session_state.tickers` with all 16 stocks and triggers a rerun.

```
┌─────────────────────────────────────────────────────────────────┐
│  👈 Search for a ticker in the sidebar, or load a portfolio:   │
│                                                                 │
│  [ 📋 Load Default Portfolio (16 stocks) ]                      │
└─────────────────────────────────────────────────────────────────┘
```

### 4.2 Sidebar Button

Add a **"📋 Load Portfolio"** button in the sidebar, below the search box and above "Clear All":

```
┌── Sidebar ──────────────────┐
│ 📈 StockSight               │
│ ─────────────────────────── │
│ 🔍 [Search ticker...]       │
│                              │
│ [ 📋 Load Portfolio ]        │
│ [ 🗑️ Clear All ]             │
│                              │
│ Active Tickers               │
│   MSFT                    ✕  │
│   AAPL                    ✕  │
│   ...                        │
└──────────────────────────────┘
```

**Behaviour:**
- Adds all 16 default tickers, **skipping** any that are already active (by slug).
- Respects the 20-ticker limit — if adding all 16 would exceed 20, adds only as many as fit and shows a toast.
- Shows a toast: `"✅ Loaded 16 portfolio stocks"` (or `"✅ Loaded 12 new portfolio stocks (4 already active)"`).

### 4.3 Chart Filter

When loading 16 tickers at once, the chart filter should auto-select the **first 3** (to keep charts readable). The user can add more manually. The scorecard always shows all tickers regardless of chart filter.

### 4.4 Scorecard Table Height

The Summary Scorecard table height is set dynamically (35px per row + 45px header) so all tickers are visible without scrolling — important when loading 16 stocks at once.

---

## 5. Implementation

### 5.1 New File: `data/portfolio.py`

```python
"""
portfolio.py – Default portfolio definition.
"""

DEFAULT_PORTFOLIO = [
    {"display": "Adobe Inc. (ADBE)",                       "symbol": "ADBE",    "slug": "ADBE",         "yf_symbol": "ADBE",       "exchange": "",    "name": "Adobe Inc."},
    {"display": "ASML Holding N.V. (ASML)",                "symbol": "ASML",    "slug": "ASML",         "yf_symbol": "ASML",       "exchange": "",    "name": "ASML Holding N.V."},
    {"display": "Constellation Software Inc. (TSX:CSU)",   "symbol": "CSU",     "slug": "tsx/CSU",      "yf_symbol": "CSU.TO",     "exchange": "TSX", "name": "Constellation Software Inc."},
    {"display": "Fair Isaac Corporation (FICO)",            "symbol": "FICO",    "slug": "FICO",         "yf_symbol": "FICO",       "exchange": "",    "name": "Fair Isaac Corporation"},
    {"display": "Alphabet Inc. (GOOG)",                    "symbol": "GOOG",    "slug": "GOOG",         "yf_symbol": "GOOG",       "exchange": "",    "name": "Alphabet Inc."},
    {"display": "Intuit Inc. (INTU)",                      "symbol": "INTU",    "slug": "INTU",         "yf_symbol": "INTU",       "exchange": "",    "name": "Intuit Inc."},
    {"display": "Kelly Partners Group (ASX:KPG)",          "symbol": "KPG",     "slug": "asx/KPG",      "yf_symbol": "KPG.AX",     "exchange": "ASX", "name": "Kelly Partners Group Holdings Limited"},
    {"display": "Lifco AB (STO:LIFCO.B)",                  "symbol": "LIFCO.B", "slug": "sto/LIFCO.B",  "yf_symbol": "LIFCO-B.ST", "exchange": "STO", "name": "Lifco AB (publ)"},
    {"display": "Mastercard Incorporated (MA)",             "symbol": "MA",      "slug": "MA",           "yf_symbol": "MA",         "exchange": "",    "name": "Mastercard Incorporated"},
    {"display": "Meta Platforms, Inc. (META)",              "symbol": "META",    "slug": "META",         "yf_symbol": "META",       "exchange": "",    "name": "Meta Platforms, Inc."},
    {"display": "Microsoft Corporation (MSFT)",             "symbol": "MSFT",    "slug": "MSFT",         "yf_symbol": "MSFT",       "exchange": "",    "name": "Microsoft Corporation"},
    {"display": "NVIDIA Corporation (NVDA)",                "symbol": "NVDA",    "slug": "NVDA",         "yf_symbol": "NVDA",       "exchange": "",    "name": "NVIDIA Corporation"},
    {"display": "Novo Nordisk A/S (NVO)",                   "symbol": "NVO",     "slug": "NVO",          "yf_symbol": "NVO",        "exchange": "",    "name": "Novo Nordisk A/S"},
    {"display": "Ferrari N.V. (RACE)",                      "symbol": "RACE",    "slug": "RACE",         "yf_symbol": "RACE",       "exchange": "",    "name": "Ferrari N.V."},
    {"display": "Taiwan Semiconductor (TSM)",               "symbol": "TSM",     "slug": "TSM",          "yf_symbol": "TSM",        "exchange": "",    "name": "Taiwan Semiconductor Manufacturing Company Limited"},
    {"display": "Visa Inc. (V)",                            "symbol": "V",       "slug": "V",            "yf_symbol": "V",          "exchange": "",    "name": "Visa Inc."},
]
```

Each entry matches the **exact same dict shape** returned by `search.py`, so the rest of the app needs zero changes to handle them.

### 5.2 Changes to `app.py`

#### 5.2.1 Import

```python
from data.portfolio import DEFAULT_PORTFOLIO
```

#### 5.2.2 Helper Function

```python
def _load_portfolio():
    """Add default portfolio tickers, skipping duplicates and respecting the 20-ticker limit."""
    existing_slugs = {t["slug"] for t in st.session_state.tickers}
    added = 0
    skipped = 0
    for ticker in DEFAULT_PORTFOLIO:
        if len(st.session_state.tickers) >= 20:
            st.toast(f"⚠️ Hit 20-ticker limit. {len(DEFAULT_PORTFOLIO) - added - skipped} stocks not added.")
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
```

#### 5.2.3 Sidebar Button

Insert between the search box and the "Clear All" button:

```python
if st.button("📋 Load Portfolio", use_container_width=True):
    _load_portfolio()
    st.rerun()
```

#### 5.2.4 Empty State CTA

Replace the current:

```python
st.info("👈 Search for a ticker in the sidebar to get started.")
st.stop()
```

With:

```python
st.info("👈 Search for a ticker in the sidebar, or load a portfolio to get started.")
col_cta, _ = st.columns([1, 2])
with col_cta:
    if st.button("📋 Load Default Portfolio (16 stocks)", use_container_width=True):
        _load_portfolio()
        st.rerun()
st.stop()
```

---

## 6. Files Changed

| File | Change |
|---|---|
| `data/portfolio.py` | **NEW** — default portfolio constant |
| `app.py` | Import `DEFAULT_PORTFOLIO`, add `_load_portfolio()`, sidebar button, empty-state CTA |

No changes to fetcher, metrics, charts, indicators, scraper, or search.

---

## 7. Edge Cases

| Case | Behaviour |
|---|---|
| First visit, click "Load Portfolio" | All 16 tickers added, scorecard shows immediately |
| Already have 5 tickers, click "Load Portfolio" | Adds up to 15 more (skipping dupes), respects 20 limit |
| Already have 18 tickers, click "Load Portfolio" | Adds 2, toasts "Hit 20-ticker limit" |
| All 16 already active | Adds 0, toasts "✅ Loaded 0 portfolio stocks (16 already active)" |
| Click "Clear All" then "Load Portfolio" | Clears, then loads fresh 16 |
| Manually remove one portfolio stock, then "Load Portfolio" | Re-adds the removed one only |

---

## 8. Future Extensions (Not in Scope)

- **Multiple portfolios** — dropdown to choose between e.g. "Quality Growth", "Dividend", "Value".
- **Editable portfolios** — let users save/name their own portfolio in local storage or a file.
- **Portfolio weighting** — show weighted scorecard based on allocation %.
