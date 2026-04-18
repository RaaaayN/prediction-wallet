"""Tests for the Persistent Middle Office (Risk & Middle Office phase)."""

import pytest
from services.middle_office_service import MiddleOfficeService
from db.schema import init_db
import config
import os
import json

@pytest.fixture
def db_path(tmp_path, monkeypatch):
    db_file = str(tmp_path / "test_mo.db")
    monkeypatch.setattr(config, "USE_POSTGRES", False)
    monkeypatch.setattr(config, "DATABASE_URL", "")
    monkeypatch.setattr(config, "MARKET_DB", db_file)
    init_db(db_file)
    return db_file

def test_reconcile_persistence(db_path, monkeypatch):
    """Verify that reconciliation runs and breaks are saved to DB."""
    from services.execution_service import ExecutionService
    
    # 1. Mock empty portfolio
    monkeypatch.setattr(ExecutionService, "load_portfolio", lambda self: {
        "positions": {"AAPL": 100.0},
        "cash": 1000.0
    })
    
    svc = MiddleOfficeService()
    # This should find breaks because Trading Core ledger is empty
    breaks = svc.reconcile_holdings()
    assert len(breaks) > 0
    
    # 2. Verify DB state
    from db.repository import get_connection, q
    with get_connection(db_path) as conn:
        run = conn.execute(q("SELECT * FROM reconciliation_runs")).fetchone()
        assert run is not None
        assert run["total_breaks"] == len(breaks)
        
        db_breaks = conn.execute(q("SELECT * FROM reconciliation_breaks WHERE run_id = ?"), (run["run_id"],)).fetchall()
        assert len(db_breaks) == len(breaks)

def test_tca_persistence(db_path, monkeypatch):
    """Verify that TCA reports are persisted and idempotent."""
    from db.repository import save_order, save_trade_execution_v2
    import uuid
    from utils.time import utc_now_iso
    
    cycle_id = "tca_test_cycle"
    
    # 1. Setup a fake execution
    order_id = "o1"
    save_order({
        "order_id": order_id,
        "cycle_id": cycle_id,
        "instrument_id": "EQ:AAPL",
        "symbol": "AAPL",
        "side": "buy",
        "requested_quantity": 10,
        "status": "filled",
        "created_at": utc_now_iso(),
        "updated_at": utc_now_iso()
    }, db_path=db_path)
    
    save_trade_execution_v2({
        "execution_id": "e1",
        "order_id": order_id,
        "instrument_id": "EQ:AAPL",
        "symbol": "AAPL",
        "side": "buy",
        "quantity": 10,
        "market_price": 150.0,
        "fill_price": 151.0,
        "notional": 1510.0,
        "slippage": 10.0,
        "executed_at": utc_now_iso()
    }, db_path=db_path)
    
    svc = MiddleOfficeService()
    
    # 2. First call: compute and save
    report1 = svc.generate_tca_report(cycle_id)
    assert report1.total_trades == 1
    
    from db.repository import get_connection, q
    with get_connection(db_path) as conn:
        count = conn.execute(q("SELECT COUNT(*) FROM tca_reports WHERE cycle_id = ?"), (cycle_id,)).fetchone()[0]
        assert count == 1
        
    # 3. Second call: should load from DB
    report2 = svc.generate_tca_report(cycle_id)
    assert report2.total_trades == 1
    assert report2.total_notional == report1.total_notional
