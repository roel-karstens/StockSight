"""
metrics.py – Financial metric calculations.

Computes the 7 key metrics from raw yfinance financial data:
1. Gross Margin (%)
2. PEG Ratio (-)
3. Revenue Growth (%)
4. ROCE (%)
5. Free Cash Flow Growth (%)
6. Long-Term Debt / FCF (-)
7. DCF Margin of Safety (%) – compares intrinsic value (DCF) to market price
"""

import numpy as np
import pandas as pd


# ---------------------------------------------------------------------------
# Column name helpers – yfinance column names can vary between versions
# ---------------------------------------------------------------------------

def _find_col(df: pd.DataFrame, candidates: list[str]) -> str | None:
    """Return the first column name from candidates that exists in df."""
    for c in candidates:
        if c in df.columns:
            return c
    return None


def _safe_get(df: pd.DataFrame, candidates: list[str]) -> pd.Series:
    """Return a Series for the first matching column, or NaN Series."""
    col = _find_col(df, candidates)
    if col is not None:
        return df[col]
    return pd.Series(np.nan, index=df.index)


# ---------------------------------------------------------------------------
# Individual metric calculators
# ---------------------------------------------------------------------------

def gross_margin(income: pd.DataFrame) -> pd.Series:
    """Gross Margin (%) = Gross Profit / Total Revenue × 100."""
    revenue = _safe_get(income, ["Total Revenue", "Revenue"])
    gross_profit = _safe_get(income, ["Gross Profit"])
    return (gross_profit / revenue * 100).replace([np.inf, -np.inf], np.nan)


def revenue_growth(income: pd.DataFrame) -> pd.Series:
    """Revenue Growth (%) = YoY percentage change in revenue."""
    revenue = _safe_get(income, ["Total Revenue", "Revenue"])
    return (revenue.pct_change() * 100).replace([np.inf, -np.inf], np.nan)


def roce(income: pd.DataFrame, balance: pd.DataFrame) -> pd.Series:
    """ROCE (%) = EBIT / (Total Assets − Current Liabilities) × 100."""
    ebit = _safe_get(income, ["EBIT", "Operating Income"])
    total_assets = _safe_get(balance, ["Total Assets"])
    current_liabilities = _safe_get(balance, ["Current Liabilities"])

    # Align indices (fiscal year dates)
    common_idx = ebit.index.intersection(total_assets.index).intersection(current_liabilities.index)
    capital_employed = total_assets.loc[common_idx] - current_liabilities.loc[common_idx]
    result = (ebit.loc[common_idx] / capital_employed * 100).replace([np.inf, -np.inf], np.nan)
    return result.reindex(income.index)


def fcf_growth(cashflow: pd.DataFrame) -> pd.Series:
    """Free Cash Flow Growth (%) = YoY percentage change in FCF."""
    fcf = _safe_get(cashflow, ["Free Cash Flow"])
    return (fcf.pct_change() * 100).replace([np.inf, -np.inf], np.nan)


def ltd_over_fcf(balance: pd.DataFrame, cashflow: pd.DataFrame) -> pd.Series:
    """Long-Term Debt / Free Cash Flow."""
    ltd = _safe_get(balance, ["Long Term Debt", "Long-Term Debt", "LongTermDebt"])
    fcf = _safe_get(cashflow, ["Free Cash Flow"])

    common_idx = ltd.index.intersection(fcf.index)
    result = (ltd.loc[common_idx] / fcf.loc[common_idx]).replace([np.inf, -np.inf], np.nan)
    return result.reindex(balance.index)


def peg_ratio(
    income: pd.DataFrame,
    history: pd.DataFrame,
) -> pd.Series:
    """
    PEG Ratio = PE / EPS Growth Rate.

    PE is computed from year-end closing price / diluted EPS.
    EPS growth is YoY % change.
    """
    eps = _safe_get(income, ["Diluted EPS", "Basic EPS"])

    if eps.isna().all():
        # Fallback: compute EPS from net income / shares
        net_income = _safe_get(income, ["Net Income", "Net Income Common Stockholders"])
        shares = _safe_get(income, [
            "Diluted Average Shares", "Basic Average Shares",
            "Shares Outstanding", "Ordinary Shares Number",
        ])
        if not net_income.isna().all() and not shares.isna().all():
            eps = net_income / shares
        else:
            return pd.Series(np.nan, index=income.index)

    eps_growth_pct = eps.pct_change() * 100  # e.g. 15 means 15%

    # Get year-end prices aligned to fiscal year end dates
    if history is None or history.empty:
        return pd.Series(np.nan, index=income.index)

    # Normalize timezones – history index is often tz-aware, income index is tz-naive
    hist_index = history.index.tz_localize(None) if history.index.tz is not None else history.index

    year_end_prices = []
    for date in income.index:
        # Find the closest price to fiscal year end
        date_naive = date.tz_localize(None) if hasattr(date, 'tz') and date.tz is not None else date
        mask = hist_index <= date_naive
        if mask.any():
            year_end_prices.append(history.loc[history.index[mask], "Close"].iloc[-1])
        else:
            year_end_prices.append(np.nan)

    prices = pd.Series(year_end_prices, index=income.index)
    pe = prices / eps
    peg = (pe / eps_growth_pct).replace([np.inf, -np.inf], np.nan)
    return peg


# ---------------------------------------------------------------------------
# DCF Valuation
# ---------------------------------------------------------------------------

# Default DCF assumptions
DCF_PROJECTION_YEARS = 10
DCF_TERMINAL_GROWTH = 0.03   # 3% perpetual growth
DCF_DISCOUNT_RATE = 0.10     # 10% WACC (simplified)
DCF_FCF_GROWTH_DEFAULT = 0.08  # 8% default if we can't estimate


def dcf_margin_of_safety(
    cashflow: pd.DataFrame,
    balance: pd.DataFrame,
    income: pd.DataFrame,
    history: pd.DataFrame,
    info: dict,
) -> pd.Series:
    """
    DCF Margin of Safety (%) for each fiscal year.

    For each year, computes an intrinsic value per share using a simple
    two-stage DCF model (high growth → terminal value), then compares
    to the actual stock price at that fiscal year end.

    Margin of Safety = (Intrinsic Value - Market Price) / Market Price × 100
    Positive = undervalued, Negative = overvalued.
    """
    fcf_series = _safe_get(cashflow, ["Free Cash Flow"])
    shares = _safe_get(income, ["Diluted Average Shares", "Basic Average Shares"])
    # Fall back to balance sheet shares
    if shares.isna().all():
        shares = _safe_get(balance, ["Ordinary Shares Number", "Share Issued"])

    total_debt = _safe_get(balance, ["Total Debt", "Net Debt"])
    cash = _safe_get(balance, [
        "Cash And Cash Equivalents",
        "Cash Cash Equivalents And Short Term Investments",
    ])

    # Get year-end prices
    if history is None or history.empty:
        return pd.Series(np.nan, index=cashflow.index)

    hist_index = history.index.tz_localize(None) if history.index.tz is not None else history.index

    # Estimate FCF growth rate from available data – use average of all available
    fcf_growth_rates = fcf_series.pct_change()
    avg_fcf_growth = fcf_growth_rates.dropna()
    if not avg_fcf_growth.empty:
        mean_growth = avg_fcf_growth.mean()
        mean_growth = max(min(mean_growth, 0.25), 0.02)  # clamp 2-25%
    else:
        mean_growth = DCF_FCF_GROWTH_DEFAULT

    results = []
    common_idx = fcf_series.index.intersection(shares.index)

    for i, date in enumerate(cashflow.index):
        try:
            fcf_val = fcf_series.loc[date]
            shares_val = shares.reindex(cashflow.index, method="nearest").loc[date]
            debt_val = total_debt.reindex(cashflow.index, method="nearest").loc[date]
            cash_val = cash.reindex(cashflow.index, method="nearest").loc[date]

            if pd.isna(fcf_val) or pd.isna(shares_val) or shares_val <= 0 or fcf_val <= 0:
                results.append(np.nan)
                continue

            # Use the overall average growth rate for stability
            est_growth = mean_growth

            # Stage 1: project FCF for 10 years
            discount_rate = DCF_DISCOUNT_RATE
            projected_fcf = []
            current_fcf = fcf_val
            for yr in range(1, DCF_PROJECTION_YEARS + 1):
                current_fcf *= (1 + est_growth)
                discounted = current_fcf / (1 + discount_rate) ** yr
                projected_fcf.append(discounted)

            # Stage 2: terminal value (Gordon Growth Model)
            terminal_fcf = current_fcf * (1 + DCF_TERMINAL_GROWTH)
            terminal_value = terminal_fcf / (discount_rate - DCF_TERMINAL_GROWTH)
            discounted_terminal = terminal_value / (1 + discount_rate) ** DCF_PROJECTION_YEARS

            # Enterprise value
            enterprise_value = sum(projected_fcf) + discounted_terminal

            # Equity value = EV - debt + cash
            debt_adj = debt_val if not pd.isna(debt_val) else 0
            cash_adj = cash_val if not pd.isna(cash_val) else 0
            equity_value = enterprise_value - debt_adj + cash_adj

            intrinsic_per_share = equity_value / shares_val

            # Get stock price at fiscal year end
            date_naive = date.tz_localize(None) if hasattr(date, 'tz') and date.tz is not None else date
            mask = hist_index <= date_naive
            if mask.any():
                market_price = history.loc[history.index[mask], "Close"].iloc[-1]
            else:
                results.append(np.nan)
                continue

            # Margin of safety: positive = undervalued
            mos = (intrinsic_per_share - market_price) / market_price * 100
            results.append(mos)

        except Exception:
            results.append(np.nan)

    return pd.Series(results, index=cashflow.index)


# ---------------------------------------------------------------------------
# Master function: compute all metrics for a single ticker
# ---------------------------------------------------------------------------

def compute_all_metrics(data: dict, years: int = 10) -> pd.DataFrame:
    """
    Compute all 7 metrics from fetched data.

    Supports both yfinance and stockanalysis.com data sources.
    When source is stockanalysis, pre-calculated ratios are used where available.

    Args:
        data: dict returned by fetcher.fetch_financials() or scraper.fetch_stockanalysis()
        years: number of years of history to return

    Returns:
        DataFrame with columns: year, gross_margin, peg_ratio, revenue_growth,
        roce, fcf_growth, ltd_fcf, dcf_mos
    """
    source = data.get("source", "yfinance")

    if source == "stockanalysis":
        return _compute_from_stockanalysis(data, years)
    else:
        return _compute_from_yfinance(data, years)


def _compute_from_yfinance(data: dict, years: int) -> pd.DataFrame:
    """Compute metrics from yfinance raw financial data (original logic)."""
    income = data["income"]
    balance = data["balance"]
    cashflow = data["cashflow"]
    history = data["history"]

    # Trim to requested number of years (keep extra row for YoY calculations)
    n = min(years + 1, len(income))
    income_trimmed = income.iloc[-n:]
    balance_trimmed = balance.iloc[-n:] if not balance.empty else balance
    cashflow_trimmed = cashflow.iloc[-n:] if not cashflow.empty else cashflow

    df = pd.DataFrame(index=income_trimmed.index)
    df.index.name = "date"

    df["gross_margin"] = gross_margin(income_trimmed)
    df["revenue_growth"] = revenue_growth(income_trimmed)
    df["roce"] = roce(income_trimmed, balance_trimmed)
    df["fcf_growth"] = fcf_growth(cashflow_trimmed)
    df["ltd_fcf"] = ltd_over_fcf(balance_trimmed, cashflow_trimmed)
    df["peg_ratio"] = peg_ratio(income_trimmed, history)
    df["dcf_mos"] = dcf_margin_of_safety(
        cashflow_trimmed, balance_trimmed, income_trimmed, history, data.get("info", {})
    )

    # Drop the first row (NaN from pct_change) and limit to requested years
    df = df.iloc[1:]  # drop first row used for pct_change
    df = df.iloc[-years:]

    # Create readable year labels
    df["year"] = df.index.strftime("%Y")

    return df


def _sa_get(df: pd.DataFrame, candidates: list[str]) -> pd.Series:
    """Get a column from a stockanalysis DataFrame by trying candidate names."""
    for c in candidates:
        if c in df.columns:
            return df[c]
    return pd.Series(np.nan, index=df.index)


def _compute_from_stockanalysis(data: dict, years: int) -> pd.DataFrame:
    """Compute metrics from stockanalysis.com scraped data.

    Uses pre-calculated ratios where available, computes LT Debt/FCF and DCF ourselves.
    """
    income = data["income"]
    balance = data["balance"]
    cashflow = data["cashflow"]
    ratios = data.get("ratios", pd.DataFrame())
    info = data.get("info", {})

    # Use the longest available DataFrame's index
    if not income.empty:
        idx = income.index
    elif not ratios.empty:
        idx = ratios.index
    else:
        return pd.DataFrame()

    # Limit to requested years
    idx = idx[-years:]
    df = pd.DataFrame(index=idx)
    df.index.name = "year_label"

    # 1. Gross Margin (%) – pre-calculated on income statement page
    df["gross_margin"] = _sa_get(income, ["Gross Margin"]).reindex(idx)

    # 2. Revenue Growth (%) – pre-calculated on income statement page
    df["revenue_growth"] = _sa_get(income, ["Revenue Growth (YoY)", "Revenue Growth"]).reindex(idx)

    # 3. PEG Ratio – pre-calculated on ratios page
    df["peg_ratio"] = _sa_get(ratios, ["PEG Ratio"]).reindex(idx)

    # 4. ROCE (%) – pre-calculated on ratios page
    roce_series = _sa_get(ratios, ["Return on Capital Employed (ROCE)", "ROCE"])
    # Strip % if stored as string-like values (already parsed as float)
    df["roce"] = roce_series.reindex(idx)

    # 5. FCF Growth (%) – pre-calculated on income statement page
    df["fcf_growth"] = _sa_get(income, ["Free Cash Flow Growth"]).reindex(idx)
    # Also try cash flow page
    if df["fcf_growth"].isna().all():
        df["fcf_growth"] = _sa_get(cashflow, ["Free Cash Flow Growth"]).reindex(idx)

    # 6. LT Debt / FCF – compute from scraped raw data
    ltd = _sa_get(balance, ["Long-Term Debt", "Long Term Debt"]).reindex(idx)
    fcf_vals = _sa_get(income, ["Free Cash Flow"]).reindex(idx)
    if fcf_vals.isna().all():
        fcf_vals = _sa_get(cashflow, ["Free Cash Flow"]).reindex(idx)
    df["ltd_fcf"] = (ltd / fcf_vals).replace([np.inf, -np.inf], np.nan)

    # 7. DCF Margin of Safety – compute from scraped data
    df["dcf_mos"] = _dcf_from_stockanalysis(income, balance, cashflow, ratios, info, idx)

    # Year labels – index is already year strings from scraper
    df["year"] = idx

    return df


def _dcf_from_stockanalysis(
    income: pd.DataFrame,
    balance: pd.DataFrame,
    cashflow: pd.DataFrame,
    ratios: pd.DataFrame,
    info: dict,
    idx: pd.Index,
) -> pd.Series:
    """Compute DCF Margin of Safety from stockanalysis.com scraped data."""
    # Get FCF (in millions on stockanalysis.com)
    fcf_series = _sa_get(income, ["Free Cash Flow"]).reindex(idx)
    if fcf_series.isna().all():
        fcf_series = _sa_get(cashflow, ["Free Cash Flow"]).reindex(idx)

    shares_series = _sa_get(income, [
        "Shares Outstanding (Diluted)", "Shares Outstanding (Basic)"
    ]).reindex(idx)

    total_debt_series = _sa_get(balance, ["Total Debt"]).reindex(idx)
    cash_series = _sa_get(balance, [
        "Cash & Short-Term Investments", "Cash & Equivalents",
    ]).reindex(idx)

    # Stock price per year from ratios page
    price_series = _sa_get(ratios, ["Last Close Price"]).reindex(idx)

    # Average FCF growth for projection
    fcf_growth_rates = fcf_series.pct_change().dropna()
    if not fcf_growth_rates.empty:
        mean_growth = fcf_growth_rates.mean()
        mean_growth = max(min(mean_growth, 0.25), 0.02)
    else:
        mean_growth = DCF_FCF_GROWTH_DEFAULT

    results = []
    for year in idx:
        try:
            fcf_val = fcf_series.get(year, np.nan)
            shares_val = shares_series.get(year, np.nan)
            debt_val = total_debt_series.get(year, np.nan)
            cash_val = cash_series.get(year, np.nan)
            price_val = price_series.get(year, np.nan)

            # stockanalysis.com reports in millions; shares in millions too
            # FCF and debt in millions, shares in millions → per-share = millions/millions = OK
            if pd.isna(fcf_val) or pd.isna(shares_val) or shares_val <= 0 or fcf_val <= 0:
                results.append(np.nan)
                continue

            if pd.isna(price_val) or price_val <= 0:
                results.append(np.nan)
                continue

            est_growth = mean_growth

            # Stage 1: project FCF
            projected_fcf = []
            current_fcf = fcf_val
            for yr in range(1, DCF_PROJECTION_YEARS + 1):
                current_fcf *= (1 + est_growth)
                discounted = current_fcf / (1 + DCF_DISCOUNT_RATE) ** yr
                projected_fcf.append(discounted)

            # Stage 2: terminal value
            terminal_fcf = current_fcf * (1 + DCF_TERMINAL_GROWTH)
            terminal_value = terminal_fcf / (DCF_DISCOUNT_RATE - DCF_TERMINAL_GROWTH)
            discounted_terminal = terminal_value / (1 + DCF_DISCOUNT_RATE) ** DCF_PROJECTION_YEARS

            enterprise_value = sum(projected_fcf) + discounted_terminal
            debt_adj = debt_val if not pd.isna(debt_val) else 0
            cash_adj = cash_val if not pd.isna(cash_val) else 0
            equity_value = enterprise_value - debt_adj + cash_adj

            intrinsic_per_share = equity_value / shares_val
            mos = (intrinsic_per_share - price_val) / price_val * 100
            results.append(mos)
        except Exception:
            results.append(np.nan)

    return pd.Series(results, index=idx)
