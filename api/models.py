"""Explicit Pydantic models for API response contracts."""

from __future__ import annotations
from pydantic import BaseModel, Field
from typing import Any

class ConfigResponse(BaseModel):
    ai_provider: str
    agent_backend: str
    execution_mode: str
    target_allocation: dict[str, float]
    hedge_fund_enabled: bool

class PortfolioResponse(BaseModel):
    cash: float
    total_value: float
    peak_value: float = 0.0
    pnl_dollars: float
    pnl_pct: float
    positions: dict[str, float]
    history: list[dict[str, Any]] = Field(default_factory=list)
    current_weights: dict[str, float] = Field(default_factory=dict)
    target_weights: dict[str, float] = Field(default_factory=dict)
    weight_deviation: dict[str, float] = Field(default_factory=dict)
    last_rebalanced: str | None = None

class PositionRow(BaseModel):
    ticker: str
    quantity: float
    price: float
    value: float
    weight: float
    target_weight: float
    drift: float
    side: str
    idea_id: str | None = None
    gross_exposure: float
    net_exposure: float

class MarketStatusResponse(BaseModel):
    tickers: list[str]
    last_refresh: dict[str, str | None]

class RunResponse(BaseModel):
    step: str
    status: str
    cycle_id: str | None = None

class OnboardingStatusResponse(BaseModel):
    needs_onboarding: bool
    profile: str
    positions_count: int

# Trading Core v1
class InstrumentRow(BaseModel):
    instrument_id: str
    symbol: str
    name: str
    asset_class: str
    sector: str | None = None
    is_active: bool

class TradingCoreOrderRow(BaseModel):
    order_id: str
    cycle_id: str
    symbol: str
    side: str
    requested_quantity: float
    status: str
    created_at: str

class TradingCoreExecutionRow(BaseModel):
    execution_id: str
    order_id: str
    symbol: str
    side: str
    quantity: float
    market_price: float
    fill_price: float
    notional: float
    fees: float
    executed_at: str

class TradingCorePositionRow(BaseModel):
    instrument_id: str
    symbol: str
    quantity: float
    avg_cost: float
    last_price: float
    market_value: float
    updated_at: str

class CashMovementRow(BaseModel):
    cash_movement_id: str
    cycle_id: str | None = None
    movement_type: str
    amount: float
    created_at: str
    description: str | None = None


class SettingsResponse(BaseModel):
    ai_provider: str
    gemini_model: str
    claude_model: str
    has_gemini_key: bool
    has_anthropic_key: bool
    execution_mode: str
    agent_backend: str
    trading_core_enabled: bool
    portfolio_profile: str
    max_trades_per_cycle: int
    max_order_fraction_of_portfolio: float
    benchmark_ticker: str
    market_data_ttl_seconds: int
    risk_free_rate: float
    # Profile specific
    drift_threshold: float
    kill_switch_drawdown: float


class SettingsUpdateRequest(BaseModel):
    ai_provider: str | None = None
    gemini_model: str | None = None
    claude_model: str | None = None
    gemini_api_key: str | None = None
    anthropic_api_key: str | None = None
    execution_mode: str | None = None
    agent_backend: str | None = None
    trading_core_enabled: bool | None = None
    portfolio_profile: str | None = None
    max_trades_per_cycle: int | None = None
    max_order_fraction_of_portfolio: float | None = None
    benchmark_ticker: str | None = None
    market_data_ttl_seconds: int | None = None
    risk_free_rate: float | None = None
    drift_threshold: float | None = None
    kill_switch_drawdown: float | None = None
