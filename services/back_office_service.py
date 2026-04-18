"""Back Office service for NAV calculation and accounting journals."""

from __future__ import annotations
from typing import List, Dict, Any, Optional
from datetime import datetime
import json
import uuid

from services.execution_service import ExecutionService
from services.market_service import MarketService
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
