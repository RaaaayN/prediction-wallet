"""Trading Core Service for orchestrating SecurityMaster, OMS, and Ledger."""

from __future__ import annotations
from typing import Dict, List, Optional
from trading_core.security_master import SecurityMaster
from trading_core.oms import OrderManagementSystem
from trading_core.ledger import Ledger
from trading_core.market_data import MarketDataHandler
from trading_core.brokers.simulation import SimulationBrokerAdapter
from trading_core.models import OrderSide, OrderStatus, MarketPrice, Execution
from services.market_service import MarketService
from config import INITIAL_CAPITAL

class TradingCoreService:
    """Orchestrates the Trading Core components with persistence."""

    def __init__(self, db_path: str | None = None, profile_name: str | None = None):
        self.db_path = db_path
        self.profile_name = profile_name
        
        # 1. Initialize Components
        self.security_master = SecurityMaster(db_path=db_path, profile_name=profile_name)
        self.oms = OrderManagementSystem(self.security_master, db_path=db_path, profile_name=profile_name)
        self.ledger = Ledger(initial_cash=INITIAL_CAPITAL, db_path=db_path, profile_name=profile_name)
        
        # 2. Market and Broker
        self.market_service = MarketService()
        self.market_data_handler = MarketDataHandler(self.market_service, self.security_master)
        self.broker_adapter = SimulationBrokerAdapter()

        # 3. Bootstrap State from DB
        self.security_master.bootstrap()
        self.oms.load_from_db()
        self.ledger.load_from_db()

    def execute_order(self, cycle_id: str, symbol: str, side: OrderSide, quantity: float, reason: Optional[str] = None) -> Execution:
        """Complete order lifecycle: Create -> Validate -> Submit -> Execute -> Apply to Ledger."""
        # 1. Market Price Snapshot
        market_price = self.market_data_handler.get_market_price(symbol)
        from db.repository import save_market_price
        save_market_price(market_price.model_dump(), db_path=self.db_path, profile_name=self.profile_name)

        # 2. OMS: Create & Validate
        order = self.oms.create_order(
            cycle_id=cycle_id,
            symbol=symbol,
            side=side,
            quantity=quantity,
            reason=reason
        )
        self.oms.update_status(order.order_id, OrderStatus.VALIDATED, event_type="validation_passed")

        # 3. Broker: Execute
        self.oms.update_status(order.order_id, OrderStatus.SUBMITTED, event_type="order_submitted")
        
        execution = self.broker_adapter.execute_order(order, market_price)
        
        self.oms.update_status(order.order_id, OrderStatus.FILLED, event_type="execution_filled")
        from db.repository import save_trade_execution_v2
        save_trade_execution_v2(execution.model_dump(), db_path=self.db_path, profile_name=self.profile_name)

        # 4. Ledger: Apply
        self.ledger.apply_execution(execution, cycle_id=cycle_id)
        
        return execution

    def get_positions(self):
        return self.ledger.list_positions()

    def get_cash(self):
        return self.ledger.get_cash()
