# 📊 Portfolio Risk Analyzer

A live quantitative risk dashboard built with Streamlit and powered by Yahoo Finance. Analyze any combination of stocks, ETFs, or funds with institutional-grade metrics — in seconds.

---

## Features

- **Portfolio Builder** — Add any Yahoo Finance ticker with custom weights; dollar-amount calculator auto-converts positions to weights
- **10 Risk Metrics** — Annualised return, volatility, Sharpe, Sortino, Max Drawdown, Calmar, VaR 95%, CVaR 95%, Beta, Alpha
- **Interactive Charts** — Cumulative returns vs benchmark, underwater drawdown chart, correlation heatmap, return distribution with normal fit, rolling 90-day volatility & Sharpe
- **Per-Holding Breakdown** — Individual metrics table for every position
- **Allocation Pie** — Visual portfolio composition
- **Live Data** — Pulls real-time prices from Yahoo Finance (1-hour cache)

---

## Setup

```bash
# 1. Clone the repo
git clone https://github.com/YOUR_USERNAME/portfolio-risk-analyzer.git
cd portfolio-risk-analyzer

# 2. Install dependencies
pip install -r requirements.txt

# 3. Run the app
streamlit run app.py
```

Then open [http://localhost:8501](http://localhost:8501) in your browser.

---

## Requirements

- Python 3.9+
- See `requirements.txt` for full dependency list

---

## Deployment

Deploy for free on **Streamlit Community Cloud**:

1. Push this repo to GitHub
2. Go to [share.streamlit.io](https://share.streamlit.io)
3. Connect your repo — Streamlit auto-detects `app.py` and deploys

No secrets or API keys needed. Yahoo Finance data is public.

---

## Usage

1. **Add tickers** in the sidebar (e.g. `AAPL`, `BND`, `GLD`)
2. Set **weights** (must sum to 100%) or use the **Dollar Amount Calculator**
3. Choose a **lookback period**, risk-free rate, and benchmark
4. Click **▶ Run Analysis**

---

## Disclaimer

Data sourced from Yahoo Finance via yfinance. Past performance does not guarantee future results. For educational and informational purposes only — not financial advice.
