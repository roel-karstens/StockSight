"""
metrics.py – Financial metric calculations.

Computes the 10 key metrics from raw financial data:
1. Stock Price ($) – year-end closing price
2. Gross Margin (%)
3. ROCE (%)
4. Long-Term Debt / FCF (-)
5. Revenue Growth (%)
6. Free Cash Flow Growth (%)
7. PE Ratio (-)
8. PEG Ratio (-)
9. DCF Margin of Safety (%) – compares intrinsic value (DCF) to market price
10. Implied FCF Growth (%) – reverse DCF: what growth rate justifies the price?
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
    return (revenue.pct_change(fill_method=None) * 100).replace([np.inf, -np.inf], np.nan)


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
    return (fcf.pct_change(fill_method=None) * 100).replace([np.inf, -np.inf], np.nan)


def ltd_over_fcf(balance: pd.DataFrame, cashflow: pd.DataFrame) -> pd.Series:
    """Long-Term Debt / Free Cash Flow."""
    ltd = _safe_get(balance, ["Long Term Debt", "Long-Term Debt", "LongTermDebt"])
    fcf = _safe_get(cashflow, ["Free Cash Flow"])

    common_idx = ltd.index.intersection(fcf.index)
    result = (ltd.loc[common_idx] / fcf.loc[common_idx]).replace([np.inf, -np.inf], np.nan)
    return result.reindex(balance.index)


def _year_end_prices(dates: pd.Index, history: pd.DataFrame) -> pd.Series:
    """Get the stock price closest to each fiscal year-end date."""
    if history is None or history.empty:
        return pd.Series(np.nan, index=dates)

    hist_index = history.index.tz_localize(None) if history.index.tz is not None else history.index
    prices = []
    for date in dates:
        date_naive = date.tz_localize(None) if hasattr(date, 'tz') and date.tz is not None else date
        mask = hist_index <= date_naive
        if mask.any():
            prices.append(history.loc[history.index[mask], "Close"].iloc[-1])
        else:
            prices.append(np.nan)
    return pd.Series(prices, index=dates)


def stock_price(income: pd.DataFrame, history: pd.DataFrame) -> pd.Series:
    """Year-end closing stock price ($)."""
    return _year_end_prices(income.index, history)


def pe_ratio(income: pd.DataFrame, history: pd.DataFrame) -> pd.Series:
    """PE Ratio = Year-End Stock Price / Diluted EPS."""
    eps = _safe_get(income, ["Diluted EPS", "Basic EPS"])

    if eps.isna().all():
        net_income = _safe_get(income, ["Net Income", "Net Income Common Stockholders"])
        shares = _safe_get(income, [
            "Diluted Average Shares", "Basic Average Shares",
            "Shares Outstanding", "Ordinary Shares Number",
        ])
        if not net_income.isna().all() and not shares.isna().all():
            eps = net_income / shares
        else:
            return pd.Series(np.nan, index=income.index)

    prices = _year_end_prices(income.index, history)
    result = (prices / eps).replace([np.inf, -np.inf], np.nan)
    return result


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

    eps_growth_pct = eps.pct_change(fill_method=None) * 100  # e.g. 15 means 15%

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
    fcf_growth_rates = fcf_series.pct_change(fill_method=None)
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
# Reverse DCF – Implied FCF Growth Rate
# ---------------------------------------------------------------------------

def _dcf_intrinsic_per_share(fcf, shares, debt, cash, growth,
                              discount=DCF_DISCOUNT_RATE,
                              terminal_g=DCF_TERMINAL_GROWTH,
                              years=DCF_PROJECTION_YEARS):
    """Compute intrinsic value per share for a given FCF growth rate."""
    cf = fcf
    pv_sum = 0.0
    for yr in range(1, years + 1):
        cf *= (1 + growth)
        pv_sum += cf / (1 + discount) ** yr
    tv = cf * (1 + terminal_g) / (discount - terminal_g)
    pv_tv = tv / (1 + discount) ** years
    equity = pv_sum + pv_tv - debt + cash
    return equity / shares


def _solve_implied_growth(fcf, shares, debt, cash, market_price,
                           discount=DCF_DISCOUNT_RATE,
                           terminal_g=DCF_TERMINAL_GROWTH,
                           years=DCF_PROJECTION_YEARS):
    """Bisection search: find growth rate where intrinsic value = market price."""
    if fcf <= 0 or shares <= 0 or market_price <= 0:
        return np.nan

    lo, hi = -0.10, 0.60  # search between -10% and 60%
    target = market_price
    for _ in range(100):
        mid = (lo + hi) / 2
        iv = _dcf_intrinsic_per_share(fcf, shares, debt, cash, mid,
                                       discount, terminal_g, years)
        if iv < target:
            lo = mid
        else:
            hi = mid
    return mid


def implied_fcf_growth(
    cashflow: pd.DataFrame,
    balance: pd.DataFrame,
    income: pd.DataFrame,
    history: pd.DataFrame,
) -> pd.Series:
    """
    Reverse DCF Implied Growth Rate (%) for each fiscal year.

    Finds the FCF growth rate that would make intrinsic value = market price.
    """
    fcf_series = _safe_get(cashflow, ["Free Cash Flow"])
    shares = _safe_get(income, ["Diluted Average Shares", "Basic Average Shares"])
    if shares.isna().all():
        shares = _safe_get(balance, ["Ordinary Shares Number", "Share Issued"])

    total_debt = _safe_get(balance, ["Total Debt", "Net Debt"])
    cash_series = _safe_get(balance, [
        "Cash And Cash Equivalents",
        "Cash Cash Equivalents And Short Term Investments",
    ])

    prices = _year_end_prices(cashflow.index, history)

    results = []
    for date in cashflow.index:
        try:
            fcf_val = fcf_series.loc[date]
            shares_val = shares.reindex(cashflow.index, method="nearest").loc[date]
            debt_val = total_debt.reindex(cashflow.index, method="nearest").loc[date]
            cash_val = cash_series.reindex(cashflow.index, method="nearest").loc[date]
            price_val = prices.loc[date]

            if pd.isna(fcf_val) or pd.isna(shares_val) or shares_val <= 0 or fcf_val <= 0:
                results.append(np.nan)
                continue
            if pd.isna(price_val) or price_val <= 0:
                results.append(np.nan)
                continue

            debt_adj = debt_val if not pd.isna(debt_val) else 0
            cash_adj = cash_val if not pd.isna(cash_val) else 0

            g = _solve_implied_growth(fcf_val, shares_val, debt_adj, cash_adj, price_val)
            results.append(g * 100 if not np.isnan(g) else np.nan)  # as percentage
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

    if source == "combined":
        return _compute_combined(data, years)
    elif source == "stockanalysis":
        return _compute_from_stockanalysis(data, years)
    else:
        return _compute_from_yfinance(data, years)


def _compute_combined(data: dict, years: int) -> pd.DataFrame:
    """Compute metrics from combined SA financials + yfinance prices.

    Uses StockAnalysis.com pre-calculated ratios (Gross Margin, ROCE, etc.)
    and yfinance price history for year-end prices, PE, DCF, Implied Growth.
    Always appends a "Now" row with the live market price.
    """
    income = data["income"]       # SA
    balance = data["balance"]     # SA
    cashflow = data["cashflow"]   # SA
    ratios = data.get("ratios", pd.DataFrame())  # SA
    history = data.get("history", pd.DataFrame())  # yfinance
    info = data.get("info", {})   # yfinance
    yf_income = data.get("yf_income", pd.DataFrame())  # yfinance (for FY dates)

    if income.empty:
        return pd.DataFrame()

    # SA index is year strings like "2021", "2022", ...
    sa_idx = income.index[-years:] if len(income) > years else income.index

    # --- Map SA year labels to actual fiscal-year-end dates from yfinance ---
    # yfinance income has exact dates like 2025-06-30
    fy_date_map = {}
    if not yf_income.empty:
        for dt in yf_income.index:
            fy_date_map[str(dt.year)] = dt

    # Build the actual date index, falling back to Dec 31 if yfinance doesn't have a date
    actual_dates = []
    for yr_str in sa_idx:
        if yr_str in fy_date_map:
            actual_dates.append(fy_date_map[yr_str])
        else:
            # Approximate: use June 30 if we know the FY month, else Dec 31
            try:
                actual_dates.append(pd.Timestamp(f"{yr_str}-12-31"))
            except Exception:
                actual_dates.append(pd.Timestamp.now().normalize())

    date_index = pd.DatetimeIndex(actual_dates)

    # --- Build DataFrame with actual dates as index ---
    df = pd.DataFrame(index=date_index)
    df.index.name = "date"

    # SA pre-calculated metrics (reindex from SA year index → our date index)
    def _sa_reindex(series_or_col):
        """Map a SA-indexed series to our date_index."""
        vals = []
        for yr_str, dt in zip(sa_idx, date_index):
            vals.append(series_or_col.get(yr_str, np.nan) if hasattr(series_or_col, 'get') else np.nan)
        return pd.Series(vals, index=date_index)

    # 1. Gross Margin
    df["gross_margin"] = _sa_reindex(_sa_get(income, ["Gross Margin"]))

    # 2. Revenue Growth
    df["revenue_growth"] = _sa_reindex(
        _sa_get(income, ["Revenue Growth (YoY)", "Revenue Growth"])
    )

    # 3. ROCE
    df["roce"] = _sa_reindex(
        _sa_get(ratios, ["Return on Capital Employed (ROCE)", "ROCE"])
    )

    # 4. FCF Growth
    fcf_g = _sa_get(income, ["Free Cash Flow Growth"])
    if fcf_g.isna().all():
        fcf_g = _sa_get(cashflow, ["Free Cash Flow Growth"])
    df["fcf_growth"] = _sa_reindex(fcf_g)

    # 5. LT Debt / FCF
    ltd = _sa_get(balance, ["Long-Term Debt", "Long Term Debt"])
    fcf_vals = _sa_get(income, ["Free Cash Flow"])
    if fcf_vals.isna().all():
        fcf_vals = _sa_get(cashflow, ["Free Cash Flow"])
    ltd_reindexed = _sa_reindex(ltd)
    fcf_reindexed = _sa_reindex(fcf_vals)
    df["ltd_fcf"] = (ltd_reindexed / fcf_reindexed).replace([np.inf, -np.inf], np.nan)

    # 6. PEG Ratio (from SA)
    df["peg_ratio"] = _sa_reindex(_sa_get(ratios, ["PEG Ratio"]))

    # --- Price-dependent metrics: use yfinance year-end prices ---
    if not history.empty:
        prices = _year_end_prices(date_index, history)
    else:
        # Fall back to SA Last Close Price
        prices = _sa_reindex(_sa_get(ratios, ["Last Close Price"]))
    df["stock_price"] = prices

    # 7. PE Ratio: use yfinance year-end price / SA EPS
    eps = _sa_reindex(_sa_get(income, ["EPS (Diluted)", "EPS (Basic)"]))
    df["pe_ratio"] = (df["stock_price"] / eps).replace([np.inf, -np.inf], np.nan)

    # 8. DCF Margin of Safety – compute from SA financials + yfinance prices
    shares = _sa_reindex(
        _sa_get(income, ["Shares Outstanding (Diluted)", "Shares Outstanding (Basic)"])
    )
    total_debt = _sa_reindex(_sa_get(balance, ["Total Debt"]))
    cash = _sa_reindex(
        _sa_get(balance, ["Cash & Short-Term Investments", "Cash & Equivalents"])
    )

    # Average FCF growth for projection
    fcf_growth_rates = fcf_reindexed.pct_change(fill_method=None).dropna()
    if not fcf_growth_rates.empty:
        mean_growth = max(min(fcf_growth_rates.mean(), 0.25), 0.02)
    else:
        mean_growth = DCF_FCF_GROWTH_DEFAULT

    dcf_results = []
    implied_results = []
    for i, dt in enumerate(date_index):
        try:
            f = fcf_reindexed.iloc[i]
            s = shares.iloc[i]
            d = total_debt.iloc[i]
            c = cash.iloc[i]
            p = df["stock_price"].iloc[i]

            if pd.isna(f) or f <= 0 or pd.isna(s) or s <= 0 or pd.isna(p) or p <= 0:
                dcf_results.append(np.nan)
                implied_results.append(np.nan)
                continue

            d_adj = d if not pd.isna(d) else 0
            c_adj = c if not pd.isna(c) else 0

            iv = _dcf_intrinsic_per_share(f, s, d_adj, c_adj, mean_growth)
            dcf_results.append((iv - p) / p * 100)

            g = _solve_implied_growth(f, s, d_adj, c_adj, p)
            implied_results.append(g * 100 if not np.isnan(g) else np.nan)
        except Exception:
            dcf_results.append(np.nan)
            implied_results.append(np.nan)

    df["dcf_mos"] = dcf_results
    df["implied_growth"] = implied_results

    # Date labels: "30-Jun-2025" format
    df["year"] = df.index.strftime("%d-%b-%Y")

    # --- Always append a "Now" row with live price ---
    current_price = info.get("currentPrice") or info.get("regularMarketPrice")
    if current_price and not df.empty:
        today = pd.Timestamp.now().normalize()
        now_row = df.iloc[[-1]].copy()
        now_row.index = pd.DatetimeIndex([today])
        now_row["year"] = today.strftime("%d-%b-%Y")
        now_row["stock_price"] = current_price

        # Recompute PE
        last_eps = eps.iloc[-1]
        if not pd.isna(last_eps) and last_eps != 0:
            now_row["pe_ratio"] = current_price / last_eps

        # Recompute DCF MoS and Implied Growth
        last_fcf = fcf_reindexed.iloc[-1]
        last_shares = shares.iloc[-1]
        last_debt = total_debt.iloc[-1]
        last_cash = cash.iloc[-1]

        if not pd.isna(last_fcf) and last_fcf > 0 and not pd.isna(last_shares) and last_shares > 0:
            d_adj = last_debt if not pd.isna(last_debt) else 0
            c_adj = last_cash if not pd.isna(last_cash) else 0

            iv = _dcf_intrinsic_per_share(last_fcf, last_shares, d_adj, c_adj, mean_growth)
            now_row["dcf_mos"] = (iv - current_price) / current_price * 100

            g = _solve_implied_growth(last_fcf, last_shares, d_adj, c_adj, current_price)
            now_row["implied_growth"] = g * 100 if not np.isnan(g) else np.nan

        # PEG: keep from latest FY (no meaningful recalc with just price change)
        df = pd.concat([df, now_row])

    return df


def _compute_from_yfinance(data: dict, years: int) -> pd.DataFrame:
    """Compute metrics from yfinance raw financial data (original logic)."""
    income = data["income"]
    balance = data["balance"]
    cashflow = data["cashflow"]
    history = data["history"]
    info = data.get("info", {})

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
    df["pe_ratio"] = pe_ratio(income_trimmed, history)
    df["stock_price"] = stock_price(income_trimmed, history)
    df["dcf_mos"] = dcf_margin_of_safety(
        cashflow_trimmed, balance_trimmed, income_trimmed, history, info
    )
    df["implied_growth"] = implied_fcf_growth(
        cashflow_trimmed, balance_trimmed, income_trimmed, history
    )

    # Drop the first row (NaN from pct_change) and limit to requested years
    df = df.iloc[1:]  # drop first row used for pct_change
    df = df.iloc[-years:]

    # Create readable year labels
    df["year"] = df.index.strftime("%Y")

    # --- Append a "Now" row using current price + latest fiscal year financials ---
    current_price = info.get("currentPrice") or info.get("regularMarketPrice")
    if current_price and not df.empty:
        today = pd.Timestamp.now().normalize()
        last_fy = df.index[-1]
        last_price = df["stock_price"].iloc[-1]

        # Only add "Now" if the price differs meaningfully (>1%) from latest FY
        price_changed = pd.isna(last_price) or abs(current_price - last_price) / max(last_price, 1) > 0.01
        if today > last_fy and price_changed:
            today_row = df.iloc[[-1]].copy()
            today_row.index = pd.DatetimeIndex([today])
            today_row["year"] = "Now"
            today_row["stock_price"] = current_price

            # Recompute PE with current price
            eps_col = _find_col(income_trimmed, ["Diluted EPS", "Basic EPS"])
            if eps_col and not pd.isna(income_trimmed[eps_col].iloc[-1]):
                today_row["pe_ratio"] = current_price / income_trimmed[eps_col].iloc[-1]

            # Recompute DCF MoS and Implied Growth with current price
            fcf_val = _safe_get(cashflow_trimmed, ["Free Cash Flow"]).iloc[-1]
            shares_val = _safe_get(income_trimmed, ["Diluted Average Shares", "Basic Average Shares"]).iloc[-1]
            if pd.isna(shares_val):
                shares_val = _safe_get(balance_trimmed, ["Ordinary Shares Number", "Share Issued"]).iloc[-1]
            debt_val = _safe_get(balance_trimmed, ["Total Debt", "Net Debt"]).iloc[-1]
            cash_val = _safe_get(balance_trimmed, [
                "Cash And Cash Equivalents",
                "Cash Cash Equivalents And Short Term Investments",
            ]).iloc[-1]

            if not pd.isna(fcf_val) and fcf_val > 0 and not pd.isna(shares_val) and shares_val > 0:
                debt_adj = debt_val if not pd.isna(debt_val) else 0
                cash_adj = cash_val if not pd.isna(cash_val) else 0

                # FCF growth rate (same as used in DCF)
                fcf_growth_rates = _safe_get(cashflow_trimmed, ["Free Cash Flow"]).pct_change(fill_method=None).dropna()
                if not fcf_growth_rates.empty:
                    mean_g = max(min(fcf_growth_rates.mean(), 0.25), 0.02)
                else:
                    mean_g = DCF_FCF_GROWTH_DEFAULT

                iv = _dcf_intrinsic_per_share(fcf_val, shares_val, debt_adj, cash_adj, mean_g)
                today_row["dcf_mos"] = (iv - current_price) / current_price * 100

                g = _solve_implied_growth(fcf_val, shares_val, debt_adj, cash_adj, current_price)
                today_row["implied_growth"] = g * 100 if not np.isnan(g) else np.nan

            # Keep other metrics (gross_margin, roce, etc.) from latest FY — still valid
            df = pd.concat([df, today_row])

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

    # 8. PE Ratio – pre-calculated on ratios page
    df["pe_ratio"] = _sa_get(ratios, ["PE Ratio"]).reindex(idx)

    # 9. Stock Price – from ratios page
    df["stock_price"] = _sa_get(ratios, ["Last Close Price"]).reindex(idx)

    # 10. Implied FCF Growth – reverse DCF from scraped data
    df["implied_growth"] = _implied_growth_from_stockanalysis(
        income, balance, cashflow, ratios, info, idx
    )

    # Year labels – index is already year strings from scraper
    df["year"] = idx

    # --- Append a "Now" row using current price + latest fiscal year financials ---
    current_price = info.get("currentPrice") or info.get("regularMarketPrice")
    if current_price and not df.empty:
        last_price = df["stock_price"].iloc[-1]
        # Only add "Now" if the price differs meaningfully (>1%) from latest year
        price_changed = pd.isna(last_price) or abs(current_price - last_price) / max(last_price, 1) > 0.01
        if not price_changed:
            # Latest year already has current price; skip "Now" row
            return df
        now_row = df.iloc[[-1]].copy()
        now_row.index = pd.Index(["Now"])
        now_row["year"] = "Now"
        now_row["stock_price"] = current_price

        # Recompute PE with current price
        last_year = idx[-1]
        eps_series = _sa_get(ratios, ["EPS (Diluted)", "EPS (Basic)"]).reindex(idx)
        eps_val = eps_series.get(last_year, np.nan)
        if not pd.isna(eps_val) and eps_val != 0:
            now_row["pe_ratio"] = current_price / eps_val

        # Recompute DCF MoS and Implied Growth with current price
        fcf_vals = _sa_get(income, ["Free Cash Flow"]).reindex(idx)
        if fcf_vals.isna().all():
            fcf_vals = _sa_get(cashflow, ["Free Cash Flow"]).reindex(idx)
        shares_vals = _sa_get(income, [
            "Shares Outstanding (Diluted)", "Shares Outstanding (Basic)"
        ]).reindex(idx)
        total_debt_vals = _sa_get(balance, ["Total Debt"]).reindex(idx)
        cash_vals = _sa_get(balance, [
            "Cash & Short-Term Investments", "Cash & Equivalents",
        ]).reindex(idx)

        fcf_val = fcf_vals.get(last_year, np.nan)
        shares_val = shares_vals.get(last_year, np.nan)
        debt_val = total_debt_vals.get(last_year, np.nan)
        cash_val = cash_vals.get(last_year, np.nan)

        if not pd.isna(fcf_val) and fcf_val > 0 and not pd.isna(shares_val) and shares_val > 0:
            debt_adj = debt_val if not pd.isna(debt_val) else 0
            cash_adj = cash_val if not pd.isna(cash_val) else 0

            fcf_growth_rates = fcf_vals.pct_change(fill_method=None).dropna()
            if not fcf_growth_rates.empty:
                mean_g = max(min(fcf_growth_rates.mean(), 0.25), 0.02)
            else:
                mean_g = DCF_FCF_GROWTH_DEFAULT

            iv = _dcf_intrinsic_per_share(fcf_val, shares_val, debt_adj, cash_adj, mean_g)
            now_row["dcf_mos"] = (iv - current_price) / current_price * 100

            g = _solve_implied_growth(fcf_val, shares_val, debt_adj, cash_adj, current_price)
            now_row["implied_growth"] = g * 100 if not np.isnan(g) else np.nan

        df = pd.concat([df, now_row])

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
    fcf_growth_rates = fcf_series.pct_change(fill_method=None).dropna()
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


def _implied_growth_from_stockanalysis(
    income: pd.DataFrame,
    balance: pd.DataFrame,
    cashflow: pd.DataFrame,
    ratios: pd.DataFrame,
    info: dict,
    idx: pd.Index,
) -> pd.Series:
    """Compute Implied FCF Growth from stockanalysis.com scraped data (reverse DCF)."""
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

    price_series = _sa_get(ratios, ["Last Close Price"]).reindex(idx)

    results = []
    for year in idx:
        try:
            fcf_val = fcf_series.get(year, np.nan)
            shares_val = shares_series.get(year, np.nan)
            debt_val = total_debt_series.get(year, np.nan)
            cash_val = cash_series.get(year, np.nan)
            price_val = price_series.get(year, np.nan)

            if pd.isna(fcf_val) or pd.isna(shares_val) or shares_val <= 0 or fcf_val <= 0:
                results.append(np.nan)
                continue
            if pd.isna(price_val) or price_val <= 0:
                results.append(np.nan)
                continue

            debt_adj = debt_val if not pd.isna(debt_val) else 0
            cash_adj = cash_val if not pd.isna(cash_val) else 0

            g = _solve_implied_growth(fcf_val, shares_val, debt_adj, cash_adj, price_val)
            results.append(g * 100 if not np.isnan(g) else np.nan)
        except Exception:
            results.append(np.nan)

    return pd.Series(results, index=idx)