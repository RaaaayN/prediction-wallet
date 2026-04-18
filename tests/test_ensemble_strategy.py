"""Tests for Ensemble Strategy logic."""

import pytest
from strategies.ensemble import EnsembleStrategy

@pytest.fixture
def target_alloc():
    return {"AAPL": 0.5}

def test_ensemble_no_sentiment(target_alloc):
    # AAPL is 40% (underweight), target 50%. Drift 10% > 5% threshold.
    # No sentiment provided (defaults to 0.0)
    strat = EnsembleStrategy(target_alloc, drift_threshold=0.05)
    portfolio = {"cash": 60000, "positions": {"AAPL": 266.67}} # ~40k at $150
    prices = {"AAPL": 150.0}
    
    trades = strat.get_trades(portfolio, prices, {})
    assert len(trades) == 1
    assert trades[0]["ticker"] == "AAPL"
    assert trades[0]["action"] == "buy"
    # Should target full 50% rebalance (diff is 10k -> 66.67 shares)
    assert trades[0]["quantity"] == pytest.approx(66.67, rel=0.01)

def test_ensemble_negative_sentiment_blocks_buy(target_alloc):
    # AAPL underweight, but sentiment is extremely negative (-0.9)
    # Adjustment factor = max(0, 1 + -0.9 * 0.2) = 0.82
    # So buy size should be reduced.
    strat = EnsembleStrategy(target_alloc, drift_threshold=0.05, sentiment_weight=0.5)
    portfolio = {"cash": 60000, "positions": {"AAPL": 266.67}}
    prices = {"AAPL": 150.0}
    sentiment = {"AAPL": -0.8}
    
    trades = strat.get_trades(portfolio, prices, sentiment)
    assert len(trades) == 1
    # Base diff is 10000. Adj factor = 1 + (-0.8 * 0.5) = 0.6
    # Adj diff = 6000 -> 40 shares.
    assert trades[0]["quantity"] == pytest.approx(40.0, rel=0.01)

def test_ensemble_positive_sentiment_on_sell(target_alloc):
    # AAPL is 60% (overweight), but sentiment is positive (0.8)
    # Adjustment factor = 1 - (0.8 * 0.5) = 0.6
    # Should reduce sell size (holding onto winner longer)
    strat = EnsembleStrategy(target_alloc, drift_threshold=0.05, sentiment_weight=0.5)
    portfolio = {"cash": 40000, "positions": {"AAPL": 400.0}} # 60k
    prices = {"AAPL": 150.0}
    sentiment = {"AAPL": 0.8}
    
    trades = strat.get_trades(portfolio, prices, sentiment)
    assert len(trades) == 1
    assert trades[0]["action"] == "sell"
    # Base diff is -10000. Adj diff = -6000 -> 40 shares.
    assert trades[0]["quantity"] == pytest.approx(40.0, rel=0.01)
