# 📈 StockSight

A lightweight stock financial health dashboard. Search any ticker, compare up to 5 stocks side-by-side, and instantly see color-coded indicators for key metrics.

![Python](https://img.shields.io/badge/Python-3.11+-blue)
![Streamlit](https://img.shields.io/badge/Streamlit-1.30+-red)
![License](https://img.shields.io/badge/License-MIT-green)

## Metrics

| Metric | What it tells you | 🟢 Good | 🔴 Bad |
|--------|-------------------|---------|--------|
| **Gross Margin** | Pricing power & cost efficiency | ≥ 50% | < 20% |
| **PEG Ratio** | Growth-adjusted valuation | ≤ 2.0 | > 3.0 |
| **Revenue Growth** | Top-line momentum | > 10% | < 0% |
| **ROCE** | Capital efficiency | ≥ 15% | < 5% |
| **FCF Growth** | Cash generation trend | > 10% | < 0% |
| **LT Debt / FCF** | Debt sustainability | < 4.0x | > 5.0x |
| **DCF Margin of Safety** | Intrinsic value vs. market price | ≥ +20% | < −20% |

## Quick Start

```bash
# Clone
git clone git@github.com:roel-karstens/StockSight.git
cd StockSight

# Set up environment
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# Run
streamlit run app.py
```

Open http://localhost:8501, type a ticker (e.g. `MSFT`), and click **➕ Add**.

## How It Works

- **Data**: All financial data comes from [Yahoo Finance](https://finance.yahoo.com/) via the `yfinance` library — no API key needed.
- **Metrics**: Computed from raw income statements, balance sheets, and cash flow statements.
- **DCF Model**: Two-stage discounted cash flow (10-year projection at estimated FCF growth → terminal value at 3% perpetual growth, discounted at 10% WACC).
- **Charts**: Interactive Plotly charts with dashed threshold reference lines.
- **Caching**: Data is cached for 1 hour via `st.cache_data` to avoid repeated API calls.

## Project Structure

```
StockSight/
├── app.py              # Streamlit entry point
├── data/
│   ├── fetcher.py      # yfinance data fetching + caching
│   └── metrics.py      # All 7 metric calculations
├── ui/
│   ├── charts.py       # Plotly chart builders
│   └── indicators.py   # Threshold config & 🟢🟡🔴 logic
├── requirements.txt
├── POC.MD              # Design document
└── README.md
```

## Data Source

Yahoo Finance typically provides 3–4 years of annual financial statements. The dashboard works best for US-listed stocks but supports any ticker that `yfinance` recognizes (international included).

## License

MIT
