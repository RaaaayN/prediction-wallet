"""Feature Engineering Service for Quantitative ML."""

from __future__ import annotations
import pandas as pd
import numpy as np
from pathlib import Path
from services.data_lake_service import DataLakeService
from market.fetcher import add_technical_indicators

class FeatureService:
    def __init__(self):
        self.lake = DataLakeService()

    def prepare_training_data(self, ticker: str, days: int = 365) -> pd.DataFrame:
        """Fetch data and create features + labels for ML training using Alpha Factory."""
        from market.fetcher import MarketDataService
        from ml.alpha_factory import compute_alpha_features, compute_target_label
        
        mkt = MarketDataService()
        df = mkt.get_historical(ticker, days=days)
        if df is None or df.empty:
            return pd.DataFrame()
            
        # 1. Base Technical Indicators (needed for factory)
        df = add_technical_indicators(df)
        
        # 2. Institutional Alpha Factory (USER DEFINED FORMULAS)
        df = compute_alpha_features(df)
        
        # 3. Labeling (USER DEFINED TARGET)
        df = compute_target_label(df)
        
        return df.dropna()

    def create_gold_bundle(self, tickers: list[str], dataset_name: str):
        """Create a multi-ticker dataset ready for training."""
        bundle = {}
        for t in tickers:
            df = self.prepare_training_data(t)
            if not df.empty:
                bundle[t] = df
        
        return self.lake.save_gold(dataset_name, bundle)
