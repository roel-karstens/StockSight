# Feature 3: Show Calculation Formulas per Metric

## 1. Summary

Add an **ℹ️ info button** next to each chart title that opens a **popover/expander** showing the exact formula, data sources, and thresholds used for that metric. This gives users transparency into how each number is calculated — especially useful for complex metrics like DCF Margin of Safety and PEG Ratio.

---

## 2. Motivation

- Users see numbers but don't know how they're computed
- Different data sources (StockAnalysis.com vs yfinance) use different raw fields — this should be visible
- DCF has many assumptions (discount rate, growth rate, terminal growth) that users need to understand
- Threshold logic (🟢🟡🔴) is opaque without showing the boundaries

---

## 3. Metric Formulas

### 3.1 Gross Margin (%)

```
Gross Margin = (Gross Profit / Total Revenue) × 100
```

| Field | yfinance column | StockAnalysis field |
|---|---|---|
| Gross Profit | `Gross Profit` | Pre-calculated: `Gross Margin` on income page |
| Total Revenue | `Total Revenue` / `Revenue` | — |

**Thresholds:** 🟢 ≥ 50% · 🟡 20–50% · 🔴 < 20%

---

### 3.2 PEG Ratio

```
PEG Ratio = PE Ratio / EPS Growth Rate

Where:
  PE Ratio = Year-End Stock Price / Diluted EPS
  EPS Growth Rate = YoY % change in Diluted EPS
```

| Field | yfinance column | StockAnalysis field |
|---|---|---|
| Diluted EPS | `Diluted EPS` (fallback: `Net Income / Shares`) | — |
| Year-End Price | Closest price to fiscal year-end from history | — |
| PEG Ratio | Computed | Pre-calculated: `PEG Ratio` on ratios page |

**Thresholds:** 🟢 ≤ 2.0 · 🟡 2.0–3.0 · 🔴 > 3.0 (negative PEG = 🔴)

---

### 3.3 Revenue Growth (%)

```
Revenue Growth = ((Revenue_current - Revenue_previous) / Revenue_previous) × 100
```

| Field | yfinance column | StockAnalysis field |
|---|---|---|
| Revenue | `Total Revenue` / `Revenue` | Pre-calculated: `Revenue Growth (YoY)` on income page |

**Thresholds:** 🟢 > 10% · 🟡 0–10% · 🔴 < 0%

---

### 3.4 ROCE (%)

```
ROCE = (EBIT / Capital Employed) × 100

Where:
  Capital Employed = Total Assets − Current Liabilities
```

| Field | yfinance column | StockAnalysis field |
|---|---|---|
| EBIT | `EBIT` / `Operating Income` | — |
| Total Assets | `Total Assets` | — |
| Current Liabilities | `Current Liabilities` | — |
| ROCE | Computed | Pre-calculated: `Return on Capital Employed (ROCE)` on ratios page |

**Thresholds:** 🟢 ≥ 15% · 🟡 5–15% · 🔴 < 5%

---

### 3.5 Free Cash Flow Growth (%)

```
FCF Growth = ((FCF_current - FCF_previous) / FCF_previous) × 100
```

| Field | yfinance column | StockAnalysis field |
|---|---|---|
| Free Cash Flow | `Free Cash Flow` (cash flow statement) | Pre-calculated: `Free Cash Flow Growth` on income page |

**Thresholds:** 🟢 > 10% · 🟡 0–10% · 🔴 < 0%

---

### 3.6 Long-Term Debt / FCF

```
LT Debt / FCF = Long-Term Debt / Free Cash Flow
```

| Field | yfinance column | StockAnalysis field |
|---|---|---|
| Long-Term Debt | `Long Term Debt` / `LongTermDebt` | `Long-Term Debt` (balance sheet) |
| Free Cash Flow | `Free Cash Flow` (cash flow) | `Free Cash Flow` (income/cash flow page) |

**Thresholds:** 🟢 < 4.0x · 🟡 4.0–5.0x · 🔴 > 5.0x

---

### 3.7 DCF Margin of Safety (%)

```
Margin of Safety = ((Intrinsic Value per Share − Market Price) / Market Price) × 100

Where:
  Intrinsic Value per Share = Equity Value / Shares Outstanding
  Equity Value = Enterprise Value − Total Debt + Cash
  Enterprise Value = Σ(Discounted Projected FCF) + Discounted Terminal Value

Stage 1 — Project FCF for 10 years:
  FCF_year_n = FCF_current × (1 + growth_rate)^n
  Discounted_FCF_n = FCF_year_n / (1 + WACC)^n

Stage 2 — Terminal Value (Gordon Growth Model):
  Terminal_FCF = FCF_year_10 × (1 + terminal_growth)
  Terminal_Value = Terminal_FCF / (WACC − terminal_growth)
  Discounted_Terminal = Terminal_Value / (1 + WACC)^10
```

**Assumptions:**

| Parameter | Value | Notes |
|---|---|---|
| WACC (discount rate) | 10% | Simplified, not company-specific |
| Terminal growth rate | 3% | Long-term GDP-like growth |
| Projection years | 10 | Standard DCF horizon |
| FCF growth rate | Avg of historical YoY FCF growth | Clamped to 2–25% range |

| Field | yfinance column | StockAnalysis field |
|---|---|---|
| Free Cash Flow | `Free Cash Flow` | `Free Cash Flow` |
| Shares Outstanding | `Diluted Average Shares` | `Shares Outstanding (Diluted)` |
| Total Debt | `Total Debt` / `Net Debt` | `Total Debt` |
| Cash | `Cash And Cash Equivalents` | `Cash & Short-Term Investments` |
| Market Price | Year-end close from price history | `Last Close Price` (ratios page) |

**Thresholds:** 🟢 ≥ +20% (undervalued) · 🟡 -20% to +20% · 🔴 < -20% (overvalued)

---

## 4. UI Design

### 4.1 Info Popover Next to Chart Title

Use Streamlit's `st.popover` (available since Streamlit 1.33) to place an **ℹ️** button inline next to the chart title. Clicking it opens a floating panel with the formula and details.

```
┌─────────────────────────────────────────────┐
│ Gross Margin (%)  ℹ️                         │
│ ┌─────────────────────────────────────────┐ │
│ │         📈 Chart                        │ │
│ └─────────────────────────────────────────┘ │
└─────────────────────────────────────────────┘

      ↓ click ℹ️

┌──────────────────────────────────────┐
│ 📐 Gross Margin                      │
│                                      │
│ **Formula:**                         │
│ Gross Margin = (Gross Profit /       │
│   Total Revenue) × 100              │
│                                      │
│ **Data source fields:**              │
│ • yfinance: `Gross Profit`,         │
│   `Total Revenue`                    │
│ • StockAnalysis: pre-calculated      │
│   `Gross Margin` on income page      │
│                                      │
│ **Thresholds:**                      │
│ 🟢 Good: ≥ 50%                       │
│ 🟡 Neutral: 20–50%                   │
│ 🔴 Bad: < 20%                        │
└──────────────────────────────────────┘
```

### 4.2 Layout

Each chart cell currently renders:
1. Badge row (🟢 MSFT 68.6%)
2. Plotly chart

After this feature:
1. **Title row** with metric label + ℹ️ popover
2. Badge row
3. Plotly chart

The chart's own Plotly title is removed (set to empty) since Streamlit now renders the title with the info button.

### 4.3 Streamlit Implementation

```python
# For each metric chart cell:
title_col, info_col = st.columns([10, 1])
with title_col:
    st.markdown(f"**{THRESHOLDS[metric_key]['label']} ({THRESHOLDS[metric_key]['unit'] or '-'})**")
with info_col:
    with st.popover("ℹ️"):
        st.markdown(METRIC_FORMULAS[metric_key])
```

---

## 5. Formula Content Store

### 5.1 New Constant: `METRIC_FORMULAS` in `ui/indicators.py`

Add a `METRIC_FORMULAS` dict to `ui/indicators.py` alongside `THRESHOLDS`. Each entry is a Markdown string shown in the popover.

```python
METRIC_FORMULAS = {
    "gross_margin": """
**📐 Gross Margin (%)**

**Formula:**
$$\\text{Gross Margin} = \\frac{\\text{Gross Profit}}{\\text{Total Revenue}} \\times 100$$

**Data fields:**
- **yfinance:** `Gross Profit` ÷ `Total Revenue`
- **StockAnalysis:** pre-calculated `Gross Margin` on income page

**Thresholds:**
- 🟢 Good: ≥ 50%
- 🟡 Neutral: 20–50%
- 🔴 Bad: < 20%
""",
    # ... etc for each metric
}
```

---

## 6. Files Changed

| File | Change | Description |
|---|---|---|
| `ui/indicators.py` | **MODIFIED** | Add `METRIC_FORMULAS` dict with Markdown formula text for all 7 metrics |
| `app.py` | **MODIFIED** | Add title row with `st.popover("ℹ️")` for each chart cell; remove Plotly title from charts to avoid duplication |
| `ui/charts.py` | **MODIFIED** | Remove `title` from `fig.update_layout()` (title now rendered by Streamlit with the info button) |

---

## 7. Implementation Plan

| Step | Task | Effort |
|---|---|---|
| 1 | Add `METRIC_FORMULAS` dict to `ui/indicators.py` with all 7 formulas | Medium |
| 2 | Update `app.py` chart rendering: add title + ℹ️ popover row above each chart | Small |
| 3 | Update `ui/charts.py`: remove Plotly title to avoid duplication | Small |
| 4 | Test all 7 popovers render correctly with Markdown/LaTeX | Small |

---

## 8. Testing Checklist

- [ ] Each of the 7 charts has an ℹ️ button next to the title
- [ ] Clicking ℹ️ opens a popover with the formula, data fields, and thresholds
- [ ] LaTeX formulas render correctly in the popover
- [ ] Popover works on both desktop and mobile layouts
- [ ] Chart title no longer duplicated (Plotly title removed)
- [ ] DCF popover shows all assumptions (WACC, terminal growth, projection years, FCF growth clamping)
- [ ] Data source fields mention both yfinance and StockAnalysis column names
