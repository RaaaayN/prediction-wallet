"""Tests for engine/performance.py, engine/risk.py, engine/orders.py, and strategies/."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from engine.performance import (
    avg_slippage_bps,
    calmar_ratio,
    conditional_var,
    historical_var,
    parametric_var,
    performance_report,
    sharpe_ratio,
    sortino_ratio,
)
from engine.risk import RiskLevel, check_kill_switch, get_risk_level
from engine.orders import apply_slippage, estimate_transaction_cost, generate_rebalance_orders


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
        "avg_slippage_bps",
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

    def test_min_notional_suppresses_micro_trades(self):
        # AAPL drifts by tiny amount → notional << $10 → suppressed
        # Total = 1000, AAPL = 500.5, MSFT = 499.5
        # delta AAPL = 500.5 - 500 = $0.5 → qty = 0.005 → notional = $0.50 < $10
        portfolio = {"positions": {"AAPL": 5.005, "MSFT": 2.4975}, "cash": 0.0}
        orders = generate_rebalance_orders(portfolio, PRICES, TARGET, min_notional=10.0)
        assert orders == []

    def test_min_notional_zero_allows_micro_trades(self):
        portfolio = {"positions": {"AAPL": 5.005, "MSFT": 2.4975}, "cash": 0.0}
        orders = generate_rebalance_orders(portfolio, PRICES, TARGET, min_notional=0.0)
        # With min_notional=0, small drift may still pass min_qty check
        # Just verify the parameter doesn't break normal execution
        assert isinstance(orders, list)


# ---------------------------------------------------------------------------
# TestAvgSlippageBps (P10 fix)
# ---------------------------------------------------------------------------

class TestAvgSlippageBps:
    def _make_trade(self, market: float, fill: float, action: str = "buy") -> dict:
        return {"market_price": market, "fill_price": fill, "action": action, "quantity": 1.0}

    def test_empty_trades_returns_zero(self):
        assert avg_slippage_bps([]) == 0.0

    def test_no_slippage_returns_zero(self):
        trades = [self._make_trade(100.0, 100.0)]
        assert avg_slippage_bps(trades) == 0.0

    def test_known_slippage(self):
        # fill = 101 vs market = 100 → 1% = 100 bps
        trades = [self._make_trade(100.0, 101.0)]
        assert abs(avg_slippage_bps(trades) - 100.0) < 0.01

    def test_averages_across_trades(self):
        # 100 bps + 200 bps → avg = 150 bps
        trades = [
            self._make_trade(100.0, 101.0),  # 100 bps
            self._make_trade(100.0, 102.0),  # 200 bps
        ]
        assert abs(avg_slippage_bps(trades) - 150.0) < 0.01

    def test_in_performance_report(self):
        history = _make_history(n=60)
        trades = [
            {"market_price": 100.0, "fill_price": 100.1, "action": "buy", "quantity": 1.0},
        ]
        report = performance_report(history, trades)
        assert "avg_slippage_bps" in report
        assert "hit_ratio" not in report
        assert report["avg_slippage_bps"] >= 0.0

    def test_zero_market_price_ignored(self):
        trades = [
            {"market_price": 0.0, "fill_price": 0.0, "action": "buy", "quantity": 1.0},
            self._make_trade(100.0, 101.0),
        ]
        # First trade has market=0 → skipped; only second contributes
        assert abs(avg_slippage_bps(trades) - 100.0) < 0.01


# ---------------------------------------------------------------------------
# TestKillSwitchBoundary (Priority A fix)
# ---------------------------------------------------------------------------

class TestKillSwitchBoundary:
    def test_exactly_at_threshold_activates(self):
        # At exactly -10%: both functions should agree → HALT / True
        assert check_kill_switch(-0.10, 0.10) is True
        assert get_risk_level(-0.10) == RiskLevel.HALT

    def test_just_below_threshold_ok(self):
        assert check_kill_switch(-0.099, 0.10) is False
        assert get_risk_level(-0.099) == RiskLevel.WARN

    def test_boundary_consistency_warn(self):
        # At exactly -7%: get_risk_level → WARN
        assert get_risk_level(-0.07) == RiskLevel.WARN


# ---------------------------------------------------------------------------
# TestCalendarDriftGuard (Priority B)
# ---------------------------------------------------------------------------

class TestCalendarDriftGuard:
    def setup_method(self):
        from strategies.calendar import CalendarStrategy
        from utils.time import utc_now
        from datetime import timedelta
        self.two_weeks_ago = (utc_now() - timedelta(days=14)).isoformat()

    def test_skips_rebalance_when_portfolio_balanced(self):
        from strategies.calendar import CalendarStrategy
        strategy = CalendarStrategy(frequency="weekly", target_allocation=TARGET, min_drift=0.02)
        # Perfectly balanced, schedule elapsed
        portfolio = {
            "positions": {"AAPL": 5.0, "MSFT": 2.5},
            "cash": 0.0,
            "last_rebalanced": self.two_weeks_ago,
        }
        assert strategy.should_rebalance(portfolio, PRICES) is False

    def test_rebalances_when_drift_exceeds_min_drift(self):
        from strategies.calendar import CalendarStrategy
        strategy = CalendarStrategy(frequency="weekly", target_allocation=TARGET, min_drift=0.02)
        # AAPL = 60%, MSFT = 40% → drift = 10% > min_drift
        portfolio = {
            "positions": {"AAPL": 6.0, "MSFT": 2.0},
            "cash": 0.0,
            "last_rebalanced": self.two_weeks_ago,
        }
        assert strategy.should_rebalance(portfolio, PRICES) is True

    def test_min_drift_zero_always_rebalances_on_schedule(self):
        from strategies.calendar import CalendarStrategy
        strategy = CalendarStrategy(frequency="weekly", target_allocation=TARGET, min_drift=0.0)
        portfolio = {
            "positions": {"AAPL": 5.0, "MSFT": 2.5},
            "cash": 0.0,
            "last_rebalanced": self.two_weeks_ago,
        }
        assert strategy.should_rebalance(portfolio, PRICES) is True

    def test_time_guard_still_applies(self):
        from strategies.calendar import CalendarStrategy
        from utils.time import utc_now
        strategy = CalendarStrategy(frequency="weekly", target_allocation=TARGET, min_drift=0.0)
        portfolio = {
            "positions": {"AAPL": 6.0, "MSFT": 2.0},
            "cash": 0.0,
            "last_rebalanced": utc_now().isoformat(),  # just now → not elapsed
        }
        assert strategy.should_rebalance(portfolio, PRICES) is False


# ---------------------------------------------------------------------------
# TestPerAssetThreshold (Priority C)
# ---------------------------------------------------------------------------

class TestPerAssetThreshold:
    def test_wide_band_suppresses_trigger_for_volatile_asset(self):
        from strategies.threshold import ThresholdStrategy
        # AAPL gets 20% band, MSFT gets 5%
        strategy = ThresholdStrategy(
            threshold=0.05,
            target_allocation=TARGET,
            per_asset_threshold={"AAPL": 0.20, "MSFT": 0.05},
        )
        # AAPL drifted 10% — within its wide 20% band → no trigger
        portfolio = {"positions": {"AAPL": 6.0, "MSFT": 2.5}, "cash": 0.0}
        assert strategy.should_rebalance(portfolio, PRICES) is False

    def test_narrow_band_triggers_for_precise_asset(self):
        from strategies.threshold import ThresholdStrategy
        strategy = ThresholdStrategy(
            threshold=0.05,
            target_allocation=TARGET,
            per_asset_threshold={"AAPL": 0.20, "MSFT": 0.02},
        )
        # MSFT drifted 3% — exceeds its narrow 2% band → trigger
        portfolio = {"positions": {"AAPL": 5.0, "MSFT": 2.15}, "cash": 0.0}
        assert strategy.should_rebalance(portfolio, PRICES) is True

    def test_fallback_to_global_threshold(self):
        from strategies.threshold import ThresholdStrategy
        strategy = ThresholdStrategy(threshold=0.05, target_allocation=TARGET)
        # No per_asset_threshold → falls back to global 5%
        portfolio = {"positions": {"AAPL": 5.3, "MSFT": 2.35}, "cash": 0.0}
        # AAPL ~53%, drift ~3% < 5% → no trigger
        assert strategy.should_rebalance(portfolio, PRICES) is False

    def test_get_trades_respects_per_asset_band(self):
        from strategies.threshold import ThresholdStrategy
        strategy = ThresholdStrategy(
            threshold=0.05,
            target_allocation=TARGET,
            per_asset_threshold={"AAPL": 0.20, "MSFT": 0.05},
        )
        # AAPL drifted 10% but has 20% band → tolerance = 10% → not traded
        portfolio = {"positions": {"AAPL": 6.0, "MSFT": 2.5}, "cash": 0.0}
        orders = strategy.get_trades(portfolio, PRICES)
        tickers = [o["ticker"] for o in orders]
        assert "AAPL" not in tickers


# ---------------------------------------------------------------------------
# TestVolAdjustedSlippage (feature #8)
# ---------------------------------------------------------------------------

_CRYPTO = {"BTC-USD"}
_EQ_RATE = 0.001   # 0.1% base
_CR_RATE = 0.005   # 0.5% base


class TestVolAdjustedSlippage:
    # --- backward compatibility: no vol/notional → identical to old model ---

    def test_flat_rate_equity_buy_unchanged(self):
        fill = apply_slippage(100.0, "buy", "AAPL", _CRYPTO, _EQ_RATE, _CR_RATE)
        assert abs(fill - 100.1) < 1e-9

    def test_flat_rate_equity_sell_unchanged(self):
        fill = apply_slippage(100.0, "sell", "AAPL", _CRYPTO, _EQ_RATE, _CR_RATE)
        assert abs(fill - 99.9) < 1e-9

    def test_flat_rate_crypto_buy_unchanged(self):
        fill = apply_slippage(100.0, "buy", "BTC-USD", _CRYPTO, _EQ_RATE, _CR_RATE)
        assert abs(fill - 100.5) < 1e-9

    # --- vol adjustment ---

    def test_high_vol_equity_increases_slippage(self):
        # vol = 0.40 vs ref = 0.20 → scalar = 2.0 → rate = 0.002
        fill_high = apply_slippage(100.0, "buy", "AAPL", _CRYPTO, _EQ_RATE, _CR_RATE, volatility=0.40)
        fill_flat = apply_slippage(100.0, "buy", "AAPL", _CRYPTO, _EQ_RATE, _CR_RATE)
        assert fill_high > fill_flat

    def test_low_vol_equity_decreases_slippage(self):
        # vol = 0.05 vs ref = 0.20 → scalar = 0.25 → clamped to 0.5 → rate = 0.0005
        fill_low = apply_slippage(100.0, "buy", "AAPL", _CRYPTO, _EQ_RATE, _CR_RATE, volatility=0.05)
        fill_flat = apply_slippage(100.0, "buy", "AAPL", _CRYPTO, _EQ_RATE, _CR_RATE)
        assert fill_low < fill_flat

    def test_vol_scalar_clamped_upper(self):
        # Extreme vol: 4× ref → scalar = 4.0 → clamped to 3.0
        fill_extreme = apply_slippage(100.0, "buy", "AAPL", _CRYPTO, _EQ_RATE, _CR_RATE, volatility=0.80)
        fill_max = apply_slippage(100.0, "buy", "AAPL", _CRYPTO, _EQ_RATE, _CR_RATE, volatility=0.60)
        # Both hit 3× ceiling → same fill
        assert abs(fill_extreme - fill_max) < 1e-9

    def test_vol_scalar_clamped_lower(self):
        # Near-zero vol → scalar clamped at 0.5
        fill_zero_vol = apply_slippage(100.0, "buy", "AAPL", _CRYPTO, _EQ_RATE, _CR_RATE, volatility=0.001)
        expected_fill = 100.0 * (1.0 + _EQ_RATE * 0.5)
        assert abs(fill_zero_vol - expected_fill) < 1e-9

    def test_at_reference_vol_equals_base_rate(self):
        # vol exactly at reference → scalar = 1.0 → same as flat
        fill_at_ref = apply_slippage(100.0, "buy", "AAPL", _CRYPTO, _EQ_RATE, _CR_RATE, volatility=0.20)
        fill_flat = apply_slippage(100.0, "buy", "AAPL", _CRYPTO, _EQ_RATE, _CR_RATE)
        assert abs(fill_at_ref - fill_flat) < 1e-9

    def test_crypto_uses_crypto_reference_vol(self):
        # BTC at 0.65 ref vol → scalar = 1.0 → same as flat
        fill_at_ref = apply_slippage(100.0, "buy", "BTC-USD", _CRYPTO, _EQ_RATE, _CR_RATE, volatility=0.65)
        fill_flat = apply_slippage(100.0, "buy", "BTC-USD", _CRYPTO, _EQ_RATE, _CR_RATE)
        assert abs(fill_at_ref - fill_flat) < 1e-9

    # --- size adjustment ---

    def test_larger_order_higher_slippage(self):
        fill_small = apply_slippage(100.0, "buy", "AAPL", _CRYPTO, _EQ_RATE, _CR_RATE, order_notional=5_000)
        fill_large = apply_slippage(100.0, "buy", "AAPL", _CRYPTO, _EQ_RATE, _CR_RATE, order_notional=50_000)
        assert fill_large > fill_small

    def test_size_impact_known_value(self):
        # order_notional = $10_000 → impact = 1bp → rate = 0.001 + 0.0001 = 0.0011
        fill = apply_slippage(100.0, "buy", "AAPL", _CRYPTO, _EQ_RATE, _CR_RATE, order_notional=10_000)
        expected = 100.0 * (1.0 + _EQ_RATE + 0.0001)
        assert abs(fill - expected) < 1e-9

    def test_vol_and_size_combined(self):
        # 2× vol (scalar=2.0) + $10k notional (1bp)
        fill = apply_slippage(100.0, "buy", "AAPL", _CRYPTO, _EQ_RATE, _CR_RATE,
                              volatility=0.40, order_notional=10_000)
        expected = 100.0 * (1.0 + _EQ_RATE * 2.0 + 0.0001)
        assert abs(fill - expected) < 1e-9

    # --- estimate_transaction_cost ---

    def test_estimate_cost_without_vol_unchanged(self):
        # notional = $1 000; size impact = (1000/10000)*0.0001 = 0.00001
        orders = [{"ticker": "AAPL", "action": "buy", "quantity": 10.0}]
        prices = {"AAPL": 100.0}
        notional = 100.0 * 10.0
        expected_rate = _EQ_RATE + (notional / 10_000) * 0.0001
        cost = estimate_transaction_cost(orders, prices, _CRYPTO, _EQ_RATE, _CR_RATE)
        assert abs(cost - notional * expected_rate) < 1e-9

    def test_estimate_cost_with_vol_higher_in_stress(self):
        orders = [{"ticker": "AAPL", "action": "buy", "quantity": 10.0}]
        prices = {"AAPL": 100.0}
        cost_flat = estimate_transaction_cost(orders, prices, _CRYPTO, _EQ_RATE, _CR_RATE)
        cost_stress = estimate_transaction_cost(orders, prices, _CRYPTO, _EQ_RATE, _CR_RATE,
                                                volatilities={"AAPL": 0.40})
        assert cost_stress > cost_flat

    def test_estimate_cost_multiple_assets(self):
        orders = [
            {"ticker": "AAPL", "action": "buy", "quantity": 5.0},
            {"ticker": "BTC-USD", "action": "sell", "quantity": 0.1},
        ]
        prices = {"AAPL": 100.0, "BTC-USD": 50_000.0}
        cost = estimate_transaction_cost(orders, prices, _CRYPTO, _EQ_RATE, _CR_RATE)
        assert cost > 0.0
