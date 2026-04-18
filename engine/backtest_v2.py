"""Baseline Event-Driven Backtester (v2)."""

from __future__ import annotations

import pandas as pd
from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, List, Optional

from config import (
    CRYPTO_TICKERS,
    DRIFT_THRESHOLD,
    INITIAL_CAPITAL,
    TARGET_ALLOCATION,
    SLIPPAGE_EQUITIES,
    SLIPPAGE_CRYPTO,
    SECTOR_MAP,
    BENCHMARK_TICKER,
)
from engine.orders import apply_slippage, generate_rebalance_orders
from engine.performance import performance_report
from engine.hedge_fund import compute_exposures
from market.fetcher import MarketDataService

@dataclass
class BacktestResult:
    strategy_name: str
    history: List[dict]
    trades: List[dict]
    metrics: dict
    exposures: List[dict]

class EventDrivenBacktester:
    def __init__(
        self,
        days: int = 90,
        initial_capital: float = INITIAL_CAPITAL,
        commission_fixed: float = 0.0,
        commission_bps: float = 0.0,
    ):
        self.days = days
        self.initial_capital = initial_capital
        self.commission_fixed = commission_fixed
        self.commission_bps = commission_bps
        self.market_svc = MarketDataService()
        
    def _get_data(self, tickers: List[str]) -> pd.DataFrame:
        """Fetch and align data for all tickers."""
        price_data = {}
        volume_data = {}
        
        all_tickers = sorted(list(set(tickers + [BENCHMARK_TICKER])))
        for ticker in all_tickers:
            df = self.market_svc.get_historical(ticker, days=self.days + 30)
            if df is not None and not df.empty:
                price_data[ticker] = df["Close"]
                volume_data[ticker] = df["Volume"] if "Volume" in df.columns else pd.Series(0, index=df.index)

        if not price_data:
            return pd.DataFrame()

        # Align on common index
        combined_prices = pd.DataFrame(price_data).dropna()
        combined_volumes = pd.DataFrame(volume_data).reindex(combined_prices.index).fillna(0)
        
        # Filter for requested days
        combined_prices = combined_prices.tail(self.days)
        combined_volumes = combined_volumes.loc[combined_prices.index]
        
        return combined_prices, combined_volumes

    def run(self, strategy_type: str = "threshold", benchmark_ticker: str = BENCHMARK_TICKER) -> BacktestResult:
        tickers = list(TARGET_ALLOCATION.keys())
        prices_df, volumes_df = self._get_data(tickers)
        
        if prices_df.empty:
            raise ValueError("No market data found for tickers.")

        # Initialize portfolio
        portfolio = {
            "positions": {t: 0.0 for t in tickers},
            "cash": self.initial_capital,
            "last_rebalanced": None
        }
        
        history = []
        trades = []
        exposures_history = []
        
        # Initial allocation at first available prices
        first_date = prices_df.index[0]
        first_prices = prices_df.loc[first_date].to_dict()
        
        for ticker, weight in TARGET_ALLOCATION.items():
            price = first_prices.get(ticker, 0.0)
            if price > 0:
                target_value = self.initial_capital * weight
                qty = target_value / price
                portfolio["positions"][ticker] = qty
                portfolio["cash"] -= target_value
        
        last_rebalance_idx = 0
        
        # Event loop
        for idx, (timestamp, current_prices_series) in enumerate(prices_df.iterrows()):
            current_prices = current_prices_series.to_dict()
            portfolio_value = portfolio["cash"] + sum(
                qty * current_prices.get(t, 0.0) for t, qty in portfolio["positions"].items()
            )
            
            # Record state
            snapshot = {
                "date": str(timestamp.date()),
                "total_value": portfolio_value,
                "cash": portfolio["cash"],
                "positions": portfolio["positions"].copy()
            }
            history.append(snapshot)
            
            # Record exposures
            exp = compute_exposures(
                portfolio["positions"], 
                current_prices, 
                portfolio["cash"],
                sector_map=SECTOR_MAP
            )
            exposures_history.append({"date": str(timestamp.date()), **exp})

            # Check for rebalance
            should_rebalance = False
            if strategy_type == "threshold":
                for t, target_w in TARGET_ALLOCATION.items():
                    current_w = (portfolio["positions"].get(t, 0.0) * current_prices.get(t, 0.0)) / portfolio_value if portfolio_value > 0 else 0.0
                    if abs(current_w - target_w) > DRIFT_THRESHOLD:
                        should_rebalance = True
                        break
            elif strategy_type == "calendar":
                if idx - last_rebalance_idx >= 7: # Weekly
                    should_rebalance = True
            
            if should_rebalance:
                orders = generate_rebalance_orders(portfolio, current_prices, TARGET_ALLOCATION)
                executed_in_cycle = self._apply_orders(portfolio, orders, current_prices, timestamp)
                trades.extend(executed_in_cycle)
                last_rebalance_idx = idx

        # Benchmark history
        benchmark_prices = prices_df[benchmark_ticker]
        benchmark_history = []
        if not benchmark_prices.empty:
            # Assume buy and hold benchmark from first date
            bench_start_price = benchmark_prices.iloc[0]
            for ts, p in benchmark_prices.items():
                bench_val = (self.initial_capital / bench_start_price) * p
                benchmark_history.append({"date": str(ts.date()), "total_value": bench_val})

        # Metrics
        metrics = performance_report(
            history, 
            trades, 
            benchmark_history=benchmark_history,
            exposures_history=exposures_history
        )
        
        return BacktestResult(
            strategy_name=strategy_type,
            history=history,
            trades=trades,
            metrics=metrics,
            exposures=exposures_history
        )

    def _apply_orders(self, portfolio: dict, orders: list, prices: dict, timestamp: datetime) -> list:
        executed = []
        for order in orders:
            ticker = order["ticker"]
            qty = order["quantity"]
            action = order["action"]
            price = prices.get(ticker, 0.0)
            
            if price <= 0 or qty <= 0:
                continue
                
            fill_price = apply_slippage(
                price, action, ticker, CRYPTO_TICKERS, SLIPPAGE_EQUITIES, SLIPPAGE_CRYPTO
            )
            
            notional = fill_price * qty
            fee = self.commission_fixed + (notional * self.commission_bps)
            
            if action == "buy":
                total_cost = notional + fee
                if portfolio["cash"] >= total_cost:
                    portfolio["positions"][ticker] = portfolio["positions"].get(ticker, 0.0) + qty
                    portfolio["cash"] -= total_cost
                    executed.append({
                        "timestamp": str(timestamp),
                        "ticker": ticker,
                        "action": action,
                        "quantity": qty,
                        "market_price": price,
                        "fill_price": fill_price,
                        "commission": fee,
                        "success": True
                    })
            elif action == "sell":
                held = portfolio["positions"].get(ticker, 0.0)
                qty_to_sell = min(qty, held)
                if qty_to_sell > 0:
                    proceeds = (fill_price * qty_to_sell) - fee
                    portfolio["positions"][ticker] = held - qty_to_sell
                    portfolio["cash"] += proceeds
                    executed.append({
                        "timestamp": str(timestamp),
                        "ticker": ticker,
                        "action": action,
                        "quantity": qty_to_sell,
                        "market_price": price,
                        "fill_price": fill_price,
                        "commission": fee,
                        "success": True
                    })
        return executed
