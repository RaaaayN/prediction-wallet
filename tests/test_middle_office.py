"""Tests for Middle Office and industrialized Stress Testing."""

import pytest
import uuid
from services.middle_office_service import MiddleOfficeService
from engine.stress_testing import run_stress_test_v2, ASSET_CLASS_SCENARIOS
from trading_core.models import Position, InstrumentType
from unittest.mock import MagicMock
import db.repository
import db.schema
import db.connection
import config

@pytest.fixture(autouse=True)
def setup_db(monkeypatch, tmp_path):
    """Automatically reset DB and force SQLite for every test."""
    # 1. Force config to SQLite using our new dynamic config + settings
    db_file = str(tmp_path / f"test_pw_{uuid.uuid4().hex[:8]}.db")
    
    # config now reads from config.settings
    monkeypatch.setattr(config.settings, "market_db", db_file)
    monkeypatch.setattr(config.settings, "database_url", None)
    
    # 2. Reset global connection state
    db.connection.clear_connection_cache()
    
    # 3. Initialize the temporary DB
    db.schema.init_db(db_file)
    
    return db_file

def test_stress_test_v2_logic():
    portfolio = {
        "positions": {"AAPL": 10.0, "BTC-USD": 0.1},
        "cash": 5000.0
    }
    prices = {"AAPL": 150.0, "BTC-USD": 50000.0}
    
    results = run_stress_test_v2(portfolio, prices)
    assert len(results) == len(ASSET_CLASS_SCENARIOS)
    
    crash = next(r for r in results if r["scenario"] == "equity_crash")
    assert crash["portfolio_value_after"] == 10050.0
    assert crash["pnl_dollars"] == -1450.0

def test_reconciliation_logic(setup_db):
    from services.execution_service import ExecutionService
    db_file = setup_db
    
    # 1. Mock legacy state: 10 AAPL, $10000 cash
    mock_portfolio = {
        "positions": {"AAPL": 10.0},
        "cash": 10000.0
    }
    mock_exe_svc = MagicMock(spec=ExecutionService)
    mock_exe_svc.load_portfolio.return_value = mock_portfolio
    
    mo_svc = MiddleOfficeService(execution_service=mock_exe_svc)
    
    # 2. Case A: Match
    db.repository.save_position_ledger([{
        "instrument_id": "EQUITY:AAPL",
        "symbol": "AAPL",
        "quantity": 10.0,
        "avg_cost": 150.0,
        "last_price": 150.0,
        "market_value": 1500.0,
        "updated_at": "now"
    }], db_path=db_file)
    db.repository.save_cash_movement({
        "cash_movement_id": f"init_{uuid.uuid4().hex[:8]}",
        "movement_type": "deposit",
        "amount": 10000.0,
        "created_at": "now",
        "description": "init"
    }, db_path=db_file)
    
    breaks = mo_svc.reconcile_holdings()
    assert len(breaks) == 0
    
    # 3. Case B: Discrepancy
    mock_portfolio["cash"] = 9000.0
    breaks = mo_svc.reconcile_holdings()
    assert len(breaks) == 1
    assert breaks[0].break_type == "CASH_MISMATCH"

def test_sync_legacy_to_ledger(setup_db):
    from services.execution_service import ExecutionService
    db_file = setup_db
    
    # Seed ledger: 20 MSFT, $5000 cash
    db.repository.save_position_ledger([{
        "instrument_id": "EQUITY:MSFT",
        "symbol": "MSFT",
        "quantity": 20.0,
        "avg_cost": 300.0,
        "last_price": 300.0,
        "market_value": 6000.0,
        "updated_at": "now"
    }], db_path=db_file)
    db.repository.save_cash_movement({
        "cash_movement_id": f"sync_init_{uuid.uuid4().hex[:8]}",
        "movement_type": "deposit",
        "amount": 5000.0,
        "created_at": "now",
        "description": "init"
    }, db_path=db_file)
    
    # Mock legacy store
    store_portfolio = {"positions": {}, "cash": 0.0}
    def mock_save(p): store_portfolio.update(p)
    
    mock_exe_svc = MagicMock(spec=ExecutionService)
    mock_exe_svc.load_portfolio.return_value = {"positions": {}, "cash": 0.0}
    mock_exe_svc.save_portfolio.side_effect = mock_save
    
    mo_svc = MiddleOfficeService(execution_service=mock_exe_svc)
    mo_svc.sync_legacy_to_ledger()
    
    assert store_portfolio["positions"] == {"MSFT": 20.0}
    assert store_portfolio["cash"] == 5000.0
