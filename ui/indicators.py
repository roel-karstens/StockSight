"""
indicators.py – Threshold logic and good/bad/neutral badge rendering.
"""

# ---------------------------------------------------------------------------
# Threshold configuration
# ---------------------------------------------------------------------------

THRESHOLDS = {
    "gross_margin": {
        "label": "Gross Margin",
        "good": 50,
        "bad": 20,
        "higher_is_better": True,
        "unit": "%",
        "format": ".1f",
    },
    "peg_ratio": {
        "label": "PEG Ratio",
        "good": 2.0,
        "bad": 3.0,
        "higher_is_better": False,
        "unit": "",
        "format": ".2f",
    },
    "revenue_growth": {
        "label": "Revenue Growth",
        "good": 10,
        "bad": 0,
        "higher_is_better": True,
        "unit": "%",
        "format": ".1f",
    },
    "roce": {
        "label": "ROCE",
        "good": 15,
        "bad": 5,
        "higher_is_better": True,
        "unit": "%",
        "format": ".1f",
    },
    "fcf_growth": {
        "label": "FCF Growth",
        "good": 10,
        "bad": 0,
        "higher_is_better": True,
        "unit": "%",
        "format": ".1f",
    },
    "ltd_fcf": {
        "label": "LT Debt / FCF",
        "good": 4.0,
        "bad": 5.0,
        "higher_is_better": False,
        "unit": "x",
        "format": ".2f",
    },
    "dcf_mos": {
        "label": "DCF Margin of Safety",
        "good": 20,
        "bad": -20,
        "higher_is_better": True,
        "unit": "%",
        "format": ".1f",
    },
}

# Ordered list of metric keys for consistent display
METRIC_ORDER = [
    "gross_margin",
    "peg_ratio",
    "revenue_growth",
    "roce",
    "fcf_growth",
    "ltd_fcf",
    "dcf_mos",
]


def evaluate(metric_key: str, value: float) -> str:
    """
    Evaluate a metric value against thresholds.

    Returns: 'good', 'neutral', or 'bad'.
    """
    import math

    if value is None or (isinstance(value, float) and math.isnan(value)):
        return "neutral"

    t = THRESHOLDS[metric_key]

    if t["higher_is_better"]:
        if value >= t["good"]:
            return "good"
        elif value < t["bad"]:
            return "bad"
        else:
            return "neutral"
    else:
        # Lower is better (PEG, LT Debt/FCF)
        if value <= t["good"]:
            if metric_key == "peg_ratio" and value < 0:
                return "bad"  # Negative PEG means negative earnings growth
            return "good"
        elif value > t["bad"]:
            return "bad"
        else:
            return "neutral"


def rating_emoji(rating: str) -> str:
    """Return a colored emoji for a rating."""
    return {"good": "🟢", "neutral": "🟡", "bad": "🔴"}.get(rating, "⚪")


def rating_color(rating: str) -> str:
    """Return a CSS/Plotly color for a rating."""
    return {"good": "#22c55e", "neutral": "#eab308", "bad": "#ef4444"}.get(rating, "#6b7280")


def format_value(metric_key: str, value: float) -> str:
    """Format a metric value with its unit."""
    import math

    if value is None or (isinstance(value, float) and math.isnan(value)):
        return "N/A"

    t = THRESHOLDS[metric_key]
    fmt = t["format"]
    unit = t["unit"]
    return f"{value:{fmt}}{unit}"


def badge_html(metric_key: str, symbol: str, value: float) -> str:
    """Return an HTML badge string for a metric value."""
    rating = evaluate(metric_key, value)
    emoji = rating_emoji(rating)
    formatted = format_value(metric_key, value)
    return f"{emoji} **{symbol}**: {formatted}"


# ---------------------------------------------------------------------------
# Formula descriptions for info popovers
# ---------------------------------------------------------------------------

METRIC_FORMULAS = {
    "gross_margin": """**📐 Gross Margin (%)**

**Formula:**

$$\\text{Gross Margin} = \\frac{\\text{Gross Profit}}{\\text{Total Revenue}} \\times 100$$

**Data source fields:**
- **yfinance:** `Gross Profit` ÷ `Total Revenue`
- **StockAnalysis:** pre-calculated `Gross Margin` on income page

**Thresholds:**
- 🟢 Good: ≥ 50%
- 🟡 Neutral: 20–50%
- 🔴 Bad: < 20%

**Interpretation:** Measures how much profit a company retains after direct production costs. Higher margins indicate stronger pricing power and cost efficiency.
""",
    "peg_ratio": """**📐 PEG Ratio**

**Formula:**

$$\\text{PEG} = \\frac{\\text{PE Ratio}}{\\text{EPS Growth Rate (\\%)}}$$

where:

$$\\text{PE} = \\frac{\\text{Year-End Stock Price}}{\\text{Diluted EPS}}$$

$$\\text{EPS Growth} = \\frac{\\text{EPS}_{\\text{current}} - \\text{EPS}_{\\text{previous}}}{\\text{EPS}_{\\text{previous}}} \\times 100$$

**Data source fields:**
- **yfinance:** `Diluted EPS`, year-end close price from history
- **StockAnalysis:** pre-calculated `PEG Ratio` on ratios page

**Thresholds:**
- 🟢 Good: ≤ 2.0
- 🟡 Neutral: 2.0–3.0
- 🔴 Bad: > 3.0 (or negative)

**Interpretation:** Adjusts the PE ratio for growth. A PEG < 1 suggests the stock may be undervalued relative to its earnings growth.
""",
    "revenue_growth": """**📐 Revenue Growth (%)**

**Formula:**

$$\\text{Revenue Growth} = \\frac{\\text{Revenue}_{\\text{current}} - \\text{Revenue}_{\\text{previous}}}{\\text{Revenue}_{\\text{previous}}} \\times 100$$

**Data source fields:**
- **yfinance:** `Total Revenue` (YoY percentage change)
- **StockAnalysis:** pre-calculated `Revenue Growth (YoY)` on income page

**Thresholds:**
- 🟢 Good: > 10%
- 🟡 Neutral: 0–10%
- 🔴 Bad: < 0% (shrinking revenue)

**Interpretation:** Measures how fast a company is growing its top line. Sustained double-digit growth signals strong demand.
""",
    "roce": """**📐 Return on Capital Employed (ROCE) (%)**

**Formula:**

$$\\text{ROCE} = \\frac{\\text{EBIT}}{\\text{Capital Employed}} \\times 100$$

where:

$$\\text{Capital Employed} = \\text{Total Assets} - \\text{Current Liabilities}$$

**Data source fields:**
- **yfinance:** `EBIT` (or `Operating Income`), `Total Assets`, `Current Liabilities`
- **StockAnalysis:** pre-calculated `Return on Capital Employed (ROCE)` on ratios page

**Thresholds:**
- 🟢 Good: ≥ 15%
- 🟡 Neutral: 5–15%
- 🔴 Bad: < 5%

**Interpretation:** Measures how efficiently a company generates profit from its capital. Higher ROCE means better capital allocation.
""",
    "fcf_growth": """**📐 Free Cash Flow Growth (%)**

**Formula:**

$$\\text{FCF Growth} = \\frac{\\text{FCF}_{\\text{current}} - \\text{FCF}_{\\text{previous}}}{\\text{FCF}_{\\text{previous}}} \\times 100$$

**Data source fields:**
- **yfinance:** `Free Cash Flow` from cash flow statement (YoY change)
- **StockAnalysis:** pre-calculated `Free Cash Flow Growth` on income page

**Thresholds:**
- 🟢 Good: > 10%
- 🟡 Neutral: 0–10%
- 🔴 Bad: < 0% (shrinking FCF)

**Interpretation:** Free cash flow is the cash available after capital expenditures. Growing FCF indicates improving ability to fund dividends, buybacks, and acquisitions.
""",
    "ltd_fcf": """**📐 Long-Term Debt / Free Cash Flow**

**Formula:**

$$\\text{LT Debt / FCF} = \\frac{\\text{Long-Term Debt}}{\\text{Free Cash Flow}}$$

**Data source fields:**
- **yfinance:** `Long Term Debt` (balance sheet) ÷ `Free Cash Flow` (cash flow)
- **StockAnalysis:** `Long-Term Debt` (balance sheet) ÷ `Free Cash Flow` (income/cash flow page)

**Thresholds:**
- 🟢 Good: < 4.0×
- 🟡 Neutral: 4.0–5.0×
- 🔴 Bad: > 5.0×

**Interpretation:** Shows how many years of free cash flow it would take to pay off long-term debt. Lower is better — indicates manageable debt levels.
""",
    "dcf_mos": """**📐 DCF Margin of Safety (%)**

**Formula:**

$$\\text{Margin of Safety} = \\frac{\\text{Intrinsic Value} - \\text{Market Price}}{\\text{Market Price}} \\times 100$$

**Two-stage DCF model:**

*Stage 1 — Project FCF for 10 years:*

$$\\text{FCF}_n = \\text{FCF}_{\\text{current}} \\times (1 + g)^n$$

$$\\text{Discounted FCF}_n = \\frac{\\text{FCF}_n}{(1 + \\text{WACC})^n}$$

*Stage 2 — Terminal Value (Gordon Growth Model):*

$$\\text{Terminal Value} = \\frac{\\text{FCF}_{10} \\times (1 + g_{\\text{terminal}})}{\\text{WACC} - g_{\\text{terminal}}}$$

*Equity Value:*

$$\\text{Equity} = \\sum \\text{Discounted FCF} + \\text{Discounted Terminal} - \\text{Debt} + \\text{Cash}$$

$$\\text{Intrinsic Value per Share} = \\frac{\\text{Equity}}{\\text{Shares Outstanding}}$$

**Assumptions:**

| Parameter | Value |
|---|---|
| WACC (discount rate) | 10% |
| Terminal growth | 3% |
| Projection years | 10 |
| FCF growth rate | Average of historical YoY FCF growth, clamped to 2–25% |

**Data source fields:**
- **yfinance:** `Free Cash Flow`, `Diluted Average Shares`, `Total Debt`, `Cash And Cash Equivalents`, year-end close price
- **StockAnalysis:** `Free Cash Flow`, `Shares Outstanding (Diluted)`, `Total Debt`, `Cash & Short-Term Investments`, `Last Close Price`

**Thresholds:**
- 🟢 Good: ≥ +20% (undervalued)
- 🟡 Neutral: −20% to +20%
- 🔴 Bad: < −20% (overvalued)

**Interpretation:** Positive = stock trades below estimated intrinsic value (potential upside). Negative = overvalued relative to DCF model. Highly sensitive to growth rate assumptions.
""",
}
