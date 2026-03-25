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
    # Confidence scoring fields (#11)
    confidence: float = Field(
        default=0.5,
        ge=0.0,
        le=1.0,
        description=(
            "Self-reported decision confidence on a 0–1 scale. "
            "1.0 = very high confidence (strong signal, fresh data, clear drift). "
            "0.5 = neutral / uncertain. "
            "0.0 = very low confidence (conflicting signals, stale data, noisy market). "
            "Use as a soft signal: lower confidence should not hard-block execution."
        ),
    )
    data_freshness: str = Field(
        default="unknown",
        description=(
            "Freshness of the market data used for this decision. "
            "Set deterministically from MarketDataStatus.refreshed_at timestamps. "
            "Values: 'fresh' (all tickers < 24h), 'partial' (some stale), "
            "'stale' (all > 24h), 'unknown' (no refresh data)."
        ),
    )


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
    # Per-trade explainability fields
    weight_before: float = 0.0   # portfolio weight of this ticker before execution
    target_weight: float = 0.0   # target allocation for this ticker
    drift_before: float = 0.0    # weight_before − target_weight
    slippage_pct: float = 0.0    # (fill_price − market_price) / market_price, signed
    notional: float = 0.0        # abs(quantity × fill_price) in portfolio currency


class CycleAudit(BaseModel):
    cycle_id: str
    timestamp: str
    strategy_name: str
    agent_backend: str
    execution_mode: str
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
