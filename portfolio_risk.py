import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
import plotly.graph_objects as go
import plotly.express as px
from scipy import stats
from datetime import datetime, timedelta

st.set_page_config(page_title="Portfolio Risk Analyzer", page_icon="📊", layout="wide")

# ── Animated gradient background + UI theme ───────────────────────────────────
st.markdown("""
<style>
/* Moving gradient background */
.stApp {
    background: linear-gradient(-45deg, #0b0920, #1a1040, #0d1f3c, #1b0a30, #0a1628);
    background-size: 500% 500%;
    animation: gradientShift 22s ease infinite;
}
@keyframes gradientShift {
    0%   { background-position: 0% 50%; }
    25%  { background-position: 100% 0%; }
    50%  { background-position: 100% 50%; }
    75%  { background-position: 0% 100%; }
    100% { background-position: 0% 50%; }
}

/* Sidebar glass */
[data-testid="stSidebar"] {
    background: rgba(8, 6, 28, 0.85) !important;
    border-right: 1px solid rgba(120, 100, 220, 0.18);
    backdrop-filter: blur(14px);
}
[data-testid="stSidebar"] * { color: rgba(220, 215, 255, 0.92) !important; }

/* Metric cards */
[data-testid="metric-container"] {
    background: rgba(255, 255, 255, 0.055);
    border: 1px solid rgba(140, 120, 255, 0.22);
    border-radius: 14px;
    padding: 16px 14px;
    backdrop-filter: blur(12px);
    transition: transform 0.18s ease, border-color 0.18s ease, box-shadow 0.18s ease;
}
[data-testid="metric-container"]:hover {
    transform: translateY(-3px);
    border-color: rgba(160, 140, 255, 0.5);
    box-shadow: 0 6px 24px rgba(100, 80, 200, 0.18);
}
[data-testid="stMetricValue"]  { color: #ffffff !important; font-weight: 700 !important; }
[data-testid="stMetricLabel"]  { color: rgba(200, 195, 255, 0.82) !important; }

/* Section headers */
h1, h2, h3 { color: rgba(225, 220, 255, 0.96) !important; }

/* Dividers */
hr { border-color: rgba(140, 120, 255, 0.18) !important; }

/* Streamlit dataframe */
[data-testid="stDataFrame"] { border-radius: 12px; overflow: hidden; }

/* Primary button glow */
.stButton > button[kind="primary"] {
    background: linear-gradient(135deg, #5a3fcc, #8855ff);
    border: none;
    box-shadow: 0 2px 12px rgba(120, 80, 240, 0.35);
    transition: box-shadow 0.2s;
}
.stButton > button[kind="primary"]:hover {
    box-shadow: 0 4px 20px rgba(120, 80, 240, 0.55);
}

/* Info icon colour */
[data-testid="stMetricHelpIcon"] svg { fill: rgba(160, 140, 255, 0.7) !important; }
</style>
""", unsafe_allow_html=True)

# ── Constants ─────────────────────────────────────────────────────────────────
TRADING_DAYS = 252
DEFAULT_HOLDINGS = [
    ("AAPL", 25.0), ("MSFT", 25.0), ("GOOGL", 20.0), ("BND", 15.0), ("GLD", 15.0),
]

STAT_HELP = {
    "ann_ret": (
        "Compound Annual Growth Rate over the selected period. "
        "Shows how much $1 grew per year on average. "
        "10% means $10,000 compounded to ~$11,000 each year."
    ),
    "vol": (
        "Annualised standard deviation of daily returns. "
        "Measures how wildly the portfolio swings. "
        "A 15% volatile portfolio can reasonably move ±15% around its trend in a year."
    ),
    "sharpe": (
        "Return earned per unit of total risk. "
        "Formula: (Portfolio Return − Risk-Free Rate) ÷ Volatility. "
        "Rule of thumb: >0 beats cash, >1.0 is good, >2.0 is excellent. "
        "Negative means T-bills would have been safer."
    ),
    "sortino": (
        "Like the Sharpe ratio but only penalises downside swings — not upside ones. "
        "Rewards portfolios that have big gains without big losses. "
        ">1.0 is solid. Higher than Sharpe means your losses were smaller than your gains."
    ),
    "mdd": (
        "The largest peak-to-trough decline in the period before a new high was reached. "
        "If your portfolio hit $150K then fell to $105K before recovering, max drawdown = −30%. "
        "Tells you the worst-case pain you would have had to sit through."
    ),
    "calmar": (
        "Annualised return divided by the maximum drawdown. "
        "Measures how much gain you earned per unit of loss endured. "
        ">1.0 means you earned more than the deepest trough you ever experienced."
    ),
    "var95": (
        "Value at Risk at 95% confidence — daily. "
        "On any given day, there is a 5% chance of losing MORE than this amount. "
        "e.g. −1.5% means roughly 1 day per month could see losses exceeding 1.5%."
    ),
    "cvar95": (
        "Conditional VaR / Expected Shortfall — the average loss on the days "
        "that actually exceed the VaR threshold. "
        "More conservative than VaR: it tells you how bad the bad days typically get."
    ),
    "beta": (
        "Sensitivity to benchmark movements. "
        "Beta 1.0 = mirrors the market exactly. "
        "0.7 = 70% as volatile as the benchmark. "
        "1.3 = amplifies moves by 30%. "
        "Negative beta means the portfolio tends to move opposite to the benchmark."
    ),
    "alpha": (
        "Return above what benchmark exposure alone would predict (annualised). "
        "Positive alpha means your stock selection or tilts added real value "
        "beyond just riding the market. The 'skill' component."
    ),
}

# ── Session-state bootstrap ───────────────────────────────────────────────────
if "active_rows" not in st.session_state:
    st.session_state.active_rows = list(range(len(DEFAULT_HOLDINGS)))
    st.session_state.next_id = len(DEFAULT_HOLDINGS)
    for i, (t, w) in enumerate(DEFAULT_HOLDINGS):
        st.session_state[f"tk_{i}"] = t
        st.session_state[f"wt_{i}"] = w
        st.session_state[f"dol_{i}"] = 0.0


def _add_row():
    nid = st.session_state.next_id
    st.session_state.active_rows.append(nid)
    st.session_state[f"tk_{nid}"] = ""
    st.session_state[f"wt_{nid}"] = 0.0
    st.session_state[f"dol_{nid}"] = 0.0
    st.session_state.next_id += 1


def _remove_row(rid):
    st.session_state.active_rows.remove(rid)


def _clear_all():
    for key in list(st.session_state.keys()):
        if isinstance(key, str) and key[:3] in ("tk_", "wt_", "do"):
            del st.session_state[key]
    st.session_state.active_rows = []
    st.session_state.next_id = 0


# ── Sidebar ───────────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("## 📊 Portfolio Builder")

    # Add / Clear row
    btn_add, btn_clr = st.columns(2)
    btn_add.button("＋ Add Ticker", on_click=_add_row, use_container_width=True)
    btn_clr.button("✕ Clear All", on_click=_clear_all, use_container_width=True)

    if st.session_state.active_rows:
        hdr_tk, hdr_wt, _ = st.columns([3, 2, 1])
        hdr_tk.caption("Ticker")
        hdr_wt.caption("Weight %")

    for rid in list(st.session_state.active_rows):
        c_tk, c_wt, c_rm = st.columns([3, 2, 1])
        c_tk.text_input("Ticker", key=f"tk_{rid}",
                        label_visibility="collapsed", placeholder="e.g. AAPL")
        c_wt.number_input("Weight", key=f"wt_{rid}",
                          label_visibility="collapsed",
                          min_value=0.0, max_value=100.0, step=1.0, format="%.1f")
        c_rm.button("✕", key=f"rm_{rid}", on_click=_remove_row, args=(rid,))

    if st.session_state.active_rows:
        total_w = sum(
            st.session_state.get(f"wt_{rid}", 0.0)
            for rid in st.session_state.active_rows
        )
        if abs(total_w - 100.0) < 0.1:
            st.success(f"Weights: {total_w:.1f}% ✓")
        else:
            st.warning(f"Weights sum to {total_w:.1f}% — will be normalised")
    else:
        st.info("No tickers yet — click ＋ Add Ticker above.")

    # ── Dollar Amount Calculator ──────────────────────────────────────────────
    st.divider()
    with st.expander("💰 Dollar Amount Calculator"):
        st.caption(
            "Enter your position size in dollars for each ticker. "
            "Click **Apply** to convert to portfolio weights automatically."
        )

        active_named = [
            (rid, st.session_state.get(f"tk_{rid}", "").strip().upper())
            for rid in st.session_state.active_rows
            if st.session_state.get(f"tk_{rid}", "").strip()
        ]

        if not active_named:
            st.info("Add tickers above to use this calculator.")
        else:
            for rid, ticker in active_named:
                st.number_input(
                    f"$ {ticker}",
                    key=f"dol_{rid}",
                    min_value=0.0, step=500.0, format="%.0f",
                )

            total_dol = sum(
                st.session_state.get(f"dol_{rid}", 0.0) for rid, _ in active_named
            )

            if total_dol > 0:
                st.caption(f"**Total: ${total_dol:,.0f}**")
                st.caption("Resulting weights:")
                for rid, ticker in active_named:
                    amt = st.session_state.get(f"dol_{rid}", 0.0)
                    pct = amt / total_dol * 100
                    bar = "█" * int(pct / 5) + "░" * (20 - int(pct / 5))
                    st.caption(f"`{ticker:<6}` {bar}  {pct:.1f}%")

                if st.button("Apply to Weights", use_container_width=True, key="apply_dol"):
                    for rid, _ in active_named:
                        amt = st.session_state.get(f"dol_{rid}", 0.0)
                        st.session_state[f"wt_{rid}"] = round(amt / total_dol * 100, 1)
                    st.rerun()
            else:
                st.caption("Enter at least one dollar amount above.")

    # ── Settings ─────────────────────────────────────────────────────────────
    st.divider()
    st.markdown("### ⚙️ Settings")
    period_options = {"1 Year": 365, "2 Years": 730, "3 Years": 1095, "5 Years": 1825}
    period_label = st.selectbox("Lookback period", list(period_options.keys()), index=2)
    lookback_days = period_options[period_label]
    rf_rate = st.number_input(
        "Risk-free rate (%)", value=4.5, min_value=0.0, max_value=20.0,
        step=0.1, format="%.2f"
    ) / 100
    benchmark = st.text_input("Benchmark ticker", value="SPY").strip().upper()
    run = st.button("▶ Run Analysis", type="primary", use_container_width=True)

# ── Helpers ───────────────────────────────────────────────────────────────────

@st.cache_data(ttl=3600)
def fetch_prices(tickers: list, start: str, end: str) -> pd.DataFrame:
    raw = yf.download(tickers, start=start, end=end, auto_adjust=True, progress=False)
    if isinstance(raw.columns, pd.MultiIndex):
        prices = raw["Close"]
    else:
        prices = raw[["Close"]] if "Close" in raw.columns else raw
    prices.columns = [c.upper() for c in prices.columns]
    return prices.dropna(how="all")


def portfolio_returns(prices: pd.DataFrame, weights: np.ndarray) -> pd.Series:
    return (prices.pct_change().dropna() * weights).sum(axis=1)


def annualised_vol(returns: pd.Series) -> float:
    return float(returns.std() * np.sqrt(TRADING_DAYS))


def sharpe_ratio(returns: pd.Series, rf: float) -> float:
    vol = annualised_vol(returns)
    return (returns.mean() * TRADING_DAYS - rf) / vol if vol else np.nan


def sortino_ratio(returns: pd.Series, rf: float) -> float:
    daily_rf = rf / TRADING_DAYS
    downside = returns[returns < daily_rf] - daily_rf
    dv = np.sqrt((downside ** 2).mean() * TRADING_DAYS)
    return (returns.mean() * TRADING_DAYS - rf) / dv if dv else np.nan


def max_drawdown(returns: pd.Series) -> float:
    cum = (1 + returns).cumprod()
    return float(((cum - cum.cummax()) / cum.cummax()).min())


def drawdown_series(returns: pd.Series) -> pd.Series:
    cum = (1 + returns).cumprod()
    return (cum - cum.cummax()) / cum.cummax()


def var_cvar(returns: pd.Series, confidence: float = 0.95) -> tuple:
    v = float(np.percentile(returns, (1 - confidence) * 100))
    return v, float(returns[returns <= v].mean())


def beta_alpha(port: pd.Series, bench: pd.Series, rf: float) -> tuple:
    aligned = pd.concat([port, bench], axis=1).dropna()
    slope, intercept, *_ = stats.linregress(aligned.iloc[:, 1], aligned.iloc[:, 0])
    alpha = (intercept - (rf / TRADING_DAYS) * (1 - slope)) * TRADING_DAYS
    return float(slope), float(alpha)


def calmar_ratio(returns: pd.Series) -> float:
    ann = (1 + returns).prod() ** (TRADING_DAYS / len(returns)) - 1
    mdd = abs(max_drawdown(returns))
    return ann / mdd if mdd else np.nan


def dark_theme(fig: go.Figure) -> go.Figure:
    fig.update_layout(
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(12, 8, 32, 0.65)",
        font=dict(color="rgba(210, 205, 255, 0.9)"),
        legend=dict(bgcolor="rgba(0,0,0,0)", bordercolor="rgba(140,120,255,0.2)"),
    )
    fig.update_xaxes(
        gridcolor="rgba(120, 100, 200, 0.15)",
        zerolinecolor="rgba(120, 100, 200, 0.25)",
        linecolor="rgba(120, 100, 200, 0.2)",
    )
    fig.update_yaxes(
        gridcolor="rgba(120, 100, 200, 0.15)",
        zerolinecolor="rgba(120, 100, 200, 0.25)",
        linecolor="rgba(120, 100, 200, 0.2)",
    )
    return fig


# ── Main ──────────────────────────────────────────────────────────────────────

st.markdown("# 📊 Portfolio Risk Analyzer")
st.caption("Live quantitative risk report — powered by Yahoo Finance")

if not run:
    st.info("Configure your portfolio in the sidebar, then click **▶ Run Analysis**.")
    st.stop()

holdings_raw = [
    (st.session_state.get(f"tk_{rid}", "").strip().upper(),
     st.session_state.get(f"wt_{rid}", 0.0))
    for rid in st.session_state.active_rows
    if st.session_state.get(f"tk_{rid}", "").strip()
]
if not holdings_raw:
    st.error("Add at least one ticker in the sidebar.")
    st.stop()

tickers = [t for t, _ in holdings_raw]
raw_weights = np.array([w for _, w in holdings_raw], dtype=float)
weights = raw_weights / raw_weights.sum()

end_date = datetime.today().strftime("%Y-%m-%d")
start_date = (datetime.today() - timedelta(days=lookback_days + 30)).strftime("%Y-%m-%d")
fetch_list = list(dict.fromkeys(tickers + ([benchmark] if benchmark else [])))

with st.spinner("Fetching live market data…"):
    try:
        prices = fetch_prices(fetch_list, start_date, end_date)
    except Exception as e:
        st.error(f"Data fetch failed: {e}")
        st.stop()

missing = [t for t in tickers if t not in prices.columns]
if missing:
    st.error(f"Could not fetch data for: {', '.join(missing)}. Check the ticker symbols.")
    st.stop()

port_prices = prices[tickers].dropna()
if len(port_prices) < 60:
    st.error("Not enough price history — try a shorter lookback or check your tickers.")
    st.stop()

port_ret = portfolio_returns(port_prices, weights)
individual_ret = port_prices.pct_change().dropna()

has_bench = benchmark in prices.columns
bench_ret = prices[benchmark].pct_change().dropna() if has_bench else None

# ── Compute metrics ───────────────────────────────────────────────────────────
ann_ret = (1 + port_ret).prod() ** (TRADING_DAYS / len(port_ret)) - 1
vol     = annualised_vol(port_ret)
sp      = sharpe_ratio(port_ret, rf_rate)
so      = sortino_ratio(port_ret, rf_rate)
mdd     = max_drawdown(port_ret)
var95, cvar95 = var_cvar(port_ret, 0.95)
calmar_r = calmar_ratio(port_ret)

beta_v = alpha_v = None
if has_bench and bench_ret is not None:
    ab = bench_ret.reindex(port_ret.index).dropna()
    ap = port_ret.reindex(ab.index)
    if len(ap) > 30:
        beta_v, alpha_v = beta_alpha(ap, ab, rf_rate)

# ── Summary metrics ───────────────────────────────────────────────────────────
st.subheader("Portfolio Summary")

c1, c2, c3, c4, c5, c6 = st.columns(6)
c1.metric("Annualised Return",    f"{ann_ret:.2%}", help=STAT_HELP["ann_ret"])
c2.metric("Annualised Volatility",f"{vol:.2%}",     help=STAT_HELP["vol"])
c3.metric("Sharpe Ratio",         f"{sp:.2f}",      help=STAT_HELP["sharpe"])
c4.metric("Sortino Ratio",        f"{so:.2f}",      help=STAT_HELP["sortino"])
c5.metric("Max Drawdown",         f"{mdd:.2%}",     help=STAT_HELP["mdd"])
c6.metric("Calmar Ratio",         f"{calmar_r:.2f}",help=STAT_HELP["calmar"])

c7, c8, c9, c10 = st.columns(4)
c7.metric("VaR 95% (daily)",  f"{var95:.2%}",  help=STAT_HELP["var95"])
c8.metric("CVaR 95% (daily)", f"{cvar95:.2%}", help=STAT_HELP["cvar95"])
if beta_v is not None:
    c9.metric(f"Beta vs {benchmark}",        f"{beta_v:.2f}", help=STAT_HELP["beta"])
    c10.metric(f"Alpha vs {benchmark} (ann.)",f"{alpha_v:.2%}",help=STAT_HELP["alpha"])

st.divider()

# ── Charts row 1: cumulative returns & drawdown ───────────────────────────────
col_l, col_r = st.columns(2)

with col_l:
    st.subheader("Cumulative Returns")
    cum_port = (1 + port_ret).cumprod() - 1
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=cum_port.index, y=cum_port * 100,
                             name="Portfolio", line=dict(color="#7B68EE", width=2.5)))
    if has_bench and bench_ret is not None:
        cum_bench = (1 + bench_ret.reindex(port_ret.index).dropna()).cumprod() - 1
        fig.add_trace(go.Scatter(x=cum_bench.index, y=cum_bench * 100,
                                  name=benchmark,
                                  line=dict(color="#FF8C42", width=2, dash="dash")))
    fig.update_layout(yaxis_title="Return (%)", margin=dict(l=0, r=0, t=10, b=0),
                       height=320, legend=dict(orientation="h", y=1.02))
    dark_theme(fig)
    st.plotly_chart(fig, use_container_width=True)

with col_r:
    st.subheader("Underwater (Drawdown) Chart")
    dd = drawdown_series(port_ret)
    fig2 = go.Figure()
    fig2.add_trace(go.Scatter(x=dd.index, y=dd * 100,
                               fill="tozeroy", fillcolor="rgba(255,60,60,0.12)",
                               line=dict(color="#FF4560", width=1.8), name="Drawdown"))
    fig2.update_layout(yaxis_title="Drawdown (%)", margin=dict(l=0, r=0, t=10, b=0),
                        height=320)
    dark_theme(fig2)
    st.plotly_chart(fig2, use_container_width=True)

# ── Charts row 2: correlation heatmap & return distribution ──────────────────
col_l2, col_r2 = st.columns(2)

with col_l2:
    st.subheader("Correlation Heatmap")
    corr = individual_ret.corr()
    hfig = px.imshow(corr, text_auto=".2f", color_continuous_scale="RdBu_r",
                      zmin=-1, zmax=1, aspect="auto")
    hfig.update_layout(margin=dict(l=0, r=0, t=10, b=0), height=380,
                        coloraxis_colorbar=dict(title="ρ"))
    dark_theme(hfig)
    st.plotly_chart(hfig, use_container_width=True)

with col_r2:
    st.subheader("Return Distribution")
    mu, sigma = port_ret.mean() * 100, port_ret.std() * 100
    x_range = np.linspace(mu - 4.5 * sigma, mu + 4.5 * sigma, 250)
    dfig = go.Figure()
    dfig.add_trace(go.Histogram(x=port_ret * 100, nbinsx=60,
                                 histnorm="probability density",
                                 marker_color="#7B68EE", opacity=0.7,
                                 name="Daily returns"))
    dfig.add_trace(go.Scatter(x=x_range, y=stats.norm.pdf(x_range, mu, sigma),
                               mode="lines", line=dict(color="#FF8C42", width=2),
                               name="Normal fit"))
    dfig.add_vline(x=var95 * 100, line=dict(color="#FF4560", dash="dash", width=1.5),
                    annotation_text="VaR 95%", annotation_position="top right")
    dfig.update_layout(yaxis_title="Density", xaxis_title="Daily Return (%)",
                        legend=dict(orientation="h", y=1.02),
                        margin=dict(l=0, r=0, t=10, b=0), height=380)
    dark_theme(dfig)
    st.plotly_chart(dfig, use_container_width=True)

# ── Rolling charts ────────────────────────────────────────────────────────────
st.subheader("Rolling 90-Day Volatility & Sharpe")
WINDOW = 90
roll_l, roll_r = st.columns(2)

with roll_l:
    roll_vol = port_ret.rolling(WINDOW).std() * np.sqrt(TRADING_DAYS) * 100
    rvfig = go.Figure()
    rvfig.add_trace(go.Scatter(x=roll_vol.index, y=roll_vol,
                                fill="tozeroy", fillcolor="rgba(123,104,238,0.12)",
                                line=dict(color="#7B68EE"), name="Rolling vol"))
    rvfig.update_layout(yaxis_title="Volatility (%)", margin=dict(l=0, r=0, t=10, b=0),
                         height=280)
    dark_theme(rvfig)
    st.plotly_chart(rvfig, use_container_width=True)

with roll_r:
    daily_rf = rf_rate / TRADING_DAYS
    roll_sp = ((port_ret.rolling(WINDOW).mean() - daily_rf)
               / port_ret.rolling(WINDOW).std() * np.sqrt(TRADING_DAYS))
    rsfig = go.Figure()
    rsfig.add_trace(go.Scatter(x=roll_sp.index, y=roll_sp,
                                line=dict(color="#00CBA0"), name="Rolling Sharpe"))
    rsfig.add_hline(y=1.0, line=dict(color="rgba(0,200,80,0.5)", dash="dot", width=1),
                     annotation_text="1.0", annotation_position="bottom right")
    rsfig.add_hline(y=0.0, line=dict(color="rgba(200,200,200,0.3)", dash="dot", width=1))
    rsfig.update_layout(yaxis_title="Sharpe Ratio", margin=dict(l=0, r=0, t=10, b=0),
                         height=280)
    dark_theme(rsfig)
    st.plotly_chart(rsfig, use_container_width=True)

# ── Per-asset table ───────────────────────────────────────────────────────────
st.divider()
st.subheader("Individual Holding Metrics")

rows = []
for i, ticker in enumerate(tickers):
    r = individual_ret[ticker]
    ann_r = (1 + r).prod() ** (TRADING_DAYS / len(r)) - 1
    row = {
        "Ticker":         ticker,
        "Weight":         f"{weights[i]:.1%}",
        "Ann. Return":    f"{ann_r:.2%}",
        "Volatility":     f"{annualised_vol(r):.2%}",
        "Sharpe":         f"{sharpe_ratio(r, rf_rate):.2f}",
        "Max Drawdown":   f"{max_drawdown(r):.2%}",
        "VaR 95%":        f"{var_cvar(r)[0]:.2%}",
    }
    if has_bench and bench_ret is not None:
        ab2 = bench_ret.reindex(r.index).dropna()
        b, a = beta_alpha(r.reindex(ab2.index), ab2, rf_rate)
        row["Beta"] = f"{b:.2f}"
        row[f"Alpha (ann.)"] = f"{a:.2%}"
    rows.append(row)

st.dataframe(pd.DataFrame(rows).set_index("Ticker"), use_container_width=True)

# ── Allocation pie ────────────────────────────────────────────────────────────
st.subheader("Portfolio Allocation")
pfig = px.pie(values=weights * 100, names=tickers, hole=0.45,
               color_discrete_sequence=["#7B68EE","#00CBA0","#FF8C42",
                                         "#FF4560","#00B4D8","#F9C74F",
                                         "#90BE6D","#F3722C","#577590","#43AA8B"])
pfig.update_traces(textposition="outside", textinfo="percent+label",
                    textfont=dict(color="rgba(220,215,255,0.9)"))
pfig.update_layout(margin=dict(l=0, r=0, t=10, b=0), height=380,
                    showlegend=False, paper_bgcolor="rgba(0,0,0,0)")
st.plotly_chart(pfig, use_container_width=True)

st.caption(
    "Data sourced from Yahoo Finance via yfinance · "
    "1-hour data cache · "
    "Past performance does not guarantee future results · "
    "For educational and informational purposes only."
)
