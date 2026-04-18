"""Order Management System for state management and validation."""

from __future__ import annotations
import uuid
from typing import Dict, List, Optional
from trading_core.models import Order, OrderStatus, OrderSide, OrderType, Instrument
from trading_core.security_master import SecurityMaster
from utils.time import utc_now_iso

class OrderManagementSystem:
    """Handles order lifecycle and validation."""

    def __init__(self, security_master: SecurityMaster, db_path: str | None = None, profile_name: str | None = None):
        self.security_master = security_master
        self._orders: Dict[str, Order] = {}
        self.db_path = db_path
        self.profile_name = profile_name

    def load_from_db(self, cycle_id: Optional[str] = None):
        """Load orders from database."""
        from db.repository import get_trading_core_orders
        rows = get_trading_core_orders(cycle_id=cycle_id, db_path=self.db_path, profile_name=self.profile_name)
        for row in rows:
            order = Order(**row)
            self._orders[order.order_id] = order

    def create_order(
        self,
        cycle_id: str,
        symbol: str,
        side: OrderSide,
        quantity: float,
        order_type: OrderType = OrderType.MARKET,
        reason: Optional[str] = None
    ) -> Order:
        """Create a new order in the CREATED state and persist to DB."""
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

        # Persistence
        from db.repository import save_order, save_order_event
        save_order(order.model_dump(), db_path=self.db_path, profile_name=self.profile_name)
        save_order_event(
            order_id=order.order_id,
            to_status=OrderStatus.CREATED.value,
            event_type="order_created",
            payload={"reason": reason},
            db_path=self.db_path,
            profile_name=self.profile_name
        )
        
        return order

    def update_status(self, order_id: str, new_status: OrderStatus, event_type: str = "status_updated", payload: Optional[Dict] = None) -> Order:
        """Apply a state transition to an order and persist to DB."""
        order = self._orders.get(order_id)
        if not order:
            raise ValueError(f"Order {order_id} not found.")

        from_status = order.status
        order.status = new_status
        order.updated_at = utc_now_iso()

        # Persistence
        from db.repository import save_order, save_order_event
        save_order(order.model_dump(), db_path=self.db_path, profile_name=self.profile_name)
        save_order_event(
            order_id=order_id,
            from_status=from_status.value,
            to_status=new_status.value,
            event_type=event_type,
            payload=payload,
            db_path=self.db_path,
            profile_name=self.profile_name
        )

        return order

    def get_order(self, order_id: str) -> Optional[Order]:
        return self._orders.get(order_id)

    def list_orders(self, cycle_id: Optional[str] = None) -> List[Order]:
        if cycle_id:
            return [o for o in self._orders.values() if o.cycle_id == cycle_id]
        return list(self._orders.values())
