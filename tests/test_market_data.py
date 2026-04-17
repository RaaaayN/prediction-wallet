"""Tests for market data and metrics modules."""

import numpy as np
import pandas as pd
import pytest

from engine.monte_carlo import run_monte_carlo
from engine.regime import detect_regime
from market.metrics import PortfolioMetrics
from services.market_service import MarketService, add_technical_indicators


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


def test_monte_carlo_supports_flat_position_format():
    portfolio = {"positions": {"AAPL": 10.0, "MSFT": 5.0}, "cash": 1000.0}
    prices = {"AAPL": 100.0, "MSFT": 200.0}
    historical_returns = {
        "AAPL": [0.001] * 60,
        "MSFT": [0.0005] * 60,
    }

    result = run_monte_carlo(portfolio, prices, historical_returns, n_paths=200, horizon=20)

    assert result["initial_value"] == pytest.approx(3000.0)
    assert result["confidence_intervals"]["sharpe"]["p95"] >= result["confidence_intervals"]["sharpe"]["p5"]


def test_regime_detection_exposes_vol_percentile():
    base = np.random.normal(0.0005, 0.01, 120)
    stressed = np.concatenate([base[:90], np.random.normal(-0.002, 0.03, 30)])
    returns_df = pd.DataFrame({"AAPL": stressed, "MSFT": stressed * 0.9})

    regime = detect_regime(returns_df)

    assert "vol_percentile" in regime
    assert regime["regime"] in {"bull", "bear", "normal", "risk_off"}


@pytest.mark.asyncio
async def test_async_market_fetch_returns_latency_metrics():
    class AsyncFakeMarketService(MarketService):
        def _needs_refresh(self, ticker: str) -> bool:
            return True

        def _download(self, ticker: str, period: str):
            idx = pd.date_range("2024-01-01", periods=40, freq="B")
            return pd.DataFrame({"Close": np.linspace(100, 110, len(idx))}, index=idx)

        def _save_to_db(self, df: pd.DataFrame, ticker: str) -> None:
            return None

        def _record_refresh(self, ticker: str, success: bool, error: str) -> None:
            return None

    service = AsyncFakeMarketService()
    frames, latencies = await service.fetch_and_store_async(["AAPL", "MSFT"], period="3mo")

    assert set(frames) == {"AAPL", "MSFT"}
    assert set(latencies) == {"AAPL", "MSFT"}
    assert all(latency >= 0 for latency in latencies.values())


def test_add_technical_indicators_handles_duplicate_close_columns():
    dates = pd.date_range("2024-01-01", periods=40, freq="B")
    df = pd.DataFrame(
        np.column_stack([
            np.linspace(100, 120, len(dates)),
            np.linspace(100, 120, len(dates)),
            np.linspace(101, 121, len(dates)),
        ]),
        index=dates,
        columns=["Close", "Close", "Open"],
    )

    enriched = add_technical_indicators(df)

    assert "SMA20" in enriched.columns
    assert "EMA20" in enriched.columns
    assert enriched["SMA20"].dropna().shape[0] > 0


def test_add_technical_indicators_handles_multiindex_ticker_layout():
    dates = pd.date_range("2024-01-01", periods=40, freq="B")
    cols = pd.MultiIndex.from_tuples([
        ("TEST", "Open"),
        ("TEST", "High"),
        ("TEST", "Low"),
        ("TEST", "Close"),
        ("TEST", "Volume"),
    ])
    df = pd.DataFrame(
        np.column_stack([
            np.linspace(99, 119, len(dates)),
            np.linspace(101, 121, len(dates)),
            np.linspace(98, 118, len(dates)),
            np.linspace(100, 120, len(dates)),
            np.linspace(1000, 2000, len(dates)),
        ]),
        index=dates,
        columns=cols,
    )

    enriched = add_technical_indicators(df)

    assert "Close" in enriched.columns
    assert "MACD" in enriched.columns
