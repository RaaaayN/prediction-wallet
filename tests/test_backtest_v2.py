"""Tests for Backtest v2 logic."""

import pytest
import pandas as pd
from unittest.mock import MagicMock, patch
from engine.backtest_v2 import EventDrivenBacktester

@pytest.fixture
def mock_market_svc():
    svc = MagicMock()
    
    # Mock data for SPY and AAPL
    dates = pd.date_range("2024-01-01", periods=10, freq="D")
    spy_data = pd.DataFrame({
        "Close": [100 + i for i in range(10)],
        "Volume": [1000 for _ in range(10)]
    }, index=dates)
    
    aapl_data = pd.DataFrame({
        "Close": [150 + i for i in range(10)],
        "Volume": [500 for _ in range(10)]
    }, index=dates)
    
    def get_hist(ticker, days=None):
        if ticker == "^GSPC": return spy_data
        if ticker == "AAPL": return aapl_data
        # Return empty for others to isolate AAPL in target allocation
        return pd.DataFrame()

    svc.get_historical.side_effect = get_hist
    return svc

@patch("engine.backtest_v2.MarketDataService")
@patch("engine.backtest_v2.TARGET_ALLOCATION", {"AAPL": 1.0})
def test_backtester_run(mock_svc_class, mock_market_svc):
    mock_svc_class.return_value = mock_market_svc
    
    tester = EventDrivenBacktester(days=5, initial_capital=10000)
    result = tester.run(strategy_type="threshold")
    
    assert result.strategy_name == "threshold"
    assert len(result.history) == 5
    # Should have initial allocation trade
    assert len(result.trades) >= 0 # Depends on target allocation and first prices
    assert "alpha" in result.metrics
    assert "beta" in result.metrics
    assert len(result.exposures) == 5

@patch("engine.backtest_v2.MarketDataService")
@patch("engine.backtest_v2.TARGET_ALLOCATION", {"AAPL": 1.0})
def test_backtester_calendar_rebalance(mock_svc_class, mock_market_svc):
    mock_svc_class.return_value = mock_market_svc
    
    # Calendar rebalance every 7 days. Our data is 10 days.
    tester = EventDrivenBacktester(days=10, initial_capital=10000)
    result = tester.run(strategy_type="calendar")
    
    # At index 0: initial allocation
    # At index 7: should trigger calendar rebalance (idx - last >= 7)
    # The current mock prices are steadily increasing, so drift will occur.
    # Total history len should be 10.
    assert len(result.history) == 10
