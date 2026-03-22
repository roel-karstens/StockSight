"""
allocation.py – Portfolio allocation classification.

Takes yfinance info dicts for each ticker and builds a DataFrame
with country, sector, cap-size-bucket, and equal-weight columns
suitable for treemap visualisation.
"""

import pandas as pd


# ---------------------------------------------------------------------------
# Cap-size classification
# ---------------------------------------------------------------------------

_CAP_BUCKETS = [
    (200_000_000_000, "Mega Cap"),
    (10_000_000_000, "Large Cap"),
    (2_000_000_000, "Mid Cap"),
    (0, "Small Cap"),
]


def _classify_cap(market_cap: float | None) -> str:
    """Return a human-readable cap-size bucket label."""
    if market_cap is None:
        return "Unknown"
    for threshold, label in _CAP_BUCKETS:
        if market_cap >= threshold:
            return label
    return "Small Cap"


def _fmt_cap(market_cap: float | None) -> str:
    """Format market cap as a short human-readable string (e.g. '$2.8T')."""
    if market_cap is None:
        return "N/A"
    if market_cap >= 1e12:
        return f"${market_cap / 1e12:.1f}T"
    if market_cap >= 1e9:
        return f"${market_cap / 1e9:.1f}B"
    if market_cap >= 1e6:
        return f"${market_cap / 1e6:.0f}M"
    return f"${market_cap:,.0f}"


def build_allocation_df(
    ticker_infos: dict[str, dict],
) -> pd.DataFrame:
    """
    Build an allocation DataFrame from yfinance info dicts.

    Parameters
    ----------
    ticker_infos : dict[str, dict]
        Mapping of ticker symbol → yfinance ``ticker.info`` dict.

    Returns
    -------
    pd.DataFrame with columns:
        ticker, country, sector, industry, market_cap, cap_bucket,
        cap_label, weight
    """
    n = len(ticker_infos)
    if n == 0:
        return pd.DataFrame()

    weight = 100.0 / n

    rows = []
    for symbol, info in ticker_infos.items():
        mc = info.get("marketCap")
        rows.append(
            {
                "ticker": symbol,
                "country": info.get("country") or "Unknown",
                "sector": info.get("sector") or "Unknown",
                "industry": info.get("industry") or "Unknown",
                "market_cap": mc,
                "cap_bucket": _classify_cap(mc),
                "cap_label": _fmt_cap(mc),
                "weight": weight,
            }
        )

    return pd.DataFrame(rows)
