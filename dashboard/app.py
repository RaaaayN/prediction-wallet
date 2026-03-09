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
    try:
        from db.repository import get_executions
        df = get_executions(limit=500)
        if not df.empty:
            return df.to_dict("records")
    except Exception:
        pass
    # fallback: JSONL trades log
    from execution.simulator import TradeSimulator
    sim = TradeSimulator()
    return sim.get_trade_history()


@st.cache_data(ttl=60)
def load_history_df():
    try:
        from db.repository import get_history
        return get_history(days=365)
    except Exception:
        return None


@st.cache_data(ttl=30)
def load_agent_runs():
    try:
        from db.repository import get_agent_runs
        return get_agent_runs(limit=20)
    except Exception:
        return []


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
    ["Overview", "Allocation", "Trade History", "Performance", "Risk",
     "Agent Trace", "Strategy Comparison", "Run Agent", "Reports"],
)

strategy = st.sidebar.selectbox("Strategy", ["threshold", "calendar"], index=0)

# ─────────────────────────────────────────────────────────────────────────────
# Load data
# ─────────────────────────────────────────────────────────────────────────────
try:
    portfolio = load_portfolio()
    prices = load_prices()
    trades = load_trades()
    history_df = load_history_df()
    agent_runs = load_agent_runs()
    summary = compute_summary(portfolio, prices)
    data_ok = True
except Exception as e:
    st.error(f"Failed to load data: {e}")
    portfolio, prices, trades, summary = {}, {}, [], {}
    history_df, agent_runs = None, []
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
        if history_df is not None and not history_df.empty:
            hist_df = history_df.copy()
            hist_df["timestamp"] = pd.to_datetime(hist_df["timestamp"])
            fig = px.line(
                hist_df, x="timestamp", y="total_value",
                title="Portfolio Value Over Time",
                labels={"total_value": "Value ($)", "timestamp": "Date"},
            )
            fig.update_layout(height=350)
            st.plotly_chart(fig, use_container_width=True)
        else:
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


elif page == "Performance":
    st.title("Performance")

    @st.cache_data(ttl=120)
    def load_benchmark_history(days: int = 365):
        try:
            from market.fetcher import MarketDataService
            svc = MarketDataService()
            df = svc.get_historical("^GSPC", days=days)
            if df is not None and not df.empty and "Close" in df.columns:
                return df["Close"].dropna()
        except Exception:
            pass
        return None

    if history_df is not None and not history_df.empty:
        hist = history_df.copy()
        hist["timestamp"] = pd.to_datetime(hist["timestamp"])
        hist = hist.sort_values("timestamp").reset_index(drop=True)

        port_returns = hist["total_value"].pct_change().dropna()
        start_val = hist["total_value"].iloc[0]

        # Build comparison chart
        fig = go.Figure()
        fig.add_trace(go.Scatter(
            x=hist["timestamp"], y=hist["total_value"],
            name="Portfolio", line=dict(color="#2b6cb0", width=2),
        ))

        # Buy-and-hold baseline (no rebalancing from start)
        bah_curve = start_val * (1 + port_returns.cumsum())
        bah_index = hist["timestamp"].iloc[1:]
        fig.add_trace(go.Scatter(
            x=bah_index, y=bah_curve.values,
            name="Buy & Hold (baseline)", line=dict(color="#68d391", width=1.5, dash="dot"),
        ))

        # Benchmark (S&P 500)
        bm = load_benchmark_history(days=365)
        if bm is not None and not bm.empty:
            start_ts = hist["timestamp"].iloc[0]
            bm_aligned = bm[bm.index >= start_ts.tz_localize(None) if bm.index.tz is None else start_ts]
            if not bm_aligned.empty:
                bm_scaled = (bm_aligned / bm_aligned.iloc[0]) * start_val
                fig.add_trace(go.Scatter(
                    x=bm_scaled.index, y=bm_scaled.values,
                    name="S&P 500", line=dict(color="#fc8181", width=1.5, dash="dash"),
                ))

        fig.update_layout(
            title="Cumulative Return — Portfolio vs Benchmarks",
            xaxis_title="Date", yaxis_title="Value ($)",
            height=400, legend=dict(orientation="h", y=-0.2),
        )
        st.plotly_chart(fig, use_container_width=True)

        st.markdown("---")
        st.subheader("Performance Metrics")

        from engine.performance import (
            cumulative_return, annualized_return, sharpe_ratio,
            max_drawdown, turnover, transaction_costs_total, hit_ratio,
        )
        hist_list = [
            {"date": str(r["timestamp"]), "total_value": r["total_value"]}
            for _, r in hist.iterrows()
        ]
        trades_list = trades if isinstance(trades, list) else []

        cum_ret_gross = cumulative_return(hist_list)
        costs = transaction_costs_total(trades_list)
        net_final = hist["total_value"].iloc[-1] - costs
        cum_ret_net = (net_final - hist["total_value"].iloc[0]) / hist["total_value"].iloc[0]
        ann_ret = annualized_return(hist_list)
        vol = float(port_returns.std() * (252 ** 0.5)) if not port_returns.empty else 0.0
        sharpe = sharpe_ratio(port_returns)
        mdd = max_drawdown(hist_list)
        avg_val = float(hist["total_value"].mean())
        to = turnover(trades_list, avg_val)
        hr = hit_ratio(trades_list)

        col1, col2 = st.columns(2)
        with col1:
            st.markdown("**Gross (before costs)**")
            st.dataframe(pd.DataFrame([
                {"Metric": "Cumulative Return", "Value": f"{cum_ret_gross:.2%}"},
                {"Metric": "Annualized Return", "Value": f"{ann_ret:.2%}"},
                {"Metric": "Volatility (ann.)", "Value": f"{vol:.2%}"},
                {"Metric": "Sharpe Ratio", "Value": f"{sharpe:.2f}"},
                {"Metric": "Max Drawdown", "Value": f"{mdd:.2%}"},
                {"Metric": "Turnover (ann.)", "Value": f"{to:.2%}"},
                {"Metric": "Hit Ratio", "Value": f"{hr:.1%}"},
            ]), use_container_width=True, hide_index=True)
        with col2:
            st.markdown("**Net (after transaction costs)**")
            st.dataframe(pd.DataFrame([
                {"Metric": "Cumulative Return (net)", "Value": f"{cum_ret_net:.2%}"},
                {"Metric": "Transaction Costs", "Value": f"${costs:,.2f}"},
                {"Metric": "Cost drag", "Value": f"{cum_ret_gross - cum_ret_net:.2%}"},
            ]), use_container_width=True, hide_index=True)
    else:
        st.info("No portfolio history in DB yet. Run at least one agent cycle to populate data.")


elif page == "Risk":
    st.title("Risk")

    if history_df is not None and not history_df.empty:
        hist = history_df.copy()
        hist["timestamp"] = pd.to_datetime(hist["timestamp"])
        hist = hist.sort_values("timestamp").reset_index(drop=True)
        port_returns = hist["total_value"].pct_change().dropna()

        # Rolling volatility
        from engine.performance import rolling_volatility, parametric_var, conditional_var
        from config import KILL_SWITCH_DRAWDOWN

        col_left, col_right = st.columns(2)

        with col_left:
            st.subheader("Rolling Volatility (30d annualised)")
            if len(port_returns) >= 5:
                roll_vol = rolling_volatility(port_returns, window=min(30, len(port_returns) - 1)).dropna()
                if not roll_vol.empty:
                    vol_index = hist["timestamp"].iloc[len(hist) - len(roll_vol):]
                    fig_vol = go.Figure(go.Scatter(
                        x=vol_index, y=roll_vol.values * 100,
                        fill="tozeroy", line=dict(color="#667eea"),
                    ))
                    fig_vol.update_layout(
                        yaxis_title="Volatility (%)", height=300,
                        xaxis_title="Date",
                    )
                    st.plotly_chart(fig_vol, use_container_width=True)
                else:
                    st.info("Need more data points for rolling volatility.")
            else:
                st.info("Need at least 5 data points for rolling volatility.")

        with col_right:
            st.subheader("Drawdown")
            values = hist["total_value"]
            peak = values.cummax()
            drawdown_series = (values - peak) / peak * 100

            fig_dd = go.Figure()
            fig_dd.add_trace(go.Scatter(
                x=hist["timestamp"], y=drawdown_series,
                fill="tozeroy", name="Drawdown",
                line=dict(color="#fc8181"),
                fillcolor="rgba(252,129,129,0.3)",
            ))
            fig_dd.add_hline(
                y=-KILL_SWITCH_DRAWDOWN * 100,
                line_dash="dash", line_color="red",
                annotation_text=f"Kill switch -{KILL_SWITCH_DRAWDOWN:.0%}",
            )
            fig_dd.update_layout(
                yaxis_title="Drawdown (%)", height=300,
                xaxis_title="Date",
            )
            st.plotly_chart(fig_dd, use_container_width=True)

        st.markdown("---")
        st.subheader("Risk Metrics")

        total_val = summary.get("total", 0)
        var_95 = parametric_var(port_returns, confidence=0.95, portfolio_value=total_val)
        cvar_95 = conditional_var(port_returns, confidence=0.95, portfolio_value=total_val)
        var_99 = parametric_var(port_returns, confidence=0.99, portfolio_value=total_val)

        col1, col2, col3 = st.columns(3)
        col1.metric("VaR 95% (1-day)", f"${var_95:,.0f}", help="Maximum expected daily loss at 95% confidence")
        col2.metric("CVaR 95% (1-day)", f"${cvar_95:,.0f}", help="Expected loss beyond VaR threshold")
        col3.metric("VaR 99% (1-day)", f"${var_99:,.0f}", help="Maximum expected daily loss at 99% confidence")

        st.markdown("---")
        st.subheader("Correlation Matrix")
        try:
            from market.fetcher import MarketDataService
            svc = MarketDataService()
            returns_dict = {}
            for ticker in list(TARGET_ALLOCATION.keys()):
                df_t = svc.get_historical(ticker, days=90)
                if df_t is not None and not df_t.empty and "Close" in df_t.columns:
                    r = df_t["Close"].pct_change().dropna()
                    returns_dict[ticker] = r
            if len(returns_dict) >= 2:
                returns_df = pd.DataFrame(returns_dict).dropna(how="all")
                corr = returns_df.corr()
                fig_corr = go.Figure(go.Heatmap(
                    z=corr.values,
                    x=corr.columns.tolist(),
                    y=corr.index.tolist(),
                    colorscale="RdBu_r",
                    zmin=-1, zmax=1,
                    text=corr.round(2).values,
                    texttemplate="%{text}",
                ))
                fig_corr.update_layout(
                    title="30-Day Return Correlations",
                    height=450,
                )
                st.plotly_chart(fig_corr, use_container_width=True)
            else:
                st.info("Not enough ticker data for correlation matrix.")
        except Exception as e:
            st.warning(f"Could not compute correlation matrix: {e}")
    else:
        st.info("No portfolio history in DB yet. Run at least one agent cycle to populate data.")


elif page == "Agent Trace":
    st.title("Agent Trace")

    runs = agent_runs  # loaded at top: get_agent_runs(limit=20)

    if not runs:
        st.info("No agent runs recorded yet. Run at least one agent cycle to populate data.")
    else:
        # Summary table
        summary_rows = []
        for r in runs:
            summary_rows.append({
                "Cycle ID": r.get("cycle_id", ""),
                "Timestamp": r.get("timestamp", "")[:19],
                "Strategy": r.get("strategy", ""),
                "Signal": "Yes" if r.get("signal") else "No",
                "Trades": r.get("trades_count", 0),
                "Kill Switch": "ACTIVE" if r.get("kill_switch") else "OK",
            })
        summary_df = pd.DataFrame(summary_rows)
        st.dataframe(
            summary_df.style.apply(
                lambda col: ["background-color: #fed7d7" if v == "ACTIVE" else "" for v in col]
                if col.name == "Kill Switch" else [""] * len(col),
                axis=0,
            ),
            use_container_width=True,
            hide_index=True,
        )

        st.markdown("---")
        st.subheader("Cycle Detail")

        selected_cycle = st.selectbox(
            "Select a cycle to inspect",
            options=[r["cycle_id"] for r in runs],
            format_func=lambda cid: next(
                (f"{r['timestamp'][:19]} — {r['strategy']} — {r['trades_count']} trades"
                 for r in runs if r["cycle_id"] == cid), cid
            ),
        )

        if selected_cycle:
            run = next((r for r in runs if r["cycle_id"] == selected_cycle), None)
            if run:
                col1, col2, col3 = st.columns(3)
                col1.metric("Strategy", run.get("strategy", "—"))
                col2.metric("Trades executed", run.get("trades_count", 0))
                col3.metric("Kill Switch", "ACTIVE" if run.get("kill_switch") else "OK")

                # Drift table from positions snapshot
                try:
                    from db.repository import get_positions_by_cycle, get_executions
                    positions_snap = get_positions_by_cycle(selected_cycle)
                    if positions_snap:
                        st.markdown("**Drift by asset (at cycle snapshot)**")
                        drift_rows = []
                        for p in positions_snap:
                            drift = p.get("drift", 0)
                            drift_rows.append({
                                "Ticker": p["ticker"],
                                "Weight": f"{p.get('weight', 0):.1%}",
                                "Target": f"{p.get('target_weight', 0):.1%}",
                                "Drift": f"{drift:+.1%}",
                                "Alert": "OVERWEIGHT" if drift > 0.05 else ("UNDERWEIGHT" if drift < -0.05 else "OK"),
                            })
                        drift_df = pd.DataFrame(drift_rows)
                        st.dataframe(
                            drift_df.style.apply(
                                lambda col: [
                                    "background-color: #fed7d7" if v == "OVERWEIGHT"
                                    else "background-color: #c6f6d5" if v == "UNDERWEIGHT"
                                    else "" for v in col
                                ] if col.name == "Alert" else [""] * len(col),
                                axis=0,
                            ),
                            use_container_width=True,
                            hide_index=True,
                        )

                    # Executions for this cycle
                    all_exec = get_executions(limit=500)
                    if not all_exec.empty and "cycle_id" in all_exec.columns:
                        cycle_trades = all_exec[all_exec["cycle_id"] == selected_cycle]
                        if not cycle_trades.empty:
                            st.markdown("**Orders executed**")
                            show_cols = [c for c in ["ticker", "action", "quantity", "fill_price", "cost", "slippage", "reason", "success"] if c in cycle_trades.columns]
                            st.dataframe(cycle_trades[show_cols], use_container_width=True, hide_index=True)
                        else:
                            st.info("No trades recorded for this cycle.")
                except Exception as exc:
                    st.warning(f"Could not load cycle details: {exc}")

                # LLM analysis
                analysis = run.get("analysis", "")
                if analysis:
                    with st.expander("LLM Analysis", expanded=False):
                        st.markdown(analysis)
                else:
                    st.caption("No LLM analysis stored for this cycle.")

                # Kill switch detail
                if run.get("kill_switch"):
                    st.error("Kill switch was ACTIVE during this cycle — no trades were executed.")


elif page == "Strategy Comparison":
    st.title("Strategy Comparison")
    st.markdown("Deterministic backtest on historical prices from market.db — no LLM calls.")

    @st.cache_data(ttl=300)
    def run_strategy_comparison(days: int = 90):
        from market.fetcher import MarketDataService
        from engine.orders import generate_rebalance_orders, apply_slippage
        from engine.performance import (
            cumulative_return, sharpe_ratio, max_drawdown, transaction_costs_total,
        )
        from config import TARGET_ALLOCATION, INITIAL_CAPITAL, DRIFT_THRESHOLD, CRYPTO_TICKERS, SLIPPAGE_EQUITIES, SLIPPAGE_CRYPTO

        svc = MarketDataService()
        tickers = list(TARGET_ALLOCATION.keys())

        # Load all price series from DB
        price_series: dict[str, pd.Series] = {}
        for ticker in tickers:
            df = svc.get_historical(ticker, days=days + 30)
            if df is not None and not df.empty and "Close" in df.columns:
                price_series[ticker] = df["Close"].dropna()

        if not price_series:
            return None

        # Build a common date index (intersection of all tickers)
        common_idx = None
        for s in price_series.values():
            idx = s.index.normalize()
            common_idx = idx if common_idx is None else common_idx.intersection(idx)

        if common_idx is None or len(common_idx) < 5:
            return None

        common_idx = sorted(common_idx)[-days:]

        def prices_on(date) -> dict:
            result = {}
            for t, s in price_series.items():
                idx_norm = s.index.normalize()
                matches = s[idx_norm == date]
                if not matches.empty:
                    result[t] = float(matches.iloc[-1])
            return result

        def init_portfolio(day0_prices):
            port = {"positions": {}, "cash": INITIAL_CAPITAL, "last_rebalanced": None}
            for t, w in TARGET_ALLOCATION.items():
                p = day0_prices.get(t, 0)
                if p > 0:
                    qty = (INITIAL_CAPITAL * w) / p
                    port["positions"][t] = qty
                    port["cash"] -= qty * p
            return port

        def apply_orders(port, orders, prices):
            executed = []
            for o in orders:
                t, qty, action = o["ticker"], o["quantity"], o["action"]
                p = prices.get(t, 0)
                if p <= 0:
                    continue
                fp = apply_slippage(p, action, t, CRYPTO_TICKERS, SLIPPAGE_EQUITIES, SLIPPAGE_CRYPTO)
                if action == "buy":
                    cost = fp * qty
                    if port["cash"] >= cost:
                        port["positions"][t] = port["positions"].get(t, 0) + qty
                        port["cash"] -= cost
                        executed.append({"ticker": t, "action": action, "quantity": qty,
                                         "market_price": p, "fill_price": fp, "success": True})
                else:
                    held = port["positions"].get(t, 0)
                    qty = min(qty, held)
                    if qty > 0:
                        port["positions"][t] = held - qty
                        port["cash"] += fp * qty
                        executed.append({"ticker": t, "action": action, "quantity": qty,
                                         "market_price": p, "fill_price": fp, "success": True})
            return executed

        def portfolio_value(port, prices):
            return port["cash"] + sum(
                qty * prices.get(t, 0) for t, qty in port["positions"].items()
            )

        results = {}

        for strat_name in ["threshold", "calendar", "buy_and_hold"]:
            day0_prices = prices_on(common_idx[0])
            if not day0_prices:
                continue
            port = init_portfolio(day0_prices)
            equity = []
            all_trades = []
            last_rebal_day = 0

            for i, date in enumerate(common_idx):
                prices = prices_on(date)
                if not prices:
                    continue
                val = portfolio_value(port, prices)
                equity.append({"date": str(date.date()), "total_value": val})

                if strat_name == "buy_and_hold":
                    pass  # never rebalance

                elif strat_name == "threshold":
                    # compute weights, check drift
                    total = val
                    if total > 0:
                        trigger = any(
                            abs(port["positions"].get(t, 0) * prices.get(t, 0) / total
                                - TARGET_ALLOCATION.get(t, 0)) > DRIFT_THRESHOLD
                            for t in TARGET_ALLOCATION
                        )
                        if trigger:
                            orders = generate_rebalance_orders(port, prices, TARGET_ALLOCATION)
                            trades = apply_orders(port, orders, prices)
                            all_trades.extend(trades)

                elif strat_name == "calendar":
                    # weekly rebalance (every 7 days)
                    if i - last_rebal_day >= 7:
                        orders = generate_rebalance_orders(port, prices, TARGET_ALLOCATION)
                        trades = apply_orders(port, orders, prices)
                        all_trades.extend(trades)
                        last_rebal_day = i

            results[strat_name] = {
                "equity": equity,
                "trades": all_trades,
                "cum_ret": cumulative_return(equity),
                "sharpe": sharpe_ratio(pd.Series([e["total_value"] for e in equity]).pct_change().dropna()),
                "max_dd": max_drawdown(equity),
                "n_trades": len(all_trades),
                "costs": transaction_costs_total(all_trades),
            }

        return results

    backtest_days = st.slider("Backtest window (days)", min_value=30, max_value=252, value=90, step=10)

    if st.button("Compare strategies", type="primary"):
        with st.spinner("Running deterministic backtests on market.db..."):
            results = run_strategy_comparison(days=backtest_days)
            if results:
                st.session_state["comparison_results"] = results
            else:
                st.warning("Not enough historical data in market.db. Run the agent at least once to fetch prices.")

    if "comparison_results" in st.session_state:
        results = st.session_state["comparison_results"]

        # Equity curve chart
        fig = go.Figure()
        colors_map = {"threshold": "#2b6cb0", "calendar": "#d69e2e", "buy_and_hold": "#68d391"}
        labels_map = {"threshold": "Threshold (5%)", "calendar": "Calendar (weekly)", "buy_and_hold": "Buy & Hold"}
        for strat, data in results.items():
            eq = pd.DataFrame(data["equity"])
            if eq.empty:
                continue
            fig.add_trace(go.Scatter(
                x=pd.to_datetime(eq["date"]), y=eq["total_value"],
                name=labels_map.get(strat, strat),
                line=dict(color=colors_map.get(strat, "#999"), width=2),
            ))
        fig.update_layout(
            title=f"Strategy Comparison — {backtest_days}-day backtest",
            xaxis_title="Date", yaxis_title="Portfolio Value ($)",
            height=400, legend=dict(orientation="h", y=-0.2),
        )
        st.plotly_chart(fig, use_container_width=True)

        # Comparison table
        st.subheader("Summary")
        table_rows = []
        for strat, data in results.items():
            table_rows.append({
                "Strategy": labels_map.get(strat, strat),
                "Cumulative Return": f"{data['cum_ret']:+.2%}",
                "Sharpe Ratio": f"{data['sharpe']:.2f}",
                "Max Drawdown": f"{data['max_dd']:.2%}",
                "# Trades": data["n_trades"],
                "Transaction Costs": f"${data['costs']:,.2f}",
            })
        st.dataframe(pd.DataFrame(table_rows), use_container_width=True, hide_index=True)
    else:
        st.info("Click 'Compare strategies' to run the backtest.")


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
