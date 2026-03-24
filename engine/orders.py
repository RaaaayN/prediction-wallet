"""Order generation and slippage logic — no I/O, no LLM."""

from __future__ import annotations


def generate_rebalance_orders(
    portfolio: dict,
    prices: dict[str, float],
    target: dict[str, float],
    min_qty: float = 0.001,
    min_drift: float = 0.0,
) -> list[dict]:
    """Generate buy/sell orders to restore target weights.

    Args:
        portfolio: dict with 'positions' (ticker→qty) and 'cash' keys
        prices: ticker → current price
        target: ticker → target weight
        min_qty: minimum order quantity to include
        min_drift: skip order if |current_weight - target_weight| <= min_drift (tolerance band)

    Returns:
        List of {"action", "ticker", "quantity", "reason"}
    """
    positions = portfolio.get("positions", {})
    cash = portfolio.get("cash", 0.0)

    market_values = {ticker: qty * prices.get(ticker, 0.0) for ticker, qty in positions.items()}
    total = sum(market_values.values()) + cash
    if total <= 0:
        return []

    orders = []
    for ticker, target_weight in target.items():
        current_value = market_values.get(ticker, 0.0)
        current_weight = current_value / total
        if min_drift > 0.0 and abs(current_weight - target_weight) <= min_drift:
            continue
        target_value = target_weight * total
        delta_value = target_value - current_value
        price = prices.get(ticker, 0.0)
        if price <= 0:
            continue
        quantity = abs(delta_value) / price
        if quantity < min_qty:
            continue
        action = "buy" if delta_value > 0 else "sell"
        reason = (
            f"Rebalance {ticker}: current weight {current_weight:.1%} → "
            f"target {target_weight:.1%} (delta ${delta_value:+,.0f})"
        )
        orders.append({
            "action": action,
            "ticker": ticker,
            "quantity": round(quantity, 6),
            "reason": reason,
        })

    return orders


def apply_slippage(
    price: float,
    action: str,
    ticker: str,
    crypto_tickers: set[str],
    slippage_eq: float,
    slippage_crypto: float,
) -> float:
    """Return fill price after applying slippage model.

    Args:
        price: market price
        action: "buy" or "sell"
        ticker: asset ticker
        crypto_tickers: set of crypto ticker symbols
        slippage_eq: slippage rate for equities/ETFs
        slippage_crypto: slippage rate for crypto

    Returns:
        Adjusted fill price
    """
    rate = slippage_crypto if ticker in crypto_tickers else slippage_eq
    if action == "buy":
        return price * (1.0 + rate)
    return price * (1.0 - rate)


def estimate_transaction_cost(
    orders: list[dict],
    prices: dict[str, float],
    crypto_tickers: set[str],
    slippage_eq: float,
    slippage_crypto: float,
) -> float:
    """Estimate total transaction cost (slippage) for a list of orders.

    Args:
        orders: list of {"action", "ticker", "quantity"} dicts
        prices: ticker → price
        crypto_tickers: set of crypto tickers
        slippage_eq: equity slippage rate
        slippage_crypto: crypto slippage rate

    Returns:
        Total estimated slippage cost in dollars
    """
    total_cost = 0.0
    for order in orders:
        ticker = order["ticker"]
        quantity = order["quantity"]
        price = prices.get(ticker, 0.0)
        if price <= 0:
            continue
        rate = slippage_crypto if ticker in crypto_tickers else slippage_eq
        total_cost += price * quantity * rate
    return total_cost
