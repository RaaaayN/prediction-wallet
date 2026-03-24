"""Typed domain models for the portfolio agent cycle."""

from __future__ import annotations

from pydantic import BaseModel, Field, ConfigDict


class TickerMetrics(BaseModel):
    model_config = ConfigDict(extra="ignore")

    last_price: float = 0.0
    volatility_30d: float = 0.0
    ytd_return: float = 0.0
    sharpe: float = 0.0


class MarketDataStatus(BaseModel):
    ticker: str
    refreshed_at: str | None = None
    success: bool = False
    error: str | None = None


class PortfolioSnapshot(BaseModel):
    positions: dict[str, float]
    cash: float
    peak_value: float
    total_value: float
    current_weights: dict[str, float]
    target_weights: dict[str, float]
    weight_deviation: dict[str, float]
    pnl_dollars: float
    pnl_pct: float
    last_rebalanced: str | None = None


class MarketSnapshot(BaseModel):
    prices: dict[str, float]
    metrics: dict[str, TickerMetrics] = Field(default_factory=dict)
    refresh_status: list[MarketDataStatus] = Field(default_factory=list)


class RiskStatus(BaseModel):
    kill_switch_active: bool
    drawdown: float
    max_trades_per_cycle: int
    max_order_fraction_of_portfolio: float
    allowed_tickers: list[str]
    execution_mode: str
    mcp_required: bool = False


class TradeProposal(BaseModel):
    action: str
    ticker: str
    quantity: float
    reason: str


class RejectedTrade(BaseModel):
    action: str
    ticker: str
    quantity: float
    reason: str
    rejection_reason: str


class TradeDecision(BaseModel):
    cycle_id: str
    summary: str
    market_outlook: str
    rationale: str
    rebalance_needed: bool
    approved_trades: list[TradeProposal] = Field(default_factory=list)
    rejected_trades: list[RejectedTrade] = Field(default_factory=list)
    risk_flags: list[str] = Field(default_factory=list)


class PolicyViolation(BaseModel):
    code: str
    message: str
    ticker: str | None = None


class PolicyEvaluation(BaseModel):
    approved: bool
    allowed_trades: list[TradeProposal] = Field(default_factory=list)
    blocked_trades: list[RejectedTrade] = Field(default_factory=list)
    violations: list[PolicyViolation] = Field(default_factory=list)


class ExecutionResult(BaseModel):
    trade_id: str = ""
    action: str
    ticker: str
    quantity: float
    market_price: float
    fill_price: float
    cost: float
    timestamp: str
    reason: str
    success: bool
    error: str = ""


class CycleAudit(BaseModel):
    cycle_id: str
    timestamp: str
    strategy_name: str
    agent_backend: str
    execution_mode: str
    mcp_profile: str
    portfolio: PortfolioSnapshot
    market: MarketSnapshot
    risk: RiskStatus
    trade_plan: list[TradeProposal] = Field(default_factory=list)
    decision: TradeDecision
    policy: PolicyEvaluation
    executions: list[ExecutionResult] = Field(default_factory=list)
    report_path: str | None = None
    observability: dict = Field(default_factory=dict)
    errors: list[str] = Field(default_factory=list)


class CycleObservation(BaseModel):
    cycle_id: str
    strategy_name: str
    portfolio: PortfolioSnapshot
    market: MarketSnapshot
    risk: RiskStatus
    trade_plan: list[TradeProposal] = Field(default_factory=list)
    observability: dict = Field(default_factory=dict)
