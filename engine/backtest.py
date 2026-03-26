"""Deterministic strategy comparison backtest logic."""

from __future__ import annotations

import pandas as pd

from config import (
    CRYPTO_TICKERS,
    DRIFT_THRESHOLD,
    INITIAL_CAPITAL,
    KILL_SWITCH_DRAWDOWN,
    SLIPPAGE_CRYPTO,
    SLIPPAGE_EQUITIES,
    TARGET_ALLOCATION,
)
from engine.orders import apply_slippage, generate_rebalance_orders
from engine.performance import cumulative_return, max_drawdown, sharpe_ratio, transaction_costs_total
from market.fetcher import MarketDataService


STRESS_SCENARIOS: list[dict] = [
    {
        "name": "covid_march_2020",
        "description": "COVID-19 crash (Feb–Mar 2020): equities −35%, crypto −50%, bonds +15% (flight to quality)",
        "shocks": {
            "AAPL": -0.35, "MSFT": -0.35, "GOOGL": -0.35, "AMZN": +0.20, "NVDA": -0.40,
            "TLT": +0.15, "BND": +0.08,
            "BTC-USD": -0.50, "ETH-USD": -0.60,
        },
    },
    {
        "name": "gfc_2008",
        "description": "Global Financial Crisis (Sep–Oct 2008): equities −45%, bonds +10%",
        "shocks": {
            "AAPL": -0.45, "MSFT": -0.45, "GOOGL": -0.45, "AMZN": -0.40, "NVDA": -0.55,
            "TLT": +0.10, "BND": +0.08,
            "BTC-USD": -0.60, "ETH-USD": -0.65,  # stress-plausible; crypto was nascent in 2008
        },
    },
    {
        "name": "rate_shock_2022",
        "description": "Fed rate shock 2022: growth equities −30–55%, bonds −15–25%, crypto −65–70%",
        "shocks": {
            "AAPL": -0.25, "MSFT": -0.30, "GOOGL": -0.40, "AMZN": -0.50, "NVDA": -0.55,
            "TLT": -0.25, "BND": -0.15,
            "BTC-USD": -0.65, "ETH-USD": -0.70,
        },
    },
    {
        "name": "tech_selloff",
        "description": "Concentrated tech selloff: tech −40–50%, bonds flat, crypto −20%",
        "shocks": {
            "AAPL": -0.40, "MSFT": -0.40, "GOOGL": -0.40, "AMZN": -0.40, "NVDA": -0.50,
            "TLT": 0.0, "BND": 0.0,
            "BTC-USD": -0.20, "ETH-USD": -0.25,
        },
    },
]


def run_stress_test(
    portfolio: dict,
    prices: dict[str, float],
    scenarios: list[dict] | None = None,
    kill_switch_threshold: float = KILL_SWITCH_DRAWDOWN,
) -> list[dict]:
    """Apply shock scenarios to the current portfolio and measure impact.

    Pure simulation — no trades, no I/O. Each scenario applies multiplicative
    price shocks and reports the resulting portfolio value, P&L, and whether
    the kill switch would be triggered.

    Args:
        portfolio: dict with 'positions' (ticker→qty) and 'cash'
        prices: ticker → current market price
        scenarios: list of scenario dicts with 'name', 'description', 'shocks'
                   (default: STRESS_SCENARIOS)
        kill_switch_threshold: positive drawdown threshold (default from config)

    Returns:
        List of result dicts, one per scenario:
          scenario, description, portfolio_value_before, portfolio_value_after,
          pnl_dollars, pnl_pct, kill_switch_triggered, weights_after
    """
    if scenarios is None:
        scenarios = STRESS_SCENARIOS

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
        shocked_prices = {
            ticker: price * (1.0 + shocks.get(ticker, 0.0))
            for ticker, price in prices.items()
        }
        stressed_value = cash + sum(
            qty * shocked_prices.get(ticker, 0.0) for ticker, qty in positions.items()
        )
        pnl_dollars = stressed_value - current_value
        pnl_pct = pnl_dollars / current_value  # current_value > 0 (checked above)

        # Portfolio weights under the scenario
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


def run_strategy_comparison(days: int = 90) -> dict | None:
    svc = MarketDataService()
    tickers = list(TARGET_ALLOCATION.keys())
    price_series: dict[str, pd.Series] = {}

    for ticker in tickers:
        df = svc.get_historical(ticker, days=days + 30)
        if df is not None and not df.empty and "Close" in df.columns:
            price_series[ticker] = df["Close"].dropna()

    if not price_series:
        return None

    common_idx = None
    for series in price_series.values():
        idx = series.index.normalize()
        common_idx = idx if common_idx is None else common_idx.intersection(idx)
    if common_idx is None or len(common_idx) < 5:
        return None
    common_idx = sorted(common_idx)[-days:]

    def prices_on(date):
        prices = {}
        for ticker, series in price_series.items():
            matches = series[series.index.normalize() == date]
            if not matches.empty:
                prices[ticker] = float(matches.iloc[-1])
        return prices

    def init_portfolio(day0_prices):
        portfolio = {"positions": {}, "cash": INITIAL_CAPITAL, "last_rebalanced": None}
        for ticker, weight in TARGET_ALLOCATION.items():
            price = day0_prices.get(ticker, 0)
            if price > 0:
                qty = (INITIAL_CAPITAL * weight) / price
                portfolio["positions"][ticker] = qty
                portfolio["cash"] -= qty * price
        return portfolio

    def portfolio_value(portfolio, prices):
        return portfolio["cash"] + sum(qty * prices.get(t, 0) for t, qty in portfolio["positions"].items())

    def apply_orders(portfolio, orders, prices):
        executed = []
        for order in orders:
            ticker, qty, action = order["ticker"], order["quantity"], order["action"]
            price = prices.get(ticker, 0)
            if price <= 0:
                continue
            fill = apply_slippage(price, action, ticker, CRYPTO_TICKERS, SLIPPAGE_EQUITIES, SLIPPAGE_CRYPTO)
            if action == "buy":
                cost = fill * qty
                if portfolio["cash"] >= cost:
                    portfolio["positions"][ticker] = portfolio["positions"].get(ticker, 0) + qty
                    portfolio["cash"] -= cost
                    executed.append({"ticker": ticker, "action": action, "quantity": qty, "market_price": price, "fill_price": fill, "success": True})
            else:
                held = portfolio["positions"].get(ticker, 0)
                qty = min(qty, held)
                if qty > 0:
                    portfolio["positions"][ticker] = held - qty
                    portfolio["cash"] += fill * qty
                    executed.append({"ticker": ticker, "action": action, "quantity": qty, "market_price": price, "fill_price": fill, "success": True})
        return executed

    results = {}
    for strategy_name in ["threshold", "calendar", "buy_and_hold"]:
        first_prices = prices_on(common_idx[0])
        if not first_prices:
            continue
        portfolio = init_portfolio(first_prices)
        equity = []
        trades = []
        last_rebalance_idx = 0

        for idx, date in enumerate(common_idx):
            prices = prices_on(date)
            if not prices:
                continue
            value = portfolio_value(portfolio, prices)
            equity.append({"date": str(date.date()), "total_value": value})
            if strategy_name == "buy_and_hold":
                continue
            if strategy_name == "threshold":
                if any(abs(portfolio["positions"].get(t, 0) * prices.get(t, 0) / value - TARGET_ALLOCATION.get(t, 0)) > DRIFT_THRESHOLD for t in TARGET_ALLOCATION if value > 0):
                    trades.extend(apply_orders(portfolio, generate_rebalance_orders(portfolio, prices, TARGET_ALLOCATION), prices))
            if strategy_name == "calendar" and idx - last_rebalance_idx >= 7:
                trades.extend(apply_orders(portfolio, generate_rebalance_orders(portfolio, prices, TARGET_ALLOCATION), prices))
                last_rebalance_idx = idx

        returns = pd.Series([point["total_value"] for point in equity]).pct_change().dropna()
        results[strategy_name] = {
            "equity": equity,
            "trades": trades,
            "cum_ret": cumulative_return(equity),
            "sharpe": sharpe_ratio(returns),
            "max_dd": max_drawdown(equity),
            "n_trades": len(trades),
            "costs": transaction_costs_total(trades),
        }
    return results
