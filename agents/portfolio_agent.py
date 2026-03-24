"""Primary Pydantic AI portfolio agent and orchestration service."""

from __future__ import annotations

import json
import uuid
from dataclasses import asdict
from time import perf_counter

from pydantic_ai import Agent, RunContext
from pydantic_ai.models.google import GoogleModel
from pydantic_ai.models.test import TestModel

from agents.deps import AgentDependencies
from agents.models import (
    CycleAudit,
    CycleObservation,
    ExecutionResult,
    MarketDataStatus,
    MarketSnapshot,
    PortfolioSnapshot,
    RejectedTrade,
    TickerMetrics,
    TradeDecision,
    TradeProposal,
)
from agents.policies import ExecutionPolicyEngine, build_risk_status
from config import AGENT_BACKEND, AI_PROVIDER, CLAUDE_MODEL, GEMINI_MODEL, TARGET_ALLOCATION
from engine.portfolio import compute_portfolio_value
from execution.kill_switch import KillSwitch
from services.execution_service import ExecutionService
from services.market_service import MarketService
from services.reporting_service import ReportingService
from strategies.calendar import CalendarStrategy
from strategies.threshold import ThresholdStrategy
from utils.time import utc_now_iso, utc_today_str


def build_agent_model(model_name: str | None = None):
    if model_name == "test":
        return TestModel()
    if AI_PROVIDER == "gemini":
        return GoogleModel(GEMINI_MODEL, provider="google-gla")
    if AI_PROVIDER == "anthropic":
        from pydantic_ai.models.anthropic import AnthropicModel

        return AnthropicModel(CLAUDE_MODEL)
    raise ValueError("Only Gemini is supported by the Pydantic AI runtime in this project.")


def build_portfolio_agent(model=None) -> Agent[AgentDependencies, TradeDecision]:
    agent = Agent(
        model=model or build_agent_model(),
        deps_type=AgentDependencies,
        output_type=TradeDecision,
        name="portfolio-agent",
        instructions=(
            "You are a governed portfolio agent. Review the current portfolio, market context, risk status, "
            "and the deterministic trade plan. Approve only trades from that plan. Return a structured TradeDecision."
        ),
        defer_model_check=True,
    )

    @agent.tool
    def get_portfolio_snapshot(ctx: RunContext[AgentDependencies]) -> PortfolioSnapshot:
        prices = ctx.deps.market_gateway.get_latest_prices(list(TARGET_ALLOCATION.keys()))
        snapshot = ctx.deps.portfolio_repository.portfolio_snapshot(prices)
        return PortfolioSnapshot(**snapshot)

    @agent.tool
    def get_market_snapshot(ctx: RunContext[AgentDependencies]) -> MarketSnapshot:
        tickers = list(TARGET_ALLOCATION.keys())
        prices = ctx.deps.market_gateway.get_latest_prices(tickers)
        metrics: dict[str, TickerMetrics] = {}
        for ticker in tickers:
            df = ctx.deps.market_gateway.get_historical(ticker, days=90)
            if df is not None and not getattr(df, "empty", True):
                from market.metrics import PortfolioMetrics

                metrics[ticker] = TickerMetrics(**PortfolioMetrics().ticker_metrics(df))
        refresh = [MarketDataStatus(**item) for item in ctx.deps.market_gateway.get_refresh_status()]
        return MarketSnapshot(prices=prices, metrics=metrics, refresh_status=refresh)

    @agent.tool
    def get_trade_plan(ctx: RunContext[AgentDependencies]) -> list[TradeProposal]:
        return [TradeProposal(**trade) for trade in ctx.deps.active_trade_plan]

    @agent.tool
    def get_risk_status(ctx: RunContext[AgentDependencies]):
        prices = ctx.deps.market_gateway.get_latest_prices(list(TARGET_ALLOCATION.keys()))
        portfolio = ctx.deps.portfolio_repository.load_portfolio()
        total = compute_portfolio_value(portfolio.get("positions", {}), portfolio.get("cash", 0.0), prices)
        peak = portfolio.get("peak_value", total)
        drawdown = (total - peak) / peak if peak > 0 else 0.0
        risk = build_risk_status(
            drawdown=drawdown,
            kill_switch_active=KillSwitch().check_with_prices(portfolio, prices),
            execution_mode=ctx.deps.execution_mode,
            mcp_required=False,
        )
        return risk

    return agent


class AuditRepositoryAdapter:
    def save_cycle_audit(self, audit: dict) -> int:
        from db.repository import save_agent_run

        return save_agent_run(audit)

    def save_decision_trace(self, trace: dict) -> int:
        from db.repository import save_decision_trace

        return save_decision_trace(trace)


class PortfolioAgentService:
    """Primary cycle service driven by Pydantic AI."""

    def __init__(
        self,
        market_gateway: MarketService | None = None,
        execution_service: ExecutionService | None = None,
        reporting_service: ReportingService | None = None,
        agent=None,
    ):
        self.market_gateway = market_gateway or MarketService()
        self.execution_service = execution_service or ExecutionService()
        self.reporting_service = reporting_service or ReportingService(
            market_service=self.market_gateway,
            execution_service=self.execution_service,
        )
        self.audit_repository = AuditRepositoryAdapter()
        self.policy_engine = ExecutionPolicyEngine()
        self.agent = agent

    def _get_strategy(self, strategy_name: str):
        if strategy_name == "calendar":
            return CalendarStrategy()
        return ThresholdStrategy()

    def observe(self, strategy_name: str = "threshold", execution_mode: str = "simulate", cycle_id: str | None = None) -> CycleObservation:
        cycle_id = cycle_id or str(uuid.uuid4())[:8]
        tickers = list(TARGET_ALLOCATION.keys())
        started = perf_counter()
        self.market_gateway.fetch_and_store(tickers, period="3mo")
        fetch_latency_ms = round((perf_counter() - started) * 1000, 2)

        prices = self.market_gateway.get_latest_prices(tickers)
        metrics: dict[str, TickerMetrics] = {}
        for ticker in tickers:
            df = self.market_gateway.get_historical(ticker, days=90)
            if df is not None and not getattr(df, "empty", True):
                from market.metrics import PortfolioMetrics

                metrics[ticker] = TickerMetrics(**PortfolioMetrics().ticker_metrics(df))

        portfolio_dict = self.execution_service.portfolio_snapshot(prices)
        portfolio = PortfolioSnapshot(**portfolio_dict)
        kill_switch = KillSwitch().check_with_prices(self.execution_service.load_portfolio(), prices)
        drawdown = (portfolio.total_value - portfolio.peak_value) / portfolio.peak_value if portfolio.peak_value > 0 else 0.0
        strategy = self._get_strategy(strategy_name)
        strategy_signal = strategy.should_rebalance(self.execution_service.load_portfolio(), prices) and not kill_switch
        trade_plan = [TradeProposal(**trade) for trade in (strategy.get_trades(self.execution_service.load_portfolio(), prices) if strategy_signal else [])]
        market = MarketSnapshot(
            prices=prices,
            metrics=metrics,
            refresh_status=[MarketDataStatus(**item) for item in self.market_gateway.get_refresh_status()],
        )
        risk = build_risk_status(drawdown=drawdown, kill_switch_active=kill_switch, execution_mode=execution_mode, mcp_required=False)
        observation = CycleObservation(
            cycle_id=cycle_id,
            strategy_name=strategy_name,
            portfolio=portfolio,
            market=market,
            risk=risk,
            trade_plan=trade_plan,
            observability={
                "provider": AI_PROVIDER,
                "agent_backend": AGENT_BACKEND,
                "fetch_latency_ms": fetch_latency_ms,
                "strategy_signal": strategy_signal,
            },
        )
        self.audit_repository.save_decision_trace({
            "cycle_id": cycle_id,
            "stage": "observe",
            "payload_json": observation.model_dump_json(),
            "mcp_tools_json": json.dumps([]),
            "provider": AI_PROVIDER,
            "agent_backend": AGENT_BACKEND,
            "execution_mode": execution_mode,
        })
        return observation

    def decide(self, observation: CycleObservation, execution_mode: str = "simulate", model_override=None):
        deps = AgentDependencies(
            market_gateway=self.market_gateway,
            portfolio_repository=self.execution_service,
            execution_gateway=self.execution_service,
            audit_repository=self.audit_repository,
            strategy_name=observation.strategy_name,
            execution_mode=execution_mode,
            active_trade_plan=[trade.model_dump() for trade in observation.trade_plan],
            cycle_id=observation.cycle_id,
        )
        agent = self.agent or build_portfolio_agent(model=model_override or build_agent_model())
        prompt = (
            f"Date: {utc_today_str()}\n"
            f"Cycle ID: {observation.cycle_id}\n"
            f"Strategy: {observation.strategy_name}\n"
            f"Execution mode: {execution_mode}\n"
            "Review the portfolio, risk status, and deterministic trade plan. "
            "Approve only safe trades from the plan and reject the others with reasons."
        )
        result = agent.run_sync(prompt, deps=deps, model=model_override)
        decision = result.output
        tool_names = self._extract_tool_names(result.all_messages_json())
        trace = {
            "cycle_id": observation.cycle_id,
            "stage": "decide",
            "payload_json": decision.model_dump_json(),
            "validation_json": json.dumps({}),
            "mcp_tools_json": json.dumps(tool_names),
            "provider": AI_PROVIDER,
            "agent_backend": AGENT_BACKEND,
            "execution_mode": execution_mode,
        }
        self.audit_repository.save_decision_trace(trace)
        return decision, {"tool_calls": len(tool_names), "tool_names": tool_names, "message_count": len(result.all_messages())}

    def execute(self, observation: CycleObservation, decision: TradeDecision, execution_mode: str = "simulate"):
        policy = self.policy_engine.evaluate(decision, observation, execution_mode)
        executions: list[ExecutionResult] = []
        trace = {
            "cycle_id": observation.cycle_id,
            "stage": "validate",
            "payload_json": decision.model_dump_json(),
            "validation_json": policy.model_dump_json(),
            "mcp_tools_json": json.dumps([]),
            "provider": AI_PROVIDER,
            "agent_backend": AGENT_BACKEND,
            "execution_mode": execution_mode,
        }
        self.audit_repository.save_decision_trace(trace)

        if execution_mode == "simulate":
            for idx, trade in enumerate(policy.allowed_trades):
                market_price = observation.market.prices.get(trade.ticker, 0.0)
                result = self.execution_service.execute_order(
                    trade.model_dump(),
                    market_price=market_price,
                    cycle_id=observation.cycle_id,
                    trades_this_cycle=idx,
                )
                executions.append(ExecutionResult(**asdict(result)))

        execution_trace = {
            "cycle_id": observation.cycle_id,
            "stage": "execute",
            "payload_json": json.dumps([execution.model_dump() for execution in executions]),
            "validation_json": policy.model_dump_json(),
            "mcp_tools_json": json.dumps([]),
            "provider": AI_PROVIDER,
            "agent_backend": AGENT_BACKEND,
            "execution_mode": execution_mode,
        }
        self.audit_repository.save_decision_trace(execution_trace)
        return policy, executions

    def audit(self, observation: CycleObservation, decision: TradeDecision, policy, executions: list[ExecutionResult], execution_mode: str = "simulate") -> CycleAudit:
        report_path = self.reporting_service.generate_cycle_report(observation.cycle_id)
        self.execution_service.update_peak(self.execution_service.get_portfolio_value(observation.market.prices))
        audit = CycleAudit(
            cycle_id=observation.cycle_id,
            timestamp=utc_now_iso(),
            strategy_name=observation.strategy_name,
            agent_backend=AGENT_BACKEND,
            execution_mode=execution_mode,
            portfolio=PortfolioSnapshot(**self.execution_service.portfolio_snapshot(observation.market.prices)),
            market=observation.market,
            risk=observation.risk,
            trade_plan=observation.trade_plan,
            decision=decision,
            policy=policy,
            executions=executions,
            report_path=report_path,
            observability=observation.observability,
        )
        self.audit_repository.save_cycle_audit(self._audit_to_legacy_dict(audit))
        self.audit_repository.save_decision_trace(
            {
                "cycle_id": observation.cycle_id,
                "stage": "audit",
                "payload_json": audit.model_dump_json(),
                "validation_json": policy.model_dump_json(),
                "mcp_tools_json": json.dumps([]),
                "provider": AI_PROVIDER,
                "agent_backend": AGENT_BACKEND,
                "execution_mode": execution_mode,
            }
        )
        return audit

    def run_cycle(self, strategy_name: str = "threshold", execution_mode: str = "simulate", model_override=None) -> CycleAudit:
        observation = self.observe(strategy_name=strategy_name, execution_mode=execution_mode)
        decision, stats = self.decide(observation, execution_mode=execution_mode, model_override=model_override)
        observation.observability.update(stats)
        policy, executions = self.execute(observation, decision, execution_mode=execution_mode)
        return self.audit(observation, decision, policy, executions, execution_mode=execution_mode)

    def run_cycle_dict(self, strategy_name: str = "threshold", execution_mode: str = "simulate", model_override=None) -> dict:
        audit = self.run_cycle(strategy_name=strategy_name, execution_mode=execution_mode, model_override=model_override)
        return {
            "cycle_id": audit.cycle_id,
            "strategy_name": audit.strategy_name,
            "strategy_signal": bool(audit.trade_plan),
            "portfolio": audit.portfolio.model_dump(),
            "market_data": audit.market.model_dump(),
            "analysis": audit.decision.rationale,
            "trades_executed": [execution.model_dump() for execution in audit.executions],
            "report_path": audit.report_path,
            "kill_switch_active": audit.risk.kill_switch_active,
            "errors": audit.errors,
            "messages": [],
            "trade_plan": [trade.model_dump() for trade in audit.trade_plan],
            "observability": audit.observability,
            "decision": audit.decision.model_dump(),
            "policy": audit.policy.model_dump(),
        }

    @staticmethod
    def _extract_tool_names(messages_json: bytes) -> list[str]:
        try:
            payload = json.loads(messages_json)
        except Exception:
            return []
        names: list[str] = []
        for message in payload:
            for part in message.get("parts", []):
                part_kind = part.get("part_kind")
                if part_kind == "tool-call":
                    names.append(part.get("tool_name", ""))
        return [name for name in names if name]

    @staticmethod
    def _audit_to_legacy_dict(audit: CycleAudit) -> dict:
        return {
            "cycle_id": audit.cycle_id,
            "strategy_name": audit.strategy_name,
            "strategy_signal": bool(audit.trade_plan),
            "analysis": audit.decision.rationale,
            "trades_executed": [execution.model_dump() for execution in audit.executions],
            "report_path": audit.report_path,
            "kill_switch_active": audit.risk.kill_switch_active,
            "errors": audit.errors,
            "observability": audit.observability,
        }
