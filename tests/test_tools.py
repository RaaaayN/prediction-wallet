"""Tests for agent tools (without real API calls)."""

import json
import os
import tempfile
import pytest

from config import INITIAL_CAPITAL


class TestTradeSimulator:
    def setup_method(self):
        # Use temp files for isolation
        self.tmpdir = tempfile.mkdtemp()
        self.portfolio_file = os.path.join(self.tmpdir, "portfolio.json")
        self.trades_log = os.path.join(self.tmpdir, "trades.log")

        from execution.simulator import TradeSimulator
        self.sim = TradeSimulator(
            portfolio_file=self.portfolio_file,
            trades_log=self.trades_log,
        )

    def test_default_portfolio(self):
        p = self.sim.load_portfolio()
        assert p["cash"] == INITIAL_CAPITAL
        assert p["positions"] == {}

    def test_buy_decreases_cash(self):
        result = self.sim.execute("buy", "AAPL", 1.0, 150.0, "test buy")
        assert result.success is True
        p = self.sim.load_portfolio()
        assert p["cash"] < INITIAL_CAPITAL
        assert "AAPL" in p["positions"]
        assert p["positions"]["AAPL"] == pytest.approx(1.0, abs=0.001)

    def test_sell_increases_cash(self):
        # First buy
        self.sim.execute("buy", "AAPL", 2.0, 150.0, "setup")
        portfolio_after_buy = self.sim.load_portfolio()
        cash_after_buy = portfolio_after_buy["cash"]

        # Then sell 1 share
        result = self.sim.execute("sell", "AAPL", 1.0, 150.0, "test sell")
        assert result.success is True
        p = self.sim.load_portfolio()
        assert p["cash"] > cash_after_buy

    def test_sell_without_position_fails(self):
        result = self.sim.execute("sell", "AAPL", 1.0, 150.0, "no position")
        assert result.success is False
        assert result.error and "position" in result.error.lower()

    def test_slippage_applied_on_buy(self):
        from config import SLIPPAGE_EQUITIES
        result = self.sim.execute("buy", "AAPL", 1.0, 100.0, "slippage test")
        expected_fill = 100.0 * (1 + SLIPPAGE_EQUITIES)
        assert result.fill_price == pytest.approx(expected_fill, rel=1e-4)

    def test_slippage_applied_on_sell(self):
        from config import SLIPPAGE_EQUITIES
        self.sim.execute("buy", "AAPL", 1.0, 100.0, "setup")
        result = self.sim.execute("sell", "AAPL", 1.0, 100.0, "slippage test")
        expected_fill = 100.0 * (1 - SLIPPAGE_EQUITIES)
        assert result.fill_price == pytest.approx(expected_fill, rel=1e-4)

    def test_crypto_has_higher_slippage(self):
        from config import SLIPPAGE_CRYPTO
        result = self.sim.execute("buy", "BTC-USD", 0.001, 50000.0, "crypto test")
        expected_fill = 50000.0 * (1 + SLIPPAGE_CRYPTO)
        assert result.fill_price == pytest.approx(expected_fill, rel=1e-4)

    def test_trade_logged_to_file(self):
        self.sim.execute("buy", "AAPL", 1.0, 100.0, "log test")
        trades = self.sim.get_trade_history()
        assert len(trades) == 1
        assert trades[0]["ticker"] == "AAPL"

    def test_insufficient_cash_scales_down(self):
        # Try to buy more than we can afford
        result = self.sim.execute("buy", "AAPL", 1_000_000.0, 1000.0, "too big")
        p = self.sim.load_portfolio()
        assert p["cash"] >= 0  # Cash should not go negative


class TestKillSwitch:
    def setup_method(self):
        self.tmpdir = tempfile.mkdtemp()
        self.trades_log = os.path.join(self.tmpdir, "trades.log")

        from execution.kill_switch import KillSwitch
        self.ks = KillSwitch(threshold=0.10, trades_log=self.trades_log)

    def test_no_trigger_when_at_peak(self):
        portfolio = {"cash": 100_000, "positions": {}, "peak_value": 100_000, "history": []}
        prices = {}
        assert self.ks.check_with_prices(portfolio, prices) is False

    def test_triggers_on_10pct_drawdown(self):
        portfolio = {"cash": 89_000, "positions": {}, "peak_value": 100_000, "history": []}
        prices = {}
        assert self.ks.check_with_prices(portfolio, prices) is True

    def test_no_trigger_on_9pct_drawdown(self):
        portfolio = {"cash": 91_000, "positions": {}, "peak_value": 100_000, "history": []}
        prices = {}
        assert self.ks.check_with_prices(portfolio, prices) is False

    def test_alert_logged_to_file(self):
        portfolio = {"cash": 85_000, "positions": {}, "peak_value": 100_000, "history": []}
        self.ks.check_with_prices(portfolio, {})
        with open(self.trades_log) as f:
            content = f.read()
        assert "KILL_SWITCH_ACTIVATED" in content
