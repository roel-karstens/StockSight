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
