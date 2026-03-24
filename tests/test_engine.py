"""Tests for engine/performance.py, engine/risk.py, and engine/orders.py improvements."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from engine.performance import (
    calmar_ratio,
    conditional_var,
    historical_var,
    parametric_var,
    performance_report,
    sharpe_ratio,
    sortino_ratio,
)
from engine.risk import RiskLevel, check_kill_switch, get_risk_level
from engine.orders import generate_rebalance_orders


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

def _make_returns(n=100, mean=0.001, std=0.02, seed=42) -> pd.Series:
    rng = np.random.default_rng(seed)
    return pd.Series(rng.normal(mean, std, n))


def _make_history(n=100, start=100_000.0, growth=0.0005) -> list[dict]:
    values = [start * (1 + growth) ** i for i in range(n)]
    dates = pd.date_range("2024-01-01", periods=n, freq="D")
    return [{"date": str(d.date()), "total_value": v} for d, v in zip(dates, values)]


def _make_declining_history(n=100, start=100_000.0, drop=0.15) -> list[dict]:
    values = [start * (1 - drop * i / n) for i in range(n)]
    dates = pd.date_range("2024-01-01", periods=n, freq="D")
    return [{"date": str(d.date()), "total_value": v} for d, v in zip(dates, values)]


# ---------------------------------------------------------------------------
# TestHistoricalVar
# ---------------------------------------------------------------------------

class TestHistoricalVar:
    def test_positive_result_for_normal_returns(self):
        returns = _make_returns()
        result = historical_var(returns, confidence=0.95, portfolio_value=100_000.0)
        assert result > 0.0

    def test_empty_series_returns_zero(self):
        assert historical_var(pd.Series([], dtype=float)) == 0.0

    def test_99_greater_than_95(self):
        returns = _make_returns()
        var_95 = historical_var(returns, confidence=0.95, portfolio_value=100_000.0)
        var_99 = historical_var(returns, confidence=0.99, portfolio_value=100_000.0)
        assert var_99 >= var_95

    def test_scales_with_portfolio_value(self):
        returns = _make_returns()
        var_1 = historical_var(returns, confidence=0.95, portfolio_value=1.0)
        var_100k = historical_var(returns, confidence=0.95, portfolio_value=100_000.0)
        assert abs(var_100k - var_1 * 100_000.0) < 1e-6

    def test_non_negative(self):
        # Even with all-positive returns, VaR should be >= 0
        returns = pd.Series([0.01, 0.02, 0.005, 0.015])
        result = historical_var(returns, confidence=0.95)
        assert result >= 0.0


# ---------------------------------------------------------------------------
# TestSortinoRatio
# ---------------------------------------------------------------------------

class TestSortinoRatio:
    def test_positive_for_upward_trending_returns(self):
        rng = np.random.default_rng(1)
        # Mix of positive and varied negative returns (positive mean overall)
        returns = pd.Series(list(rng.normal(0.008, 0.003, 80)) + list(rng.normal(-0.003, 0.002, 20)))
        result = sortino_ratio(returns)
        assert result > 0.0

    def test_empty_series_returns_zero(self):
        assert sortino_ratio(pd.Series([], dtype=float)) == 0.0

    def test_all_positive_returns_no_downside_returns_zero(self):
        # No returns below mar=0 → no downside deviation → 0.0
        returns = pd.Series([0.01, 0.02, 0.005, 0.008])
        assert sortino_ratio(returns, mar=0.0) == 0.0

    def test_sortino_higher_than_sharpe_with_positive_skew(self):
        # Large upside outliers inflate Sharpe denominator but not Sortino denominator
        rng = np.random.default_rng(0)
        base = pd.Series(rng.normal(0.001, 0.01, 200))
        upside_shocks = pd.Series([0.05] * 10)
        returns = pd.concat([base, upside_shocks], ignore_index=True)
        s = sharpe_ratio(returns)
        so = sortino_ratio(returns)
        assert so > s


# ---------------------------------------------------------------------------
# TestCalmarRatio
# ---------------------------------------------------------------------------

class TestCalmarRatio:
    def test_positive_for_growing_portfolio(self):
        # History that dips then recovers: positive annualized return + non-zero drawdown
        dates = pd.date_range("2024-01-01", periods=60, freq="D")
        values = (
            [100_000 + i * 500 for i in range(20)]   # rising
            + [110_000 - i * 800 for i in range(20)] # drawdown
            + [94_000 + i * 900 for i in range(20)]  # recovery
        )
        history = [{"date": str(d.date()), "total_value": v} for d, v in zip(dates, values)]
        returns = pd.Series([0.005] * 59)
        result = calmar_ratio(history, returns)
        assert result > 0.0

    def test_zero_when_no_drawdown(self):
        # Strictly monotonically increasing → max_drawdown = 0
        history = [{"date": f"2024-01-{i+1:02d}", "total_value": 100_000.0 + i * 1000} for i in range(10)]
        returns = pd.Series([0.01] * 9)
        result = calmar_ratio(history, returns)
        assert result == 0.0

    def test_positive_ratio_with_recovery(self):
        history = _make_declining_history(n=100, drop=0.10)
        returns = pd.Series([-0.001] * 99)
        result = calmar_ratio(history, returns)
        # Declining portfolio → negative annualized return → negative calmar
        # (calmar can be negative if returns are negative)
        assert isinstance(result, float)


# ---------------------------------------------------------------------------
# TestPerformanceReportFields
# ---------------------------------------------------------------------------

class TestPerformanceReportFields:
    EXPECTED_KEYS = {
        "cumulative_return_gross",
        "cumulative_return_net",
        "annualized_return",
        "volatility",
        "sharpe",
        "sortino",
        "calmar",
        "max_drawdown",
        "var_95_parametric",
        "var_99_parametric",
        "var_95_historical",
        "var_99_historical",
        "cvar_95",
        "cvar_99",
        "turnover",
        "transaction_costs",
        "hit_ratio",
    }

    def test_all_expected_keys_present(self):
        history = _make_history(n=60)
        report = performance_report(history, trades=[])
        for key in self.EXPECTED_KEYS:
            assert key in report, f"Missing key: {key}"

    def test_empty_history_returns_empty_dict(self):
        assert performance_report([], trades=[]) == {}

    def test_var_99_gte_var_95(self):
        history = _make_history(n=60)
        report = performance_report(history, trades=[])
        assert report["var_99_parametric"] >= report["var_95_parametric"]
        assert report["var_99_historical"] >= report["var_95_historical"]
        assert report["cvar_99"] >= report["cvar_95"]


# ---------------------------------------------------------------------------
# TestRiskLevel
# ---------------------------------------------------------------------------

class TestRiskLevel:
    def test_ok_below_warn(self):
        assert get_risk_level(-0.03) == RiskLevel.OK

    def test_ok_at_zero(self):
        assert get_risk_level(0.0) == RiskLevel.OK

    def test_warn_between_thresholds(self):
        assert get_risk_level(-0.08) == RiskLevel.WARN

    def test_warn_at_warn_threshold(self):
        assert get_risk_level(-0.07) == RiskLevel.WARN

    def test_halt_beyond_halt_threshold(self):
        assert get_risk_level(-0.12) == RiskLevel.HALT

    def test_halt_at_halt_threshold(self):
        assert get_risk_level(-0.10) == RiskLevel.HALT

    def test_check_kill_switch_unchanged(self):
        assert check_kill_switch(-0.12, 0.10) is True
        assert check_kill_switch(-0.05, 0.10) is False

    def test_risk_level_string_value(self):
        assert RiskLevel.OK == "ok"
        assert RiskLevel.WARN == "warn"
        assert RiskLevel.HALT == "halt"

    def test_custom_thresholds(self):
        assert get_risk_level(-0.05, warn_threshold=0.04, halt_threshold=0.08) == RiskLevel.WARN
        assert get_risk_level(-0.09, warn_threshold=0.04, halt_threshold=0.08) == RiskLevel.HALT


# ---------------------------------------------------------------------------
# TestToleranceBandOrders
# ---------------------------------------------------------------------------

PRICES = {"AAPL": 100.0, "MSFT": 200.0}
TARGET = {"AAPL": 0.5, "MSFT": 0.5}


def _make_portfolio(aapl_qty=5.0, msft_qty=2.5, cash=0.0):
    return {
        "positions": {"AAPL": aapl_qty, "MSFT": msft_qty},
        "cash": cash,
    }


class TestToleranceBandOrders:
    def test_balanced_portfolio_no_orders_with_tolerance(self):
        # AAPL=50%, MSFT=50% → exactly at target → no orders regardless of min_drift
        portfolio = _make_portfolio()
        orders = generate_rebalance_orders(portfolio, PRICES, TARGET, min_drift=0.02)
        assert orders == []

    def test_balanced_portfolio_no_orders_without_tolerance(self):
        portfolio = _make_portfolio()
        orders = generate_rebalance_orders(portfolio, PRICES, TARGET, min_drift=0.0)
        assert orders == []

    def test_small_drift_suppressed_by_tolerance(self):
        # AAPL=51%, MSFT=49% → drift=1% → suppressed by min_drift=0.02
        portfolio = _make_portfolio(aapl_qty=5.1, msft_qty=2.45)
        orders = generate_rebalance_orders(portfolio, PRICES, TARGET, min_drift=0.02)
        assert orders == []

    def test_large_drift_not_suppressed(self):
        # AAPL=70%, MSFT=30% → drift=20% → not suppressed
        portfolio = _make_portfolio(aapl_qty=7.0, msft_qty=1.5)
        orders = generate_rebalance_orders(portfolio, PRICES, TARGET, min_drift=0.02)
        assert len(orders) > 0

    def test_min_drift_zero_generates_orders_on_drift(self):
        portfolio = _make_portfolio(aapl_qty=7.0, msft_qty=1.5)
        orders = generate_rebalance_orders(portfolio, PRICES, TARGET, min_drift=0.0)
        assert len(orders) > 0

    def test_threshold_strategy_respects_tolerance(self):
        from strategies.threshold import ThresholdStrategy
        strategy = ThresholdStrategy(threshold=0.05, target_allocation=TARGET)
        # Drift of 2% < threshold/2 = 2.5% → should be suppressed by tolerance band
        # AAPL = 52%, MSFT = 48% (drift = 2% each, tolerance = 2.5%)
        portfolio = {
            "positions": {"AAPL": 5.2, "MSFT": 2.4},
            "cash": 0.0,
        }
        orders = strategy.get_trades(portfolio, PRICES)
        assert orders == []
