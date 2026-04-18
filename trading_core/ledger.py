"""Ledger for position tracking and cash movements."""

from __future__ import annotations
import uuid
from typing import Dict, List, Optional
from trading_core.models import Execution, Position, CashMovement, CashMovementType, OrderSide
from utils.time import utc_now_iso

class Ledger:
    """The source of truth for positions and cash."""

    def __init__(self, initial_cash: float = 0.0, initial_positions: Dict[str, Position] = None, db_path: str | None = None, profile_name: str | None = None):
        self._positions: Dict[str, Position] = initial_positions or {}
        self._cash: float = initial_cash
        self._cash_movements: List[CashMovement] = []
        self.db_path = db_path
        self.profile_name = profile_name

    def load_from_db(self):
        """Initialize cash and positions from database."""
        from db.repository import get_trading_core_positions, get_trading_core_cash_movements
        
        # 1. Load Positions
        pos_rows = get_trading_core_positions(db_path=self.db_path, profile_name=self.profile_name)
        for row in pos_rows:
            pos = Position(**row)
            self._positions[pos.instrument_id] = pos
            
        # 2. Load Cash (sum of all movements)
        movements = get_trading_core_cash_movements(db_path=self.db_path, profile_name=self.profile_name)
        self._cash_movements = [CashMovement(**m) for m in movements]
        if self._cash_movements:
            self._cash = sum(m.amount for m in self._cash_movements)

    def apply_execution(self, execution: Execution, cycle_id: Optional[str] = None):
        """Update positions and cash based on a trade execution and persist to DB."""
        # 1. Update Cash
        notional = execution.notional
        fees = execution.fees
        
        movement_type = CashMovementType.TRADE_BUY if execution.side == OrderSide.BUY else CashMovementType.TRADE_SELL
        
        # BUY: cash -= (notional + fees)
        # SELL: cash += (notional - fees)
        amount = -(notional + fees) if execution.side == OrderSide.BUY else (notional - fees)
        
        self._cash += amount
        
        movement = CashMovement(
            cash_movement_id=str(uuid.uuid4())[:13],
            cycle_id=cycle_id,
            order_id=execution.order_id,
            execution_id=execution.execution_id,
            movement_type=movement_type,
            amount=amount,
            created_at=execution.executed_at,
            description=f"{execution.side.value.upper()} {execution.quantity} {execution.symbol}"
        )
        self._cash_movements.append(movement)

        # PERSIST CASH
        from db.repository import save_cash_movement
        save_cash_movement(movement.model_dump(), db_path=self.db_path, profile_name=self.profile_name)
        
        # 2. Update Position
        inst_id = execution.instrument_id
        qty = execution.quantity
        price = execution.fill_price
        
        pos = self._positions.get(inst_id)
        if not pos:
            # New position
            pos = Position(
                instrument_id=inst_id,
                symbol=execution.symbol,
                quantity=qty if execution.side == OrderSide.BUY else -qty,
                avg_cost=price,
                last_price=price,
                market_value=qty * price if execution.side == OrderSide.BUY else -qty * price,
                updated_at=execution.executed_at
            )
            self._positions[inst_id] = pos
        else:
            # Update existing
            old_qty = pos.quantity
            old_avg_cost = pos.avg_cost
            
            delta_qty = qty if execution.side == OrderSide.BUY else -qty
            new_qty = old_qty + delta_qty
            
            if abs(new_qty) < 1e-8:
                # Closed
                self._positions.pop(inst_id)
                # Ensure we delete it from DB by sending it with 0 qty or handling separately
                pos.quantity = 0
            else:
                # Update avg cost only on increasing position or simple v1 logic
                if (old_qty > 0 and delta_qty > 0) or (old_qty < 0 and delta_qty < 0):
                    new_avg_cost = ((abs(old_qty) * old_avg_cost) + (qty * price)) / abs(new_qty)
                    pos.avg_cost = new_avg_cost
                
                pos.quantity = new_qty
                pos.last_price = price
                pos.market_value = new_qty * price
                pos.updated_at = execution.executed_at

        # PERSIST POSITION
        from db.repository import save_position_ledger
        save_position_ledger([pos.model_dump()], db_path=self.db_path, profile_name=self.profile_name)
        
        # If position was closed, remove from in-memory after save
        if abs(pos.quantity) < 1e-8 and inst_id in self._positions:
            self._positions.pop(inst_id)

    def get_cash(self) -> float:
        """Return current cash balance."""
        return self._cash

    def list_positions(self) -> List[Position]:
        """Return all active positions."""
        return list(self._positions.values())

    def list_cash_movements(self, cycle_id: Optional[str] = None) -> List[CashMovement]:
        """Return cash movement history."""
        if cycle_id:
            return [m for m in self._cash_movements if m.cycle_id == cycle_id]
        return self._cash_movements

    def get_position(self, instrument_id: str) -> Optional[Position]:
        """Get position by instrument ID."""
        return self._positions.get(instrument_id)
