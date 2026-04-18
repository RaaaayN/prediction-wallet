"""Institutional Event-Driven Backtester (v2)."""

from __future__ import annotations

import pandas as pd
from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, List, Optional, Any

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
from engine.hedge_fund import compute_exposures, classify_book_risk
from market.fetcher import MarketDataService

@dataclass
class BacktestResult:
    strategy_name: str
    history: List[dict]
    trades: List[dict]
    metrics: dict
    exposures: List[dict]
    risk_violations: List[dict]
    data_hash: Optional[str] = None

class EventDrivenBacktester:
    def __init__(
        self,
        days: int = 90,
        initial_capital: float = INITIAL_CAPITAL,
        commission_fixed: float = 0.0,
        commission_bps: float = 0.0,
        gold_dataset_name: Optional[str] = None,
        # Risk Limits
        gross_limit: float = 1.5,
        max_sector_gross: float = 0.55,
        max_single_ticker: float = 0.20,
    ):
        self.days = days
        self.initial_capital = initial_capital
        self.commission_fixed = commission_fixed
        self.commission_bps = commission_bps
        self.market_svc = MarketDataService()
        self.gold_dataset_name = gold_dataset_name
        self.data_hash = None
        
        # Risk Configuration
        self.gross_limit = gross_limit
        self.max_sector_gross = max_sector_gross
        self.max_single_ticker = max_single_ticker
        self.risk_violations = []
        
    def _get_data(self, tickers: List[str]) -> pd.DataFrame:
        """Fetch and align data for all tickers."""
        from services.data_lake_service import DataLakeService
        lake = DataLakeService()
        
        if self.gold_dataset_name:
            gold_data = lake.load_gold(self.gold_dataset_name)
            if gold_data:
                import hashlib
                from pathlib import Path
                self.data_hash = lake._compute_dataset_hash(lake.gold_path / self.gold_dataset_name)
                
                price_data = {t: df["Close"] for t, df in gold_data.items() if "Close" in df.columns}
                volume_data = {t: df["Volume"] for t, df in gold_data.items() if "Volume" in df.columns}
                
                combined_prices = pd.DataFrame(price_data).dropna()
                combined_volumes = pd.DataFrame(volume_data).reindex(combined_prices.index).fillna(0)
                return combined_prices, combined_volumes

        price_data = {}
        volume_data = {}
        
        all_tickers = sorted(list(set(tickers + [BENCHMARK_TICKER])))
        for ticker in all_tickers:
            df = self.market_svc.get_historical(ticker, days=self.days + 30)
            if df is not None and not df.empty:
                price_data[ticker] = df["Close"]
                volume_data[ticker] = df["Volume"] if "Volume" in df.columns else pd.Series(0, index=df.index)

        if not price_data:
            return pd.DataFrame(), pd.DataFrame()

        combined_prices = pd.DataFrame(price_data).dropna()
        combined_volumes = pd.DataFrame(volume_data).reindex(combined_prices.index).fillna(0)
        
        combined_prices = combined_prices.tail(self.days)
        combined_volumes = combined_volumes.loc[combined_prices.index]
        
        return combined_prices, combined_volumes

    def run(
        self, 
        strategy_type: str = "threshold", 
        benchmark_ticker: str = BENCHMARK_TICKER,
        sentiment_df: Optional[pd.DataFrame] = None,
    ) -> BacktestResult:
        tickers = list(TARGET_ALLOCATION.keys())
        prices_df, volumes_df = self._get_data(tickers)
        
        if prices_df.empty:
            raise ValueError("No market data found for tickers.")

        portfolio = {
            "positions": {t: 0.0 for t in tickers},
            "cash": self.initial_capital,
            "last_rebalanced": None
        }
        
        history = []
        trades = []
        exposures_history = []
        self.risk_violations = []
        
        # Returns for correlation-adjusted VaR
        returns_df = prices_df.pct_change().dropna()
        # Initial allocation at first available prices
        first_date = prices_df.index[0]
        first_prices = prices_df.loc[first_date].to_dict()

        initial_orders = []
        for ticker, weight in TARGET_ALLOCATION.items():
            price = first_prices.get(ticker, 0.0)
            if price > 0:
                target_value = self.initial_capital * weight
                qty = target_value / price
                initial_orders.append({"ticker": ticker, "quantity": qty, "action": "buy"})

        safe_initial_orders = self._filter_risk_constrained_orders(portfolio, initial_orders, first_prices, first_date)
        self._apply_orders(portfolio, safe_initial_orders, first_prices, first_date)

        last_rebalance_idx = 0

        for idx, (timestamp, current_prices_series) in enumerate(prices_df.iterrows()):
            current_prices = current_prices_series.to_dict()
            portfolio_value = portfolio["cash"] + sum(
                qty * current_prices.get(t, 0.0) for t, qty in portfolio["positions"].items()
            )
            
            snapshot = {
                "date": str(timestamp.date()),
                "total_value": portfolio_value,
                "cash": portfolio["cash"],
                "positions": portfolio["positions"].copy()
            }
            history.append(snapshot)
            
            exp = compute_exposures(
                portfolio["positions"], 
                current_prices, 
                portfolio["cash"],
                sector_map=SECTOR_MAP
            )
            exposures_history.append({"date": str(timestamp.date()), **exp})

            should_rebalance = False
            orders = []
            
            if strategy_type == "ensemble":
                from strategies.ensemble import EnsembleStrategy
                ensemble = EnsembleStrategy(TARGET_ALLOCATION, DRIFT_THRESHOLD)
                # Get sentiment for this timestamp
                current_sentiment = sentiment_df.loc[timestamp].to_dict() if sentiment_df is not None and timestamp in sentiment_df.index else {}
                orders = ensemble.get_trades(portfolio, current_prices, current_sentiment)
                if orders:
                    should_rebalance = True
            elif strategy_type == "threshold":
                for t, target_w in TARGET_ALLOCATION.items():
                    current_w = (portfolio["positions"].get(t, 0.0) * current_prices.get(t, 0.0)) / portfolio_value if portfolio_value > 0 else 0.0
                    if abs(current_w - target_w) > DRIFT_THRESHOLD:
                        should_rebalance = True
                        break
                if should_rebalance:
                    orders = generate_rebalance_orders(portfolio, current_prices, TARGET_ALLOCATION)
            elif strategy_type == "calendar":
                if idx - last_rebalance_idx >= 7:
                    should_rebalance = True
                    orders = generate_rebalance_orders(portfolio, current_prices, TARGET_ALLOCATION)
            
            if should_rebalance and orders:
                # Filter orders by risk constraints
                safe_orders = self._filter_risk_constrained_orders(portfolio, orders, current_prices, timestamp)
                executed_in_cycle = self._apply_orders(portfolio, safe_orders, current_prices, timestamp)
                trades.extend(executed_in_cycle)
                last_rebalance_idx = idx

        benchmark_prices = prices_df[benchmark_ticker]
        benchmark_history = []
        if not benchmark_prices.empty:
            bench_start_price = benchmark_prices.iloc[0]
            for ts, p in benchmark_prices.items():
                bench_val = (self.initial_capital / bench_start_price) * p
                benchmark_history.append({"date": str(ts.date()), "total_value": bench_val})

        metrics = performance_report(
            history, 
            trades, 
            benchmark_history=benchmark_history,
            exposures_history=exposures_history,
            returns_df=returns_df
        )
        
        return BacktestResult(
            strategy_name=strategy_type,
            history=history,
            trades=trades,
            metrics=metrics,
            exposures=exposures_history,
            risk_violations=self.risk_violations,
            data_hash=self.data_hash
        )

    def _filter_risk_constrained_orders(self, portfolio: dict, orders: list, prices: dict, timestamp: datetime) -> list:
        """Enforce strict risk limits. Block orders that violate constraints."""
        safe_orders = []
        
        # Current state
        current_exp = compute_exposures(portfolio["positions"], prices, portfolio["cash"], sector_map=SECTOR_MAP)
        
        for order in orders:
            ticker = order["ticker"]
            qty = order["quantity"]
            action = order["action"]
            price = prices.get(ticker, 0.0)
            notional = qty * price
            
            # 1. Single Ticker Cap
            portfolio_value = portfolio["cash"] + sum(q * prices.get(t, 0.0) for t, q in portfolio["positions"].items())
            future_ticker_qty = (portfolio["positions"].get(ticker, 0.0) + qty) if action == "buy" else (portfolio["positions"].get(ticker, 0.0) - qty)
            future_ticker_weight = (future_ticker_qty * price) / portfolio_value if portfolio_value > 0 else 0.0
            
            if action == "buy" and future_ticker_weight > self.max_single_ticker:
                self.risk_violations.append({
                    "timestamp": str(timestamp), "ticker": ticker, 
                    "violation": "single_ticker_cap", "details": f"{future_ticker_weight:.1%} > {self.max_single_ticker:.1%}"
                })
                continue

            # 2. Sector Cap (Incremental check)
            sector = SECTOR_MAP.get(ticker, "other")
            sector_gross = current_exp["sector_gross"].get(sector, 0.0)
            future_sector_gross = sector_gross + (notional / portfolio_value) if action == "buy" else sector_gross
            
            if action == "buy" and future_sector_gross > self.max_sector_gross:
                self.risk_violations.append({
                    "timestamp": str(timestamp), "ticker": ticker, 
                    "violation": "sector_cap", "details": f"{sector} {future_sector_gross:.1%} > {self.max_sector_gross:.1%}"
                })
                continue
            
            # 3. Gross Exposure
            # (Adding notional to gross if buy, reducing if sell but we use absolute value for gross)
            # Simplified: only buy can increase gross exposure beyond 100% (leverage)
            future_gross = current_exp["gross_exposure"] + (notional / portfolio_value) if action == "buy" else current_exp["gross_exposure"]
            if action == "buy" and future_gross > self.gross_limit:
                self.risk_violations.append({
                    "timestamp": str(timestamp), "ticker": ticker, 
                    "violation": "gross_exposure_limit", "details": f"{future_gross:.1%} > {self.gross_limit:.1%}"
                })
                continue

            safe_orders.append(order)
            
        return safe_orders

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
