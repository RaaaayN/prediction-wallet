"""Pure portfolio computation functions — no I/O, no LLM."""

from __future__ import annotations


def compute_weights(positions: dict[str, float], prices: dict[str, float], cash: float = 0.0) -> dict[str, float]:
    """Compute current portfolio weights from positions and prices.

    Args:
        positions: ticker → quantity
        prices: ticker → price
        cash: uninvested cash balance

    Returns:
        ticker → weight (fraction of total portfolio value)
    """
    market_values = {ticker: qty * prices.get(ticker, 0.0) for ticker, qty in positions.items()}
    total = sum(market_values.values()) + cash
    if total <= 0:
        return {}
    return {ticker: mv / total for ticker, mv in market_values.items()}


def compute_drift(current_weights: dict[str, float], target: dict[str, float]) -> dict[str, float]:
    """Compute signed drift from target allocation.

    Returns:
        ticker → (current_weight - target_weight), positive = overweight
    """
    all_tickers = set(current_weights) | set(target)
    return {
        ticker: current_weights.get(ticker, 0.0) - target.get(ticker, 0.0)
        for ticker in all_tickers
    }


def compute_portfolio_value(positions: dict[str, float], cash: float, prices: dict[str, float]) -> float:
    """Compute total portfolio market value.

    Args:
        positions: ticker → quantity
        cash: uninvested cash
        prices: ticker → price

    Returns:
        Total portfolio value in dollars
    """
    return cash + sum(qty * prices.get(ticker, 0.0) for ticker, qty in positions.items())


def compute_pnl(current_value: float, initial_capital: float) -> dict:
    """Compute gross P&L from initial capital.

    Returns:
        dict with keys: pnl_dollars, pnl_pct
    """
    pnl_dollars = current_value - initial_capital
    pnl_pct = pnl_dollars / initial_capital if initial_capital > 0 else 0.0
    return {"pnl_dollars": pnl_dollars, "pnl_pct": pnl_pct}
