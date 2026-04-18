"""Tests for the Trading Core v1 subsystem."""

import pytest
import uuid
from trading_core.models import (
    InstrumentType, OrderSide, OrderStatus, OrderType, 
    MarketDataSource, MarketDataFreshness
)
from trading_core.security_master import SecurityMaster
from trading_core.market_data import MarketDataHandler
from trading_core.oms import OrderManagementSystem
from trading_core.ledger import Ledger
from trading_core.brokers.simulation import SimulationBrokerAdapter
from services.market_service import MarketService
from unittest.mock import MagicMock

def test_security_master_bootstrap():
    sm = SecurityMaster()
    sm.bootstrap(existing_positions={"AAPL": 10.0, "BTC-USD": 0.5})
    
    aapl = sm.get_by_symbol("AAPL")
    assert aapl is not None
    assert aapl.asset_class == InstrumentType.EQUITY
    assert aapl.instrument_id == "EQUITY:AAPL"
    
    btc = sm.get_by_symbol("BTC-USD")
    assert btc is not None
    assert btc.asset_class == InstrumentType.CRYPTO
    assert btc.instrument_id == "CRYPTO:BTC-USD"

def test_oms_order_lifecycle():
    sm = SecurityMaster()
    sm.bootstrap()
    oms = OrderManagementSystem(sm)
    
    order = oms.create_order(
        cycle_id="test_cycle",
        symbol="AAPL",
        side=OrderSide.BUY,
        quantity=5.0,
        reason="test"
    )
    
    assert order.status == OrderStatus.CREATED
    assert order.requested_quantity == 5.0
    
    oms.update_status(order.order_id, OrderStatus.VALIDATED)
    assert oms.get_order(order.order_id).status == OrderStatus.VALIDATED
    
    oms.update_status(order.order_id, OrderStatus.SUBMITTED)
    oms.update_status(order.order_id, OrderStatus.FILLED)
    assert oms.get_order(order.order_id).status == OrderStatus.FILLED

def test_ledger_buy_sell():
    ledger = Ledger(initial_cash=10000.0)
    
    from trading_core.models import Execution
    from utils.time import utc_now_iso
    
    # 1. Buy 10 AAPL at 150
    exec1 = Execution(
        execution_id="exec1",
        order_id="order1",
        instrument_id="EQUITY:AAPL",
        symbol="AAPL",
        side=OrderSide.BUY,
        quantity=10.0,
        market_price=150.0,
        fill_price=150.0,
        notional=1500.0,
        fees=1.5,
        executed_at=utc_now_iso()
    )
    
    ledger.apply_execution(exec1, cycle_id="cycle1")
    assert ledger.get_cash() == 10000.0 - 1501.5
    
    pos = ledger.get_position("EQUITY:AAPL")
    assert pos.quantity == 10.0
    assert pos.avg_cost == 150.0
    
    # 2. Sell 5 AAPL at 160
    exec2 = Execution(
        execution_id="exec2",
        order_id="order2",
        instrument_id="EQUITY:AAPL",
        symbol="AAPL",
        side=OrderSide.SELL,
        quantity=5.0,
        market_price=160.0,
        fill_price=160.0,
        notional=800.0,
        fees=0.8,
        executed_at=utc_now_iso()
    )
    
    ledger.apply_execution(exec2, cycle_id="cycle1")
    # cash = 8498.5 + (800 - 0.8) = 8498.5 + 799.2 = 9297.7
    assert round(ledger.get_cash(), 2) == 9297.7
    
    pos = ledger.get_position("EQUITY:AAPL")
    assert pos.quantity == 5.0
    assert pos.avg_cost == 150.0 # Selling doesn't change avg cost in this v1 model

def test_simulation_broker():
    adapter = SimulationBrokerAdapter()
    from trading_core.models import Order, MarketPrice
    from utils.time import utc_now_iso
    
    order = Order(
        order_id="o1",
        cycle_id="c1",
        instrument_id="EQUITY:AAPL",
        symbol="AAPL",
        side=OrderSide.BUY,
        requested_quantity=10.0,
        created_at=utc_now_iso(),
        updated_at=utc_now_iso()
    )
    
    m_price = MarketPrice(
        instrument_id="EQUITY:AAPL",
        symbol="AAPL",
        as_of=utc_now_iso(),
        price=150.0,
        source=MarketDataSource.YFINANCE,
        freshness=MarketDataFreshness.FRESH
    )
    
    execution = adapter.execute_order(order, m_price)
    assert execution.quantity == 10.0
    assert execution.fill_price >= 150.0 # Buy slippage
    assert execution.notional == 10.0 * execution.fill_price
    assert execution.fees > 0

def test_portfolio_agent_service_with_trading_core(monkeypatch, tmp_path):
    """Verify that PortfolioAgentService uses the Trading Core when enabled."""
    import agents.portfolio_agent
    import config
    import db.schema
    import uuid
    
    unique_cycle_id = f"test_tc_cycle_{uuid.uuid4().hex[:8]}"
    
    # Use a temporary DB for this test
    db_file = str(tmp_path / "test_trading_core.db")
    monkeypatch.setattr(config, "MARKET_DB", db_file)
    db.schema.init_db(db_file)
    
    monkeypatch.setattr(agents.portfolio_agent, "TRADING_CORE_ENABLED", True)
    monkeypatch.setattr(config, "TRADING_CORE_ENABLED", True)
    
    from agents.portfolio_agent import PortfolioAgentService
    from agents.models import CycleObservation, TradeDecision, TradeProposal, MarketSnapshot, PortfolioSnapshot, RiskStatus, MarketDataStatus
    from services.execution_service import ExecutionService
    
    # Mock portfolio loading to ensure Ledger starts with 10 AAPL
    original_load = ExecutionService.load_portfolio
    monkeypatch.setattr(ExecutionService, "load_portfolio", lambda self: {
        "positions": {"AAPL": 10.0},
        "cash": 10000.0,
        "average_costs": {"AAPL": 150.0}
    })

    service = PortfolioAgentService()
    assert hasattr(service, "oms")
    assert hasattr(service, "ledger")
    
    # Mock observation and decision
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
    
    # Verify persistence in new tables
    from db.repository import get_trading_core_orders, get_trading_core_positions
    orders = get_trading_core_orders(cycle_id=unique_cycle_id, db_path=db_file)
    assert len(orders) == 1
    assert orders[0]["symbol"] == "AAPL"
    assert orders[0]["status"] == "filled"
    
    tc_positions = get_trading_core_positions(db_path=db_file)
    aapl_pos = next((p for p in tc_positions if p["symbol"] == "AAPL"), None)
    assert aapl_pos is not None
    # Original was 10.0, added 1.0
    assert aapl_pos["quantity"] == 11.0
    aapl_pos = next((p for p in tc_positions if p["symbol"] == "AAPL"), None)
    assert aapl_pos is not None
    # Original was 10.0, added 1.0
    assert aapl_pos["quantity"] == 11.0
