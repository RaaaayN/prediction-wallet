"""Deterministic policy validation for trade execution."""

from __future__ import annotations

from dataclasses import dataclass, field

from config import MAX_ORDER_FRACTION_OF_PORTFOLIO, MAX_TRADES_PER_CYCLE, TARGET_ALLOCATION
from agents.models import PolicyEvaluation, PolicyViolation, RejectedTrade, RiskStatus, TradeDecision, TradeProposal


@dataclass
class PolicyConfig:
    """Hierarchical policy rules loaded from the active portfolio profile.

    Layers:
      1. Market context (decision-level soft blocks): confidence threshold, stale data guard.
      2. Per-ticker notional cap: stricter override of the global MAX_ORDER_FRACTION_OF_PORTFOLIO.

    All fields are optional with neutral defaults so that an unconfigured engine behaves
    identically to the previous flat engine.
    """

    # Layer 1 — market context rules
    min_confidence: float = 0.0
    """Soft-block all trades when decision.confidence < min_confidence. 0.0 = disabled."""

    stale_data_blocks: bool = False
    """When True, data_freshness == 'stale' soft-blocks all trades in the decision."""

    # Layer 2 — per-ticker overrides (applied after the global notional cap passes)
    per_ticker_max_fraction: dict[str, float] = field(default_factory=dict)
    """Per-ticker notional cap as a fraction of portfolio value.
    Only applies if the value is stricter than MAX_ORDER_FRACTION_OF_PORTFOLIO.
    Example: {"BTC-USD": 0.15, "ETH-USD": 0.10}
    """

    @classmethod
    def from_profile(cls, profile: dict) -> "PolicyConfig":
        """Build a PolicyConfig from a portfolio profile dict."""
        policy = profile.get("policy") or {}
        return cls(
            min_confidence=float(policy.get("min_confidence", 0.0)),
            stale_data_blocks=bool(policy.get("stale_data_blocks", False)),
            per_ticker_max_fraction=dict(policy.get("per_ticker_max_fraction") or {}),
        )


class ExecutionPolicyEngine:
    """Validate structured trade decisions before execution.

    Policy layers (evaluated in order):
      0. Hard violations  — abort entire cycle (approved=False)
      1. Market context   — block all trades when decision quality is insufficient (approved=True)
      2. Per-trade checks — block individual trades that violate specific rules (approved=True)
    """

    def __init__(self, config: PolicyConfig | None = None) -> None:
        self._config = config or PolicyConfig()

    def evaluate(self, decision: TradeDecision, observation, mode: str) -> PolicyEvaluation:
        hard_violations: list[PolicyViolation] = []
        allowed: list[TradeProposal] = []
        blocked: list[RejectedTrade] = []

        plan_index = {
            (trade.action, trade.ticker, round(float(trade.quantity), 6)): trade
            for trade in observation.trade_plan
        }

        # ── Layer 0: Hard violations — abort entire cycle ──────────────────────
        if observation.risk.kill_switch_active:
            hard_violations.append(PolicyViolation(code="kill_switch_active", message="Kill switch is active."))
        if mode == "live":
            hard_violations.append(PolicyViolation(code="live_blocked", message="Live mode is not enabled."))
        if len(decision.approved_trades) > MAX_TRADES_PER_CYCLE:
            hard_violations.append(
                PolicyViolation(
                    code="too_many_trades",
                    message=f"Decision exceeds max trades per cycle ({MAX_TRADES_PER_CYCLE}).",
                )
            )

        if hard_violations:
            return PolicyEvaluation(approved=False, allowed_trades=[], blocked_trades=[], violations=hard_violations)

        # ── Layer 1: Market context soft blocks — apply to all trades ──────────
        market_block_reason: str | None = None
        if self._config.min_confidence > 0.0 and decision.confidence < self._config.min_confidence:
            market_block_reason = (
                f"Decision confidence too low "
                f"({decision.confidence:.2f} < {self._config.min_confidence:.2f})."
            )
        elif self._config.stale_data_blocks and getattr(decision, "data_freshness", "unknown") == "stale":
            market_block_reason = "Market data is stale; all trades soft-blocked by policy."

        if market_block_reason:
            all_blocked = [
                RejectedTrade(**trade.model_dump(), rejection_reason=market_block_reason)
                for trade in decision.approved_trades
            ]
            return PolicyEvaluation(approved=True, allowed_trades=[], blocked_trades=all_blocked, violations=[])

        # ── Layer 2: Per-trade soft blocks ─────────────────────────────────────
        total_value = observation.portfolio.total_value
        for trade in decision.approved_trades:
            key = (trade.action, trade.ticker, round(float(trade.quantity), 6))
            if trade.ticker not in TARGET_ALLOCATION:
                blocked.append(
                    RejectedTrade(**trade.model_dump(), rejection_reason="Ticker is not in the allowed universe.")
                )
                continue
            if key not in plan_index:
                blocked.append(
                    RejectedTrade(**trade.model_dump(), rejection_reason="Trade is not in the deterministic trade plan.")
                )
                continue
            price = observation.market.prices.get(trade.ticker, 0.0)
            if price <= 0:
                blocked.append(
                    RejectedTrade(**trade.model_dump(), rejection_reason="Missing or invalid market price.")
                )
                continue
            notional_fraction = (price * float(trade.quantity)) / total_value if total_value > 0 else 0
            if notional_fraction > MAX_ORDER_FRACTION_OF_PORTFOLIO:
                blocked.append(
                    RejectedTrade(
                        **trade.model_dump(),
                        rejection_reason=f"Trade exceeds notional cap ({MAX_ORDER_FRACTION_OF_PORTFOLIO:.0%}).",
                    )
                )
                continue
            # Per-ticker cap (profile override — checked only if global cap passes)
            ticker_cap = self._config.per_ticker_max_fraction.get(trade.ticker)
            if ticker_cap is not None and notional_fraction > ticker_cap:
                blocked.append(
                    RejectedTrade(
                        **trade.model_dump(),
                        rejection_reason=(
                            f"Trade exceeds per-ticker notional cap for {trade.ticker} ({ticker_cap:.0%})."
                        ),
                    )
                )
                continue
            allowed.append(trade)

        return PolicyEvaluation(approved=True, allowed_trades=allowed, blocked_trades=blocked, violations=[])


def build_risk_status(drawdown: float, kill_switch_active: bool, execution_mode: str, mcp_required: bool) -> RiskStatus:
    return RiskStatus(
        kill_switch_active=kill_switch_active,
        drawdown=drawdown,
        max_trades_per_cycle=MAX_TRADES_PER_CYCLE,
        max_order_fraction_of_portfolio=MAX_ORDER_FRACTION_OF_PORTFOLIO,
        allowed_tickers=sorted(TARGET_ALLOCATION.keys()),
        execution_mode=execution_mode,
        mcp_required=mcp_required,
    )
