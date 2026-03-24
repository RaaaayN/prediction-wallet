"""Tests for the Pydantic AI portfolio agent stack."""

import json
import tempfile

from pydantic_ai.models.test import TestModel

from agents.models import TradeDecision
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
    assert policy.approved is False
    assert executions == []
    assert policy.blocked_trades[0].ticker == "TSLA"
