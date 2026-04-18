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
    pnl_dollars: float
    pnl_pct: float
    positions: dict[str, float]
    history: list[dict[str, Any]] = Field(default_factory=list)
    current_weights: dict[str, float] = Field(default_factory=dict)
    weight_deviation: dict[str, float] = Field(default_factory=dict)

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
