"""Drawdown monitor: triggers an emergency stop if losses exceed the threshold."""

import json
from datetime import datetime

from config import KILL_SWITCH_DRAWDOWN, TRADES_LOG
from engine.risk import compute_drawdown as _compute_drawdown, check_kill_switch as _check_kill_switch


class KillSwitch:
    """Monitor portfolio drawdown and activate emergency stop if needed."""

    def __init__(self, threshold: float = KILL_SWITCH_DRAWDOWN, trades_log: str = TRADES_LOG):
        self.threshold = threshold
        self.trades_log = trades_log

    def check(self, portfolio: dict) -> bool:
        """
        Return True if the kill switch should activate.
        Computes drawdown from portfolio['peak_value'].
        """
        current_value = self._estimate_current_value(portfolio)
        peak = portfolio.get("peak_value", current_value)

        if peak <= 0:
            return False

        drawdown = _compute_drawdown(current_value, peak)

        if _check_kill_switch(drawdown, self.threshold):
            self._log_alert(current_value, peak, drawdown)
            return True
        return False

    def check_with_prices(self, portfolio: dict, prices: dict) -> bool:
        """Check kill switch using live prices for accurate valuation."""
        positions = portfolio.get("positions", {})
        cash = portfolio.get("cash", 0.0)
        market_value = cash + sum(qty * prices.get(t, 0) for t, qty in positions.items())
        peak = portfolio.get("peak_value", market_value)

        if peak <= 0:
            return False

        drawdown = _compute_drawdown(market_value, peak)

        if _check_kill_switch(drawdown, self.threshold):
            self._log_alert(market_value, peak, drawdown)
            return True
        return False

    def _estimate_current_value(self, portfolio: dict) -> float:
        """Estimate value from history if no prices available."""
        history = portfolio.get("history", [])
        if history:
            return history[-1].get("total_value", portfolio.get("cash", 0))
        return portfolio.get("cash", 0)

    def _log_alert(self, current_value: float, peak: float, drawdown: float) -> None:
        alert = {
            "event": "KILL_SWITCH_ACTIVATED",
            "timestamp": datetime.utcnow().isoformat(),
            "current_value": current_value,
            "peak_value": peak,
            "drawdown": drawdown,
            "threshold": -self.threshold,
        }
        import os
        os.makedirs(os.path.dirname(self.trades_log), exist_ok=True)
        with open(self.trades_log, "a") as f:
            f.write(json.dumps(alert) + "\n")
        print(
            f"\n⚠️  KILL SWITCH ACTIVATED — drawdown {drawdown:.1%} exceeds "
            f"threshold -{self.threshold:.0%}. Trading halted.\n"
        )
