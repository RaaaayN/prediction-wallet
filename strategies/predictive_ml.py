"""Predictive ML Strategy: Uses a trained model from MLflow to generate signals."""

from __future__ import annotations
import mlflow.sklearn
import pandas as pd
from strategies.base import BaseStrategy
from market.fetcher import add_technical_indicators
from ml.alpha_factory import compute_alpha_features, get_feature_list

class PredictiveMLStrategy(BaseStrategy):
    def __init__(self, target_allocation=None, model_run_id: str | None = None):
        super().__init__(target_allocation)
        self.model = None
        self.features = get_feature_list()
        
        if model_run_id:
            self._load_model(model_run_id)

    def _load_model(self, run_id: str):
        """Load the model from MLflow."""
        model_uri = f"runs:/{run_id}/alpha_model"
        self.model = mlflow.sklearn.load_model(model_uri)

    def should_rebalance(self, portfolio: dict, prices: dict) -> bool:
        # Always check predictions to see if weights should shift
        return True

    def get_trades(self, portfolio: dict, prices: dict) -> list[dict]:
        if not self.model:
            # Fallback to standard rebalance if no model
            return self._compute_trade_orders(portfolio, prices)

        # 1. Prepare latest features for each ticker
        predictions = {}
        for ticker in self.target.keys():
            # Get historical for feature calculation
            from market.fetcher import MarketDataService
            mkt = MarketDataService()
            df = mkt.get_historical(ticker, days=30)
            if df is not None and not df.empty:
                df = add_technical_indicators(df)
                
                # USER DEFINED FORMULAS IN INFERENCE
                df = compute_alpha_features(df)
                
                latest_x = df[self.features].tail(1)
                if not latest_x.isnull().values.any():
                    # Predict probability of being positive (1)
                    prob = self.model.predict_proba(latest_x)[0][1]
                    predictions[ticker] = prob

        # 2. Adjust target weights based on predictions
        # Assets with prob > 0.6 get overweight, < 0.4 get underweight
        adj_target = self.target.copy()
        for ticker, prob in predictions.items():
            if prob > 0.6:
                adj_target[ticker] *= 1.2
            elif prob < 0.4:
                adj_target[ticker] *= 0.8
        
        # Re-normalize weights
        total = sum(adj_target.values())
        if total > 0:
            adj_target = {k: v / total for k, v in adj_target.items()}

        return self._compute_trade_orders(portfolio, prices, min_drift=0.01)
