"""Tests for Data Lake Service and Market syncing."""

import pytest
import pandas as pd
import numpy as np
import shutil
from pathlib import Path
from services.data_lake_service import DataLakeService
from services.market_service import MarketService

@pytest.fixture
def temp_data_dir(tmp_path):
    return str(tmp_path)

@pytest.fixture
def lake(temp_data_dir):
    return DataLakeService(base_dir=temp_data_dir)

@pytest.fixture
def sample_df():
    dates = pd.date_range("2024-01-01", periods=10)
    return pd.DataFrame({
        "Open": np.random.rand(10),
        "High": np.random.rand(10),
        "Low": np.random.rand(10),
        "Close": np.random.rand(10),
        "Volume": np.random.randint(100, 1000, 10)
    }, index=dates)

def test_save_bronze_silver(lake, sample_df):
    p1 = lake.save_bronze("AAPL", sample_df)
    p2 = lake.save_silver("AAPL", sample_df)
    
    assert Path(p1).exists()
    assert Path(p2).exists()
    
    df_loaded = pd.read_parquet(p1)
    assert len(df_loaded) == 10
    assert "Close" in df_loaded.columns

def test_save_load_gold(lake, sample_df):
    df_dict = {"AAPL": sample_df, "MSFT": sample_df}
    ds_path, data_hash = lake.save_gold("test_dataset", df_dict)
    
    assert Path(ds_path).exists()
    assert len(data_hash) == 64 # SHA256
    
    loaded_dict = lake.load_gold("test_dataset")
    assert "AAPL" in loaded_dict
    assert "MSFT" in loaded_dict
    assert len(loaded_dict["AAPL"]) == 10

def test_dataset_hash_stability(lake, sample_df):
    df_dict = {"AAPL": sample_df}
    _, hash1 = lake.save_gold("ds1", df_dict)
    _, hash2 = lake.save_gold("ds2", df_dict)
    
    # Same data should produce same hash
    assert hash1 == hash2
    
    # Different data should produce different hash
    sample_df.iloc[0, 0] += 1
    _, hash3 = lake.save_gold("ds3", {"AAPL": sample_df})
    assert hash1 != hash3
