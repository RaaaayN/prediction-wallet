"""Drift-based rebalancing: triggers when any asset deviates > DRIFT_THRESHOLD from target."""

from config import DRIFT_THRESHOLD
from strategies.base import BaseStrategy


class ThresholdStrategy(BaseStrategy):
    """Rebalance whenever any position drifts beyond the configured threshold."""

    def __init__(self, threshold: float = DRIFT_THRESHOLD, target_allocation=None):
        super().__init__(target_allocation)
        self.threshold = threshold

    def should_rebalance(self, portfolio: dict, prices: dict) -> bool:
        """Return True if any asset weight deviates more than `threshold` from target."""
        current_weights = self._compute_current_weights(portfolio, prices)
        if not current_weights:
            return False

        for ticker, target_weight in self.target.items():
            current = current_weights.get(ticker, 0.0)
            if abs(current - target_weight) > self.threshold:
                return True
        return False

    def get_trades(self, portfolio: dict, prices: dict) -> list[dict]:
        """Return orders to restore target weights, skipping assets within the tolerance band."""
        return self._compute_trade_orders(portfolio, prices, min_drift=self.threshold / 2)

    def get_drift_report(self, portfolio: dict, prices: dict) -> dict[str, float]:
        """Return per-ticker drift from target (for diagnostics)."""
        current_weights = self._compute_current_weights(portfolio, prices)
        return {
            ticker: current_weights.get(ticker, 0.0) - target_weight
            for ticker, target_weight in self.target.items()
        }
