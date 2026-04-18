"""Back Office service for NAV calculation and accounting journals."""

from __future__ import annotations
from typing import List, Dict, Any, Optional
from datetime import datetime
from pathlib import Path
import json
import uuid
import sqlite3

import pandas as pd

from services.execution_service import ExecutionService
from services.market_service import MarketService
from db.connection import get_connection
from utils.time import utc_now_iso

class BackOfficeService:
    """Handles accounting journals, NAV calculation, and period close."""

    def __init__(
        self, 
        execution_service: Optional[ExecutionService] = None,
        market_service: Optional[MarketService] = None
    ):
        self.execution_service = execution_service or ExecutionService()
        self.market_service = market_service or MarketService()

    def record_trade_journal(self, execution_v2: dict, cycle_id: Optional[str] = None):
        """Record double-entry journal for a trade execution."""
        from db.repository import save_journal_entry
        
        timestamp = execution_v2["executed_at"]
        symbol = execution_v2["symbol"]
        notional = execution_v2["notional"]
        fees = execution_v2.get("fees", 0.0)
        side = execution_v2["side"]
        
        # BUY: Debit EQUITY, Credit CASH
        # SELL: Debit CASH, Credit EQUITY
        
        if side.lower() == "buy":
            # Debit Equity
            save_journal_entry({
                "cycle_id": cycle_id,
                "timestamp": timestamp,
                "account_code": f"EQUITY:{symbol}",
                "side": "DEBIT",
                "amount": notional,
                "description": f"Buy {execution_v2['quantity']} {symbol}"
            })
            # Credit Cash
            save_journal_entry({
                "cycle_id": cycle_id,
                "timestamp": timestamp,
                "account_code": "CASH",
                "side": "CREDIT",
                "amount": notional + fees,
                "description": f"Cash outflow for {symbol} buy (incl fees)"
            })
        else:
            # Debit Cash
            save_journal_entry({
                "cycle_id": cycle_id,
                "timestamp": timestamp,
                "account_code": "CASH",
                "side": "DEBIT",
                "amount": notional - fees,
                "description": f"Cash inflow from {symbol} sell (net fees)"
            })
            # Credit Equity
            save_journal_entry({
                "cycle_id": cycle_id,
                "timestamp": timestamp,
                "account_code": f"EQUITY:{symbol}",
                "side": "CREDIT",
                "amount": notional,
                "description": f"Sell {execution_v2['quantity']} {symbol}"
            })

    def calculate_daily_nav(self, as_of_date: str | None = None) -> dict:
        """Compute NAV based on Ledger positions, market prices, and cash."""
        from db.repository import get_trading_core_positions, get_trading_core_cash_movements, save_nav_run
        
        if not as_of_date:
            as_of_date = utc_now_iso()[:10]
            
        # 1. Get current state
        positions = get_trading_core_positions()
        movements = get_trading_core_cash_movements()
        
        cash_balance = sum(m["amount"] for m in movements)
        
        # 2. Price positions
        tickers = [p["symbol"] for p in positions]
        prices = self.market_service.get_latest_prices(tickers)
        
        market_value = 0.0
        unrealized_pnl = 0.0
        realized_pnl = 0.0 # Simplified for v1
        
        for p in positions:
            price = prices.get(p["symbol"], p["last_price"])
            mv = p["quantity"] * price
            market_value += mv
            unrealized_pnl += (price - p["avg_cost"]) * p["quantity"]

        total_value = cash_balance + market_value
        
        nav_data = {
            "as_of_date": as_of_date,
            "timestamp": utc_now_iso(),
            "total_value": total_value,
            "cash_balance": cash_balance,
            "market_value": market_value,
            "unrealized_pnl": unrealized_pnl,
            "realized_pnl": realized_pnl,
            "status": "tentative"
        }
        
        save_nav_run(nav_data)
        return nav_data

    def get_regulatory_mifir_export(self, cycle_id: str) -> List[Dict]:
        """Generate a MiFIR-compliant JSON record for a cycle's executions."""
        from db.repository import get_trading_core_executions, get_user_by_api_key
        
        executions = get_trading_core_executions(cycle_id=cycle_id)
        # In a real system, we'd look up the actual trader from the order/audit trail
        
        export = []
        for e in executions:
            record = {
                "report_type": "NEW",
                "transaction_id": e["execution_id"],
                "instrument_id": e["instrument_id"],
                "symbol": e["symbol"],
                "quantity": abs(e["quantity"]),
                "price": e["fill_price"],
                "currency": "USD",
                "trading_venue": e.get("venue", "XOFF"),
                "execution_timestamp": e["executed_at"],
                "side": e["side"].upper(),
                "investment_decision": "ALGO_PREDICTION_WALLET_V1",
                "executing_entity": "PREDICTION_WALLET_LAB"
            }
            export.append(record)
        return export

    def run_backup(self) -> dict:
        """Create a compressed snapshot of the database and cold record exports."""
        import shutil
        import os
        import config
        from db.repository import get_trading_core_positions

        backup_dir = Path(config.REPORTS_DIR) / "backups"
        backup_dir.mkdir(parents=True, exist_ok=True)
        
        timestamp = utc_now_iso().replace(":", "-")
        db_backup_name = f"snapshot_{timestamp}.db"
        ledger_backup_name = f"ledger_{timestamp}.json"

        # 1. Snapshot DB
        db_backup_path = backup_dir / db_backup_name
        if config.USE_POSTGRES:
            self._backup_postgres_database(db_backup_path)
        else:
            shutil.copy(str(config.MARKET_DB), str(db_backup_path))

        # 2. Export Ledger JSON (Cold record)
        positions = get_trading_core_positions()
        with open(backup_dir / ledger_backup_name, "w") as f:
            json.dump(positions, f, indent=2)
            
        # 3. Retention (Keep last 7 snapshots)
        all_snapshots = sorted(list(backup_dir.glob("snapshot_*.db")))
        if len(all_snapshots) > 7:
            for s in all_snapshots[:-7]:
                s.unlink()
                # Also unlink corresponding ledger
                l_name = s.name.replace("snapshot_", "ledger_").replace(".db", ".json")
                l_path = backup_dir / l_name
                if l_path.exists():
                    l_path.unlink()
                    
        return {
            "status": "success",
            "db_snapshot": db_backup_name,
            "ledger_export": ledger_backup_name,
            "total_backups": min(len(all_snapshots), 7)
        }

    def _backup_postgres_database(self, destination: Path) -> None:
        """Materialize the live Postgres database into a local SQLite snapshot."""
        with get_connection() as source_conn, sqlite3.connect(destination) as target_conn:
            tables = source_conn.execute(
                """
                SELECT table_name
                FROM information_schema.tables
                WHERE table_schema = 'public' AND table_type = 'BASE TABLE'
                ORDER BY table_name
                """
            ).fetchall()
            for table in tables:
                table_name = table["table_name"] if isinstance(table, dict) else table[0]
                cursor = source_conn.execute(f'SELECT * FROM "{table_name}"')
                columns = [desc[0] for desc in cursor.description] if cursor.description else []
                rows = cursor.fetchall()
                frame = pd.DataFrame.from_records(rows, columns=columns) if rows else pd.DataFrame(columns=columns)
                frame.to_sql(table_name, target_conn, if_exists="replace", index=False)
