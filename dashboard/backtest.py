"""Reusable deterministic strategy comparison logic for the dashboard."""

from __future__ import annotations

import pandas as pd

from config import (
    CRYPTO_TICKERS,
    DRIFT_THRESHOLD,
    INITIAL_CAPITAL,
    SLIPPAGE_CRYPTO,
    SLIPPAGE_EQUITIES,
    TARGET_ALLOCATION,
)
from engine.orders import apply_slippage, generate_rebalance_orders
from engine.performance import cumulative_return, max_drawdown, sharpe_ratio, transaction_costs_total
from market.fetcher import MarketDataService


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
