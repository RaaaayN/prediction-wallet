"""Tests for the Back Office and Reporting phase."""

import pytest
import sqlite3
from pathlib import Path
from services.back_office_service import BackOfficeService
from services.trading_core_service import TradingCoreService
from db.schema import init_db
import config
from trading_core.models import OrderSide
from execution.persistence import PortfolioStore

@pytest.fixture
def db_path(tmp_path, monkeypatch):
    db_file = str(tmp_path / "test_bo.db")
    monkeypatch.setattr(config, "USE_POSTGRES", False)
    monkeypatch.setattr(config, "DATABASE_URL", "")
    monkeypatch.setattr(config, "MARKET_DB", db_file)
    init_db(db_file)
    return db_file

@pytest.fixture(autouse=True)
def empty_legacy_portfolio(monkeypatch):
    monkeypatch.setattr(
        "services.execution_service.ExecutionService.load_portfolio",
        lambda self: PortfolioStore.default_portfolio(config.INITIAL_CAPITAL),
    )

def test_trade_journal_recording(db_path, monkeypatch):
    """Verify that execute_order automatically triggers journal entries."""
    monkeypatch.setattr(config, "INITIAL_CAPITAL", 10000.0)
    
    tc = TradingCoreService(db_path=db_path)
    
    # Execute a buy
    tc.execute_order(
        cycle_id="cycle_bo_1",
        symbol="AAPL",
        side=OrderSide.BUY,
        quantity=10.0
    )
    
    # Verify journals in DB
    from db.repository import get_connection, q
    with get_connection(db_path) as conn:
        journals = conn.execute(q("SELECT * FROM accounting_journals WHERE cycle_id = ?"), ("cycle_bo_1",)).fetchall()
        # Should have 2 entries: Debit Equity, Credit Cash
        assert len(journals) == 2
        
        accounts = [j["account_code"] for j in journals]
        assert "EQUITY:AAPL" in accounts
        assert "CASH" in accounts

def test_nav_calculation(db_path, monkeypatch):
    """Verify daily NAV calculation and persistence."""
    monkeypatch.setattr(config, "INITIAL_CAPITAL", 1000000.0)
    
    tc = TradingCoreService(db_path=db_path)
    # Ensure ledger in-memory and in-db starts with cash
    tc.ledger._cash = 1000000.0
    from db.repository import save_cash_movement
    from trading_core.models import CashMovement, CashMovementType
    from utils.time import utc_now_iso
    save_cash_movement({
        "cash_movement_id": "initial_deposit",
        "movement_type": "deposit",
        "amount": 1000000.0,
        "created_at": utc_now_iso(),
        "description": "Initial"
    }, db_path=db_path)

    tc.execute_order("c1", "AAPL", OrderSide.BUY, 10.0)
    
    bo = BackOfficeService(market_service=tc.market_service)
    nav = bo.calculate_daily_nav(as_of_date="2026-04-18")
    
    assert nav["as_of_date"] == "2026-04-18"
    assert nav["total_value"] > 0
    
    # Verify persistence
    from db.repository import get_nav_history
    history = get_nav_history(db_path=db_path)
    assert len(history) == 1
    assert history[0]["as_of_date"] == "2026-04-18"

def test_mifir_export(db_path, monkeypatch):
    """Verify regulatory export structure."""
    monkeypatch.setattr(config, "INITIAL_CAPITAL", 10000.0)
    
    tc = TradingCoreService(db_path=db_path)
    tc.execute_order("reg_cycle", "AAPL", OrderSide.BUY, 5.0)
    
    bo = BackOfficeService()
    export = bo.get_regulatory_mifir_export("reg_cycle")
    
    assert len(export) == 1
    assert export[0]["symbol"] == "AAPL"
    assert "transaction_id" in export[0]
    assert export[0]["investment_decision"] == "ALGO_PREDICTION_WALLET_V1"


def test_backup_logic_postgres_snapshot(tmp_path, monkeypatch):
    """Verify that Postgres backups snapshot the live tables into SQLite."""
    import services.back_office_service as bo_module

    monkeypatch.setattr(config, "USE_POSTGRES", True)
    monkeypatch.setattr(config, "DATABASE_URL", "postgresql://example")
    reports_dir = str(tmp_path / "reports")
    monkeypatch.setattr(config, "REPORTS_DIR", reports_dir)

    class FakeCursor:
        def __init__(self, rows, columns):
            self._rows = rows
            self.description = [(column, None, None, None, None, None, None) for column in columns]

        def fetchall(self):
            return self._rows

    class FakeConnection:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def execute(self, query):
            if "information_schema.tables" in query:
                return FakeCursor([{"table_name": "positions"}], ["table_name"])
            if 'SELECT * FROM "positions"' in query:
                return FakeCursor([{"ticker": "AAPL", "quantity": 2.5}], ["ticker", "quantity"])
            raise AssertionError(f"Unexpected query: {query}")

    monkeypatch.setattr(bo_module, "get_connection", lambda: FakeConnection())
    monkeypatch.setattr(
        "db.repository.get_trading_core_positions",
        lambda: [{"ticker": "AAPL", "quantity": 2.5, "price": 100.0}],
    )

    svc = BackOfficeService(execution_service=object(), market_service=object())
    result = svc.run_backup()

    backup_path = Path(reports_dir) / "backups"
    snapshot_file = backup_path / result["db_snapshot"]
    assert snapshot_file.exists()

    with sqlite3.connect(snapshot_file) as conn:
        rows = conn.execute('SELECT ticker, quantity FROM "positions"').fetchall()
    assert rows == [("AAPL", 2.5)]
