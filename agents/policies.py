"""Deterministic policy validation for trade execution."""

from __future__ import annotations

from dataclasses import dataclass, field

from config import HEDGE_FUND_PROFILE, MAX_ORDER_FRACTION_OF_PORTFOLIO, MAX_SECTOR_CONCENTRATION, MAX_TRADES_PER_CYCLE, SECTOR_MAP, TARGET_ALLOCATION
from agents.models import PolicyEvaluation, PolicyViolation, RejectedTrade, RiskStatus, TradeDecision, TradeProposal
from engine.hedge_fund import compute_exposures
from engine.portfolio import compute_sector_exposure


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

    regime_block: bool = False
    """When True, soft-block all trades if regime is 'risk_off' or 'bear'."""

    gross_exposure_limit: float | None = None
    net_exposure_min: float | None = None
    net_exposure_max: float | None = None
    max_single_name_long: float | None = None
    max_single_name_short: float | None = None
    max_sector_gross: float | None = None
    max_sector_net: float | None = None
    conviction_floor: float = 0.0
    short_squeeze_blocklist: list[str] = field(default_factory=list)

    @classmethod
    def from_profile(cls, profile: dict) -> "PolicyConfig":
        """Build a PolicyConfig from a portfolio profile dict."""
        policy = profile.get("policy") or {}
        return cls(
            min_confidence=float(policy.get("min_confidence", 0.0)),
            stale_data_blocks=bool(policy.get("stale_data_blocks", False)),
            per_ticker_max_fraction=dict(policy.get("per_ticker_max_fraction") or {}),
            regime_block=bool(policy.get("regime_block", False)),
            gross_exposure_limit=policy.get("gross_exposure_limit"),
            net_exposure_min=policy.get("net_exposure_min"),
            net_exposure_max=policy.get("net_exposure_max"),
            max_single_name_long=policy.get("max_single_name_long"),
            max_single_name_short=policy.get("max_single_name_short"),
            max_sector_gross=policy.get("max_sector_gross"),
            max_sector_net=policy.get("max_sector_net"),
            conviction_floor=float(policy.get("conviction_floor", 0.0)),
            short_squeeze_blocklist=list(policy.get("short_squeeze_blocklist") or []),
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

    def evaluate(self, decision: TradeDecision, observation, mode: str, regime: str | None = None) -> PolicyEvaluation:
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

        if not market_block_reason and self._config.regime_block and regime in ("risk_off", "bear"):
            market_block_reason = f"Market regime '{regime}' — soft-blocked by policy."

        if market_block_reason:
            all_blocked = [
                RejectedTrade(**trade.model_dump(), rejection_reason=market_block_reason)
                for trade in decision.approved_trades
            ]
            return PolicyEvaluation(approved=True, allowed_trades=[], blocked_trades=all_blocked, violations=[])

        # ── Layer 2: Per-trade soft blocks ─────────────────────────────────────
        total_value = observation.portfolio.total_value
        current_positions = getattr(observation.portfolio, "positions", {}) or {}
        if not isinstance(current_positions, dict):
            current_positions = {}
        current_sides = getattr(observation.portfolio, "position_sides", {}) or {}
        if not isinstance(current_sides, dict):
            current_sides = {}
        current_cash = getattr(observation.portfolio, "cash", 0.0)
        if not isinstance(current_cash, (int, float)):
            current_cash = 0.0
        beta_map = {
            ticker: (HEDGE_FUND_PROFILE.get("universe", {}).get(ticker, {}) or {}).get("beta", 1.0)
            for ticker in current_positions
        }
        current_exposure = compute_exposures(
            current_positions,
            observation.market.prices,
            current_cash,
            position_sides=current_sides,
            sector_map=SECTOR_MAP,
            beta_map=beta_map,
        )
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
            if self._config.conviction_floor > 0 and getattr(trade, "conviction", decision.confidence) < self._config.conviction_floor:
                blocked.append(
                    RejectedTrade(
                        **trade.model_dump(),
                        rejection_reason=(
                            f"Trade conviction below floor "
                            f"({getattr(trade, 'conviction', decision.confidence):.2f} < {self._config.conviction_floor:.2f})."
                        ),
                    )
                )
                continue
            if getattr(trade, "side", "long") == "short" and trade.ticker in self._config.short_squeeze_blocklist:
                blocked.append(
                    RejectedTrade(
                        **trade.model_dump(),
                        rejection_reason=f"Short squeeze risk flag active for {trade.ticker}.",
                    )
                )
                continue
            # Sector concentration check: block buys that push a sector above MAX_SECTOR_CONCENTRATION.
            # Sells always pass — they reduce concentration.
            sector = SECTOR_MAP.get(trade.ticker)
            if sector and trade.action == "buy":
                current_exposure = compute_sector_exposure(
                    observation.portfolio.current_weights, SECTOR_MAP
                )
                added_weight = (price * float(trade.quantity)) / total_value if total_value > 0 else 0.0
                projected = current_exposure.get(sector, 0.0) + added_weight
                if projected > MAX_SECTOR_CONCENTRATION:
                    blocked.append(
                        RejectedTrade(
                            **trade.model_dump(),
                            rejection_reason=(
                                f"Sector concentration limit: {sector} would reach "
                                f"{projected:.1%} > {MAX_SECTOR_CONCENTRATION:.1%}."
                            ),
                        )
                    )
                    continue

            projected_positions = dict(current_positions)
            projected_sides = dict(current_sides)
            signed_quantity = float(trade.quantity)
            price = observation.market.prices.get(trade.ticker, 0.0)
            signed_value = signed_quantity * price
            trade_side = getattr(trade, "side", "long")
            if trade_side == "short":
                if trade.action == "sell":
                    projected_positions[trade.ticker] = projected_positions.get(trade.ticker, 0.0) - signed_quantity
                    projected_sides[trade.ticker] = "short"
                else:
                    projected_positions[trade.ticker] = projected_positions.get(trade.ticker, 0.0) + signed_quantity
                    if abs(projected_positions[trade.ticker]) < 1e-6:
                        projected_positions.pop(trade.ticker, None)
                        projected_sides.pop(trade.ticker, None)
            else:
                if trade.action == "buy":
                    projected_positions[trade.ticker] = projected_positions.get(trade.ticker, 0.0) + signed_quantity
                    projected_sides[trade.ticker] = "long"
                else:
                    projected_positions[trade.ticker] = projected_positions.get(trade.ticker, 0.0) - signed_quantity
                    if abs(projected_positions[trade.ticker]) < 1e-6:
                        projected_positions.pop(trade.ticker, None)
                        projected_sides.pop(trade.ticker, None)
            projected_exposure = compute_exposures(
                projected_positions,
                observation.market.prices,
                current_cash,
                position_sides=projected_sides,
                sector_map=SECTOR_MAP,
                beta_map={ticker: (HEDGE_FUND_PROFILE.get("universe", {}).get(ticker, {}) or {}).get("beta", 1.0) for ticker in projected_positions},
            )
            gross = projected_exposure.get("gross_exposure", 0.0)
            net = projected_exposure.get("net_exposure", 0.0)
            if self._config.gross_exposure_limit is not None and gross > self._config.gross_exposure_limit:
                blocked.append(
                    RejectedTrade(
                        **trade.model_dump(),
                        rejection_reason=(
                            f"Projected gross exposure {gross:.1%} exceeds limit "
                            f"{self._config.gross_exposure_limit:.1%}."
                        ),
                    )
                )
                continue
            if self._config.net_exposure_min is not None and net < self._config.net_exposure_min:
                blocked.append(
                    RejectedTrade(
                        **trade.model_dump(),
                        rejection_reason=(
                            f"Projected net exposure {net:.1%} below floor "
                            f"{self._config.net_exposure_min:.1%}."
                        ),
                    )
                )
                continue
            if self._config.net_exposure_max is not None and net > self._config.net_exposure_max:
                blocked.append(
                    RejectedTrade(
                        **trade.model_dump(),
                        rejection_reason=(
                            f"Projected net exposure {net:.1%} exceeds cap "
                            f"{self._config.net_exposure_max:.1%}."
                        ),
                    )
                )
                continue
            name_conc = projected_exposure.get("single_name_concentration", {}).get(trade.ticker, 0.0)
            if trade_side == "short" and self._config.max_single_name_short is not None and name_conc > self._config.max_single_name_short:
                blocked.append(
                    RejectedTrade(
                        **trade.model_dump(),
                        rejection_reason=(
                            f"Projected short concentration {name_conc:.1%} exceeds cap "
                            f"{self._config.max_single_name_short:.1%}."
                        ),
                    )
                )
                continue
            if trade_side != "short" and self._config.max_single_name_long is not None and name_conc > self._config.max_single_name_long:
                blocked.append(
                    RejectedTrade(
                        **trade.model_dump(),
                        rejection_reason=(
                            f"Projected long concentration {name_conc:.1%} exceeds cap "
                            f"{self._config.max_single_name_long:.1%}."
                        ),
                    )
                )
                continue
            if self._config.max_sector_gross is not None:
                projected_sector_gross = projected_exposure.get("sector_gross", {}).get(sector or "other", 0.0)
                if projected_sector_gross > self._config.max_sector_gross:
                    blocked.append(
                        RejectedTrade(
                            **trade.model_dump(),
                            rejection_reason=(
                                f"Projected sector gross {sector or 'other'} {projected_sector_gross:.1%} exceeds cap "
                                f"{self._config.max_sector_gross:.1%}."
                            ),
                        )
                    )
                    continue
            if self._config.max_sector_net is not None:
                projected_sector_net = abs(projected_exposure.get("sector_net", {}).get(sector or "other", 0.0))
                if projected_sector_net > self._config.max_sector_net:
                    blocked.append(
                        RejectedTrade(
                            **trade.model_dump(),
                            rejection_reason=(
                                f"Projected sector net {sector or 'other'} {projected_sector_net:.1%} exceeds cap "
                                f"{self._config.max_sector_net:.1%}."
                            ),
                        )
                    )
                    continue
            allowed.append(trade)
            current_positions = projected_positions
            current_sides = projected_sides
            current_exposure = projected_exposure

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
