"""Streamlit dashboard assembly."""

from __future__ import annotations

import os
import subprocess
import sys

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from config import REPORTS_DIR, TARGET_ALLOCATION
from dashboard.backtest import run_strategy_comparison
from dashboard.data import (
    compute_summary,
    list_reports,
    load_agent_runs,
    load_decision_traces,
    load_history_df,
    load_market_status,
    load_portfolio,
    load_prices,
    load_trades,
)


def run_dashboard():
    st.set_page_config(page_title="Prediction Wallet", page_icon="PW", layout="wide", initial_sidebar_state="expanded")
    st.sidebar.title("Prediction Wallet")
    page = st.sidebar.radio("Navigation", ["Overview", "Allocation", "Trade History", "Performance", "System", "Decision Trace", "Run Agent", "Reports"])
    strategy = st.sidebar.selectbox("Strategy", ["threshold", "calendar"], index=0)
    execution_mode = st.sidebar.selectbox("Execution Mode", ["simulate", "paper", "live"], index=0)
    mcp_profile = st.sidebar.selectbox("MCP Profile", ["none", "local"], index=0)

    portfolio = load_portfolio()
    prices = load_prices()
    trades = load_trades()
    history_df = load_history_df()
    agent_runs = load_agent_runs()
    market_status = load_market_status()
    decision_traces = load_decision_traces()
    summary = compute_summary(portfolio, prices)

    if page == "Overview":
        st.title("Portfolio Overview")
        cols = st.columns(4)
        cols[0].metric("Total Value", f"${summary['total']:,.2f}")
        cols[1].metric("Cash", f"${summary['cash']:,.2f}")
        cols[2].metric("Market Value", f"${summary['market_value']:,.2f}")
        cols[3].metric("Drawdown", f"{summary['drawdown']:.2%}")
        st.subheader("Portfolio History")
        if not history_df.empty:
            hist = history_df.copy()
            hist["timestamp"] = pd.to_datetime(hist["timestamp"])
            st.plotly_chart(px.line(hist, x="timestamp", y="total_value", title="Portfolio Value Over Time"), use_container_width=True)
        st.subheader("Current Positions")
        rows = []
        total = summary["total"]
        for ticker, qty in portfolio.get("positions", {}).items():
            value = qty * prices.get(ticker, 0)
            weight = value / total if total > 0 else 0
            rows.append({"Ticker": ticker, "Quantity": round(qty, 4), "Price": f"${prices.get(ticker, 0):.2f}", "Value": f"${value:,.2f}", "Weight": f"{weight:.1%}", "Target": f"{TARGET_ALLOCATION.get(ticker, 0):.1%}", "Drift": f"{weight - TARGET_ALLOCATION.get(ticker, 0):+.1%}"})
        st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)

    elif page == "Allocation":
        st.title("Allocation")
        total = summary["total"]
        current_weights = {ticker: portfolio.get("positions", {}).get(ticker, 0) * prices.get(ticker, 0) / total if total > 0 else 0 for ticker in TARGET_ALLOCATION}
        col1, col2 = st.columns(2)
        col1.plotly_chart(px.pie(names=list(current_weights.keys()), values=list(current_weights.values()), title="Current Allocation", hole=0.45), use_container_width=True)
        col2.plotly_chart(px.pie(names=list(TARGET_ALLOCATION.keys()), values=list(TARGET_ALLOCATION.values()), title="Target Allocation", hole=0.45), use_container_width=True)
        drifts = [current_weights.get(t, 0) - TARGET_ALLOCATION[t] for t in TARGET_ALLOCATION]
        fig = go.Figure(go.Bar(x=list(TARGET_ALLOCATION.keys()), y=[d * 100 for d in drifts], text=[f"{d:+.1%}" for d in drifts], textposition="outside"))
        fig.add_hline(y=5, line_dash="dash")
        fig.add_hline(y=-5, line_dash="dash")
        st.plotly_chart(fig, use_container_width=True)

    elif page == "Trade History":
        st.title("Trade History")
        trade_df = pd.DataFrame([t for t in trades if "trade_id" in t])
        if trade_df.empty:
            st.info("No trades recorded yet.")
        else:
            st.dataframe(trade_df.sort_values("timestamp", ascending=False), use_container_width=True, hide_index=True)

    elif page == "Performance":
        st.title("Performance")
        if history_df.empty:
            st.info("No portfolio history in DB yet.")
        else:
            hist = history_df.copy()
            hist["timestamp"] = pd.to_datetime(hist["timestamp"])
            st.plotly_chart(px.line(hist, x="timestamp", y="total_value", title="Portfolio Value"), use_container_width=True)
            if st.button("Compare strategies"):
                results = run_strategy_comparison(days=90)
                if results:
                    table = pd.DataFrame([
                        {"Strategy": name, "Cumulative Return": f"{data['cum_ret']:+.2%}", "Sharpe": f"{data['sharpe']:.2f}", "Max Drawdown": f"{data['max_dd']:.2%}", "Trades": data["n_trades"], "Costs": f"${data['costs']:,.2f}"}
                        for name, data in results.items()
                    ])
                    st.dataframe(table, use_container_width=True, hide_index=True)

    elif page == "System":
        st.title("System Status")
        st.subheader("Latest Agent Runs")
        st.dataframe(pd.DataFrame(agent_runs), use_container_width=True, hide_index=True)
        st.subheader("Market Data Freshness")
        st.dataframe(pd.DataFrame(market_status), use_container_width=True, hide_index=True)

    elif page == "Decision Trace":
        st.title("Decision Trace")
        trace_df = pd.DataFrame(decision_traces)
        if trace_df.empty:
            st.info("No decision traces recorded yet.")
        else:
            st.dataframe(trace_df[["cycle_id", "stage", "provider", "agent_backend", "execution_mode", "created_at"]], use_container_width=True, hide_index=True)
            selected = st.selectbox("Trace entry", trace_df.index, format_func=lambda idx: f"{trace_df.loc[idx, 'cycle_id']} - {trace_df.loc[idx, 'stage']}")
            st.code(trace_df.loc[selected, "payload_json"])
            if trace_df.loc[selected, "validation_json"]:
                st.code(trace_df.loc[selected, "validation_json"])

    elif page == "Run Agent":
        st.title("Run Rebalancing Agent")
        if st.button("Run Agent Cycle", type="primary"):
            result = subprocess.run(
                [sys.executable, "main.py", "run-cycle", "--strategy", strategy, "--mode", execution_mode, "--use-mcp", mcp_profile],
                capture_output=True,
                text=True,
                cwd=os.getcwd(),
            )
            if result.returncode == 0:
                st.success("Agent cycle complete.")
                st.code(result.stdout)
                st.cache_data.clear()
            else:
                st.error(result.stderr or result.stdout)

    elif page == "Reports":
        st.title("Audit Reports")
        for filename in list_reports():
            path = os.path.join(REPORTS_DIR, filename)
            col1, col2 = st.columns([4, 1])
            col1.write(filename)
            with open(path, "rb") as f:
                col2.download_button("Download", data=f, file_name=filename, mime="application/pdf", key=filename)
