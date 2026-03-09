"""Engine package — pure deterministic logic, zero LLM imports."""

from engine.portfolio import (
    compute_weights,
    compute_drift,
    compute_portfolio_value,
    compute_pnl,
)
from engine.orders import (
    generate_rebalance_orders,
    apply_slippage,
    estimate_transaction_cost,
)
from engine.risk import compute_drawdown, check_kill_switch
from engine.performance import (
    cumulative_return,
    annualized_return,
    rolling_volatility,
    sharpe_ratio,
    max_drawdown,
    turnover,
    transaction_costs_total,
    tracking_error,
    hit_ratio,
    parametric_var,
    conditional_var,
    performance_report,
)

__all__ = [
    "compute_weights",
    "compute_drift",
    "compute_portfolio_value",
    "compute_pnl",
    "generate_rebalance_orders",
    "apply_slippage",
    "estimate_transaction_cost",
    "compute_drawdown",
    "check_kill_switch",
    "cumulative_return",
    "annualized_return",
    "rolling_volatility",
    "sharpe_ratio",
    "max_drawdown",
    "turnover",
    "transaction_costs_total",
    "tracking_error",
    "hit_ratio",
    "parametric_var",
    "conditional_var",
    "performance_report",
]
