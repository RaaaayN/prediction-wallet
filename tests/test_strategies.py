"""Tests for rebalancing strategies."""

from datetime import timedelta

import pytest

from strategies.threshold import ThresholdStrategy
from strategies.calendar import CalendarStrategy
from utils.time import utc_now


TARGET = {"AAPL": 0.5, "MSFT": 0.5}
PRICES = {"AAPL": 100.0, "MSFT": 200.0}


def _make_portfolio(aapl_qty=5.0, msft_qty=2.5, cash=0.0, last_rebalanced=None):
    return {
        "positions": {"AAPL": aapl_qty, "MSFT": msft_qty},
        "cash": cash,
        "last_rebalanced": last_rebalanced,
        "peak_value": aapl_qty * 100 + msft_qty * 200 + cash,
    }


class TestThresholdStrategy:
    def setup_method(self):
        self.strategy = ThresholdStrategy(threshold=0.05, target_allocation=TARGET)

    def test_no_rebalance_when_balanced(self):
        portfolio = _make_portfolio(aapl_qty=5.0, msft_qty=2.5)
        # Total = 500 + 500 = 1000 → AAPL=50%, MSFT=50% → no drift
        assert self.strategy.should_rebalance(portfolio, PRICES) is False

    def test_rebalance_triggered_on_drift(self):
        # AAPL has 70%, MSFT 30% → AAPL drifted +20%
        portfolio = _make_portfolio(aapl_qty=7.0, msft_qty=1.5)
        # Total = 700 + 300 = 1000 → AAPL=70%, MSFT=30% → drift > 5%
        assert self.strategy.should_rebalance(portfolio, PRICES) is True

    def test_get_trades_returns_list(self):
        portfolio = _make_portfolio(aapl_qty=7.0, msft_qty=1.5)
        trades = self.strategy.get_trades(portfolio, PRICES)
        assert isinstance(trades, list)
        assert len(trades) > 0

    def test_get_trades_has_required_keys(self):
        portfolio = _make_portfolio(aapl_qty=7.0, msft_qty=1.5)
        trades = self.strategy.get_trades(portfolio, PRICES)
        for trade in trades:
            assert "action" in trade
            assert "ticker" in trade
            assert "quantity" in trade
            assert "reason" in trade
            assert trade["action"] in ("buy", "sell")

    def test_empty_portfolio_no_signal(self):
        portfolio = {"positions": {}, "cash": 1000.0, "peak_value": 1000.0}
        # No current weights → no drift → no signal
        assert self.strategy.should_rebalance(portfolio, PRICES) is False

    def test_drift_report(self):
        portfolio = _make_portfolio(aapl_qty=7.0, msft_qty=1.5)
        report = self.strategy.get_drift_report(portfolio, PRICES)
        assert "AAPL" in report
        assert "MSFT" in report
        assert report["AAPL"] > 0.05  # AAPL is overweight


class TestCalendarStrategy:
    def setup_method(self):
        self.strategy = CalendarStrategy(frequency="weekly", target_allocation=TARGET)

    def test_rebalance_if_never_rebalanced(self):
        portfolio = _make_portfolio()
        assert self.strategy.should_rebalance(portfolio, PRICES) is True

    def test_no_rebalance_if_recent(self):
        recent = utc_now().isoformat()
        portfolio = _make_portfolio(last_rebalanced=recent)
        assert self.strategy.should_rebalance(portfolio, PRICES) is False

    def test_rebalance_after_one_week(self):
        old = (utc_now() - timedelta(weeks=2)).isoformat()
        portfolio = _make_portfolio(last_rebalanced=old)
        assert self.strategy.should_rebalance(portfolio, PRICES) is True

    def test_monthly_not_triggered_after_two_weeks(self):
        monthly = CalendarStrategy(frequency="monthly", target_allocation=TARGET)
        two_weeks_ago = (utc_now() - timedelta(days=14)).isoformat()
        portfolio = _make_portfolio(last_rebalanced=two_weeks_ago)
        assert monthly.should_rebalance(portfolio, PRICES) is False

    def test_get_trades_has_required_keys(self):
        portfolio = _make_portfolio(aapl_qty=7.0, msft_qty=1.5)
        trades = self.strategy.get_trades(portfolio, PRICES)
        for trade in trades:
            assert "action" in trade
            assert "ticker" in trade

    def test_invalid_frequency_raises(self):
        with pytest.raises(ValueError):
            CalendarStrategy(frequency="hourly")
