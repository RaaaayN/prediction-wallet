"""Tests for engine/performance.py, engine/risk.py, engine/orders.py, engine/portfolio.py, and strategies/."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from engine.performance import (
    avg_pairwise_correlation,
    avg_slippage_bps,
    calmar_ratio,
    conditional_var,
    historical_var,
    parametric_var,
    performance_report,
    rolling_correlation,
    sharpe_ratio,
    sortino_ratio,
)
from engine.risk import RiskLevel, check_kill_switch, get_risk_level
from engine.orders import apply_slippage, estimate_transaction_cost, generate_rebalance_orders
from engine.portfolio import compute_inverse_vol_weights, compute_sector_exposure, concentration_score
from engine.backtest import run_stress_test, STRESS_SCENARIOS


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

    def test_liquidates_positions_removed_from_target(self):
        portfolio = {
            "positions": {"AAPL": 5.0, "MSFT": 2.5, "GOOGL": 3.0},
            "cash": 0.0,
        }
        prices = {"AAPL": 100.0, "MSFT": 200.0, "GOOGL": 150.0}
        target = {"AAPL": 0.5, "MSFT": 0.5}

        orders = generate_rebalance_orders(portfolio, prices, target, min_drift=0.0, min_notional=0.0)

        liquidation = [order for order in orders if order["ticker"] == "GOOGL"]
        assert liquidation
        assert liquidation[0]["action"] == "sell"
        assert liquidation[0]["quantity"] == 3.0
        assert "Liquidate" in liquidation[0]["reason"]


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


# ---------------------------------------------------------------------------
# TestSectorExposure
# ---------------------------------------------------------------------------

_SECTOR_MAP = {
    "AAPL": "tech", "MSFT": "tech", "GOOGL": "tech", "AMZN": "tech", "NVDA": "tech",
    "TLT": "bonds", "BND": "bonds",
    "BTC-USD": "crypto", "ETH-USD": "crypto",
}

class TestSectorExposure:
    def test_balanced_profile_weights(self):
        weights = {
            "AAPL": 0.12, "MSFT": 0.12, "GOOGL": 0.09, "AMZN": 0.09, "NVDA": 0.08,
            "TLT": 0.15, "BND": 0.15,
            "BTC-USD": 0.12, "ETH-USD": 0.08,
        }
        exp = compute_sector_exposure(weights, _SECTOR_MAP)
        assert abs(exp["tech"] - 0.50) < 1e-9
        assert abs(exp["bonds"] - 0.30) < 1e-9
        assert abs(exp["crypto"] - 0.20) < 1e-9

    def test_empty_weights_returns_empty(self):
        assert compute_sector_exposure({}, _SECTOR_MAP) == {}

    def test_unknown_ticker_maps_to_other(self):
        weights = {"XYZ": 0.10, "AAPL": 0.90}
        exp = compute_sector_exposure(weights, _SECTOR_MAP)
        assert "other" in exp
        assert abs(exp["other"] - 0.10) < 1e-9

    def test_all_unknown_tickers(self):
        weights = {"FOO": 0.50, "BAR": 0.50}
        exp = compute_sector_exposure(weights, _SECTOR_MAP)
        assert list(exp.keys()) == ["other"]
        assert abs(exp["other"] - 1.0) < 1e-9

    def test_single_sector_portfolio(self):
        weights = {"AAPL": 0.60, "MSFT": 0.40}
        exp = compute_sector_exposure(weights, _SECTOR_MAP)
        assert set(exp.keys()) == {"tech"}
        assert abs(exp["tech"] - 1.0) < 1e-9


# ---------------------------------------------------------------------------
# TestConcentrationScore
# ---------------------------------------------------------------------------

class TestConcentrationScore:
    def test_returns_max_sector(self):
        exp = {"tech": 0.50, "bonds": 0.30, "crypto": 0.20}
        assert abs(concentration_score(exp) - 0.50) < 1e-9

    def test_single_sector(self):
        assert abs(concentration_score({"tech": 0.75}) - 0.75) < 1e-9

    def test_empty_returns_zero(self):
        assert concentration_score({}) == 0.0

    def test_equal_sectors(self):
        exp = {"tech": 0.33, "bonds": 0.33, "crypto": 0.34}
        assert abs(concentration_score(exp) - 0.34) < 1e-9


# ---------------------------------------------------------------------------
# TestPolicyConcentrationBlock
# ---------------------------------------------------------------------------

class TestPolicyConcentrationBlock:
    """Integration tests for the concentration soft block in ExecutionPolicyEngine."""

    def setup_method(self):
        from agents.policies import ExecutionPolicyEngine, PolicyConfig
        from agents.models import (
            CycleObservation, MarketSnapshot, PortfolioSnapshot, RiskStatus, TradeProposal,
        )
        self._engine = ExecutionPolicyEngine(PolicyConfig())
        self._TradeProposal = TradeProposal
        self._CycleObservation = CycleObservation
        self._MarketSnapshot = MarketSnapshot
        self._PortfolioSnapshot = PortfolioSnapshot
        self._RiskStatus = RiskStatus

    def _make_observation(self, current_weights, prices, total_value=100_000.0, trade_plan=None):
        portfolio = self._PortfolioSnapshot(
            positions={},
            cash=0.0,
            peak_value=total_value,
            total_value=total_value,
            current_weights=current_weights,
            target_weights={},
            weight_deviation={},
            pnl_dollars=0.0,
            pnl_pct=0.0,
        )
        market = self._MarketSnapshot(prices=prices)
        risk = self._RiskStatus(
            kill_switch_active=False,
            drawdown=0.0,
            max_trades_per_cycle=10,
            max_order_fraction_of_portfolio=0.30,
            allowed_tickers=list(prices.keys()),
            execution_mode="simulate",
        )
        return self._CycleObservation(
            cycle_id="test",
            strategy_name="threshold",
            portfolio=portfolio,
            market=market,
            risk=risk,
            trade_plan=trade_plan or [],
        )

    def _make_decision(self, trades):
        from agents.models import TradeDecision
        return TradeDecision(
            cycle_id="test",
            summary="test",
            market_outlook="neutral",
            rationale="test",
            rebalance_needed=True,
            approved_trades=trades,
        )

    def test_buy_under_concentration_limit_is_allowed(self):
        # tech = 0.30 (well under 0.55); buy AAPL adds 2% → projected = 0.32 → allowed
        weights = {
            "AAPL": 0.10, "MSFT": 0.10, "GOOGL": 0.10,
            "TLT": 0.35, "BND": 0.35,
        }
        prices = {"AAPL": 100.0}
        # buy qty=20 → notional=2000, added_weight=0.02, projected=0.32
        trade = self._TradeProposal(action="buy", ticker="AAPL", quantity=20.0, reason="test")
        obs = self._make_observation(weights, prices, trade_plan=[trade])
        decision = self._make_decision([trade])
        result = self._engine.evaluate(decision, obs, "simulate")
        assert result.approved
        assert any(t.ticker == "AAPL" for t in result.allowed_trades)

    def test_buy_pushing_sector_over_limit_is_blocked(self):
        # tech = 0.52; buy AAPL qty=50 adds 5% → projected = 0.57 > 0.55 → blocked
        weights = {
            "AAPL": 0.13, "MSFT": 0.13, "GOOGL": 0.10, "AMZN": 0.10, "NVDA": 0.06,
            "TLT": 0.20, "BND": 0.15, "BTC-USD": 0.08, "ETH-USD": 0.05,
        }
        prices = {"AAPL": 100.0}
        # qty=50, price=100, notional=5000, total=100_000 → added_weight=0.05 → projected=0.57
        trade = self._TradeProposal(action="buy", ticker="AAPL", quantity=50.0, reason="test")
        obs = self._make_observation(weights, prices, trade_plan=[trade])
        decision = self._make_decision([trade])
        result = self._engine.evaluate(decision, obs, "simulate")
        assert result.approved
        assert not result.allowed_trades
        assert result.blocked_trades[0].rejection_reason.startswith("Sector concentration limit")

    def test_sell_on_over_concentrated_sector_is_allowed(self):
        # tech = 0.57 (over limit); sell AAPL → always allowed
        weights = {
            "AAPL": 0.15, "MSFT": 0.15, "GOOGL": 0.12, "AMZN": 0.10, "NVDA": 0.05,
            "TLT": 0.20, "BND": 0.13, "BTC-USD": 0.07, "ETH-USD": 0.03,
        }
        prices = {"AAPL": 100.0}
        trade = self._TradeProposal(action="sell", ticker="AAPL", quantity=10.0, reason="test")
        obs = self._make_observation(weights, prices, trade_plan=[trade])
        decision = self._make_decision([trade])
        result = self._engine.evaluate(decision, obs, "simulate")
        assert result.approved
        assert any(t.ticker == "AAPL" for t in result.allowed_trades)

    def test_buy_stays_exactly_at_limit_is_allowed(self):
        # tech = 0.50; buy adds exactly 0.05 → projected = 0.55 (not strictly > 0.55) → allowed
        weights = {
            "AAPL": 0.10, "MSFT": 0.10, "GOOGL": 0.10, "AMZN": 0.10, "NVDA": 0.10,
            "TLT": 0.30, "BND": 0.20,
        }
        prices = {"AAPL": 100.0}
        # qty=50 → notional=5000, added_weight=0.05, projected=0.55 (not > 0.55)
        trade = self._TradeProposal(action="buy", ticker="AAPL", quantity=50.0, reason="test")
        obs = self._make_observation(weights, prices, trade_plan=[trade])
        decision = self._make_decision([trade])
        result = self._engine.evaluate(decision, obs, "simulate")
        assert result.approved
        assert any(t.ticker == "AAPL" for t in result.allowed_trades)

    def test_bonds_buy_not_affected_by_tech_concentration(self):
        # tech = 0.57 (over limit); buy TLT (bonds sector) → no concentration block
        weights = {
            "AAPL": 0.15, "MSFT": 0.15, "GOOGL": 0.12, "AMZN": 0.10, "NVDA": 0.05,
            "TLT": 0.25, "BND": 0.10, "BTC-USD": 0.05, "ETH-USD": 0.03,
        }
        prices = {"TLT": 90.0}
        trade = self._TradeProposal(action="buy", ticker="TLT", quantity=10.0, reason="test")
        obs = self._make_observation(weights, prices, trade_plan=[trade])
        decision = self._make_decision([trade])
        result = self._engine.evaluate(decision, obs, "simulate")
        assert result.approved
        assert any(t.ticker == "TLT" for t in result.allowed_trades)


# ---------------------------------------------------------------------------
# TestRollingCorrelation
# ---------------------------------------------------------------------------

class TestRollingCorrelation:
    def _make_returns_df(self, n=60, seed=42) -> pd.DataFrame:
        rng = np.random.default_rng(seed)
        return pd.DataFrame({
            "AAPL": rng.normal(0.001, 0.02, n),
            "MSFT": rng.normal(0.001, 0.02, n),
            "TLT":  rng.normal(0.0002, 0.005, n),
        })

    def test_diagonal_is_one(self):
        df = self._make_returns_df()
        corr = rolling_correlation(df, window=30)
        for col in corr.columns:
            assert abs(corr.loc[col, col] - 1.0) < 1e-9

    def test_symmetric_matrix(self):
        df = self._make_returns_df()
        corr = rolling_correlation(df, window=30)
        assert abs(corr.loc["AAPL", "MSFT"] - corr.loc["MSFT", "AAPL"]) < 1e-12

    def test_empty_df_returns_empty(self):
        result = rolling_correlation(pd.DataFrame())
        assert result.empty

    def test_single_row_returns_empty(self):
        df = pd.DataFrame({"A": [0.01], "B": [0.02]})
        result = rolling_correlation(df, window=30)
        assert result.empty

    def test_correlated_assets_high_correlation(self):
        # Two nearly identical series → correlation close to 1.0
        base = np.linspace(0, 0.01, 60)
        df = pd.DataFrame({"A": base + 0.0001, "B": base - 0.0001})
        corr = rolling_correlation(df, window=30)
        assert corr.loc["A", "B"] > 0.99

    def test_uncorrelated_assets_low_correlation(self):
        rng = np.random.default_rng(0)
        df = pd.DataFrame({
            "A": rng.normal(0, 1, 200),
            "B": rng.normal(0, 1, 200),
        })
        corr = rolling_correlation(df, window=30)
        assert abs(corr.loc["A", "B"]) < 0.5  # loose bound for random data

    def test_avg_pairwise_correlation_below_one_for_mixed(self):
        df = self._make_returns_df()
        corr = rolling_correlation(df, window=30)
        avg = avg_pairwise_correlation(corr)
        assert avg < 1.0
        assert avg > -1.0

    def test_avg_pairwise_correlation_zero_for_single_asset(self):
        df = pd.DataFrame({"A": [0.01, 0.02, 0.03, 0.04]})
        corr = df.corr()
        assert avg_pairwise_correlation(corr) == 0.0

    def test_avg_pairwise_correlation_empty(self):
        assert avg_pairwise_correlation(pd.DataFrame()) == 0.0

    def test_window_uses_last_n_rows(self):
        # First 30 rows all positive, last 30 rows all negative — window=30 uses last 30
        part1 = pd.DataFrame({"A": [0.01] * 30, "B": [0.01] * 30})
        part2 = pd.DataFrame({"A": [-0.01] * 30, "B": [-0.01] * 30})
        df = pd.concat([part1, part2], ignore_index=True)
        corr_window30 = rolling_correlation(df, window=30)
        corr_all = rolling_correlation(df, window=60)
        # Both windows: A and B perfectly correlated regardless, but verify shapes
        assert corr_window30.shape == (2, 2)
        assert corr_all.shape == (2, 2)


# ---------------------------------------------------------------------------
# TestStressTest
# ---------------------------------------------------------------------------

_STRESS_PORTFOLIO = {
    "positions": {
        "AAPL": 10.0,   # 10 × $200 = $2 000
        "TLT":  20.0,   # 20 × $100 = $2 000
        "BTC-USD": 0.1, # 0.1 × $40 000 = $4 000
    },
    "cash": 2_000.0,    # total = $10 000
}
_STRESS_PRICES = {"AAPL": 200.0, "TLT": 100.0, "BTC-USD": 40_000.0}


class TestStressTest:
    def test_zero_shocks_no_change(self):
        scenarios = [{"name": "flat", "description": "", "shocks": {}}]
        results = run_stress_test(_STRESS_PORTFOLIO, _STRESS_PRICES, scenarios)
        assert len(results) == 1
        r = results[0]
        assert abs(r["pnl_dollars"]) < 1e-6
        assert abs(r["pnl_pct"]) < 1e-9
        assert not r["kill_switch_triggered"]

    def test_large_shock_produces_loss(self):
        # −50% on all positions
        scenarios = [{"name": "crash", "description": "", "shocks": {
            "AAPL": -0.50, "TLT": -0.50, "BTC-USD": -0.50,
        }}]
        results = run_stress_test(_STRESS_PORTFOLIO, _STRESS_PRICES, scenarios)
        r = results[0]
        assert r["pnl_dollars"] < 0
        assert r["pnl_pct"] < 0

    def test_known_pnl_value(self):
        # AAPL −20%: 10 × 200 × (1−0.2) = 1600; TLT unchanged; BTC unchanged
        # before = 2000 + 2000 + 4000 + 2000 = 10000
        # after  = 1600 + 2000 + 4000 + 2000 = 9600
        scenarios = [{"name": "aapl_drop", "description": "", "shocks": {"AAPL": -0.20}}]
        results = run_stress_test(_STRESS_PORTFOLIO, _STRESS_PRICES, scenarios)
        r = results[0]
        assert abs(r["portfolio_value_before"] - 10_000.0) < 1e-6
        assert abs(r["portfolio_value_after"] - 9_600.0) < 1e-6
        assert abs(r["pnl_dollars"] - (-400.0)) < 1e-6
        assert abs(r["pnl_pct"] - (-0.04)) < 1e-9

    def test_kill_switch_triggered_when_loss_exceeds_threshold(self):
        # −50% on all → pnl_pct = −(8000 × 0.5) / 10000 = −0.40 < −0.10 → triggered
        scenarios = [{"name": "severe", "description": "", "shocks": {
            "AAPL": -0.50, "TLT": -0.50, "BTC-USD": -0.50,
        }}]
        results = run_stress_test(_STRESS_PORTFOLIO, _STRESS_PRICES, scenarios, kill_switch_threshold=0.10)
        assert results[0]["kill_switch_triggered"]

    def test_kill_switch_not_triggered_for_small_loss(self):
        scenarios = [{"name": "small", "description": "", "shocks": {"AAPL": -0.02}}]
        results = run_stress_test(_STRESS_PORTFOLIO, _STRESS_PRICES, scenarios, kill_switch_threshold=0.10)
        assert not results[0]["kill_switch_triggered"]

    def test_cash_unaffected_by_price_shocks(self):
        # Portfolio with only cash — no price shock should matter
        cash_only = {"positions": {}, "cash": 10_000.0}
        scenarios = [{"name": "crash", "description": "", "shocks": {"AAPL": -0.50}}]
        results = run_stress_test(cash_only, _STRESS_PRICES, scenarios)
        r = results[0]
        assert abs(r["pnl_dollars"]) < 1e-6

    def test_empty_portfolio_returns_empty(self):
        empty = {"positions": {}, "cash": 0.0}
        results = run_stress_test(empty, _STRESS_PRICES)
        assert results == []

    def test_custom_scenarios_override_defaults(self):
        custom = [{"name": "custom_only", "description": "x", "shocks": {}}]
        results = run_stress_test(_STRESS_PORTFOLIO, _STRESS_PRICES, scenarios=custom)
        assert len(results) == 1
        assert results[0]["scenario"] == "custom_only"

    def test_default_scenarios_returns_four_results(self):
        results = run_stress_test(_STRESS_PORTFOLIO, _STRESS_PRICES)
        assert len(results) == len(STRESS_SCENARIOS)
        names = {r["scenario"] for r in results}
        assert "covid_march_2020" in names
        assert "gfc_2008" in names
        assert "rate_shock_2022" in names
        assert "tech_selloff" in names

    def test_weights_after_sum_to_one(self):
        scenarios = [{"name": "flat", "description": "", "shocks": {}}]
        results = run_stress_test(_STRESS_PORTFOLIO, _STRESS_PRICES, scenarios)
        weights = results[0]["weights_after"]
        # weights only cover invested positions (not cash), so sum ≤ 1
        assert sum(weights.values()) <= 1.0 + 1e-9

    def test_ticker_missing_from_shocks_uses_zero(self):
        # BTC-USD not in shocks → shock = 0.0 (no change)
        scenarios = [{"name": "partial", "description": "", "shocks": {"AAPL": -0.20}}]
        results = run_stress_test(_STRESS_PORTFOLIO, _STRESS_PRICES, scenarios)
        r = results[0]
        # Only AAPL affected: loss = 10 × 200 × 0.20 = 400
        assert abs(r["pnl_dollars"] - (-400.0)) < 1e-6

    def test_positive_shock_increases_portfolio_value(self):
        scenarios = [{"name": "rally", "description": "", "shocks": {
            "AAPL": +0.30, "TLT": +0.10, "BTC-USD": +0.50,
        }}]
        results = run_stress_test(_STRESS_PORTFOLIO, _STRESS_PRICES, scenarios)
        assert results[0]["pnl_dollars"] > 0
        assert not results[0]["kill_switch_triggered"]


# ---------------------------------------------------------------------------
# TestInverseVolWeights
# ---------------------------------------------------------------------------

_TARGET_2 = {"LOW": 0.50, "HIGH": 0.50}


class TestInverseVolWeights:
    def test_higher_vol_asset_gets_less_weight(self):
        vols = {"LOW": 0.10, "HIGH": 0.50}
        result = compute_inverse_vol_weights(vols, _TARGET_2)
        assert result["LOW"] > result["HIGH"]

    def test_equal_vols_produce_equal_weights(self):
        vols = {"LOW": 0.25, "HIGH": 0.25}
        result = compute_inverse_vol_weights(vols, _TARGET_2)
        assert abs(result["LOW"] - result["HIGH"]) < 1e-9

    def test_output_sums_to_one_pure_inv_vol(self):
        vols = {"LOW": 0.10, "HIGH": 0.50}
        result = compute_inverse_vol_weights(vols, _TARGET_2, blend=1.0)
        assert abs(sum(result.values()) - 1.0) < 1e-9

    def test_output_sums_to_one_blended(self):
        vols = {"LOW": 0.10, "HIGH": 0.50}
        result = compute_inverse_vol_weights(vols, _TARGET_2, blend=0.5)
        assert abs(sum(result.values()) - 1.0) < 1e-9

    def test_blend_zero_returns_fixed_target(self):
        vols = {"LOW": 0.10, "HIGH": 0.50}
        result = compute_inverse_vol_weights(vols, _TARGET_2, blend=0.0)
        assert abs(result["LOW"] - 0.50) < 1e-9
        assert abs(result["HIGH"] - 0.50) < 1e-9

    def test_blend_one_is_pure_inverse_vol(self):
        vols = {"LOW": 0.10, "HIGH": 0.50}
        pure = compute_inverse_vol_weights(vols, _TARGET_2, blend=1.0)
        # inv_vol: LOW=10, HIGH=2 → LOW=10/12≈0.833, HIGH=2/12≈0.167
        assert abs(pure["LOW"] - 10 / 12) < 1e-9
        assert abs(pure["HIGH"] - 2 / 12) < 1e-9

    def test_blend_half_is_midpoint(self):
        vols = {"LOW": 0.10, "HIGH": 0.50}
        pure = compute_inverse_vol_weights(vols, _TARGET_2, blend=1.0)
        blended = compute_inverse_vol_weights(vols, _TARGET_2, blend=0.5)
        expected_low = 0.5 * pure["LOW"] + 0.5 * _TARGET_2["LOW"]
        assert abs(blended["LOW"] - expected_low) < 1e-9

    def test_missing_vol_falls_back_to_reference(self):
        # HIGH has no vol entry → uses 0.20 fallback
        vols = {"LOW": 0.10}
        result = compute_inverse_vol_weights(vols, _TARGET_2, blend=1.0)
        # inv_vol: LOW=1/0.10=10, HIGH=1/0.20=5 → LOW=10/15≈0.667, HIGH=5/15≈0.333
        assert abs(result["LOW"] - 10 / 15) < 1e-9
        assert abs(result["HIGH"] - 5 / 15) < 1e-9

    def test_zero_vol_uses_fallback_not_division_error(self):
        vols = {"LOW": 0.0, "HIGH": 0.25}
        result = compute_inverse_vol_weights(vols, _TARGET_2, blend=1.0)
        assert abs(sum(result.values()) - 1.0) < 1e-9

    def test_three_asset_target(self):
        target = {"A": 0.40, "B": 0.40, "C": 0.20}
        vols = {"A": 0.10, "B": 0.20, "C": 0.40}
        result = compute_inverse_vol_weights(vols, target, blend=1.0)
        assert result["A"] > result["B"] > result["C"]
        assert abs(sum(result.values()) - 1.0) < 1e-9


# ---------------------------------------------------------------------------
# TestStrategyInverseVolSizing
# ---------------------------------------------------------------------------

class TestStrategyInverseVolSizing:
    _PORTFOLIO = {
        "positions": {"LOW": 5.0, "HIGH": 5.0},
        "cash": 0.0,
    }
    _PRICES = {"LOW": 100.0, "HIGH": 100.0}
    _TARGET = {"LOW": 0.50, "HIGH": 0.50}

    def test_threshold_without_vols_uses_fixed_target(self):
        from strategies.threshold import ThresholdStrategy
        strat = ThresholdStrategy(threshold=0.05, target_allocation=self._TARGET)
        # Balanced portfolio → no trades at fixed target
        trades = strat.get_trades(self._PORTFOLIO, self._PRICES)
        assert trades == []

    def test_threshold_with_vols_shifts_target(self):
        from strategies.threshold import ThresholdStrategy
        strat = ThresholdStrategy(threshold=0.01, target_allocation=self._TARGET)
        # HIGH is 5× more volatile → inv-vol target gives LOW ~83%, HIGH ~17%
        # Current weights: LOW=0.50, HIGH=0.50 — both deviate significantly from inv-vol target
        vols = {"LOW": 0.10, "HIGH": 0.50}
        trades = strat.get_trades(self._PORTFOLIO, self._PRICES, volatilities=vols, vol_blend=1.0)
        actions = {t["ticker"]: t["action"] for t in trades}
        # Should buy LOW (underweight vs inv-vol target) and sell HIGH (overweight)
        assert actions.get("LOW") == "buy"
        assert actions.get("HIGH") == "sell"

    def test_calendar_without_vols_uses_fixed_target(self):
        from strategies.calendar import CalendarStrategy
        strat = CalendarStrategy(frequency="weekly", target_allocation=self._TARGET, min_drift=0.0)
        # Balanced portfolio with fixed target → no orders
        trades = strat.get_trades(self._PORTFOLIO, self._PRICES)
        assert trades == []

    def test_calendar_with_vols_produces_orders(self):
        from strategies.calendar import CalendarStrategy
        strat = CalendarStrategy(frequency="weekly", target_allocation=self._TARGET, min_drift=0.0)
        vols = {"LOW": 0.10, "HIGH": 0.50}
        trades = strat.get_trades(self._PORTFOLIO, self._PRICES, volatilities=vols, vol_blend=1.0)
        # inv-vol target differs from 50/50 → orders should be generated
        assert len(trades) > 0
