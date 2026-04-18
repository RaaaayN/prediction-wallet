"""Tests for MarketService sync to Data Lake."""

import pytest
import pandas as pd
import numpy as np
from pathlib import Path
from unittest.mock import patch
from services.market_service import MarketService
from services.data_lake_service import DataLakeService

@pytest.fixture
def temp_data_dir(tmp_path):
    # Setup directories
    (tmp_path / "profiles/balanced").mkdir(parents=True)
    return str(tmp_path)

@patch("services.market_service.MARKET_DB", "sqlite:///:memory:")
def test_market_sync_to_lake(temp_data_dir):
    # Mock MarketService to have some data in DB
    svc = MarketService(db_path=":memory:", profile_name="balanced")
    
    # Manually insert some data into the mock DB
    dates = pd.date_range("2024-01-01", periods=10)
    df = pd.DataFrame({
        "Open": [10.0]*10, "Close": [11.0]*10, "Volume": [1000]*10
    }, index=dates)
    
    with patch.object(MarketService, "_load_from_db", return_value=df):
        with patch("services.data_lake_service.DATA_DIR", temp_data_dir):
            synced = svc.sync_to_lake(["AAPL"])
            
            assert synced["AAPL"] == "synced"
            
            # Verify files in temp lake
            bronze_p = Path(temp_data_dir) / "lake/bronze/AAPL.parquet"
            silver_p = Path(temp_data_dir) / "lake/silver/AAPL.parquet"
            assert bronze_p.exists()
            assert silver_p.exists()
