"""Order generation and slippage logic — no I/O, no LLM."""

from __future__ import annotations


def generate_rebalance_orders(
    portfolio: dict,
    prices: dict[str, float],
    target: dict[str, float],
    min_qty: float = 0.001,
    min_drift: float = 0.0,
    min_notional: float = 10.0,
) -> list[dict]:
    """Generate buy/sell orders to restore target weights.

    Args:
        portfolio: dict with 'positions' (ticker→qty) and 'cash' keys
        prices: ticker → current price
        target: ticker → target weight
        min_qty: minimum order quantity to include
        min_drift: skip order if |current_weight - target_weight| <= min_drift (tolerance band)
        min_notional: skip order if quantity × price < min_notional in dollars (default $10)

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
        if quantity * price < min_notional:
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
    volatility: float | None = None,
    order_notional: float | None = None,
) -> float:
    """Return fill price after applying a vol-adjusted, size-adjusted slippage model.

    The base rate is scaled by current volatility relative to a reference vol, then
    a small linear market-impact term is added for order size. Both adjustments are
    optional — omitting them reproduces the original flat-rate behaviour.

    Args:
        price: market price
        action: "buy" or "sell"
        ticker: asset ticker
        crypto_tickers: set of crypto ticker symbols
        slippage_eq: base slippage rate for equities/ETFs
        slippage_crypto: base slippage rate for crypto
        volatility: annualised 30-day vol for this ticker (e.g. 0.25 = 25%).
            When provided, the base rate is scaled by ``vol / ref_vol``,
            clamped to [0.5×, 3.0×] to avoid extremes.
        order_notional: trade size in dollars. When provided, adds a linear
            market-impact term of 1 bp per $10 000 of notional.

    Returns:
        Adjusted fill price
    """
    # Reference vols: "normal" regime for each asset class
    _REF_VOL_EQUITY = 0.20   # 20% annualised — typical S&P 500 constituent
    _REF_VOL_CRYPTO = 0.65   # 65% annualised — typical BTC/ETH

    base_rate = slippage_crypto if ticker in crypto_tickers else slippage_eq
    ref_vol = _REF_VOL_CRYPTO if ticker in crypto_tickers else _REF_VOL_EQUITY

    rate = base_rate

    # Vol adjustment: widen/tighten spread proportionally to volatility regime
    if volatility is not None and volatility > 0 and ref_vol > 0:
        vol_scalar = max(0.5, min(3.0, volatility / ref_vol))
        rate = base_rate * vol_scalar

    # Size adjustment: linear market impact (1 bp per $10 000 of order notional)
    if order_notional is not None and order_notional > 0:
        rate += (order_notional / 10_000) * 0.0001

    if action == "buy":
        return price * (1.0 + rate)
    return price * (1.0 - rate)


def estimate_transaction_cost(
    orders: list[dict],
    prices: dict[str, float],
    crypto_tickers: set[str],
    slippage_eq: float,
    slippage_crypto: float,
    volatilities: dict[str, float] | None = None,
) -> float:
    """Estimate total transaction cost (slippage) for a list of orders.

    Args:
        orders: list of {"action", "ticker", "quantity"} dicts
        prices: ticker → price
        crypto_tickers: set of crypto tickers
        slippage_eq: equity base slippage rate
        slippage_crypto: crypto base slippage rate
        volatilities: optional ticker → annualised 30-day vol. When provided,
            each order's cost uses the vol-adjusted + size-adjusted model.

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
        notional = price * quantity
        vol = volatilities.get(ticker) if volatilities else None
        fill = apply_slippage(
            price, order.get("action", "buy"), ticker,
            crypto_tickers, slippage_eq, slippage_crypto,
            volatility=vol, order_notional=notional,
        )
        total_cost += abs(fill - price) * quantity
    return total_cost
