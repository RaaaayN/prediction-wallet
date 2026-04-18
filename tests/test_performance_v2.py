"""Tests for new Phase 1 performance metrics."""

import pandas as pd
import numpy as np
import pytest
from engine.performance import compute_liquidity_risk, compute_alpha_beta

def test_compute_liquidity_risk():
    # 10,000 shares, 100,000 ADV, 10% participation -> 1 day
    assert compute_liquidity_risk(10000, 100000, 0.1) == 1.0
    
    # 20,000 shares, 100,000 ADV, 10% participation -> 2 days
    assert compute_liquidity_risk(20000, 100000, 0.1) == 2.0
    
    # Zero volume
    assert compute_liquidity_risk(10000, 0, 0.1) == float("inf")

def test_compute_alpha_beta():
    # Benchmark returns: constant 1% daily
    # Portfolio returns: constant 2% daily
    # No risk-free rate
    dates = pd.date_range("2024-01-01", periods=10)
    bm_ret = pd.Series(0.01, index=dates)
    port_ret = pd.Series(0.02, index=dates)
    
    # y = port_ret, x = bm_ret
    # y = alpha + beta * x
    # 0.02 = alpha + beta * 0.01
    # If we have perfect linear relationship with slope 2 and intercept 0:
    # beta = 2, alpha = 0
    # But wait, if port_ret is ALWAYS 0.02 and bm_ret is ALWAYS 0.01, stats.linregress might be unstable
    # Let's add some noise or use a clear slope
    
    x = pd.Series([0.01, -0.01, 0.02, -0.02], index=dates[:4])
    y = 0.0001 + 1.5 * x # alpha_daily = 0.0001, beta = 1.5
    
    alpha, beta = compute_alpha_beta(y, x)
    
    assert beta == pytest.approx(1.5)
    assert alpha == pytest.approx(0.0001 * 252)

def test_compute_alpha_beta_empty():
    alpha, beta = compute_alpha_beta(pd.Series(dtype=float), pd.Series(dtype=float))
    assert alpha == 0.0
    assert beta == 1.0
