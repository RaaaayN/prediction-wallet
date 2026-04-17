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
    position_sides: dict[str, str] = Field(default_factory=dict)
    average_costs: dict[str, float] = Field(default_factory=dict)
    cash: float
    peak_value: float
    total_value: float
    current_weights: dict[str, float]
    target_weights: dict[str, float]
    weight_deviation: dict[str, float]
    pnl_dollars: float
    pnl_pct: float
    last_rebalanced: str | None = None


class IdeaProposal(BaseModel):
    idea_id: str
    ticker: str
    side: str
    thesis: str
    catalyst: str
    time_horizon: str
    conviction: float = Field(ge=0.0, le=1.0)
    upside_case: str = ""
    downside_case: str = ""
    invalidation_rule: str
    status: str
    sleeve: str = "core_longs"
    edge_source: str = ""
    why_now: str = ""
    key_risk: str = ""
    supporting_signals: list[str] = Field(default_factory=list)
    evidence_quality: str = "medium"
    review_status: str = "approved"
    origin_cycle_id: str | None = None
    llm_generated: bool = False


class IdeaBookEntry(IdeaProposal):
    source: str = "profile_seed"
    crowded_score: float = 0.0
    short_squeeze_risk: bool = False
    last_updated: str | None = None


class PositionIntent(BaseModel):
    ticker: str
    side: str
    target_weight: float = 0.0
    conviction: float = Field(default=0.5, ge=0.0, le=1.0)
    sizing_reason: str = ""
    sleeve: str = "core_longs"
    idea_id: str | None = None


class BookConstructionDecision(BaseModel):
    cycle_id: str
    summary: str
    gross_exposure: float = 0.0
    net_exposure: float = 0.0
    intents: list[PositionIntent] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)


class ExposureSnapshot(BaseModel):
    gross_exposure: float = 0.0
    net_exposure: float = 0.0
    long_exposure: float = 0.0
    short_exposure: float = 0.0
    leverage_used: float = 0.0
    beta_adjusted_exposure: float = 0.0
    factor_exposure: dict[str, float] = Field(default_factory=dict)
    sector_gross: dict[str, float] = Field(default_factory=dict)
    sector_net: dict[str, float] = Field(default_factory=dict)
    single_name_concentration: dict[str, float] = Field(default_factory=dict)
    top5_concentration: float = 0.0


class BookRiskSnapshot(BaseModel):
    breaches: list[str] = Field(default_factory=list)
    near_breaches: list[str] = Field(default_factory=list)
    crowded_names: list[str] = Field(default_factory=list)
    short_squeeze_names: list[str] = Field(default_factory=list)
    exposure: ExposureSnapshot = Field(default_factory=ExposureSnapshot)


class PnLAttribution(BaseModel):
    realized_total: float = 0.0
    unrealized_total: float = 0.0
    by_side: dict[str, float] = Field(default_factory=dict)
    by_sector: dict[str, float] = Field(default_factory=dict)
    by_idea: dict[str, float] = Field(default_factory=dict)
    by_sleeve: dict[str, float] = Field(default_factory=dict)


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
    side: str = "long"
    idea_id: str | None = None
    conviction: float = Field(default=0.5, ge=0.0, le=1.0)
    sleeve: str = "core_longs"


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
    side: str = "long"
    idea_id: str | None = None
    sleeve: str = "core_longs"
    # Per-trade explainability fields
    weight_before: float = 0.0   # portfolio weight of this ticker before execution
    target_weight: float = 0.0   # target allocation for this ticker
    drift_before: float = 0.0    # weight_before − target_weight
    slippage_pct: float = 0.0    # (fill_price − market_price) / market_price, signed
    notional: float = 0.0        # abs(quantity × fill_price) in portfolio currency
    exposure_before: float = 0.0
    exposure_after: float = 0.0
    gross_impact: float = 0.0
    net_impact: float = 0.0


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
    ideas: list[IdeaBookEntry] = Field(default_factory=list)
    book_construction: BookConstructionDecision | None = None
    exposures: ExposureSnapshot = Field(default_factory=ExposureSnapshot)
    book_risk: BookRiskSnapshot = Field(default_factory=BookRiskSnapshot)
    pnl_attribution: PnLAttribution = Field(default_factory=PnLAttribution)
    observability: dict = Field(default_factory=dict)
    errors: list[str] = Field(default_factory=list)


class CycleObservation(BaseModel):
    cycle_id: str
    strategy_name: str
    portfolio: PortfolioSnapshot
    market: MarketSnapshot
    risk: RiskStatus
    ideas: list[IdeaBookEntry] = Field(default_factory=list)
    research: list[IdeaProposal] = Field(default_factory=list)
    construction: BookConstructionDecision | None = None
    exposures: ExposureSnapshot = Field(default_factory=ExposureSnapshot)
    book_risk: BookRiskSnapshot = Field(default_factory=BookRiskSnapshot)
    trade_plan: list[TradeProposal] = Field(default_factory=list)
    observability: dict = Field(default_factory=dict)
