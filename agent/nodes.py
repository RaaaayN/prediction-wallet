"""LangGraph node implementations for the portfolio rebalancing agent."""

import json
import uuid
from datetime import datetime

from config import TARGET_ALLOCATION, AI_PROVIDER
from agent.state import AgentState
from agent.llm import get_llm_client
from agent.prompts import SYSTEM_PROMPT, ANALYSIS_TEMPLATE, DECISION_PROMPT
from agent.tools import TOOL_SCHEMAS, dispatch_tool
from execution.kill_switch import KillSwitch
from execution.simulator import TradeSimulator
from market.fetcher import MarketDataService
from market.metrics import PortfolioMetrics
from strategies.threshold import ThresholdStrategy
from strategies.calendar import CalendarStrategy

_llm = get_llm_client()
_fetcher = MarketDataService()
_simulator = TradeSimulator()
_kill_switch = KillSwitch()
_metrics_calc = PortfolioMetrics()


def _get_strategy(name: str):
    if name == "calendar":
        return CalendarStrategy()
    return ThresholdStrategy()


# ---------------------------------------------------------------------------
# Node 1: Observe
# ---------------------------------------------------------------------------

def observe_node(state: AgentState) -> AgentState:
    """Fetch prices, compute metrics, evaluate strategy signal."""
    print(f"[observe] Fetching market data (provider: {AI_PROVIDER})...")
    tickers = list(TARGET_ALLOCATION.keys())

    _fetcher.fetch_and_store(tickers, period="3mo")

    prices = _fetcher.get_latest_prices(tickers)
    portfolio = _simulator.load_portfolio()

    market_data: dict = {"prices": prices, "metrics": {}}
    for ticker in tickers:
        df = _fetcher.get_historical(ticker, days=90)
        if df is not None and not df.empty:
            market_data["metrics"][ticker] = _metrics_calc.ticker_metrics(df)

    total_value = portfolio["cash"] + sum(
        qty * prices.get(t, 0) for t, qty in portfolio.get("positions", {}).items()
    )
    _simulator.update_peak(total_value)
    portfolio = _simulator.load_portfolio()

    kill_active = _kill_switch.check_with_prices(portfolio, prices)
    strategy = _get_strategy(state.get("strategy_name", "threshold"))
    signal = strategy.should_rebalance(portfolio, prices) and not kill_active

    print(f"[observe] Total value: ${total_value:,.2f} | Signal: {signal} | Kill switch: {kill_active}")

    return {
        **state,
        "portfolio": portfolio,
        "market_data": market_data,
        "strategy_signal": signal,
        "kill_switch_active": kill_active,
        "cycle_id": state.get("cycle_id") or str(uuid.uuid4())[:8],
    }


# ---------------------------------------------------------------------------
# Node 2: Analyze
# ---------------------------------------------------------------------------

def analyze_node(state: AgentState) -> AgentState:
    """Ask LLM to summarize market state and identify anomalies."""
    print(f"[analyze] Running LLM market analysis ({AI_PROVIDER})...")

    portfolio = state["portfolio"]
    prices = state["market_data"]["prices"]
    metrics = state["market_data"].get("metrics", {})

    positions = portfolio.get("positions", {})
    cash = portfolio.get("cash", 0)
    total = cash + sum(qty * prices.get(t, 0) for t, qty in positions.items())
    peak = portfolio.get("peak_value", total)
    drawdown = _metrics_calc.current_drawdown(total, peak)

    pos_lines = ["| Ticker | Qty | Price | Value | Weight | Target |"]
    pos_lines.append("|--------|-----|-------|-------|--------|--------|")
    for ticker, qty in positions.items():
        price = prices.get(ticker, 0)
        value = qty * price
        weight = value / total if total > 0 else 0
        target = TARGET_ALLOCATION.get(ticker, 0)
        pos_lines.append(f"| {ticker} | {qty:.4f} | ${price:.2f} | ${value:,.0f} | {weight:.1%} | {target:.1%} |")

    met_lines = ["| Ticker | Price | Vol30d | YTD | Sharpe |"]
    met_lines.append("|--------|-------|--------|-----|--------|")
    for ticker, m in metrics.items():
        met_lines.append(
            f"| {ticker} | ${m.get('last_price', 0):.2f} | {m.get('volatility_30d', 0):.1%} | "
            f"{m.get('ytd_return', 0):.1%} | {m.get('sharpe', 0):.2f} |"
        )

    prompt = ANALYSIS_TEMPLATE.format(
        date=datetime.utcnow().strftime("%Y-%m-%d"),
        cycle_id=state["cycle_id"],
        strategy_name=state.get("strategy_name", "threshold"),
        positions_table="\n".join(pos_lines),
        cash=cash,
        total_value=total,
        peak_value=peak,
        drawdown=drawdown,
        metrics_table="\n".join(met_lines),
        signal=state["strategy_signal"],
    )

    analysis = _llm.complete(
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": prompt}],
        max_tokens=1024,
    )
    print(f"[analyze] Analysis complete ({len(analysis)} chars)")

    return {**state, "analysis": analysis}


# ---------------------------------------------------------------------------
# Node 3: Decide (tool-calling loop)
# ---------------------------------------------------------------------------

def decide_node(state: AgentState) -> AgentState:
    """LLM decides which trades to execute via tool calls."""
    print(f"[decide] Starting decision loop ({AI_PROVIDER})...")

    if state["kill_switch_active"]:
        print("[decide] Kill switch active — skipping trades.")
        return {**state, "trades_pending": [], "trades_executed": []}

    messages = [
        {"role": "user", "content": state["analysis"] + "\n\n" + DECISION_PROMPT}
    ]

    updated_messages, trades_executed = _llm.tool_loop(
        system=SYSTEM_PROMPT,
        messages=messages,
        tool_schemas=TOOL_SCHEMAS,
        dispatcher=dispatch_tool,
        max_iterations=10,
    )

    print(f"[decide] Completed {len(trades_executed)} trades")
    return {
        **state,
        "trades_pending": [],
        "trades_executed": trades_executed,
        "messages": updated_messages,
    }


# ---------------------------------------------------------------------------
# Node 4: Execute (post-trade validation)
# ---------------------------------------------------------------------------

def execute_node(state: AgentState) -> AgentState:
    """Validate executed trades and re-check kill switch."""
    print("[execute] Post-trade validation...")

    portfolio = _simulator.load_portfolio()
    prices = state["market_data"]["prices"]

    total = portfolio["cash"] + sum(
        qty * prices.get(t, 0) for t, qty in portfolio.get("positions", {}).items()
    )
    _simulator.update_peak(total)
    portfolio = _simulator.load_portfolio()

    kill_active = _kill_switch.check_with_prices(portfolio, prices)
    return {**state, "portfolio": portfolio, "kill_switch_active": kill_active}


# ---------------------------------------------------------------------------
# Node 5: Audit
# ---------------------------------------------------------------------------

def audit_node(state: AgentState) -> AgentState:
    """Log cycle summary and generate PDF report."""
    print("[audit] Generating audit report...")

    report_path = None
    try:
        from agent.tools import generate_report
        report_path = generate_report(state["cycle_id"])
        print(f"[audit] Report saved: {report_path}")
    except Exception as exc:
        print(f"[audit] Report generation failed: {exc}")

    return {**state, "report_path": report_path}


# ---------------------------------------------------------------------------
# Node: Alert (kill switch active)
# ---------------------------------------------------------------------------

def alert_node(state: AgentState) -> AgentState:
    """Emit kill switch alert — no trades, just log."""
    print("[alert] KILL SWITCH ACTIVE — all trading halted.")
    return {**state, "trades_pending": [], "trades_executed": []}
