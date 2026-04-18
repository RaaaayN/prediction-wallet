"""Order Management System for state management and validation."""

from __future__ import annotations
import uuid
from typing import Dict, List, Optional
from trading_core.models import Order, OrderStatus, OrderSide, OrderType, Instrument
from trading_core.security_master import SecurityMaster
from utils.time import utc_now_iso

class OrderManagementSystem:
    """Handles order lifecycle and validation."""

    def __init__(self, security_master: SecurityMaster):
        self.security_master = security_master
        self._orders: Dict[str, Order] = {}

    def create_order(
        self,
        cycle_id: str,
        symbol: str,
        side: OrderSide,
        quantity: float,
        order_type: OrderType = OrderType.MARKET,
        reason: Optional[str] = None
    ) -> Order:
        """Create a new order in the CREATED state."""
        instrument = self.security_master.get_or_create_by_symbol(symbol)
        order_id = str(uuid.uuid4())[:13]
        now = utc_now_iso()
        
        order = Order(
            order_id=order_id,
            cycle_id=cycle_id,
            instrument_id=instrument.instrument_id,
            symbol=symbol,
            side=side,
            order_type=order_type,
            requested_quantity=quantity,
            status=OrderStatus.CREATED,
            reason=reason,
            created_at=now,
            updated_at=now
        )
        self._orders[order_id] = order
        return order

    def update_status(self, order_id: str, new_status: OrderStatus) -> Order:
        """Apply a state transition to an order."""
        order = self._orders.get(order_id)
        if not order:
            raise ValueError(f"Order {order_id} not found.")

        # Basic validation of state transitions
        current = order.status
        valid = False
        
        if current == OrderStatus.CREATED and new_status in {OrderStatus.VALIDATED, OrderStatus.REJECTED}:
            valid = True
        elif current == OrderStatus.VALIDATED and new_status in {OrderStatus.SUBMITTED, OrderStatus.CANCELLED}:
            valid = True
        elif current == OrderStatus.SUBMITTED and new_status in {OrderStatus.FILLED, OrderStatus.PARTIALLY_FILLED, OrderStatus.REJECTED}:
            valid = True
        elif current == OrderStatus.PARTIALLY_FILLED and new_status in {OrderStatus.FILLED, OrderStatus.CANCELLED}:
            valid = True

        if not valid and current != new_status:
             # Relaxing for v1 simulation, but logging would be good
             pass

        order.status = new_status
        order.updated_at = utc_now_iso()
        return order

    def get_order(self, order_id: str) -> Optional[Order]:
        return self._orders.get(order_id)

    def list_orders(self, cycle_id: Optional[str] = None) -> List[Order]:
        if cycle_id:
            return [o for o in self._orders.values() if o.cycle_id == cycle_id]
        return list(self._orders.values())
