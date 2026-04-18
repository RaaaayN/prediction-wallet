"""Trading Core Service for orchestrating SecurityMaster, OMS, and Ledger."""

from __future__ import annotations
import uuid
from typing import Dict, List, Optional
from trading_core.security_master import SecurityMaster
from trading_core.oms import OrderManagementSystem
from trading_core.ledger import Ledger
from trading_core.market_data import MarketDataHandler
from trading_core.brokers.simulation import SimulationBrokerAdapter
from trading_core.models import CashMovement, CashMovementType, Execution, OrderSide, OrderStatus, Position
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
        self._bootstrap_from_legacy_portfolio()

    def _bootstrap_from_legacy_portfolio(self) -> None:
        """Seed Trading Core from the legacy portfolio file on first run."""
        if self.ledger.list_positions() or self.ledger.list_cash_movements():
            return

        from services.execution_service import ExecutionService
        from db.repository import save_cash_movement, save_position_ledger, upsert_instruments
        from trading_core.security_master import SecurityMaster
        from utils.time import utc_now_iso

        legacy_portfolio = ExecutionService(profile_name=self.profile_name).load_portfolio()
        legacy_positions = legacy_portfolio.get("positions", {}) or {}
        legacy_cash = float(legacy_portfolio.get("cash", INITIAL_CAPITAL) or 0.0)

        if not legacy_positions and abs(legacy_cash - self.ledger.get_cash()) < 1e-8:
            return

        seeded_at = utc_now_iso()
        sm = SecurityMaster(db_path=self.db_path, profile_name=self.profile_name)
        sm.bootstrap(existing_positions=legacy_positions)
        upsert_instruments([inst.model_dump() for inst in sm.list_instruments()], db_path=self.db_path, profile_name=self.profile_name)

        legacy_positions_rows = []
        for ticker, qty in legacy_positions.items():
            inst = sm.get_or_create_by_symbol(ticker)
            avg_cost = float((legacy_portfolio.get("average_costs") or {}).get(ticker, 0.0) or 0.0)
            legacy_positions_rows.append(
                Position(
                    instrument_id=inst.instrument_id,
                    symbol=ticker,
                    quantity=float(qty),
                    avg_cost=avg_cost,
                    last_price=avg_cost,
                    market_value=float(qty) * avg_cost,
                    updated_at=seeded_at,
                ).model_dump()
            )

        if legacy_positions_rows:
            save_position_ledger(legacy_positions_rows, db_path=self.db_path, profile_name=self.profile_name)

        save_cash_movement(
            CashMovement(
                cash_movement_id=str(uuid.uuid4())[:13],
                cycle_id="legacy-bootstrap",
                movement_type=CashMovementType.DEPOSIT,
                amount=legacy_cash,
                created_at=seeded_at,
                description="Legacy portfolio bootstrap",
            ).model_dump(),
            db_path=self.db_path,
            profile_name=self.profile_name,
        )

        self.security_master.load_from_db()
        self.oms.load_from_db()
        self.ledger.load_from_db()

    def execute_order(self, cycle_id: str, symbol: str, side: OrderSide, quantity: float, reason: Optional[str] = None) -> Execution:
        """Complete order lifecycle: Create -> Validate -> Submit -> Execute -> Apply to Ledger -> Record Journal."""
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

        # 5. Back Office: Journal Entry
        from services.back_office_service import BackOfficeService
        bo_svc = BackOfficeService(execution_service=None, market_service=self.market_service)
        bo_svc.record_trade_journal(execution.model_dump(), cycle_id=cycle_id)
        
        return execution

    def get_positions(self):
        return self.ledger.list_positions()

    def get_cash(self):
        return self.ledger.get_cash()
