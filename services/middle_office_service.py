"""Middle Office service for reconciliation and TCA."""

from __future__ import annotations
from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field
from datetime import datetime
import json

from services.execution_service import ExecutionService
from trading_core.models import Position, CashMovement
from utils.time import utc_now_iso

class ReconciliationBreak(BaseModel):
    break_type: str
    subject: str
    legacy_value: Any
    ledger_value: Any
    diff: Any
    severity: str = "error"

class TCAReport(BaseModel):
    cycle_id: str
    total_trades: int
    total_notional: float
    total_slippage_dollars: float
    avg_slippage_bps: float
    trade_details: List[Dict[str, Any]]

class MiddleOfficeService:
    """Handles trade reconciliation and transaction cost analysis."""

    def __init__(self, execution_service: Optional[ExecutionService] = None):
        self.execution_service = execution_service or ExecutionService()

    def reconcile_holdings(self) -> List[ReconciliationBreak]:
        """Compare legacy portfolio.json state against the Trading Core Ledger."""
        from db.repository import get_trading_core_positions, get_trading_core_cash_movements
        
        legacy_portfolio = self.execution_service.load_portfolio()
        legacy_positions = legacy_portfolio.get("positions", {})
        legacy_cash = legacy_portfolio.get("cash", 0.0)

        ledger_positions = {p["symbol"]: p for p in get_trading_core_positions()}
        
        breaks = []

        movements = get_trading_core_cash_movements()
        ledger_cash = sum(m["amount"] for m in movements) if movements else legacy_cash 
        
        if abs(legacy_cash - ledger_cash) > 0.01:
            breaks.append(ReconciliationBreak(
                break_type="CASH_MISMATCH",
                subject="USD",
                legacy_value=legacy_cash,
                ledger_value=ledger_cash,
                diff=legacy_cash - ledger_cash
            ))

        all_tickers = set(legacy_positions.keys()) | set(ledger_positions.keys())
        
        for ticker in all_tickers:
            legacy_qty = legacy_positions.get(ticker, 0.0)
            ledger_qty = ledger_positions.get(ticker, {}).get("quantity", 0.0)
            
            if abs(legacy_qty - ledger_qty) > 1e-6:
                breaks.append(ReconciliationBreak(
                    break_type="POSITION_QTY_MISMATCH",
                    subject=ticker,
                    legacy_value=legacy_qty,
                    ledger_value=ledger_qty,
                    diff=legacy_qty - ledger_qty
                ))

        return breaks

    def sync_legacy_to_ledger(self):
        """Force update legacy portfolio.json to match the Ledger source of truth."""
        from db.repository import get_trading_core_positions, get_trading_core_cash_movements

        ledger_positions = get_trading_core_positions()
        movements = get_trading_core_cash_movements()
        ledger_cash = sum(m["amount"] for m in movements) if movements else 0.0
        
        portfolio = self.execution_service.load_portfolio()
        
        new_positions = {}
        new_avg_costs = {}
        for p in ledger_positions:
            qty = p["quantity"]
            if abs(qty) > 1e-8:
                new_positions[p["symbol"]] = qty
                new_avg_costs[p["symbol"]] = p["avg_cost"]
        
        portfolio["positions"] = new_positions
        portfolio["average_costs"] = new_avg_costs
        portfolio["cash"] = ledger_cash
        
        self.execution_service.save_portfolio(portfolio)
        return {"status": "synced", "positions_count": len(new_positions), "cash": ledger_cash}

    def generate_tca_report(self, cycle_id: str) -> TCAReport:
        """Compute Transaction Cost Analysis for a specific cycle."""
        from db.repository import get_trading_core_executions

        executions = get_trading_core_executions(cycle_id=cycle_id)
        
        total_notional = 0.0
        total_slippage = 0.0
        details = []
        
        for e in executions:
            notional = e["notional"]
            slippage = e["slippage"]
            
            total_notional += notional
            total_slippage += slippage
            
            bps = (slippage / (notional - slippage) * 10000) if (notional - slippage) > 0 else 0.0
            
            details.append({
                "symbol": e["symbol"],
                "side": e["side"],
                "quantity": e["quantity"],
                "market_price": e["market_price"],
                "fill_price": e["fill_price"],
                "slippage_dollars": slippage,
                "slippage_bps": bps,
                "fees": e["fees"]
            })
            
        avg_bps = (total_slippage / (total_notional - total_slippage) * 10000) if (total_notional - total_slippage) > 0 else 0.0
        
        return TCAReport(
            cycle_id=cycle_id,
            total_trades=len(executions),
            total_notional=total_notional,
            total_slippage_dollars=total_slippage,
            avg_slippage_bps=avg_bps,
            trade_details=details
        )
