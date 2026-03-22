# Feature 4: Extra Metrics, Layout Overhaul & 20 Tickers

## 1. Summary

Three changes in one feature:

1. **PE Ratio** — new chart showing trailing Price/Earnings over time
2. **Reverse DCF Implied Growth** — new metric: what FCF growth rate does the market price imply?
3. **Stock Price chart** — dedicated full-width price chart at the top
4. **20 ticker support** — raise the limit from 5 to 20, with a chart filter to keep charts readable
5. **New 4-row grid layout** — reorganised chart grid

---

## 2. New Metrics

### 2.1 PE Ratio

**Formula:**

```
PE Ratio = Year-End Stock Price / Diluted EPS
```

| Field | yfinance | StockAnalysis |
|---|---|---|
| Stock Price | Year-end close from history | `Last Close Price` (ratios page) |
| Diluted EPS | `Diluted EPS` (income) | Pre-calculated `PE Ratio` on ratios page |

**Thresholds: NONE.**
A high PE is justified for a high-growth company. Showing the number without a good/bad judgment — displayed as ⚪ (neutral) in the scorecard. The chart lets users compare PE across tickers and over time, which is the real value.

**Scorecard:** Show value formatted as `XX.Xx` with ⚪ emoji (no rating).

---

### 2.2 Reverse DCF Implied Growth Rate

**What it answers:** "What annual FCF growth rate does the current market price require to be justified?"

**Method:** Use the same two-stage DCF model (10% WACC, 3% terminal growth, 10 years) but solve for the growth rate `g` where:

```
Intrinsic Value per Share(g) = Market Price
```

Use bisection search between 0% and 60% growth — no `scipy` dependency needed.

```python
def _reverse_dcf_growth(fcf, shares, debt, cash, market_price,
                         discount=0.10, terminal_g=0.03, years=10):
    """Find the FCF growth rate that makes intrinsic value = market price."""
    def intrinsic(g):
        cf = fcf
        pv_sum = 0
        for yr in range(1, years + 1):
            cf *= (1 + g)
            pv_sum += cf / (1 + discount) ** yr
        tv = cf * (1 + terminal_g) / (discount - terminal_g)
        pv_tv = tv / (1 + discount) ** years
        equity = pv_sum + pv_tv - debt + cash
        return equity / shares

    lo, hi = 0.0, 0.60  # search between 0% and 60%
    for _ in range(100):  # bisection iterations
        mid = (lo + hi) / 2
        if intrinsic(mid) < market_price:
            lo = mid
        else:
            hi = mid
    return mid  # growth rate as decimal, e.g., 0.15 = 15%
```

**Thresholds: NONE.**
Whether 15% implied growth is realistic depends entirely on the company's industry, pipeline, and historical track record. Displayed as ⚪ (neutral) in the scorecard. The number speaks for itself.

**Scorecard:** Show value formatted as `XX.X%` with ⚪ emoji (no rating).

| Field | yfinance | StockAnalysis |
|---|---|---|
| Free Cash Flow | `Free Cash Flow` (cash flow) | `Free Cash Flow` |
| Shares | `Diluted Average Shares` | `Shares Outstanding (Diluted)` |
| Total Debt | `Total Debt` (balance sheet) | `Total Debt` |
| Cash | `Cash And Cash Equivalents` | `Cash & Short-Term Investments` |
| Market Price | Year-end close from history | `Last Close Price` |

---

### 2.3 Stock Price Chart

Full-width chart at the top showing the stock price over time for all active (filtered) tickers. Uses year-end close prices already available from the history data.

**Thresholds: NONE.** Pure informational chart, no badge/rating.

---

## 3. Expand to 20 Tickers

### 3.1 Limit Change

Change the maximum from 5 to 20 in `app.py`:

```python
if len(st.session_state.tickers) >= 20:
    st.toast("⚠️ Maximum 20 tickers for comparison.")
```

### 3.2 Chart Ticker Filter (Option C)

With 20 tickers, charts become unreadable. Add a **multiselect** widget above the chart grid:

```python
st.multiselect(
    "Show in charts:",
    options=[t["symbol"] for t in st.session_state.tickers],
    default=[t["symbol"] for t in st.session_state.tickers[:5]],
    key="chart_filter",
)
```

- **Charts** only render lines for selected tickers (max recommended: ~8)
- **Scorecard table** always shows ALL tickers regardless of filter
- **Badges** above each chart only show for filtered tickers

### 3.3 Color Palette

Extend `TICKER_COLORS` in `ui/charts.py` from 5 to 20 colors. Use a perceptually distinct palette (e.g., Plotly's `qualitative.Dark24` or hand-picked 20 colors).

---

## 4. New Grid Layout

### 4.1 Layout (1 full-width + 3×3 grid)

```
Row 1 (full width):
┌─────────────────────────────────────────────────────────┐
│ Stock Price ($)                                    ℹ️   │
│ ┌─────────────────────────────────────────────────────┐ │
│ │              📈 Price Chart                         │ │
│ └─────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────┘

Row 2:
┌──────────────────┐ ┌──────────────────┐ ┌──────────────────┐
│ Gross Margin (%) │ │ ROCE (%)         │ │ LT Debt/FCF (x)  │
│     📈 Chart     │ │     📈 Chart     │ │     📈 Chart     │
└──────────────────┘ └──────────────────┘ └──────────────────┘

Row 3:
┌──────────────────┐ ┌──────────────────┐ ┌──────────────────┐
│ Revenue Grw (%)  │ │ FCF Growth (%)   │ │ PE Ratio (-)     │
│     📈 Chart     │ │     📈 Chart     │ │     📈 Chart     │
└──────────────────┘ └──────────────────┘ └──────────────────┘

Row 4:
┌──────────────────┐ ┌──────────────────┐ ┌──────────────────┐
│ PEG Ratio (-)    │ │ DCF MoS (%)      │ │ Implied Grw (%)  │
│     📈 Chart     │ │     📈 Chart     │ │     📈 Chart     │
└──────────────────┘ └──────────────────┘ └──────────────────┘

Summary Scorecard (full width, all tickers)
```

### 4.2 Metric Order

```python
METRIC_ORDER = [
    "stock_price",       # Row 1 (full width)
    "gross_margin",      # Row 2
    "roce",
    "ltd_fcf",
    "revenue_growth",    # Row 3
    "fcf_growth",
    "pe_ratio",
    "peg_ratio",         # Row 4
    "dcf_mos",
    "implied_growth",
]
```

### 4.3 Rendering Logic

```python
# Row 1: Stock price (full width)
_render_chart_cell("stock_price", charts, all_data)

# Row 2: Quality metrics
row2_cols = st.columns(3)
for i, key in enumerate(["gross_margin", "roce", "ltd_fcf"]):
    with row2_cols[i]:
        _render_chart_cell(key, charts, all_data)

# Row 3: Growth + PE
row3_cols = st.columns(3)
for i, key in enumerate(["revenue_growth", "fcf_growth", "pe_ratio"]):
    with row3_cols[i]:
        _render_chart_cell(key, charts, all_data)

# Row 4: Valuation
row4_cols = st.columns(3)
for i, key in enumerate(["peg_ratio", "dcf_mos", "implied_growth"]):
    with row4_cols[i]:
        _render_chart_cell(key, charts, all_data)
```

---

## 5. Scorecard Updates

The scorecard table adds 3 new columns:

| Ticker | Gross Margin | ROCE | LT Debt/FCF | Rev Growth | FCF Growth | PE Ratio | PEG | DCF MoS | Implied Grw |
|---|---|---|---|---|---|---|---|---|---|
| MSFT | 🟢 69.4% | 🟢 35.2% | 🟢 1.8x | 🟢 14.2% | 🟢 18.3% | ⚪ 32.1x | 🟢 1.8 | 🟡 +12.3% | ⚪ 14.2% |
| V | 🟢 67.5% | 🟢 28.1% | 🟡 4.2x | 🟢 11.5% | 🟡 6.8% | ⚪ 35.0x | 🟡 2.5 | 🔴 −44.6% | ⚪ 22.1% |

- **PE Ratio**: Always ⚪ — no threshold
- **Implied Growth**: Always ⚪ — no threshold
- **Stock Price**: NOT shown in scorecard (it's not a health metric)

---

## 6. Chart Considerations

### 6.1 PE Ratio Chart

- No threshold reference lines (no good/bad hlines)
- Y-axis: "PE Ratio"
- Negative PE values (losses) shown but capped at display range to prevent axis distortion

### 6.2 Implied Growth Chart

- No threshold reference lines
- Y-axis: "Implied FCF Growth (%)"
- If solver can't find a solution (e.g., negative FCF), show NaN

### 6.3 Stock Price Chart

- No threshold reference lines
- **Raw prices** (not normalised)
- **Each ticker gets its own Y-axis** so stocks at different price levels are all readable
- Implementation: Plotly multi-axis overlay — first ticker on `yaxis` (left), subsequent tickers on `yaxis2`, `yaxis3`, etc. (alternating left/right)
- Axis tick label color matches the line color for each ticker
- With 8+ tickers shown, outer axes may get crowded — acceptable trade-off

---

## 7. Files Changed

| File | Change | Description |
|---|---|---|
| `data/metrics.py` | **MODIFIED** | Add `pe_ratio()`, `implied_fcf_growth()`, `stock_price()` functions; wire into `compute_all_metrics()` and `_compute_from_stockanalysis()` |
| `ui/indicators.py` | **MODIFIED** | Add `pe_ratio`, `implied_growth`, `stock_price` to `THRESHOLDS` (with `good=None, bad=None` for no-threshold metrics), `METRIC_ORDER`, and `METRIC_FORMULAS` |
| `ui/charts.py` | **MODIFIED** | Extend `TICKER_COLORS` to 20 colors; handle no-threshold charts (skip hlines); add base-100 normalisation for stock price chart |
| `app.py` | **MODIFIED** | Raise limit 5→20; add multiselect chart filter; new 4-row layout (1 full-width + 3×3); filter `all_data` before passing to charts |

---

## 8. Implementation Plan

| Step | Task | Effort |
|---|---|---|
| 1 | Add `pe_ratio()` calculator in `metrics.py` | Small |
| 2 | Add `implied_fcf_growth()` with bisection solver in `metrics.py` | Medium |
| 3 | Add `stock_price()` extractor in `metrics.py` | Small |
| 4 | Wire new metrics into both yfinance and SA compute paths | Small |
| 5 | Update `THRESHOLDS`, `METRIC_ORDER`, `METRIC_FORMULAS` in `indicators.py` | Medium |
| 6 | Extend color palette to 20 in `charts.py` | Small |
| 7 | Handle no-threshold metrics in chart builder (skip hlines) | Small |
| 8 | Add base-100 normalisation option for stock price chart | Small |
| 9 | Update `app.py`: limit→20, multiselect filter, 4-row layout | Medium |
| 10 | Test with 10+ tickers to verify chart readability | Small |

---

## 9. No New Dependencies

- Bisection solver is pure Python (no `scipy`)
- All data already available from existing fetchers
- `streamlit-searchbox` already supports the workflow
