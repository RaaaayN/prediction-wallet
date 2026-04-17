"""Pure helpers to project portfolio state after a proposed trade."""

from __future__ import annotations

from engine.hedge_fund import compute_exposures


MIN_POSITION_QUANTITY = 1e-6


def project_trade_state(
    portfolio: dict,
    trade: dict,
    prices: dict[str, float],
    *,
    sector_map: dict[str, str] | None = None,
    beta_map: dict[str, float] | None = None,
) -> dict:
    positions = dict(portfolio.get("positions") or {})
    position_sides = dict(portfolio.get("position_sides") or {})
    cash = float(portfolio.get("cash", 0.0) or 0.0)

    ticker = trade.get("ticker", "")
    action = trade.get("action", "")
    side = trade.get("side", "long")
    quantity = float(trade.get("quantity", 0.0) or 0.0)
    price = float(prices.get(ticker, 0.0) or 0.0)

    if not ticker or quantity <= 0 or price <= 0:
        exposure = compute_exposures(
            positions,
            prices,
            cash,
            position_sides=position_sides,
            sector_map=sector_map,
            beta_map=beta_map,
        )
        return {
            "positions": positions,
            "position_sides": position_sides,
            "cash": cash,
            "exposure": exposure,
        }

    held = float(positions.get(ticker, 0.0) or 0.0)
    gross = price * quantity

    if side == "short":
        if action == "sell":
            cash += gross
            positions[ticker] = held - quantity
            position_sides[ticker] = "short"
        elif action == "buy" and held < 0:
            cover_qty = min(quantity, abs(held))
            cash -= price * cover_qty
            new_qty = held + cover_qty
            if abs(new_qty) < MIN_POSITION_QUANTITY:
                positions.pop(ticker, None)
                position_sides.pop(ticker, None)
            else:
                positions[ticker] = new_qty
    else:
        if action == "buy":
            cash -= gross
            positions[ticker] = held + quantity
            position_sides[ticker] = "long"
        elif action == "sell" and held > 0:
            sell_qty = min(quantity, held)
            cash += price * sell_qty
            new_qty = held - sell_qty
            if abs(new_qty) < MIN_POSITION_QUANTITY:
                positions.pop(ticker, None)
                position_sides.pop(ticker, None)
            else:
                positions[ticker] = new_qty

    exposure = compute_exposures(
        positions,
        prices,
        cash,
        position_sides=position_sides,
        sector_map=sector_map,
        beta_map=beta_map,
    )
    return {
        "positions": positions,
        "position_sides": position_sides,
        "cash": cash,
        "exposure": exposure,
    }
