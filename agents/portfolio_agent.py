"""Primary Pydantic AI portfolio agent and orchestration service."""

from __future__ import annotations

import asyncio
import json
import logging as _logging
import threading
import uuid
from dataclasses import asdict
from time import perf_counter
from time import perf_counter as _perf

_log = _logging.getLogger("prediction_wallet")


def _slog(stage: str, cycle_id: str, t0: float, **extra) -> None:
    """Emit a structured JSON log line for a cycle stage."""
    record = {"stage": stage, "cycle_id": cycle_id, "duration_ms": round((_perf() - t0) * 1000, 2), **extra}
    _log.info(json.dumps(record))


def _save_cycle_event(cycle_id: str, event_type: str, payload: dict) -> None:
    """Append a cycle event to the immutable event log. Non-critical — never raises."""
    try:
        from db.events import save_event
        save_event(cycle_id, event_type, payload)  # type: ignore[arg-type]
    except Exception:
        pass


from pydantic_ai import Agent, RunContext
from pydantic_ai.models.google import GoogleModel
from pydantic_ai.models.test import TestModel

from agents.deps import AgentDependencies
from agents.models import (
    BacktestExperimentResult,
    BookConstructionDecision,
    BookRiskSnapshot,
    CycleAudit,
    CycleObservation,
    ExposureSnapshot,
    ExecutionResult,
    GovernanceReport,
    IdeaBookEntry,
    IdeaProposal,
    MarketDataStatus,
    MarketSnapshot,
    PnLAttribution,
    PositionIntent,
    PortfolioSnapshot,
    RejectedTrade,
    TickerMetrics,
    TradeDecision,
    TradeProposal,
)
from agents.policies import ExecutionPolicyEngine, PolicyConfig, build_risk_status
from config import (
    AGENT_BACKEND, AI_PROVIDER, CLAUDE_MODEL, GEMINI_MODEL, 
    HEDGE_FUND_PROFILE, SECTOR_MAP, TARGET_ALLOCATION,
    TRADING_CORE_ENABLED
)
from engine.hedge_fund import build_position_intents, classify_book_risk, compute_exposures, compute_pnl_attribution, convert_intents_to_trade_plan
from engine.portfolio import compute_portfolio_value
from execution.kill_switch import KillSwitch
from services.execution_service import ExecutionService
from services.idea_book_service import IdeaBookService
from services.market_service import MarketService
from services.reporting_service import ReportingService
from services.mlflow_service import MLflowService
from engine.backtest_v2 import EventDrivenBacktester
from strategies import build_strategy

# Trading Core v1
from trading_core.security_master import SecurityMaster
from trading_core.market_data import MarketDataHandler
from trading_core.oms import OrderManagementSystem
from trading_core.ledger import Ledger
from trading_core.brokers.simulation import SimulationBrokerAdapter
from trading_core.models import OrderSide, OrderStatus

from utils.time import utc_now_iso, utc_today_str
from utils.telemetry import otel_enabled, stage_span


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
            "and the deterministic trade plan. Approve only trades from that plan. Return a structured TradeDecision. "
            "Always set the 'confidence' field (0.0–1.0) to reflect your certainty in the decision: "
            "1.0 for clear signals with stable market data, 0.5 for uncertain or mixed signals, "
            "0.0 for very conflicting signals or high uncertainty. "
            "The 'data_freshness' field is set automatically — do not override it."
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


def build_research_copilot(model=None) -> Agent[AgentDependencies, Any]:
    agent = Agent(
        model=model or build_agent_model(),
        deps_type=AgentDependencies,
        name="research-copilot",
        instructions=(
            "You are a quantitative research copilot. Your goal is to help launch backtests, "
            "analyze strategy performance, and log institutional experiments to MLflow. "
            "You have access to high-fidelity event-driven backtesting tools. "
            "Always link experiments to the current data lineage (data_hash)."
        ),
        defer_model_check=True,
    )

    @agent.tool
    async def run_experiment(
        self,
        ctx: RunContext[AgentDependencies],
        strategy_type: str,
        days: int = 90,
        gold_dataset: str | None = None
    ) -> BacktestExperimentResult:
        """Run an event-driven backtest experiment and log it to MLflow."""
        tester = EventDrivenBacktester(
            days=days, 
            gold_dataset_name=gold_dataset,
            profile_name=ctx.deps.profile_name
        )
        result = tester.run(strategy_type=strategy_type)

        # Log to MLflow
        mlflow_svc = MLflowService()
        mlflow_svc.log_backtest(result, {
            "strategy_type": strategy_type,
            "days": days,
            "gold_dataset": gold_dataset or "live_sync"
        })
        
        # Return summary
        return BacktestExperimentResult(
            strategy_name=result.strategy_name,
            days=days,
            annualized_return=result.metrics.get("annualized_return", 0.0),
            sharpe=result.metrics.get("sharpe", 0.0),
            max_drawdown=result.metrics.get("max_drawdown", 0.0),
            alpha=result.metrics.get("alpha", 0.0),
            beta=result.metrics.get("beta", 0.0),
            n_trades=len(result.trades),
            n_risk_violations=len(result.risk_violations),
            data_hash=result.data_hash
        )

    return agent


class AuditRepositoryAdapter:
    def save_cycle_audit(self, audit: dict) -> int:
        from db.repository import save_agent_run

        return save_agent_run(audit)

    def save_decision_trace(self, trace: dict) -> int:
        from db.repository import save_decision_trace

        return save_decision_trace(trace)


from services.trading_core_service import TradingCoreService

class PortfolioAgentService:
    """Primary cycle service driven by Pydantic AI."""

    def __init__(
        self,
        market_gateway: MarketService | None = None,
        execution_service: ExecutionService | None = None,
        reporting_service: ReportingService | None = None,
        agent=None,
        *,
        db_path: str | None = None,
        profile_name: str | None = None,
    ):
        self.profile_name = profile_name
        from portfolio_loader import get_active_profile, load_profile
        self.profile = load_profile(profile_name) if profile_name else get_active_profile()
        self.market_gateway = market_gateway or MarketService(profile_name=profile_name)
        self.execution_service = execution_service or ExecutionService(profile_name=profile_name)
        self.reporting_service = reporting_service or ReportingService(
            market_service=self.market_gateway,
            execution_service=self.execution_service,
        )
        self.audit_repository = AuditRepositoryAdapter()
        self.policy_engine = ExecutionPolicyEngine(PolicyConfig.from_profile(self.profile))
        self.idea_book_service = IdeaBookService(profile_name=profile_name)
        self.agent = agent

        # Trading Core v1
        if TRADING_CORE_ENABLED:
            self.trading_core = TradingCoreService(db_path=db_path, profile_name=profile_name)
        else:
            self.trading_core = None

    def _get_strategy(self, strategy_name: str):
        return build_strategy(strategy_name, self.profile)

    def observe(self, strategy_name: str = "threshold", execution_mode: str = "simulate", cycle_id: str | None = None) -> CycleObservation:
        cycle_id = cycle_id or str(uuid.uuid4())[:8]
        tickers = list(TARGET_ALLOCATION.keys())
        started = perf_counter()
        fetch_latencies: dict[str, float] = {}
        if hasattr(self.market_gateway, "fetch_and_store_async") and hasattr(self.market_gateway, "db_path"):
            try:
                _, fetch_latencies = self._run_async_fetch(tickers, period="3mo")
            except Exception:
                self.market_gateway.fetch_and_store(tickers, period="3mo")
        else:
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
        vols = {ticker: m.volatility_30d for ticker, m in metrics.items() if m.volatility_30d > 0}
        from portfolio_loader import get_active_profile
        vol_blend = float(get_active_profile().get("vol_blend", 0.3))
        strategy = self._get_strategy(strategy_name)
        portfolio_for_strategy = self.execution_service.load_portfolio()
        strategy_signal = strategy.should_rebalance(portfolio_for_strategy, prices) and not kill_switch
        regime_summary = self._compute_regime(tickers)
        monte_carlo_summary = self._compute_monte_carlo(portfolio_for_strategy, prices, tickers)
        seeded_ideas = self.idea_book_service.seed_from_profile()
        research = self._research_ideas(seeded_ideas, metrics)
        exposures = self._compute_exposures(portfolio_for_strategy, prices)
        construction = self._construct_book(cycle_id, research, metrics, exposures)
        hedge_fund_plan = [TradeProposal(**trade) for trade in convert_intents_to_trade_plan(
            [intent.model_dump() for intent in construction.intents],
            positions=portfolio_for_strategy.get("positions", {}),
            prices=prices,
            cash=portfolio_for_strategy.get("cash", 0.0),
        )]
        rebalance_plan = [TradeProposal(**trade) for trade in (strategy.get_trades(
            portfolio_for_strategy, prices,
            volatilities=vols if vols else None,
            vol_blend=vol_blend,
        ) if strategy_signal else [])]
        trade_plan = hedge_fund_plan or rebalance_plan
        book_risk = self._classify_book_risk(exposures, portfolio_for_strategy)
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
            ideas=seeded_ideas,
            research=research,
            construction=construction,
            exposures=ExposureSnapshot(**exposures),
            book_risk=BookRiskSnapshot(**book_risk),
            trade_plan=trade_plan,
            observability={
                "provider": AI_PROVIDER,
                "agent_backend": AGENT_BACKEND,
                "fetch_latency_ms": fetch_latency_ms,
                "fetch_latency_by_ticker_ms": fetch_latencies,
                "async_fetch_enabled": bool(fetch_latencies),
                "otel_enabled": otel_enabled(),
                "strategy_signal": strategy_signal,
                "vol_blend": vol_blend,
                "vol_assets_used": len(vols),
                "regime": regime_summary,
                "monte_carlo": monte_carlo_summary,
                "hedge_fund_pipeline": {
                    "research_count": len(research),
                    "intent_count": len(construction.intents),
                    "trade_plan_source": "hedge_fund" if hedge_fund_plan else "rebalance",
                    "gross_exposure": exposures.get("gross_exposure", 0.0),
                    "net_exposure": exposures.get("net_exposure", 0.0),
                },
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
            "event_type": "cycle_step",
            "tags": json.dumps([
                f"strategy:{strategy_name}",
                f"mode:{execution_mode}",
                f"signal:{strategy_signal}",
            ]),
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
        # Inject deterministic data_freshness (LLM cannot reliably assess timestamp staleness)
        decision = decision.model_copy(
            update={"data_freshness": self._compute_data_freshness(observation.market.refresh_status)}
        )
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
            "event_type": "cycle_step",
            "tags": json.dumps([
                f"strategy:{observation.strategy_name}",
                f"mode:{execution_mode}",
                f"rebalance:{decision.rebalance_needed}",
                f"approved_trades:{len(decision.approved_trades)}",
                f"confidence:{decision.confidence:.2f}",
                f"data_freshness:{decision.data_freshness}",
            ]),
        }
        self.audit_repository.save_decision_trace(trace)
        return decision, {"tool_calls": len(tool_names), "tool_names": tool_names, "message_count": len(result.all_messages())}

    def execute(self, observation: CycleObservation, decision: TradeDecision, execution_mode: str = "simulate"):
        regime_name = (observation.observability.get("regime") or {}).get("regime")
        with stage_span("cycle.validate", cycle_id=observation.cycle_id, execution_mode=execution_mode):
            policy = self.policy_engine.evaluate(decision, observation, execution_mode, regime=regime_name)
        executions: list[ExecutionResult] = []
        hard_violation_codes = [v.code for v in policy.violations]
        validate_event_type = "kill_switch" if "kill_switch_active" in hard_violation_codes else (
            "policy_violation" if not policy.approved else "cycle_step"
        )
        trace = {
            "cycle_id": observation.cycle_id,
            "stage": "validate",
            "payload_json": decision.model_dump_json(),
            "validation_json": policy.model_dump_json(),
            "mcp_tools_json": json.dumps([]),
            "provider": AI_PROVIDER,
            "agent_backend": AGENT_BACKEND,
            "execution_mode": execution_mode,
            "event_type": validate_event_type,
            "tags": json.dumps([
                f"approved:{policy.approved}",
                f"allowed:{len(policy.allowed_trades)}",
                f"blocked:{len(policy.blocked_trades)}",
                f"violations:{len(policy.violations)}",
            ]),
        }
        self.audit_repository.save_decision_trace(trace)

        if execution_mode == "simulate":
            with stage_span("cycle.execute", cycle_id=observation.cycle_id, execution_mode=execution_mode):
                for idx, trade in enumerate(policy.allowed_trades):
                    if TRADING_CORE_ENABLED and self.trading_core:
                        # --- Trading Core v1 Path ---
                        side = OrderSide.BUY if trade.action == "buy" else OrderSide.SELL
                        execution_v2 = self.trading_core.execute_order(
                            cycle_id=observation.cycle_id,
                            symbol=trade.ticker,
                            side=side,
                            quantity=trade.quantity,
                            reason=trade.reason
                        )

                        # Legacy Bridge: produce ExecutionResult for compat
                        # Also sync back to PortfolioStore (portfolio.json) via ExecutionService
                        result = self.execution_service.execute_order(
                            trade.model_dump(),
                            market_price=execution_v2.market_price,
                            cycle_id=observation.cycle_id,
                            trades_this_cycle=idx,
                            allow_unallocated=True
                        )
                    else:
                        # --- Legacy Path ---
                        market_price = observation.market.prices.get(trade.ticker, 0.0)
                        result = self.execution_service.execute_order(
                            trade.model_dump(),
                            market_price=market_price,
                            cycle_id=observation.cycle_id,
                            trades_this_cycle=idx,
                        )

                    w_before = observation.portfolio.current_weights.get(trade.ticker, 0.0)
                    t_weight = observation.portfolio.target_weights.get(trade.ticker, 0.0)
                    executions.append(ExecutionResult(
                        **asdict(result),
                        weight_before=round(w_before, 6),
                        target_weight=round(t_weight, 6),
                        drift_before=round(w_before - t_weight, 6),
                        slippage_pct=round(
                            (result.fill_price - result.market_price) / result.market_price, 6
                        ) if result.market_price > 0 else 0.0,
                        notional=round(abs(result.quantity * result.fill_price), 4),
                    ))
                    from db.repository import save_execution

                    save_execution(executions[-1].model_dump(), cycle_id=observation.cycle_id)

        failed_count = sum(1 for e in executions if not e.success)
        execute_event_type = "execution_failure" if failed_count > 0 else "cycle_step"
        execution_trace = {
            "cycle_id": observation.cycle_id,
            "stage": "execute",
            "payload_json": json.dumps([execution.model_dump() for execution in executions]),
            "validation_json": policy.model_dump_json(),
            "mcp_tools_json": json.dumps([]),
            "provider": AI_PROVIDER,
            "agent_backend": AGENT_BACKEND,
            "execution_mode": execution_mode,
            "event_type": execute_event_type,
            "tags": json.dumps([
                f"mode:{execution_mode}",
                f"executed:{len(executions)}",
                f"failed:{failed_count}",
            ]),
        }
        self.audit_repository.save_decision_trace(execution_trace)
        return policy, executions

    def audit(self, observation: CycleObservation, decision: TradeDecision, policy, executions: list[ExecutionResult], execution_mode: str = "simulate") -> CycleAudit:
        report_path = self.reporting_service.generate_cycle_report(observation.cycle_id)
        self.execution_service.update_peak(self.execution_service.get_portfolio_value(observation.market.prices))
        latest_portfolio = self.execution_service.load_portfolio()
        exposures = self._compute_exposures(latest_portfolio, observation.market.prices)
        book_risk = self._classify_book_risk(exposures, latest_portfolio)
        pnl_attr = compute_pnl_attribution(
            positions=latest_portfolio.get("positions", {}),
            prices=observation.market.prices,
            average_costs=latest_portfolio.get("average_costs", {}),
            position_sides=latest_portfolio.get("position_sides", {}),
            executions=[execution.model_dump() for execution in executions],
            idea_lookup={idea.idea_id: idea.model_dump() for idea in observation.ideas},
            sector_map=SECTOR_MAP,
        )
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
            ideas=observation.ideas,
            book_construction=observation.construction,
            exposures=ExposureSnapshot(**exposures),
            book_risk=BookRiskSnapshot(**book_risk),
            pnl_attribution=PnLAttribution(**pnl_attr),
            observability=observation.observability,
            errors=[v.message for v in policy.violations]
                   + [e.error for e in executions if not e.success and e.error],
        )
        from db.repository import save_snapshot

        save_snapshot(
            {
                "positions": audit.portfolio.positions,
                "cash": audit.portfolio.cash,
                "peak_value": audit.portfolio.peak_value,
            },
            observation.market.prices,
            observation.cycle_id,
        )
        self.audit_repository.save_cycle_audit(self._audit_to_legacy_dict(audit))
        audit_event_type = "policy_violation" if audit.errors else "cycle_step"
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
                "event_type": audit_event_type,
                "tags": json.dumps([
                    f"strategy:{observation.strategy_name}",
                    f"mode:{execution_mode}",
                    f"errors:{len(audit.errors)}",
                    f"executions:{len(executions)}",
                ]),
            }
        )
        return audit

    def run_cycle(self, strategy_name: str = "threshold", execution_mode: str = "simulate", model_override=None) -> CycleAudit:
        cycle_t0 = _perf()
        cycle_id = str(uuid.uuid4())[:8]
        _save_cycle_event(cycle_id, "cycle_started", {
            "strategy": strategy_name,
            "mode": execution_mode,
        })
        try:
            # --- observe ---
            t_obs = _perf()
            with stage_span("cycle.observe", cycle_id=cycle_id, execution_mode=execution_mode):
                observation = self.observe(strategy_name=strategy_name, execution_mode=execution_mode, cycle_id=cycle_id)
            _slog(
                "observe", observation.cycle_id, t_obs,
                tickers=list(observation.market.prices.keys()),
                portfolio_value=observation.portfolio.total_value,
            )
            _save_cycle_event(observation.cycle_id, "observation_captured", {
                "portfolio_value": observation.portfolio.total_value,
                "tickers": list(observation.market.prices.keys()),
                "kill_switch": observation.risk.kill_switch_active,
                "regime": (observation.observability.get("regime") or {}).get("regime"),
                "fetch_latency_ms": observation.observability.get("fetch_latency_ms"),
            })

            # --- decide ---
            t_dec = _perf()
            with stage_span("cycle.decide", cycle_id=observation.cycle_id, execution_mode=execution_mode):
                decision, stats = self.decide(observation, execution_mode=execution_mode, model_override=model_override)
            observation.observability.update(stats)
            _slog(
                "decide", observation.cycle_id, t_dec,
                confidence=float(decision.confidence),
                trades=len(decision.approved_trades),
            )
            _save_cycle_event(observation.cycle_id, "decision_made", {
                "confidence": float(decision.confidence),
                "trades_count": len(decision.approved_trades),
                "rebalance_needed": decision.rebalance_needed,
            })

            # --- validate + execute ---
            t_val = _perf()
            policy, executions = self.execute(observation, decision, execution_mode=execution_mode)
            _slog(
                "validate", observation.cycle_id, t_val,
                approved=policy.approved,
                allowed=len(policy.allowed_trades),
                blocked=len(policy.blocked_trades),
            )
            _save_cycle_event(observation.cycle_id, "policy_evaluated", {
                "approved": policy.approved,
                "allowed": len(policy.allowed_trades),
                "blocked": len(policy.blocked_trades),
                "violations": len(policy.violations),
            })
            total_notional = sum(
                abs(e.quantity * e.fill_price) for e in executions if e.success
            )
            _slog(
                "execute", observation.cycle_id, t_val,
                executed=len(executions),
            )
            _save_cycle_event(observation.cycle_id, "trade_executed", {
                "executed_count": len(executions),
                "total_notional": round(total_notional, 4),
            })

            # --- audit ---
            t_aud = _perf()
            with stage_span("cycle.audit", cycle_id=observation.cycle_id, execution_mode=execution_mode):
                audit_result = self.audit(observation, decision, policy, executions, execution_mode=execution_mode)
            total_ms = round((_perf() - cycle_t0) * 1000, 2)
            _slog("audit", observation.cycle_id, t_aud, total_ms=total_ms)
            _save_cycle_event(observation.cycle_id, "audit_complete", {
                "total_ms": total_ms,
                "cycle_id": observation.cycle_id,
            })
            return audit_result
        except Exception as exc:
            _save_cycle_event(cycle_id, "cycle_failed", {"error": str(exc)})
            raise

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

    def _compute_regime(self, tickers: list[str]) -> dict:
        try:
            from engine.regime import get_current_regime

            return get_current_regime(tickers, days=180)
        except Exception as exc:
            return {"regime": "unknown", "error": str(exc), "soft_block_recommended": False}

    def _compute_monte_carlo(self, portfolio: dict, prices: dict[str, float], tickers: list[str]) -> dict:
        try:
            from engine.monte_carlo import run_monte_carlo

            historical_returns: dict[str, list[float]] = {}
            for ticker in tickers:
                hist = self.market_gateway.get_historical(ticker, days=252)
                if hist is not None and not getattr(hist, "empty", True) and "Close" in hist.columns:
                    returns = hist["Close"].pct_change().dropna().tolist()
                    if len(returns) >= 30:
                        historical_returns[ticker] = returns
            if not historical_returns:
                return {"available": False, "reason": "insufficient_history"}
            result = run_monte_carlo(portfolio, prices, historical_returns, n_paths=10000)
            result["available"] = True
            return result
        except Exception as exc:
            return {"available": False, "reason": str(exc)}

    def _run_async_fetch(self, tickers: list[str], period: str) -> tuple[dict, dict[str, float]]:
        async_fetch = self.market_gateway.fetch_and_store_async
        try:
            asyncio.get_running_loop()
        except RuntimeError:
            return asyncio.run(async_fetch(tickers, period=period))

        result: dict[str, object] = {}
        error: list[BaseException] = []

        def _runner() -> None:
            try:
                result["value"] = asyncio.run(async_fetch(tickers, period=period))
            except BaseException as exc:  # pragma: no cover - defensive bridge
                error.append(exc)

        thread = threading.Thread(target=_runner, daemon=True)
        thread.start()
        thread.join()
        if error:
            raise error[0]
        return result.get("value", ({}, {}))  # type: ignore[return-value]

    @staticmethod
    def _compute_data_freshness(refresh_status) -> str:
        """Compute a data freshness label from MarketDataStatus timestamps.

        Returns 'fresh' (all < 24h), 'partial' (some stale), 'stale' (all > 24h),
        or 'unknown' (no refresh data available).
        """
        from datetime import datetime, timezone, timedelta

        if not refresh_status:
            return "unknown"

        threshold = datetime.now(timezone.utc) - timedelta(hours=24)
        fresh_flags: list[bool] = []
        for s in refresh_status:
            if not s.refreshed_at:
                fresh_flags.append(False)
                continue
            try:
                ts = datetime.fromisoformat(s.refreshed_at)
                if ts.tzinfo is None:
                    ts = ts.replace(tzinfo=timezone.utc)
                fresh_flags.append(ts > threshold)
            except (ValueError, AttributeError):
                fresh_flags.append(False)

        if all(fresh_flags):
            return "fresh"
        if any(fresh_flags):
            return "partial"
        return "stale"

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

    def _research_ideas(self, ideas: list[IdeaBookEntry], metrics: dict[str, TickerMetrics]) -> list[IdeaProposal]:
        metric_payload = {ticker: metric.model_dump() for ticker, metric in metrics.items()}
        return self.idea_book_service.research(metric_payload)

    def _construct_book(self, cycle_id: str, ideas: list[IdeaProposal], metrics: dict[str, TickerMetrics], exposures: dict) -> BookConstructionDecision:
        conviction_to_size = HEDGE_FUND_PROFILE.get("conviction_to_size") or {}
        metric_payload = {ticker: metric.model_dump() for ticker, metric in metrics.items()}
        intents = build_position_intents(
            [idea.model_dump() for idea in ideas if idea.status in {"investable", "portfolio"}],
            conviction_to_size=conviction_to_size,
            price_metrics=metric_payload,
            sector_gross=exposures.get("sector_gross", {}),
            sector_map=SECTOR_MAP,
        )
        return BookConstructionDecision(
            cycle_id=cycle_id,
            summary=f"Constructed {len(intents)} long/short intents from idea book.",
            gross_exposure=exposures.get("gross_exposure", 0.0),
            net_exposure=exposures.get("net_exposure", 0.0),
            intents=[PositionIntent(**intent) for intent in intents],
            notes=["Research and construction are deterministic from approved idea-book entries plus market metrics."],
        )

    def _compute_exposures(self, portfolio: dict, prices: dict[str, float]) -> dict:
        universe = HEDGE_FUND_PROFILE.get("universe") or {}
        beta_map = {ticker: (meta or {}).get("beta", 1.0) for ticker, meta in universe.items()}
        return compute_exposures(
            portfolio.get("positions", {}),
            prices,
            portfolio.get("cash", 0.0),
            position_sides=portfolio.get("position_sides", {}),
            sector_map=SECTOR_MAP,
            beta_map=beta_map,
        )

    def _classify_book_risk(self, exposures: dict, portfolio: dict) -> dict:
        policy = self.policy_engine._config
        universe = HEDGE_FUND_PROFILE.get("universe") or {}
        crowded = {ticker: float((meta or {}).get("crowded_score", 0.0)) for ticker, meta in universe.items()}
        squeeze = {ticker for ticker, meta in universe.items() if (meta or {}).get("short_squeeze_risk")}
        return classify_book_risk(
            exposures,
            gross_limit=policy.gross_exposure_limit,
            net_min=policy.net_exposure_min,
            net_max=policy.net_exposure_max,
            max_sector_gross=policy.max_sector_gross,
            max_sector_net=policy.max_sector_net,
            max_single_name_long=policy.max_single_name_long,
            max_single_name_short=policy.max_single_name_short,
            crowded_scores=crowded,
            short_squeeze_names=squeeze,
            position_sides=portfolio.get("position_sides", {}),
        )
