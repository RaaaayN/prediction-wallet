"""Tests for advanced risk metrics in risk.py."""

import pytest
import pandas as pd
import numpy as np
from engine.risk import parametric_var, historical_var, conditional_var, correlation_adjusted_var

def test_parametric_var():
    # Mean 0, Std 1%, 95% confidence -> ~1.645%
    returns = pd.Series([0.01, -0.01] * 50) # Std is 0.01
    var = parametric_var(returns, confidence=0.95, portfolio_value=100000)
    assert var > 0
    assert var == pytest.approx(100000 * 1.645 * returns.std(), rel=0.01)

def test_correlation_adjusted_var():
    dates = pd.date_range("2024-01-01", periods=10)
    # Perfectly correlated assets
    returns_df = pd.DataFrame({
        "AAPL": [0.01] * 10,
        "MSFT": [0.01] * 10
    }, index=dates)
    
    weights = {"AAPL": 0.5, "MSFT": 0.5}
    var = correlation_adjusted_var(weights, returns_df, confidence=0.95, portfolio_value=100000)
    # Since std is 0, var should be 0 (or close to 0 due to assumptions)
    assert var == pytest.approx(0.0, abs=1e-10)
    
    # Adding volatility
    returns_df.iloc[0, 0] = -0.05
    returns_df.iloc[1, 1] = -0.05
    var_vol = correlation_adjusted_var(weights, returns_df, confidence=0.95, portfolio_value=100000)
    assert var_vol > 0

def test_conditional_var():
    returns = pd.Series([-0.10, -0.05, 0.0, 0.05, 0.10])
    # 80% confidence -> cutoff is -0.10 (lowest 20%)
    cvar = conditional_var(returns, confidence=0.80, portfolio_value=100)
    assert cvar == 10.0 # Mean of returns <= -0.10 is -0.10, so 10% of 100
