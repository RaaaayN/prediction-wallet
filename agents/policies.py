"""Deterministic policy validation for trade execution."""

from __future__ import annotations

from config import MAX_ORDER_FRACTION_OF_PORTFOLIO, MAX_TRADES_PER_CYCLE, TARGET_ALLOCATION
from agents.models import PolicyEvaluation, PolicyViolation, RejectedTrade, RiskStatus, TradeDecision, TradeProposal


class ExecutionPolicyEngine:
    """Validate structured trade decisions before execution."""

    def evaluate(self, decision: TradeDecision, observation, mode: str) -> PolicyEvaluation:
        hard_violations: list[PolicyViolation] = []
        allowed: list[TradeProposal] = []
        blocked: list[RejectedTrade] = []

        plan_index = {
            (trade.action, trade.ticker, round(float(trade.quantity), 6)): trade
            for trade in observation.trade_plan
        }

        # Hard violations: abort entire cycle, no trade evaluation
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

        # Soft blocks: per-trade evaluation — blocked trades do not prevent other trades from executing
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
