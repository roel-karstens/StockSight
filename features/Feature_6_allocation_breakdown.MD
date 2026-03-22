# Feature 6 — Portfolio Allocation Breakdown

## Goal
After the summary scorecard loads, the user can view how their portfolio is
allocated across **Country**, **Sector**, and **Market-Cap Size** — visualised
as interactive Plotly treemaps that load on demand (button click) so the page
doesn't slow down.

## Data Source
All fields come from `yfinance`'s `ticker.info`, which is already fetched in
Phase 1 (`fetch_yfinance`). **Zero extra API calls needed.**

| Field         | yfinance key    | Example value              |
|--------------|-----------------|----------------------------|
| Country      | `info["country"]` | `"United States"`         |
| Sector       | `info["sector"]`  | `"Technology"`            |
| Industry     | `info["industry"]`| `"Software - Application"`|
| Market Cap   | `info["marketCap"]`| `2838053519360`           |

### Cap-size buckets

| Bucket   | Market Cap           |
|----------|----------------------|
| Mega     | ≥ $200 B             |
| Large    | $10 B – $200 B       |
| Mid      | $2 B – $10 B         |
| Small    | < $2 B               |

## Weighting
By default every stock gets **equal weight** (`100 / n_stocks`).
No editable weights in v1 — just equal allocation.

## Visualisation – Treemaps

Three Plotly treemaps rendered in a 3-column row:

1. **Country Allocation** – parent = country, child = ticker
2. **Sector Allocation** – parent = sector, child = ticker
3. **Cap Size Allocation** – parent = cap bucket, child = ticker

Each treemap:
- Tiles sized by weight (equal weight → all tiles same size within group)
- Coloured by parent category (country / sector / cap bucket)
- Hover shows: ticker, parent category, weight %
- Click-to-zoom into a category to see individual tickers

## UX

- Placed **below the scorecard**, preceded by `st.divider()` and an
  `st.subheader("📊 Portfolio Allocation")`.
- Treemaps render immediately when data is available (no extra button needed)
  because the yfinance info is already fetched.
  *Update:* Wrapped in `st.expander("📊 Portfolio Allocation", expanded=False)`
  so the section is collapsed by default and doesn't slow perceived page load.
- If a ticker is missing country/sector/cap info, it shows as "Unknown" in the
  relevant treemap.

## New / Changed Files

| File                   | Change                                           |
|------------------------|--------------------------------------------------|
| `data/allocation.py`   | **NEW** – classify tickers, build allocation df  |
| `ui/charts.py`         | Add `build_allocation_treemaps()` function       |
| `app.py`               | Extract info from yf_results, call allocation +  |
|                        | render treemaps below scorecard                  |

## Out of Scope (v1)
- Editable per-stock weights
- Dollar-weighted allocation (based on shares held)
- Drill-down to sub-industry level
