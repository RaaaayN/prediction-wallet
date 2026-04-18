"""Simulation broker adapter for the Trading Core."""

from __future__ import annotations
import uuid
from typing import Optional
from trading_core.models import Order, Execution, MarketPrice, OrderSide
from engine.orders import apply_slippage
from config import CRYPTO_TICKERS, SLIPPAGE_EQUITIES, SLIPPAGE_CRYPTO
from utils.time import utc_now_iso

class SimulationBrokerAdapter:
    """Simulates trade execution with slippage and fees."""

    def execute_order(self, order: Order, market_price: MarketPrice) -> Execution:
        """Transform an order into an execution based on simulated market conditions."""
        # 1. Apply slippage logic
        fill_price = apply_slippage(
            market_price.price,
            order.side.value,
            order.symbol,
            CRYPTO_TICKERS,
            SLIPPAGE_EQUITIES,
            SLIPPAGE_CRYPTO
        )
        
        notional = order.requested_quantity * fill_price
        
        # 2. Basic fee model: 0.1% or 10 bps for v1 simulation
        fees = notional * 0.001
        
        execution_id = str(uuid.uuid4())[:13]
        
        return Execution(
            execution_id=execution_id,
            order_id=order.order_id,
            instrument_id=order.instrument_id,
            symbol=order.symbol,
            side=order.side,
            quantity=order.requested_quantity,
            market_price=market_price.price,
            fill_price=fill_price,
            notional=notional,
            fees=fees,
            slippage=abs(fill_price - market_price.price) * order.requested_quantity,
            executed_at=utc_now_iso(),
            venue="simulation",
            simulation_mode=True
        )
