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


def compute_inverse_vol_weights(
    volatilities: dict[str, float],
    target: dict[str, float],
    blend: float = 1.0,
) -> dict[str, float]:
    """Compute inverse-volatility weighted target allocation.

    Each asset's weight is proportional to 1/volatility so that higher-vol
    assets receive less capital. The blend parameter controls the mix between
    pure inverse-vol and the original fixed target allocation.

    Args:
        volatilities: ticker → annualized 30-day volatility (e.g. 0.25 = 25%)
        target: base fixed-weight target — defines the ticker universe and is
                used as the fallback endpoint when blend < 1.0
        blend: interpolation between fixed and inverse-vol weights.
               0.0 → pure fixed target (no change); 1.0 → pure inverse-vol.
               Values in between blend linearly.

    Returns:
        ticker → adjusted weight (sums to 1.0). Only tickers in target are returned.

    Notes:
        Tickers missing from volatilities or with vol ≤ 0 fall back to a 20%
        reference vol (typical equity baseline) to avoid division by zero.
    """
    _REF_VOL_FALLBACK = 0.20
    inv_vols = {}
    for ticker in target:
        vol = volatilities.get(ticker)
        inv_vols[ticker] = 1.0 / (vol if vol and vol > 0 else _REF_VOL_FALLBACK)
    total_inv = sum(inv_vols.values())
    if total_inv <= 0:
        return dict(target)
    inv_vol_weights = {t: iv / total_inv for t, iv in inv_vols.items()}
    if blend >= 1.0:
        return inv_vol_weights
    if blend <= 0.0:
        return dict(target)
    return {
        t: blend * inv_vol_weights[t] + (1.0 - blend) * target.get(t, 0.0)
        for t in target
    }


def compute_sector_exposure(
    weights: dict[str, float],
    sector_map: dict[str, str],
) -> dict[str, float]:
    """Aggregate portfolio weights by sector.

    Args:
        weights: ticker → portfolio weight
        sector_map: ticker → sector name

    Returns:
        sector → total weight. Tickers absent from sector_map are grouped under "other".
    """
    exposure: dict[str, float] = {}
    for ticker, weight in weights.items():
        sector = sector_map.get(ticker, "other")
        exposure[sector] = exposure.get(sector, 0.0) + weight
    return exposure


def concentration_score(sector_exposure: dict[str, float]) -> float:
    """Maximum single-sector weight — simple concentration metric.

    Returns:
        Max sector weight as a fraction (0.0 if no sectors).
        Lower is better; 1.0 means 100% in one sector.
    """
    return max(sector_exposure.values(), default=0.0)


def compute_pnl(current_value: float, initial_capital: float) -> dict:
    """Compute gross P&L from initial capital.

    Returns:
        dict with keys: pnl_dollars, pnl_pct
    """
    pnl_dollars = current_value - initial_capital
    pnl_pct = pnl_dollars / initial_capital if initial_capital > 0 else 0.0
    return {"pnl_dollars": pnl_dollars, "pnl_pct": pnl_pct}
