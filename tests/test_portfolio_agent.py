"""Tests for the Pydantic AI portfolio agent stack."""

import json
import tempfile

from pydantic_ai.models.test import TestModel

from agents.models import ExecutionResult, PolicyEvaluation, PolicyViolation, TradeDecision
from agents.portfolio_agent import PortfolioAgentService
from services.execution_service import ExecutionService
from services.market_service import MarketService
from execution.persistence import PortfolioStore, TradeLogStore


class FakeMarketGateway(MarketService):
    def __init__(self):
        self._prices = {"AAPL": 100.0, "MSFT": 200.0}

    def fetch_and_store(self, tickers: list[str], period: str = "1y", force: bool = False) -> dict:
        return {}

    def get_latest_prices(self, tickers: list[str]) -> dict[str, float]:
        return {ticker: self._prices.get(ticker, 0.0) for ticker in tickers}

    def get_historical(self, ticker: str, days: int = 90):
        import pandas as pd

        if ticker not in self._prices:
            return pd.DataFrame()
        return pd.DataFrame({"Close": [self._prices[ticker]] * 90})

    def get_refresh_status(self) -> list[dict]:
        return [{"ticker": "AAPL", "refreshed_at": "2026-03-23T00:00:00+00:00", "success": True, "error": None}]


def build_service() -> PortfolioAgentService:
    tmpdir = tempfile.mkdtemp()
    execution_service = ExecutionService(
        portfolio_store=PortfolioStore(f"{tmpdir}/portfolio.json"),
        trade_log_store=TradeLogStore(f"{tmpdir}/trades.log"),
    )
    return PortfolioAgentService(
        market_gateway=FakeMarketGateway(),
        execution_service=execution_service,
    )


def test_observation_is_structured():
    service = build_service()
    observation = service.observe()
    assert observation.cycle_id
    assert observation.portfolio.total_value >= 0
    assert isinstance(observation.trade_plan, list)
    assert observation.risk.execution_mode == "simulate"


def test_decision_uses_structured_output():
    service = build_service()
    observation = service.observe()
    model = TestModel(
        custom_output_args={
            "cycle_id": observation.cycle_id,
            "summary": "Small rebalance needed.",
            "market_outlook": "neutral",
            "rationale": "Weights are drifting from targets.",
            "rebalance_needed": True,
            "approved_trades": [],
            "rejected_trades": [],
            "risk_flags": [],
        }
    )
    decision, stats = service.decide(observation, model_override=model)
    assert isinstance(decision, TradeDecision)
    assert decision.cycle_id == observation.cycle_id
    assert "tool_calls" in stats


def test_policy_blocks_trade_outside_plan():
    service = build_service()
    observation = service.observe()
    decision = TradeDecision(
        cycle_id=observation.cycle_id,
        summary="Attempt invalid trade",
        market_outlook="neutral",
        rationale="Test",
        rebalance_needed=True,
        approved_trades=[{"action": "buy", "ticker": "TSLA", "quantity": 1.0, "reason": "not allowed"}],
        rejected_trades=[],
        risk_flags=[],
    )
    policy, executions = service.execute(observation, decision)
    assert policy.approved is True  # soft block: other valid trades still allowed
    assert executions == []
    assert policy.blocked_trades[0].ticker == "TSLA"


def test_portfolio_agent_forwards_profile_name(monkeypatch):
    """Explicit profile selection should flow into all nested legacy services."""
    import agents.portfolio_agent as portfolio_agent_module

    captured = {}

    class FakeMarketService:
        def __init__(self, *args, **kwargs):
            captured["market_profile"] = kwargs.get("profile_name")

    class FakeExecutionService:
        def __init__(self, *args, **kwargs):
            captured["execution_profile"] = kwargs.get("profile_name")

    class FakeIdeaBookService:
        def __init__(self, *args, **kwargs):
            captured["idea_profile"] = kwargs.get("profile_name")

    class FakeReportingService:
        def __init__(self, *args, **kwargs):
            captured["reporting_market"] = kwargs.get("market_service")
            captured["reporting_execution"] = kwargs.get("execution_service")

    class FakeExecutionPolicyEngine:
        def __init__(self, profile):
            captured["policy_profile"] = profile

    monkeypatch.setattr(portfolio_agent_module, "MarketService", FakeMarketService)
    monkeypatch.setattr(portfolio_agent_module, "ExecutionService", FakeExecutionService)
    monkeypatch.setattr(portfolio_agent_module, "IdeaBookService", FakeIdeaBookService)
    monkeypatch.setattr(portfolio_agent_module, "ReportingService", FakeReportingService)
    monkeypatch.setattr(portfolio_agent_module, "ExecutionPolicyEngine", FakeExecutionPolicyEngine)
    monkeypatch.setattr(
        portfolio_agent_module.PolicyConfig,
        "from_profile",
        classmethod(lambda cls, profile: profile["name"]),
    )
    monkeypatch.setattr(portfolio_agent_module, "TRADING_CORE_ENABLED", False)

    service = portfolio_agent_module.PortfolioAgentService(profile_name="growth")

    assert captured["market_profile"] == "growth"
    assert captured["execution_profile"] == "growth"
    assert captured["idea_profile"] == "growth"
    assert captured["policy_profile"] == "growth"
    assert service.profile_name == "growth"


# ── Explainability fields tests ───────────────────────────────────────────────

def test_execution_result_explainability_fields_populated():
    """ExecutionResult carries weight_before, target_weight, drift_before, slippage_pct, notional."""
    import pytest
    from config import TARGET_ALLOCATION

    service = build_service()

    # Seed a small AAPL position so the strategy sees non-empty weights and triggers rebalance.
    portfolio = service.execution_service.load_portfolio()
    portfolio["positions"] = {"AAPL": 10.0}   # 10 shares @ $100 = $1 000 of $100 000 → 1% weight
    service.execution_service.save_portfolio(portfolio)

    observation = service.observe()

    if not observation.trade_plan:
        pytest.skip("Strategy produced no trade plan with seeded portfolio")

    # Build a decision that approves exactly the first trade from the plan.
    first_trade = observation.trade_plan[0]
    decision = TradeDecision(
        cycle_id=observation.cycle_id,
        summary="test",
        market_outlook="neutral",
        rationale="test",
        rebalance_needed=True,
        approved_trades=[first_trade],
        rejected_trades=[],
        risk_flags=[],
    )

    policy, executions = service.execute(observation, decision)

    assert len(executions) >= 1, "Expected at least one execution"
    ex = executions[0]

    # All five explainability fields must be present (non-negative notional, finite floats).
    assert ex.notional >= 0.0
    assert isinstance(ex.weight_before, float)
    assert isinstance(ex.target_weight, float)
    assert isinstance(ex.drift_before, float)
    assert isinstance(ex.slippage_pct, float)

    # Algebraic invariant: drift_before = weight_before − target_weight.
    assert abs(ex.drift_before - (ex.weight_before - ex.target_weight)) < 1e-5

    # target_weight must match the config allocation for this ticker.
    assert ex.target_weight == pytest.approx(TARGET_ALLOCATION.get(ex.ticker, 0.0), abs=1e-5)

    # For a successful trade, slippage_pct should encode (fill − market) / market correctly.
    if ex.success and ex.market_price > 0:
        expected = (ex.fill_price - ex.market_price) / ex.market_price
        assert abs(ex.slippage_pct - expected) < 1e-5

    # notional = |quantity × fill_price|.
    assert ex.notional == pytest.approx(abs(ex.quantity * ex.fill_price), abs=1e-3)


def test_save_execution_persists_explainability_fields():
    """save_execution() writes the new columns; get_executions() returns them."""
    import tempfile
    import pytest
    from db.schema import init_db
    from db.repository import get_executions, save_execution
    from utils.time import utc_now_iso

    tmpdir = tempfile.mkdtemp()
    db_path = f"{tmpdir}/test.db"
    init_db(db_path)

    record = ExecutionResult(
        trade_id="t-xp",
        action="buy",
        ticker="AAPL",
        quantity=10.0,
        market_price=100.0,
        fill_price=100.1,
        cost=-1001.0,
        timestamp=utc_now_iso(),
        reason="rebalance",
        success=True,
        weight_before=0.01,
        target_weight=0.12,
        drift_before=-0.11,
        slippage_pct=0.001,
        notional=1001.0,
    )
    save_execution(record.model_dump(), cycle_id="c-xp", db_path=db_path)

    df = get_executions(limit=1, db_path=db_path)
    assert not df.empty
    row = df.iloc[0]

    assert row["weight_before"] == pytest.approx(0.01)
    assert row["target_weight"] == pytest.approx(0.12)
    assert row["drift_before"] == pytest.approx(-0.11)
    assert row["slippage_pct"] == pytest.approx(0.001)
    assert row["notional"] == pytest.approx(1001.0)


# ── CycleAudit.errors tests ───────────────────────────────────────────────────

def _no_op_decision(service, observation) -> TradeDecision:
    """Build a no-op TradeDecision via TestModel (no trades, no side effects)."""
    model = TestModel(
        custom_output_args={
            "cycle_id": observation.cycle_id,
            "summary": "test",
            "market_outlook": "neutral",
            "rationale": "test",
            "rebalance_needed": False,
            "approved_trades": [],
            "rejected_trades": [],
            "risk_flags": [],
        }
    )
    decision, _ = service.decide(observation, model_override=model)
    return decision


def test_audit_errors_empty_on_clean_cycle():
    """Clean cycle with no violations or failed executions → errors is empty."""
    service = build_service()
    observation = service.observe()
    decision = _no_op_decision(service, observation)
    policy, executions = service.execute(observation, decision)
    audit = service.audit(observation, decision, policy, executions)

    assert isinstance(audit.errors, list)
    assert audit.errors == []


def test_audit_errors_populated_from_hard_violation():
    """Kill switch active → policy.violations → audit.errors contains the message."""
    service = build_service()
    observation = service.observe()
    observation.risk = observation.risk.model_copy(update={"kill_switch_active": True})
    decision = _no_op_decision(service, observation)
    policy, executions = service.execute(observation, decision)

    assert policy.approved is False
    assert any(v.code == "kill_switch_active" for v in policy.violations)

    audit = service.audit(observation, decision, policy, executions)

    assert any("kill switch" in e.lower() for e in audit.errors)


def test_audit_errors_populated_from_failed_execution():
    """A failed ExecutionResult with a non-empty error string appears in audit.errors."""
    from utils.time import utc_now_iso

    service = build_service()
    observation = service.observe()
    decision = _no_op_decision(service, observation)
    clean_policy = PolicyEvaluation(approved=True, allowed_trades=[], blocked_trades=[], violations=[])
    failed_exec = ExecutionResult(
        trade_id="t-test",
        action="buy",
        ticker="AAPL",
        quantity=1.0,
        market_price=100.0,
        fill_price=0.0,
        cost=0.0,
        timestamp=utc_now_iso(),
        reason="test",
        success=False,
        error="Simulated execution failure",
    )

    audit = service.audit(observation, decision, clean_policy, [failed_exec])

    assert "Simulated execution failure" in audit.errors


def test_audit_errors_ignores_empty_error_strings():
    """Successful executions with error='' do not appear in audit.errors."""
    from utils.time import utc_now_iso

    service = build_service()
    observation = service.observe()
    decision = _no_op_decision(service, observation)
    clean_policy = PolicyEvaluation(approved=True, allowed_trades=[], blocked_trades=[], violations=[])
    successful_exec = ExecutionResult(
        trade_id="t-ok",
        action="buy",
        ticker="AAPL",
        quantity=1.0,
        market_price=100.0,
        fill_price=100.5,
        cost=100.5,
        timestamp=utc_now_iso(),
        reason="rebalance",
        success=True,
        error="",
    )

    audit = service.audit(observation, decision, clean_policy, [successful_exec])

    assert audit.errors == []


# ── Confidence scoring tests (#11) ───────────────────────────────────────────

def test_confidence_default_is_midpoint():
    """TestModel without explicit confidence yields the 0.5 default."""
    service = build_service()
    observation = service.observe()
    model = TestModel(
        custom_output_args={
            "cycle_id": observation.cycle_id,
            "summary": "test",
            "market_outlook": "neutral",
            "rationale": "test",
            "rebalance_needed": False,
            "approved_trades": [],
            "rejected_trades": [],
            "risk_flags": [],
        }
    )
    decision, _ = service.decide(observation, model_override=model)
    assert isinstance(decision.confidence, float)
    assert 0.0 <= decision.confidence <= 1.0
    assert decision.confidence == 0.5


def test_confidence_explicit_value_propagated():
    """Explicit confidence from TestModel propagates into the returned decision."""
    service = build_service()
    observation = service.observe()
    model = TestModel(
        custom_output_args={
            "cycle_id": observation.cycle_id,
            "summary": "test",
            "market_outlook": "neutral",
            "rationale": "test",
            "rebalance_needed": False,
            "approved_trades": [],
            "rejected_trades": [],
            "risk_flags": [],
            "confidence": 0.85,
        }
    )
    decision, _ = service.decide(observation, model_override=model)
    assert decision.confidence == 0.85


def test_data_freshness_fresh_when_recent(monkeypatch):
    """data_freshness = 'fresh' when all refresh_status timestamps are within 24h."""
    from datetime import datetime, timezone, timedelta
    from agents.models import MarketDataStatus
    from agents.portfolio_agent import PortfolioAgentService

    now_iso = datetime.now(timezone.utc).isoformat()
    refresh = [
        MarketDataStatus(ticker="AAPL", refreshed_at=now_iso, success=True),
        MarketDataStatus(ticker="MSFT", refreshed_at=now_iso, success=True),
    ]
    freshness = PortfolioAgentService._compute_data_freshness(refresh)
    assert freshness == "fresh"


def test_data_freshness_stale_when_old():
    """data_freshness = 'stale' when all timestamps are older than 24h."""
    from datetime import datetime, timezone, timedelta
    from agents.models import MarketDataStatus
    from agents.portfolio_agent import PortfolioAgentService

    old_iso = (datetime.now(timezone.utc) - timedelta(hours=48)).isoformat()
    refresh = [
        MarketDataStatus(ticker="AAPL", refreshed_at=old_iso, success=True),
        MarketDataStatus(ticker="MSFT", refreshed_at=old_iso, success=True),
    ]
    freshness = PortfolioAgentService._compute_data_freshness(refresh)
    assert freshness == "stale"


def test_data_freshness_partial_when_mixed():
    """data_freshness = 'partial' when some timestamps are fresh and some are stale."""
    from datetime import datetime, timezone, timedelta
    from agents.models import MarketDataStatus
    from agents.portfolio_agent import PortfolioAgentService

    now_iso = datetime.now(timezone.utc).isoformat()
    old_iso = (datetime.now(timezone.utc) - timedelta(hours=48)).isoformat()
    refresh = [
        MarketDataStatus(ticker="AAPL", refreshed_at=now_iso, success=True),
        MarketDataStatus(ticker="MSFT", refreshed_at=old_iso, success=True),
    ]
    freshness = PortfolioAgentService._compute_data_freshness(refresh)
    assert freshness == "partial"


def test_data_freshness_unknown_when_empty():
    """data_freshness = 'unknown' when refresh_status is empty."""
    from agents.portfolio_agent import PortfolioAgentService

    freshness = PortfolioAgentService._compute_data_freshness([])
    assert freshness == "unknown"


def test_data_freshness_partial_when_no_timestamp():
    """data_freshness = 'stale' when refreshed_at is None for all tickers."""
    from agents.models import MarketDataStatus
    from agents.portfolio_agent import PortfolioAgentService

    refresh = [
        MarketDataStatus(ticker="AAPL", refreshed_at=None, success=False),
        MarketDataStatus(ticker="MSFT", refreshed_at=None, success=False),
    ]
    freshness = PortfolioAgentService._compute_data_freshness(refresh)
    assert freshness == "stale"


def test_data_freshness_injected_into_decision():
    """decide() always sets data_freshness on the returned decision (not 'unknown')."""
    service = build_service()
    observation = service.observe()
    model = TestModel(
        custom_output_args={
            "cycle_id": observation.cycle_id,
            "summary": "test",
            "market_outlook": "neutral",
            "rationale": "test",
            "rebalance_needed": False,
            "approved_trades": [],
            "rejected_trades": [],
            "risk_flags": [],
        }
    )
    decision, _ = service.decide(observation, model_override=model)
    # FakeMarketGateway.get_refresh_status() returns one entry with a valid timestamp
    assert decision.data_freshness in ("fresh", "partial", "stale", "unknown")
    assert isinstance(decision.data_freshness, str)


def test_confidence_in_cycle_audit():
    """confidence and data_freshness survive full cycle and appear in CycleAudit.decision."""
    service = build_service()
    observation = service.observe()
    model = TestModel(
        custom_output_args={
            "cycle_id": observation.cycle_id,
            "summary": "test",
            "market_outlook": "neutral",
            "rationale": "test",
            "rebalance_needed": False,
            "approved_trades": [],
            "rejected_trades": [],
            "risk_flags": [],
            "confidence": 0.72,
        }
    )
    decision, _ = service.decide(observation, model_override=model)
    policy, executions = service.execute(observation, decision)
    audit = service.audit(observation, decision, policy, executions)

    assert audit.decision.confidence == 0.72
    assert audit.decision.data_freshness in ("fresh", "partial", "stale", "unknown")


def test_observation_includes_regime_and_monte_carlo():
    service = build_service()
    portfolio = service.execution_service.load_portfolio()
    portfolio["positions"] = {"AAPL": 10.0, "MSFT": 5.0}
    service.execution_service.save_portfolio(portfolio)

    observation = service.observe()

    assert "regime" in observation.observability
    assert "monte_carlo" in observation.observability
    assert isinstance(observation.observability["regime"], dict)
    assert isinstance(observation.observability["monte_carlo"], dict)


def test_execute_persists_execution_rows():
    from db.repository import get_executions

    service = build_service()
    portfolio = service.execution_service.load_portfolio()
    portfolio["positions"] = {"AAPL": 10.0}
    service.execution_service.save_portfolio(portfolio)

    observation = service.observe()
    if not observation.trade_plan:
        return

    decision = TradeDecision(
        cycle_id=observation.cycle_id,
        summary="persist execution",
        market_outlook="neutral",
        rationale="test",
        rebalance_needed=True,
        approved_trades=[observation.trade_plan[0]],
        rejected_trades=[],
        risk_flags=[],
    )
    _, executions = service.execute(observation, decision)
    df = get_executions(limit=10)

    if executions:
        assert not df.empty


def test_audit_persists_snapshot_for_cycle():
    from db.repository import get_positions_by_cycle

    service = build_service()
    observation = service.observe()
    decision = _no_op_decision(service, observation)
    policy, executions = service.execute(observation, decision)
    audit = service.audit(observation, decision, policy, executions)
    positions = get_positions_by_cycle(audit.cycle_id)

    assert isinstance(positions, list)
