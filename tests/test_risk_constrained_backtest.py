"""Tests for risk-constrained backtesting logic."""

import pytest
import pandas as pd
from unittest.mock import MagicMock, patch
from engine.backtest_v2 import EventDrivenBacktester

@pytest.fixture
def mock_market_svc():
    svc = MagicMock()
    dates = pd.date_range("2024-01-01", periods=10, freq="D")
    # Add noise to prices to avoid identical X values in regression
    spy_data = pd.DataFrame({"Close": [100 + i*0.1 for i in range(10)], "Volume": [1000]*10}, index=dates)
    aapl_data = pd.DataFrame({"Close": [150 + i*0.2 for i in range(10)], "Volume": [500]*10}, index=dates)
    
    def get_hist(ticker, days=None):
        if ticker == "^GSPC": return spy_data
        if ticker == "AAPL": return aapl_data
        return pd.DataFrame()

    svc.get_historical.side_effect = get_hist
    return svc

@patch("engine.backtest_v2.MarketDataService")
@patch("engine.backtest_v2.TARGET_ALLOCATION", {"AAPL": 0.5}) # Target 50%
@patch("engine.backtest_v2.SECTOR_MAP", {"AAPL": "tech"})
def test_backtester_single_ticker_cap(mock_svc_class, mock_market_svc):
    mock_svc_class.return_value = mock_market_svc
    
    # Set single ticker cap to 20%
    tester = EventDrivenBacktester(
        days=5, initial_capital=10000, max_single_ticker=0.20
    )
    result = tester.run(strategy_type="threshold")
    
    # Check if AAPL weight is actually <= 20%
    last_exp = result.exposures[-1]
    aapl_weight = last_exp["single_name_concentration"].get("AAPL", 0.0)
    assert aapl_weight <= 0.20 + 0.01 # Small buffer for price movement

@patch("engine.backtest_v2.MarketDataService")
@patch("engine.backtest_v2.TARGET_ALLOCATION", {"AAPL": 0.8}) # Target 80%
@patch("engine.backtest_v2.SECTOR_MAP", {"AAPL": "tech"})
def test_backtester_sector_cap(mock_svc_class, mock_market_svc):
    mock_svc_class.return_value = mock_market_svc
    
    # Set sector cap to 30%, AAPL is in tech
    tester = EventDrivenBacktester(
        days=5, initial_capital=10000, max_sector_gross=0.30, max_single_ticker=1.0
    )
    result = tester.run(strategy_type="threshold")
    
    last_exp = result.exposures[-1]
    tech_weight = last_exp["sector_gross"].get("tech", 0.0)
    assert tech_weight <= 0.30 + 0.01
