"""Streamlit dashboard for the portfolio rebalancing agent."""

import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from config import TARGET_ALLOCATION, REPORTS_DIR

# ─────────────────────────────────────────────────────────────────────────────
# Page config
# ─────────────────────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="Prediction Wallet",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────


@st.cache_data(ttl=30)
def load_portfolio():
    from execution.simulator import TradeSimulator
    sim = TradeSimulator()
    return sim.load_portfolio()


@st.cache_data(ttl=30)
def load_prices():
    from market.fetcher import MarketDataService
    svc = MarketDataService()
    return svc.get_latest_prices(list(TARGET_ALLOCATION.keys()))


@st.cache_data(ttl=60)
def load_trades():
    from execution.simulator import TradeSimulator
    sim = TradeSimulator()
    return sim.get_trade_history()


def compute_summary(portfolio: dict, prices: dict) -> dict:
    positions = portfolio.get("positions", {})
    cash = portfolio.get("cash", 0.0)
    peak = portfolio.get("peak_value", cash)
    market_value = sum(qty * prices.get(t, 0) for t, qty in positions.items())
    total = market_value + cash
    drawdown = (total - peak) / peak if peak > 0 else 0
    return {
        "total": total,
        "cash": cash,
        "market_value": market_value,
        "peak": peak,
        "drawdown": drawdown,
    }


# ─────────────────────────────────────────────────────────────────────────────
# Sidebar
# ─────────────────────────────────────────────────────────────────────────────
st.sidebar.title("Prediction Wallet")
st.sidebar.markdown("**Autonomous Portfolio Agent**")

page = st.sidebar.radio(
    "Navigation",
    ["Overview", "Allocation", "Trade History", "Run Agent", "Reports"],
)

strategy = st.sidebar.selectbox("Strategy", ["threshold", "calendar"], index=0)

# ─────────────────────────────────────────────────────────────────────────────
# Load data
# ─────────────────────────────────────────────────────────────────────────────
try:
    portfolio = load_portfolio()
    prices = load_prices()
    trades = load_trades()
    summary = compute_summary(portfolio, prices)
    data_ok = True
except Exception as e:
    st.error(f"Failed to load data: {e}")
    portfolio, prices, trades, summary = {}, {}, [], {}
    data_ok = False

kill_switch_active = portfolio.get("kill_switch_active", False)

if kill_switch_active:
    st.error("⛔ KILL SWITCH ACTIVE — All trading is halted due to excessive drawdown.")

# ─────────────────────────────────────────────────────────────────────────────
# Pages
# ─────────────────────────────────────────────────────────────────────────────

if page == "Overview":
    st.title("Portfolio Overview")

    if data_ok:
        col1, col2, col3, col4 = st.columns(4)
        col1.metric("Total Value", f"${summary['total']:,.2f}")
        col2.metric("Cash", f"${summary['cash']:,.2f}")
        col3.metric("Market Value", f"${summary['market_value']:,.2f}")
        col4.metric(
            "Drawdown",
            f"{summary['drawdown']:.2%}",
            delta=f"{summary['drawdown']:.2%}",
            delta_color="inverse",
        )

        st.markdown("---")
        st.subheader("Portfolio History")
        history = portfolio.get("history", [])
        if history:
            hist_df = pd.DataFrame(history)
            hist_df["date"] = pd.to_datetime(hist_df["date"])
            fig = px.line(
                hist_df, x="date", y="total_value",
                title="Portfolio Value Over Time",
                labels={"total_value": "Value ($)", "date": "Date"},
            )
            fig.update_layout(height=350)
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("No history yet. Run the agent to start tracking.")

        st.markdown("---")
        st.subheader("Current Positions")
        positions = portfolio.get("positions", {})
        if positions:
            rows = []
            total = summary["total"]
            for ticker, qty in positions.items():
                price = prices.get(ticker, 0)
                value = qty * price
                weight = value / total if total > 0 else 0
                target = TARGET_ALLOCATION.get(ticker, 0)
                rows.append({
                    "Ticker": ticker,
                    "Quantity": round(qty, 4),
                    "Price": f"${price:.2f}",
                    "Value": f"${value:,.2f}",
                    "Weight": f"{weight:.1%}",
                    "Target": f"{target:.1%}",
                    "Drift": f"{weight - target:+.1%}",
                })
            st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)
        else:
            st.info("No positions. Run the agent to allocate capital.")


elif page == "Allocation":
    st.title("Allocation")

    if data_ok:
        positions = portfolio.get("positions", {})
        total = summary["total"]

        # Current weights
        current_weights = {}
        for ticker in TARGET_ALLOCATION:
            qty = positions.get(ticker, 0)
            price = prices.get(ticker, 0)
            current_weights[ticker] = qty * price / total if total > 0 else 0

        col1, col2 = st.columns(2)

        with col1:
            st.subheader("Current Allocation")
            fig = px.pie(
                names=list(current_weights.keys()),
                values=list(current_weights.values()),
                title="Current Portfolio",
                hole=0.4,
            )
            fig.update_layout(height=400)
            st.plotly_chart(fig, use_container_width=True)

        with col2:
            st.subheader("Target Allocation")
            fig = px.pie(
                names=list(TARGET_ALLOCATION.keys()),
                values=list(TARGET_ALLOCATION.values()),
                title="Target Portfolio",
                hole=0.4,
            )
            fig.update_layout(height=400)
            st.plotly_chart(fig, use_container_width=True)

        # Drift bar chart
        st.subheader("Drift from Target")
        tickers = list(TARGET_ALLOCATION.keys())
        drifts = [current_weights.get(t, 0) - TARGET_ALLOCATION[t] for t in tickers]
        drift_colors = ["#c53030" if d > 0.05 or d < -0.05 else "#2b6cb0" for d in drifts]
        fig = go.Figure(go.Bar(
            x=tickers, y=[d * 100 for d in drifts],
            marker_color=drift_colors,
            text=[f"{d:+.1%}" for d in drifts],
            textposition="outside",
        ))
        fig.add_hline(y=5, line_dash="dash", line_color="red", annotation_text="+5% threshold")
        fig.add_hline(y=-5, line_dash="dash", line_color="red", annotation_text="-5% threshold")
        fig.update_layout(
            title="Drift from Target (%)",
            yaxis_title="Drift (%)",
            height=350,
        )
        st.plotly_chart(fig, use_container_width=True)


elif page == "Trade History":
    st.title("Trade History")

    if trades:
        trade_trades = [t for t in trades if "trade_id" in t]
        if trade_trades:
            df = pd.DataFrame(trade_trades)
            df["timestamp"] = pd.to_datetime(df["timestamp"])
            df = df.sort_values("timestamp", ascending=False)

            # Summary stats
            col1, col2, col3 = st.columns(3)
            col1.metric("Total Trades", len(trade_trades))
            col2.metric("Buys", len(df[df["action"] == "buy"]))
            col3.metric("Sells", len(df[df["action"] == "sell"]))

            st.markdown("---")

            # Filter
            filter_ticker = st.multiselect("Filter by ticker", sorted(df["ticker"].unique()))
            filter_action = st.selectbox("Action", ["All", "buy", "sell"])

            filtered = df.copy()
            if filter_ticker:
                filtered = filtered[filtered["ticker"].isin(filter_ticker)]
            if filter_action != "All":
                filtered = filtered[filtered["action"] == filter_action]

            display_cols = ["timestamp", "ticker", "action", "quantity", "fill_price", "cost", "reason", "success"]
            available = [c for c in display_cols if c in filtered.columns]
            st.dataframe(filtered[available], use_container_width=True, hide_index=True)
        else:
            st.info("No trades recorded yet.")
    else:
        st.info("No trade history found.")


elif page == "Run Agent":
    st.title("Run Rebalancing Agent")

    st.markdown(f"""
    **Selected strategy:** `{strategy}`

    Click the button below to run one full agent cycle. This will:
    1. Fetch latest market data
    2. Analyze portfolio drift
    3. Ask Claude to make rebalancing decisions
    4. Execute simulated trades
    5. Generate an audit PDF report
    """)

    if kill_switch_active:
        st.error("Kill switch is active. Reset the portfolio to resume trading.")
    else:
        if st.button("▶ Run Agent Cycle", type="primary"):
            with st.spinner("Running agent cycle..."):
                try:
                    import subprocess, sys
                    result = subprocess.run(
                        [sys.executable, "main.py", "--strategy", strategy],
                        capture_output=True, text=True, cwd=os.path.dirname(os.path.dirname(__file__))
                    )
                    st.success("Agent cycle complete!")
                    if result.stdout:
                        st.code(result.stdout)
                    if result.returncode != 0 and result.stderr:
                        st.error(result.stderr)
                    # Clear cache to reload fresh data
                    st.cache_data.clear()
                    st.rerun()
                except Exception as e:
                    st.error(f"Error running agent: {e}")


elif page == "Reports":
    st.title("Audit Reports")

    os.makedirs(REPORTS_DIR, exist_ok=True)
    report_files = sorted(
        [f for f in os.listdir(REPORTS_DIR) if f.endswith(".pdf")],
        reverse=True,
    )

    if report_files:
        for rf in report_files:
            path = os.path.join(REPORTS_DIR, rf)
            col1, col2 = st.columns([4, 1])
            col1.write(f"📄 {rf}")
            with open(path, "rb") as f:
                col2.download_button(
                    label="Download",
                    data=f,
                    file_name=rf,
                    mime="application/pdf",
                    key=rf,
                )
    else:
        st.info("No reports generated yet. Run the agent to create one.")
