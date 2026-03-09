"""Tests for market data and metrics modules."""

import numpy as np
import pandas as pd
import pytest

from market.metrics import PortfolioMetrics


class TestPortfolioMetrics:
    def setup_method(self):
        self.metrics = PortfolioMetrics()

        # Synthetic price series
        np.random.seed(42)
        dates = pd.date_range("2024-01-01", periods=252, freq="B")
        prices = 100 * (1 + np.random.normal(0.0005, 0.01, 252)).cumprod()
        self.prices_series = pd.Series(prices, index=dates)
        self.prices_df = pd.DataFrame({"Close": prices}, index=dates)

    def test_calculate_returns(self):
        returns = self.metrics.calculate_returns(self.prices_df)
        assert isinstance(returns, pd.DataFrame)
        assert len(returns) == len(self.prices_df) - 1
        assert returns.isna().sum().sum() == 0

    def test_calculate_volatility(self):
        returns = self.metrics.calculate_returns(self.prices_df)
        vol = self.metrics.calculate_volatility(returns["Close"], window=30)
        assert not vol.dropna().empty
        assert (vol.dropna() > 0).all()

    def test_calculate_sharpe_positive(self):
        # Simulate mostly positive returns
        returns = pd.Series(np.random.normal(0.001, 0.01, 252))
        sharpe = self.metrics.calculate_sharpe(returns, rf=0.02)
        assert isinstance(sharpe, float)

    def test_calculate_sharpe_zero_vol(self):
        returns = pd.Series([0.0] * 100)
        sharpe = self.metrics.calculate_sharpe(returns)
        assert sharpe == 0.0

    def test_calculate_drawdown(self):
        values = pd.Series([100, 110, 105, 90, 95, 100])
        result = self.metrics.calculate_drawdown(values)
        assert "max_drawdown" in result
        assert result["max_drawdown"] < 0  # drawdown is negative

    def test_max_drawdown_correct(self):
        # Peak at 110, trough at 90 → drawdown = (90-110)/110 ≈ -18.2%
        values = pd.Series([100, 110, 90])
        result = self.metrics.calculate_drawdown(values)
        assert result["max_drawdown"] == pytest.approx(-0.1818, abs=0.001)

    def test_current_drawdown(self):
        dd = self.metrics.current_drawdown(90_000, 100_000)
        assert dd == pytest.approx(-0.1, abs=0.001)

    def test_current_drawdown_zero_peak(self):
        dd = self.metrics.current_drawdown(50_000, 0)
        assert dd == 0.0

    def test_ticker_metrics_structure(self):
        m = self.metrics.ticker_metrics(self.prices_df)
        assert "last_price" in m
        assert "volatility_30d" in m
        assert "ytd_return" in m
        assert "sharpe" in m
        assert m["last_price"] > 0
        assert m["volatility_30d"] >= 0

    def test_ticker_metrics_empty_df(self):
        m = self.metrics.ticker_metrics(pd.DataFrame())
        assert m == {}

    def test_calculate_correlations(self):
        returns_df = pd.DataFrame({
            "A": np.random.normal(0, 0.01, 100),
            "B": np.random.normal(0, 0.01, 100),
        })
        corr = self.metrics.calculate_correlations(returns_df)
        assert corr.shape == (2, 2)
        assert corr.loc["A", "A"] == pytest.approx(1.0)
