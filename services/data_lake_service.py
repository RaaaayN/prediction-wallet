"""Institutional Data Lake Service for Parquet storage and versioning."""

from __future__ import annotations

import os
import hashlib
import pandas as pd
from pathlib import Path
from datetime import datetime
from typing import Optional, List, Dict, Tuple

from config import DATA_DIR

class DataLakeService:
    """Manages Bronze/Silver/Gold data layers using Parquet."""

    def __init__(self, base_dir: Optional[str] = None):
        self.base_dir = base_dir or DATA_DIR
        self.base_path = Path(self.base_dir) / "lake"
        self.bronze_path = self.base_path / "bronze"
        self.silver_path = self.base_path / "silver"
        self.gold_path = self.base_path / "gold"
        
        # Ensure directories exist
        for p in [self.bronze_path, self.silver_path, self.gold_path]:
            p.mkdir(parents=True, exist_ok=True)

    def save_bronze(self, ticker: str, df: pd.DataFrame) -> str:
        """Save raw data to Bronze layer."""
        path = self.bronze_path / f"{ticker}.parquet"
        df.to_parquet(path, index=True)
        return str(path)

    def save_silver(self, ticker: str, df: pd.DataFrame) -> str:
        """Save cleaned data with technical indicators to Silver layer."""
        path = self.silver_path / f"{ticker}.parquet"
        df.to_parquet(path, index=True)
        return str(path)

    def save_gold(self, dataset_name: str, df_dict: Dict[str, pd.DataFrame]) -> Tuple[str, str]:
        """Save a multi-ticker strategy-ready dataset to Gold layer."""
        # Create a directory for the dataset
        ds_path = self.gold_path / dataset_name
        ds_path.mkdir(parents=True, exist_ok=True)
        
        # Save each ticker
        for ticker, df in df_dict.items():
            df.to_parquet(ds_path / f"{ticker}.parquet", index=True)
            
        # Compute a combined hash of the dataset
        data_hash = self._compute_dataset_hash(ds_path)
        return str(ds_path), data_hash

    def load_gold(self, dataset_name: str) -> Dict[str, pd.DataFrame]:
        """Load a strategy-ready dataset from Gold layer."""
        ds_path = self.gold_path / dataset_name
        if not ds_path.exists():
            return {}
        
        results = {}
        for p in ds_path.glob("*.parquet"):
            ticker = p.stem
            results[ticker] = pd.read_parquet(p)
        return results

    def _compute_dataset_hash(self, ds_path: Path) -> str:
        """Compute a SHA256 hash of all files in a dataset directory."""
        hasher = hashlib.sha256()
        for p in sorted(ds_path.glob("*.parquet")):
            with open(p, "rb") as f:
                while chunk := f.read(8192):
                    hasher.update(chunk)
        return hasher.hexdigest()

    def list_gold_datasets(self) -> List[str]:
        """List available datasets in Gold layer."""
        return [d.name for d in self.gold_path.iterdir() if d.is_dir()]
