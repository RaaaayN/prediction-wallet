"""Industrialized stress testing engine with asset-class shocks."""

from __future__ import annotations
from typing import Dict, List, Optional
from config import KILL_SWITCH_DRAWDOWN, CRYPTO_TICKERS
from trading_core.models import InstrumentType
from trading_core.security_master import SecurityMaster

# Enhanced scenarios using asset-class shocks
ASSET_CLASS_SCENARIOS: List[Dict] = [
    {
        "name": "equity_crash",
        "description": "Severe equity market crash: -30% Equities, +5% Bonds, -20% Crypto",
        "shocks": {
            InstrumentType.EQUITY: -0.30,
            InstrumentType.BOND: +0.05,
            InstrumentType.CRYPTO: -0.20,
            InstrumentType.INDEX: -0.30
        }
    },
    {
        "name": "crypto_meltdown",
        "description": "Extreme crypto drawdown: -60% Crypto, -5% Equities",
        "shocks": {
            InstrumentType.CRYPTO: -0.60,
            InstrumentType.EQUITY: -0.05
        }
    },
    {
        "name": "inflation_spike",
        "description": "Rapid inflation spike: -15% Bonds, -10% Equities, +10% Commodities/Gold",
        "shocks": {
            InstrumentType.BOND: -0.15,
            InstrumentType.EQUITY: -0.10,
            InstrumentType.CRYPTO: -0.05
        }
    },
    {
        "name": "global_recession",
        "description": "Synchronized global downturn: -25% Equities, -40% Crypto, +10% Bonds",
        "shocks": {
            InstrumentType.EQUITY: -0.25,
            InstrumentType.CRYPTO: -0.40,
            InstrumentType.BOND: +0.10
        }
    }
]

def get_asset_class(ticker: str) -> InstrumentType:
    """Heuristic to determine asset class for a ticker."""
    # Try to use SecurityMaster for more accurate mapping
    sm = SecurityMaster()
    # SecurityMaster uses HEDGE_FUND_PROFILE and config to bootstrap
    sm.bootstrap() 
    inst = sm.get_by_symbol(ticker)
    if inst:
        return inst.asset_class
    
    # Fallback to simple heuristic
    if ticker in CRYPTO_TICKERS or ("USD" in ticker and "-" in ticker):
        return InstrumentType.CRYPTO
    if ticker in {"TLT", "BND", "AGG", "IEF"}:
        return InstrumentType.BOND
    return InstrumentType.EQUITY

def run_stress_test_v2(
    portfolio: dict,
    prices: dict[str, float],
    scenarios: Optional[List[dict]] = None,
    kill_switch_threshold: float = KILL_SWITCH_DRAWDOWN,
) -> List[dict]:
    """Apply asset-class based shocks to the current portfolio.
    
    Args:
        portfolio: dict with 'positions' (ticker->qty) and 'cash'
        prices: ticker -> current market price
        scenarios: optional list of custom scenarios
        kill_switch_threshold: drawdown threshold
        
    Returns:
        List of result dicts per scenario.
    """
    if scenarios is None:
        scenarios = ASSET_CLASS_SCENARIOS

    positions = portfolio.get("positions", {})
    cash = portfolio.get("cash", 0.0)

    current_value = cash + sum(
        qty * prices.get(ticker, 0.0) for ticker, qty in positions.items()
    )
    if current_value <= 0:
        return []

    results = []
    for scenario in scenarios:
        shocks = scenario.get("shocks", {})
        
        shocked_prices = {}
        for ticker, price in prices.items():
            a_class = get_asset_class(ticker)
            # Apply asset class shock if defined, otherwise 0.0
            shock_pct = shocks.get(a_class, shocks.get(a_class.value, 0.0))
            shocked_prices[ticker] = price * (1.0 + shock_pct)

        stressed_value = cash + sum(
            qty * shocked_prices.get(ticker, 0.0) for ticker, qty in positions.items()
        )
        pnl_dollars = stressed_value - current_value
        pnl_pct = pnl_dollars / current_value

        weights_after: dict[str, float] = {}
        if stressed_value > 0:
            for ticker, qty in positions.items():
                weights_after[ticker] = (qty * shocked_prices.get(ticker, 0.0)) / stressed_value

        results.append({
            "scenario": scenario["name"],
            "description": scenario.get("description", ""),
            "portfolio_value_before": current_value,
            "portfolio_value_after": stressed_value,
            "pnl_dollars": pnl_dollars,
            "pnl_pct": pnl_pct,
            "kill_switch_triggered": pnl_pct <= -kill_switch_threshold,
            "weights_after": weights_after,
        })

    return results
