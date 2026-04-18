"""Ensemble Strategy: Quantitative Drift + NLP Sentiment."""

from __future__ import annotations

import pandas as pd
from typing import Dict, List, Optional
from strategies.threshold import ThresholdStrategy

class EnsembleStrategy:
    """Combines quantitative rebalancing with sentiment-based overlays."""

    def __init__(
        self, 
        target_allocation: Dict[str, float],
        drift_threshold: float = 0.05,
        sentiment_weight: float = 0.2
    ):
        self.base_strategy = ThresholdStrategy()
        self.target_allocation = target_allocation
        self.drift_threshold = drift_threshold
        self.sentiment_weight = sentiment_weight

    def get_trades(
        self,
        portfolio: Dict,
        current_prices: Dict[str, float],
        sentiment_scores: Dict[str, float], # New: ticker -> score (-1 to 1)
    ) -> List[Dict]:
        """Generate trades based on drift AND sentiment."""
        # 1. Get base trades from threshold drift
        # ThresholdStrategy.get_trades in this repo actually uses global config,
        # but let's assume we use a similar logic here or call it.
        # For simplicity, we re-implement the rebalance check.
        
        rebalance_orders = []
        portfolio_value = portfolio["cash"] + sum(
            qty * current_prices.get(t, 0.0) for t, qty in portfolio["positions"].items()
        )
        
        if portfolio_value <= 0:
            return []

        for ticker, target_w in self.target_allocation.items():
            current_qty = portfolio["positions"].get(ticker, 0.0)
            current_price = current_prices.get(ticker, 0.0)
            current_w = (current_qty * current_price) / portfolio_value
            
            drift = current_w - target_w
            sentiment = sentiment_scores.get(ticker, 0.0)
            
            # Rebalance trigger
            if abs(drift) > self.drift_threshold:
                # Calculate required qty to hit target
                target_value = portfolio_value * target_w
                diff_value = target_value - (current_qty * current_price)
                
                # NLP Overlay: Adjustment factor
                # If buying (diff > 0) and sentiment is negative -> reduce buy size
                # If selling (diff < 0) and sentiment is positive -> reduce sell size (hold longer)
                adj_factor = 1.0
                if diff_value > 0 and sentiment < -0.2:
                    adj_factor = max(0.0, 1.0 + (sentiment * self.sentiment_weight))
                elif diff_value < 0 and sentiment > 0.2:
                    adj_factor = max(0.0, 1.0 - (sentiment * self.sentiment_weight))

                adj_diff_value = diff_value * adj_factor
                qty = abs(adj_diff_value) / current_price if current_price > 0 else 0
                
                if qty > 0:
                    rebalance_orders.append({
                        "ticker": ticker,
                        "quantity": qty,
                        "action": "buy" if adj_diff_value > 0 else "sell"
                    })
        
        return rebalance_orders
