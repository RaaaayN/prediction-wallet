"""Composable runtime and orchestration services for the agent."""

from __future__ import annotations

from dataclasses import dataclass
from time import perf_counter

from config import AI_PROVIDER, TARGET_ALLOCATION
from agent.llm import get_llm_client
from agent.prompts import ANALYSIS_TEMPLATE, DECISION_PROMPT, SYSTEM_PROMPT
from db.repository import save_agent_run, save_execution, save_snapshot
from engine.orders import generate_rebalance_orders
from engine.portfolio import compute_portfolio_value
from execution.kill_switch import KillSwitch
from market.metrics import PortfolioMetrics
from services.execution_service import ExecutionService, MAX_TRADES_PER_CYCLE
from services.market_service import MarketService
from services.reporting_service import ReportingService
from strategies.calendar import CalendarStrategy
from strategies.threshold import ThresholdStrategy
from utils.time import utc_today_str


@dataclass
class AgentRuntime:
    llm: object
    market_service: MarketService
    execution_service: ExecutionService
    reporting_service: ReportingService
    kill_switch: KillSwitch
    metrics: PortfolioMetrics


def build_runtime() -> AgentRuntime:
    market_service = MarketService()
    execution_service = ExecutionService(execution_repo=save_execution)
    reporting_service = ReportingService(
        market_service=market_service,
        execution_service=execution_service,
    )
    return AgentRuntime(
        llm=get_llm_client(),
        market_service=market_service,
        execution_service=execution_service,
        reporting_service=reporting_service,
        kill_switch=KillSwitch(),
        metrics=PortfolioMetrics(),
    )


class AgentCycleService:
    """Pure orchestration layer for the LangGraph nodes and tools."""

    def __init__(self, runtime: AgentRuntime):
        self.runtime = runtime

    def get_strategy(self, name: str):
        if name == "calendar":
            return CalendarStrategy()
        return ThresholdStrategy()

    def observe(self, state: dict) -> dict:
        tickers = list(TARGET_ALLOCATION.keys())
        started = perf_counter()
        self.runtime.market_service.fetch_and_store(tickers, period="3mo")
        fetch_latency_ms = round((perf_counter() - started) * 1000, 2)

        prices = self.runtime.market_service.get_latest_prices(tickers)
        portfolio = self.runtime.execution_service.load_portfolio()
        market_data = {"prices": prices, "metrics": {}, "refresh_status": self.runtime.market_service.get_refresh_status()}
        for ticker in tickers:
            df = self.runtime.market_service.get_historical(ticker, days=90)
            if df is not None and not df.empty:
                market_data["metrics"][ticker] = self.runtime.metrics.ticker_metrics(df)

        total_value = compute_portfolio_value(portfolio.get("positions", {}), portfolio["cash"], prices)
        self.runtime.execution_service.update_peak(total_value)
        portfolio = self.runtime.execution_service.load_portfolio()
        kill_active = self.runtime.kill_switch.check_with_prices(portfolio, prices)
        strategy = self.get_strategy(state.get("strategy_name", "threshold"))
        signal = strategy.should_rebalance(portfolio, prices) and not kill_active
        deterministic_orders = strategy.get_trades(portfolio, prices) if signal else []

        observability = dict(state.get("observability", {}))
        observability.update({
            "fetch_latency_ms": fetch_latency_ms,
            "provider": AI_PROVIDER,
            "data_errors": [r for r in market_data["refresh_status"] if not r.get("success")],
        })

        return {
            **state,
            "portfolio": portfolio,
            "market_data": market_data,
            "strategy_signal": signal,
            "kill_switch_active": kill_active,
            "trade_plan": deterministic_orders[:MAX_TRADES_PER_CYCLE],
            "observability": observability,
        }

    def build_analysis_prompt(self, state: dict) -> str:
        portfolio = state["portfolio"]
        prices = state["market_data"]["prices"]
        metrics = state["market_data"].get("metrics", {})
        positions = portfolio.get("positions", {})
        cash = portfolio.get("cash", 0)
        total = compute_portfolio_value(positions, cash, prices)
        peak = portfolio.get("peak_value", total)
        drawdown = self.runtime.metrics.current_drawdown(total, peak)

        pos_lines = ["| Ticker | Qty | Price | Value | Weight | Target |", "|--------|-----|-------|-------|--------|--------|"]
        for ticker, qty in positions.items():
            price = prices.get(ticker, 0)
            value = qty * price
            weight = value / total if total > 0 else 0
            target = TARGET_ALLOCATION.get(ticker, 0)
            pos_lines.append(f"| {ticker} | {qty:.4f} | ${price:.2f} | ${value:,.0f} | {weight:.1%} | {target:.1%} |")

        met_lines = ["| Ticker | Price | Vol30d | YTD | Sharpe |", "|--------|-------|--------|-----|--------|"]
        for ticker, m in metrics.items():
            met_lines.append(
                f"| {ticker} | ${m.get('last_price', 0):.2f} | {m.get('volatility_30d', 0):.1%} | "
                f"{m.get('ytd_return', 0):.1%} | {m.get('sharpe', 0):.2f} |"
            )

        proposed = state.get("trade_plan", [])
        proposed_lines = "\n".join(
            f"- {order['action'].upper()} {order['ticker']} {order['quantity']:.4f}: {order['reason']}"
            for order in proposed
        ) or "- No deterministic rebalancing orders proposed."

        return ANALYSIS_TEMPLATE.format(
            date=utc_today_str(),
            cycle_id=state["cycle_id"],
            strategy_name=state.get("strategy_name", "threshold"),
            positions_table="\n".join(pos_lines),
            cash=cash,
            total_value=total,
            peak_value=peak,
            drawdown=drawdown,
            metrics_table="\n".join(met_lines),
            signal=state["strategy_signal"],
            proposed_trades=proposed_lines,
        )

    def analyze(self, state: dict) -> dict:
        prompt = self.build_analysis_prompt(state)
        analysis = self.runtime.llm.complete(
            system=SYSTEM_PROMPT,
            messages=[{"role": "user", "content": prompt}],
            max_tokens=1024,
        )
        return {**state, "analysis": analysis}

    def decide(self, state: dict, tool_loop) -> dict:
        if state["kill_switch_active"]:
            return {**state, "trades_pending": [], "trades_executed": []}

        messages = [{"role": "user", "content": state["analysis"] + "\n\n" + DECISION_PROMPT}]
        updated_messages, trades_executed, tool_stats = tool_loop(
            system=SYSTEM_PROMPT,
            messages=messages,
            max_iterations=MAX_TRADES_PER_CYCLE + 2,
        )
        observability = dict(state.get("observability", {}))
        observability.update(tool_stats)
        return {
            **state,
            "trades_pending": [],
            "trades_executed": trades_executed,
            "messages": updated_messages,
            "observability": observability,
        }

    def execute(self, state: dict) -> dict:
        portfolio = self.runtime.execution_service.load_portfolio()
        prices = state["market_data"]["prices"]
        total = compute_portfolio_value(portfolio.get("positions", {}), portfolio["cash"], prices)
        self.runtime.execution_service.update_peak(total)
        portfolio = self.runtime.execution_service.load_portfolio()
        kill_active = self.runtime.kill_switch.check_with_prices(portfolio, prices)
        return {**state, "portfolio": portfolio, "kill_switch_active": kill_active}

    def audit(self, state: dict) -> dict:
        report_path = None
        try:
            report_path = self.runtime.reporting_service.generate_cycle_report(state["cycle_id"])
        except Exception as exc:
            errors = list(state.get("errors", []))
            errors.append(f"Report generation failed: {exc}")
            state = {**state, "errors": errors}

        final_state = {**state, "report_path": report_path}
        portfolio = self.runtime.execution_service.load_portfolio()
        prices = state["market_data"]["prices"]
        save_snapshot(portfolio, prices, state["cycle_id"])
        save_agent_run(final_state)
        return final_state

    def tool_plan(self, state: dict) -> list[dict]:
        orders = state.get("trade_plan", [])
        if not orders and state.get("strategy_signal"):
            orders = generate_rebalance_orders(state["portfolio"], state["market_data"]["prices"], TARGET_ALLOCATION)
        return orders[:MAX_TRADES_PER_CYCLE]
