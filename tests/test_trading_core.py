"""Tests for the Trading Core v1 subsystem with Persistence."""

import pytest
import uuid
import os
from trading_core.models import (
    InstrumentType, OrderSide, OrderStatus, OrderType, 
    MarketDataSource, MarketDataFreshness
)
from services.trading_core_service import TradingCoreService
from db.schema import init_db
import config
from trading_core.ledger import Ledger
from execution.persistence import PortfolioStore

@pytest.fixture
def db_path(tmp_path):
    db_file = str(tmp_path / "test_trading_core.db")
    init_db(db_file)
    return db_file

@pytest.fixture(autouse=True)
def empty_legacy_portfolio(monkeypatch):
    monkeypatch.setattr(
        "services.execution_service.ExecutionService.load_portfolio",
        lambda self: PortfolioStore.default_portfolio(config.INITIAL_CAPITAL),
    )

def test_trading_core_service_lifecycle(db_path, monkeypatch):
    """Test full cycle: Order -> Execution -> Ledger -> Persistence."""
    # Ensure config points to our test DB if any global calls happen
    monkeypatch.setattr(config, "MARKET_DB", db_path)
    monkeypatch.setattr(config, "INITIAL_CAPITAL", 10000.0)
    monkeypatch.setattr(config, "USE_POSTGRES", False)

    tc = TradingCoreService(db_path=db_path)
    
    # 1. Execute Buy Order
    execution = tc.execute_order(
        cycle_id="cycle_1",
        symbol="AAPL",
        side=OrderSide.BUY,
        quantity=10.0,
        reason="test buy"
    )
    
    assert execution.quantity == 10.0
    assert tc.get_cash() < 10000.0
    
    # 2. Verify Persistence in DB
    from db.repository import get_trading_core_orders, get_trading_core_positions, get_trading_core_cash_movements
    
    orders = get_trading_core_orders(cycle_id="cycle_1", db_path=db_path)
    assert len(orders) == 1
    assert orders[0]["symbol"] == "AAPL"
    assert orders[0]["status"] == OrderStatus.FILLED.value
    
    positions = get_trading_core_positions(db_path=db_path)
    assert len(positions) == 1
    assert positions[0]["symbol"] == "AAPL"
    assert positions[0]["quantity"] == 10.0
    
    movements = get_trading_core_cash_movements(cycle_id="cycle_1", db_path=db_path)
    assert len(movements) == 1
    assert movements[0]["movement_type"] == "trade_buy"
    assert movements[0]["amount"] < 0

def test_ledger_preserves_initial_cash_when_empty(db_path, monkeypatch):
    monkeypatch.setattr(config, "MARKET_DB", db_path)
    monkeypatch.setattr(config, "USE_POSTGRES", False)

    ledger = Ledger(initial_cash=12345.0, db_path=db_path)
    ledger.load_from_db()

    assert ledger.get_cash() == pytest.approx(12345.0)

def test_trading_core_bootstraps_legacy_portfolio_when_db_empty(db_path, monkeypatch):
    monkeypatch.setattr(config, "MARKET_DB", db_path)
    monkeypatch.setattr(config, "INITIAL_CAPITAL", 10000.0)
    monkeypatch.setattr(config, "USE_POSTGRES", False)
    monkeypatch.setattr(
        "services.execution_service.ExecutionService.load_portfolio",
        lambda self: {
            "positions": {"AAPL": 10.0},
            "cash": 2500.0,
            "average_costs": {"AAPL": 150.0},
        },
    )

    tc = TradingCoreService(db_path=db_path)

    assert tc.get_cash() == pytest.approx(2500.0)
    assert len(tc.get_positions()) == 1
    assert tc.get_positions()[0].symbol == "AAPL"

    from db.repository import get_trading_core_positions, get_trading_core_cash_movements

    positions = get_trading_core_positions(db_path=db_path)
    movements = get_trading_core_cash_movements(db_path=db_path)
    assert len(positions) == 1
    assert positions[0]["quantity"] == 10.0
    assert len(movements) == 1
    assert movements[0]["amount"] == pytest.approx(2500.0)

def test_trading_core_restarts_with_state(db_path, monkeypatch):
    """Test that TradingCoreService reloads its state from the DB."""
    monkeypatch.setattr(config, "MARKET_DB", db_path)
    monkeypatch.setattr(config, "INITIAL_CAPITAL", 10000.0)
    monkeypatch.setattr(config, "USE_POSTGRES", False)

    # 1. First session: buy something
    tc1 = TradingCoreService(db_path=db_path)
    tc1.execute_order("c1", "AAPL", OrderSide.BUY, 10.0)
    cash_after = tc1.get_cash()
    
    # 2. Second session: new instance should load from DB
    tc2 = TradingCoreService(db_path=db_path)
    assert tc2.get_cash() == pytest.approx(cash_after)
    assert len(tc2.get_positions()) == 1
    assert tc2.get_positions()[0].symbol == "AAPL"

def test_portfolio_agent_integration(db_path, monkeypatch):
    """Verify that PortfolioAgentService uses TradingCoreService correctly."""
    import agents.portfolio_agent
    from agents.portfolio_agent import PortfolioAgentService
    from agents.models import CycleObservation, TradeDecision, TradeProposal, MarketSnapshot, PortfolioSnapshot, RiskStatus, MarketDataStatus
    from services.execution_service import ExecutionService
    
    monkeypatch.setattr(config, "MARKET_DB", db_path)
    monkeypatch.setattr(config, "USE_POSTGRES", False)
    monkeypatch.setattr(agents.portfolio_agent, "TRADING_CORE_ENABLED", True)
    monkeypatch.setattr(config, "TRADING_CORE_ENABLED", True)
    
    # Mock portfolio loading for legacy path compat
    monkeypatch.setattr(ExecutionService, "load_portfolio", lambda self: {
        "positions": {"AAPL": 10.0},
        "cash": 10000.0,
        "average_costs": {"AAPL": 150.0}
    })

    service = PortfolioAgentService(db_path=db_path)
    assert hasattr(service, "trading_core")
    assert service.trading_core is not None
    
    unique_cycle_id = "agent_tc_test"
    
    obs = CycleObservation(
        cycle_id=unique_cycle_id,
        strategy_name="threshold",
        portfolio=PortfolioSnapshot(
            positions={"AAPL": 10.0},
            cash=10000.0,
            peak_value=12000.0,
            total_value=11500.0,
            current_weights={"AAPL": 0.1},
            target_weights={"AAPL": 0.1},
            weight_deviation={"AAPL": 0.0},
            pnl_dollars=1500.0,
            pnl_pct=0.15
        ),
        market=MarketSnapshot(
            prices={"AAPL": 150.0},
            refresh_status=[MarketDataStatus(ticker="AAPL", refreshed_at="2024-01-01T00:00:00Z", success=True)]
        ),
        risk=RiskStatus(
            kill_switch_active=False,
            drawdown=0.0,
            max_trades_per_cycle=5,
            max_order_fraction_of_portfolio=0.3,
            allowed_tickers=["AAPL"],
            execution_mode="simulate"
        ),
        trade_plan=[TradeProposal(action="buy", ticker="AAPL", quantity=1.0, reason="test")]
    )
    
    decision = TradeDecision(
        cycle_id=unique_cycle_id,
        summary="test",
        market_outlook="test",
        rationale="test",
        rebalance_needed=True,
        approved_trades=[TradeProposal(action="buy", ticker="AAPL", quantity=1.0, reason="test")],
        confidence=1.0,
        data_freshness="fresh"
    )
    
    policy, executions = service.execute(obs, decision, execution_mode="simulate")
    
    assert len(executions) == 1
    assert executions[0].success is True
    
    # Verify that TradingCore was updated
    assert len(service.trading_core.get_positions()) > 0
