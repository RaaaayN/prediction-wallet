"""Hedge-fund specific book construction, exposures and attribution helpers."""

from __future__ import annotations

from collections import defaultdict


def normalize_position_sides(positions: dict[str, float], position_sides: dict[str, str] | None = None) -> dict[str, str]:
    if not isinstance(positions, dict):
        return {}
    sides: dict[str, str] = {}
    for ticker, quantity in positions.items():
        side = (position_sides or {}).get(ticker)
        if side in {"long", "short"}:
            sides[ticker] = side
        else:
            sides[ticker] = "short" if quantity < 0 else "long"
    return sides


def compute_exposures(
    positions: dict[str, float],
    prices: dict[str, float],
    cash: float = 0.0,
    *,
    position_sides: dict[str, str] | None = None,
    sector_map: dict[str, str] | None = None,
    beta_map: dict[str, float] | None = None,
) -> dict:
    sector_map = sector_map or {}
    beta_map = beta_map or {}
    if not isinstance(positions, dict):
        positions = {}
    if not isinstance(position_sides, dict):
        position_sides = {}
    if not isinstance(cash, (int, float)):
        cash = 0.0
    position_sides = normalize_position_sides(positions, position_sides)

    market_values = {ticker: float(quantity) * prices.get(ticker, 0.0) for ticker, quantity in positions.items()}
    gross_market_value = sum(abs(value) for value in market_values.values())
    net_market_value = sum(market_values.values())
    denominator = gross_market_value + cash
    if denominator <= 0:
        denominator = max(cash, 1.0)

    long_exposure = sum(max(value, 0.0) for value in market_values.values()) / denominator
    short_exposure = sum(abs(min(value, 0.0)) for value in market_values.values()) / denominator
    gross_exposure = gross_market_value / denominator
    net_exposure = net_market_value / denominator

    sector_gross: dict[str, float] = defaultdict(float)
    sector_net: dict[str, float] = defaultdict(float)
    single_name_concentration: dict[str, float] = {}
    beta_adjusted = 0.0

    for ticker, value in market_values.items():
        sector = sector_map.get(ticker, "other")
        gross_weight = abs(value) / denominator
        net_weight = value / denominator
        sector_gross[sector] += gross_weight
        sector_net[sector] += net_weight
        single_name_concentration[ticker] = gross_weight
        beta_adjusted += net_weight * beta_map.get(ticker, 1.0)

    top5_concentration = sum(sorted(single_name_concentration.values(), reverse=True)[:5])
    factor_exposure = {
        "momentum_proxy": round(sum(
            single_name_concentration.get(t, 0.0)
            for t, s in position_sides.items()
            if s == "long"
        ), 6),
        "short_interest_proxy": round(sum(
            single_name_concentration.get(t, 0.0)
            for t, s in position_sides.items()
            if s == "short"
        ), 6),
    }

    return {
        "gross_exposure": round(gross_exposure, 6),
        "net_exposure": round(net_exposure, 6),
        "long_exposure": round(long_exposure, 6),
        "short_exposure": round(short_exposure, 6),
        "leverage_used": round(gross_exposure, 6),
        "beta_adjusted_exposure": round(beta_adjusted, 6),
        "factor_exposure": factor_exposure,
        "sector_gross": {k: round(v, 6) for k, v in sector_gross.items()},
        "sector_net": {k: round(v, 6) for k, v in sector_net.items()},
        "single_name_concentration": {k: round(v, 6) for k, v in single_name_concentration.items()},
        "top5_concentration": round(top5_concentration, 6),
    }


def classify_book_risk(
    exposure: dict,
    *,
    gross_limit: float | None = None,
    net_min: float | None = None,
    net_max: float | None = None,
    max_sector_gross: float | None = None,
    max_sector_net: float | None = None,
    max_single_name_long: float | None = None,
    max_single_name_short: float | None = None,
    crowded_scores: dict[str, float] | None = None,
    short_squeeze_names: set[str] | None = None,
    position_sides: dict[str, str] | None = None,
) -> dict:
    crowded_scores = crowded_scores or {}
    short_squeeze_names = short_squeeze_names or set()
    position_sides = position_sides or {}
    breaches: list[str] = []
    near_breaches: list[str] = []

    gross = exposure.get("gross_exposure", 0.0)
    net = exposure.get("net_exposure", 0.0)
    if gross_limit is not None:
        if gross > gross_limit:
            breaches.append(f"Gross exposure {gross:.1%} > {gross_limit:.1%}")
        elif gross > gross_limit * 0.9:
            near_breaches.append(f"Gross exposure near limit at {gross:.1%}")
    if net_min is not None and net < net_min:
        breaches.append(f"Net exposure {net:.1%} < {net_min:.1%}")
    elif net_min is not None and net < net_min + 0.05:
        near_breaches.append(f"Net exposure near floor at {net:.1%}")
    if net_max is not None and net > net_max:
        breaches.append(f"Net exposure {net:.1%} > {net_max:.1%}")
    elif net_max is not None and net > net_max - 0.05:
        near_breaches.append(f"Net exposure near cap at {net:.1%}")

    for sector, value in (exposure.get("sector_gross") or {}).items():
        if max_sector_gross is not None and value > max_sector_gross:
            breaches.append(f"Sector gross {sector} {value:.1%} > {max_sector_gross:.1%}")
    for sector, value in (exposure.get("sector_net") or {}).items():
        if max_sector_net is not None and abs(value) > max_sector_net:
            breaches.append(f"Sector net {sector} {value:.1%} exceeds +/-{max_sector_net:.1%}")

    crowded_names: list[str] = []
    squeeze_names: list[str] = []
    for ticker, value in (exposure.get("single_name_concentration") or {}).items():
        side = position_sides.get(ticker, "long")
        limit = max_single_name_short if side == "short" else max_single_name_long
        if limit is not None and value > limit:
            breaches.append(f"{ticker} {side} concentration {value:.1%} > {limit:.1%}")
        elif limit is not None and value > limit * 0.9:
            near_breaches.append(f"{ticker} {side} concentration near limit at {value:.1%}")
        if crowded_scores.get(ticker, 0.0) >= 0.65:
            crowded_names.append(ticker)
        if ticker in short_squeeze_names and side == "short":
            squeeze_names.append(ticker)

    return {
        "breaches": sorted(set(breaches)),
        "near_breaches": sorted(set(near_breaches)),
        "crowded_names": sorted(set(crowded_names)),
        "short_squeeze_names": sorted(set(squeeze_names)),
        "exposure": exposure,
    }


def score_idea(idea: dict, *, price_metrics: dict | None = None, crowded_score: float = 0.0) -> dict:
    metrics = price_metrics or {}
    vol = float(metrics.get("volatility_30d", 0.20) or 0.20)
    sharpe = float(metrics.get("sharpe", 0.0) or 0.0)
    ytd = float(metrics.get("ytd_return", 0.0) or 0.0)
    base_conviction = float(idea.get("conviction", 0.5))
    conviction = base_conviction + min(0.10, max(-0.10, sharpe * 0.02)) - crowded_score * 0.08
    conviction = max(0.0, min(1.0, conviction))
    summary = (
        f"{idea.get('ticker')} {idea.get('side')} idea with conviction {conviction:.2f}; "
        f"30d vol {vol:.1%}, YTD {ytd:.1%}, crowded {crowded_score:.0%}."
    )
    return {
        **idea,
        "conviction": round(conviction, 4),
        "status": idea.get("status", "watchlist"),
        "thesis": idea.get("thesis", summary),
        "catalyst": idea.get("catalyst", "Monitoring catalyst"),
    }


def build_position_intents(
    ideas: list[dict],
    *,
    conviction_to_size: dict[str, float] | None = None,
    price_metrics: dict[str, dict] | None = None,
    sector_gross: dict[str, float] | None = None,
    sector_map: dict[str, str] | None = None,
) -> list[dict]:
    conviction_to_size = conviction_to_size or {"high": 0.12, "medium": 0.08, "low": 0.04}
    price_metrics = price_metrics or {}
    sector_gross = sector_gross or {}
    sector_map = sector_map or {}
    intents: list[dict] = []

    for idea in ideas:
        conviction = float(idea.get("conviction", 0.5))
        if conviction >= 0.7:
            bucket = "high"
        elif conviction >= 0.55:
            bucket = "medium"
        else:
            bucket = "low"
        base_weight = float(conviction_to_size.get(bucket, 0.05))
        vol = float((price_metrics.get(idea.get("ticker"), {}) or {}).get("volatility_30d", 0.20) or 0.20)
        vol_scalar = max(0.6, min(1.2, 0.20 / vol if vol > 0 else 1.0))
        sector = sector_map.get(idea.get("ticker"), "other")
        concentration_scalar = 0.8 if sector_gross.get(sector, 0.0) > 0.35 else 1.0
        target_weight = round(base_weight * vol_scalar * concentration_scalar, 6)
        intents.append({
            "ticker": idea.get("ticker"),
            "side": idea.get("side", "long"),
            "target_weight": target_weight,
            "conviction": conviction,
            "sizing_reason": (
                f"bucket={bucket}, vol_scalar={vol_scalar:.2f}, "
                f"sector_scalar={concentration_scalar:.2f}"
            ),
            "sleeve": idea.get("sleeve", "core_longs"),
            "idea_id": idea.get("idea_id"),
        })
    return intents


def convert_intents_to_trade_plan(
    intents: list[dict],
    *,
    positions: dict[str, float],
    prices: dict[str, float],
    cash: float,
) -> list[dict]:
    market_values = {ticker: float(quantity) * prices.get(ticker, 0.0) for ticker, quantity in positions.items()}
    denominator = sum(abs(value) for value in market_values.values()) + cash
    if denominator <= 0:
        denominator = max(cash, 1.0)

    plan: list[dict] = []
    for intent in intents:
        ticker = intent["ticker"]
        price = prices.get(ticker, 0.0)
        if price <= 0:
            continue
        side = intent.get("side", "long")
        signed_target_weight = intent.get("target_weight", 0.0) * (1.0 if side == "long" else -1.0)
        current_value = market_values.get(ticker, 0.0)
        target_value = signed_target_weight * denominator
        delta_value = target_value - current_value
        if abs(delta_value) < 10.0:
            continue
        quantity = round(abs(delta_value) / price, 6)
        if quantity <= 0:
            continue
        action = "buy" if delta_value > 0 else "sell"
        plan.append({
            "action": action,
            "ticker": ticker,
            "quantity": quantity,
            "reason": f"Construct {side} book toward {intent.get('target_weight', 0.0):.1%} target.",
            "side": side,
            "idea_id": intent.get("idea_id"),
            "conviction": intent.get("conviction", 0.5),
            "sleeve": intent.get("sleeve", "core_longs"),
        })
    return plan


def compute_pnl_attribution(
    *,
    positions: dict[str, float],
    prices: dict[str, float],
    average_costs: dict[str, float] | None = None,
    position_sides: dict[str, str] | None = None,
    executions: list[dict] | None = None,
    idea_lookup: dict[str, dict] | None = None,
    sector_map: dict[str, str] | None = None,
) -> dict:
    average_costs = average_costs or {}
    position_sides = normalize_position_sides(positions, position_sides)
    executions = executions or []
    idea_lookup = idea_lookup or {}
    sector_map = sector_map or {}

    by_side: dict[str, float] = defaultdict(float)
    by_sector: dict[str, float] = defaultdict(float)
    by_idea: dict[str, float] = defaultdict(float)
    by_sleeve: dict[str, float] = defaultdict(float)
    realized_total = 0.0
    unrealized_total = 0.0

    for exec_ in executions:
        if not exec_.get("success", True):
            continue
        side = exec_.get("side", "long")
        signed = -1.0 if exec_.get("action") == "buy" else 1.0
        pnl = signed * float(exec_.get("notional", abs(exec_.get("fill_price", 0.0) * exec_.get("quantity", 0.0))))
        realized_total += pnl
        by_side[side] += pnl
        ticker = exec_.get("ticker", "")
        by_sector[sector_map.get(ticker, "other")] += pnl
        if exec_.get("idea_id"):
            by_idea[exec_["idea_id"]] += pnl
            by_sleeve[idea_lookup.get(exec_["idea_id"], {}).get("sleeve", exec_.get("sleeve", "unspecified"))] += pnl

    for ticker, quantity in positions.items():
        price = prices.get(ticker, 0.0)
        cost = average_costs.get(ticker, price)
        side = position_sides.get(ticker, "long")
        signed_qty = float(quantity)
        pnl = (price - cost) * signed_qty
        unrealized_total += pnl
        by_side[side] += pnl
        by_sector[sector_map.get(ticker, "other")] += pnl
        for idea_id, idea in idea_lookup.items():
            if idea.get("ticker") == ticker and idea.get("status") in {"portfolio", "investable"}:
                by_idea[idea_id] += pnl
                by_sleeve[idea.get("sleeve", "unspecified")] += pnl

    return {
        "realized_total": round(realized_total, 6),
        "unrealized_total": round(unrealized_total, 6),
        "by_side": {k: round(v, 6) for k, v in by_side.items()},
        "by_sector": {k: round(v, 6) for k, v in by_sector.items()},
        "by_idea": {k: round(v, 6) for k, v in by_idea.items()},
        "by_sleeve": {k: round(v, 6) for k, v in by_sleeve.items()},
    }
