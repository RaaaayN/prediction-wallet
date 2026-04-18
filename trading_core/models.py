"""Canonical models for the Trading Core subsystem."""

from __future__ import annotations
from enum import Enum
from pydantic import BaseModel, Field, ConfigDict
from typing import Any, Dict, Optional


class InstrumentType(str, Enum):
    EQUITY = "equity"
    CRYPTO = "crypto"
    BOND = "bond"
    CASH = "cash"
    INDEX = "index"


class OrderSide(str, Enum):
    BUY = "buy"
    SELL = "sell"


class OrderType(str, Enum):
    MARKET = "market"
    LIMIT = "limit"


class OrderStatus(str, Enum):
    CREATED = "created"
    VALIDATED = "validated"
    SUBMITTED = "submitted"
    PARTIALLY_FILLED = "partially_filled"
    FILLED = "filled"
    REJECTED = "rejected"
    CANCELLED = "cancelled"


class MarketDataSource(str, Enum):
    YFINANCE = "yfinance"
    COINGECKO = "coingecko"
    MANUAL = "manual"
    SIMULATION = "simulation"


class MarketDataFreshness(str, Enum):
    FRESH = "fresh"
    PARTIAL = "partial"
    STALE = "stale"
    UNKNOWN = "unknown"


class Instrument(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    instrument_id: str = Field(..., description="Stable, deterministic ID (e.g. 'EQUITY:AAPL')")
    symbol: str
    name: str
    asset_class: InstrumentType
    quote_currency: str = "USD"
    exchange: Optional[str] = None
    sector: Optional[str] = None
    is_active: bool = True
    metadata_json: Dict[str, Any] = Field(default_factory=dict)


class MarketPrice(BaseModel):
    instrument_id: str
    symbol: str
    as_of: str
    price: float
    source: MarketDataSource
    freshness: MarketDataFreshness
    is_stale: bool = False
    status: str = "ok"


class Order(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    order_id: str
    cycle_id: str
    instrument_id: str
    symbol: str
    side: OrderSide
    order_type: OrderType = OrderType.MARKET
    requested_quantity: float
    status: OrderStatus = OrderStatus.CREATED
    broker_adapter: str = "simulation"
    reason: Optional[str] = None
    created_at: str
    updated_at: str


class Execution(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    execution_id: str
    order_id: str
    instrument_id: str
    symbol: str
    side: OrderSide
    quantity: float
    market_price: float
    fill_price: float
    notional: float
    fees: float = 0.0
    slippage: float = 0.0
    executed_at: str
    venue: str = "simulation"
    simulation_mode: bool = True


class Position(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    instrument_id: str
    symbol: str
    quantity: float
    avg_cost: float
    last_price: float
    market_value: float
    updated_at: str


class CashMovementType(str, Enum):
    TRADE_BUY = "trade_buy"
    TRADE_SELL = "trade_sell"
    DEPOSIT = "deposit"
    WITHDRAWAL = "withdrawal"
    FEE = "fee"
    DIVIDEND = "dividend"


class CashMovement(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    cash_movement_id: str
    cycle_id: Optional[str] = None
    order_id: Optional[str] = None
    execution_id: Optional[str] = None
    movement_type: CashMovementType
    amount: float
    currency: str = "USD"
    created_at: str
    description: Optional[str] = None
