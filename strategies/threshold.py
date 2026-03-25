"""Drift-based rebalancing: triggers when any asset deviates > DRIFT_THRESHOLD from target."""

from config import DRIFT_THRESHOLD
from engine.orders import generate_rebalance_orders as _generate_orders
from strategies.base import BaseStrategy


class ThresholdStrategy(BaseStrategy):
    """Rebalance whenever any position drifts beyond the configured threshold.

    Supports optional per-asset thresholds to widen bands for high-volatility assets
    (e.g. BTC/ETH) and narrow them for low-volatility assets (e.g. BND/TLT).
    """

    def __init__(
        self,
        threshold: float = DRIFT_THRESHOLD,
        target_allocation=None,
        per_asset_threshold: dict[str, float] | None = None,
    ):
        super().__init__(target_allocation)
        self.threshold = threshold
        self.per_asset_threshold = per_asset_threshold or {}

    def _get_threshold(self, ticker: str) -> float:
        """Return the drift threshold for a specific asset (falls back to global threshold)."""
        return self.per_asset_threshold.get(ticker, self.threshold)

    def should_rebalance(self, portfolio: dict, prices: dict) -> bool:
        """Return True if any asset weight deviates more than its per-asset threshold from target."""
        current_weights = self._compute_current_weights(portfolio, prices)
        if not current_weights:
            return False

        for ticker, target_weight in self.target.items():
            current = current_weights.get(ticker, 0.0)
            if abs(current - target_weight) > self._get_threshold(ticker):
                return True
        return False

    def get_trades(
        self,
        portfolio: dict,
        prices: dict,
        volatilities: dict[str, float] | None = None,
        vol_blend: float = 1.0,
    ) -> list[dict]:
        """Return orders to restore target weights, respecting per-asset tolerance bands.

        Args:
            volatilities: optional ticker → annualised 30-day vol for inverse-vol sizing.
                          When provided, target weights are adjusted before order generation.
            vol_blend: blend between fixed (0.0) and pure inverse-vol (1.0) targets.
        """
        from engine.portfolio import compute_inverse_vol_weights
        effective_target = (
            compute_inverse_vol_weights(volatilities, self.target, blend=vol_blend)
            if volatilities
            else self.target
        )
        current_weights = self._compute_current_weights(portfolio, prices)
        orders = _generate_orders(portfolio, prices, effective_target, min_qty=0.001)
        filtered = []
        for order in orders:
            ticker = order["ticker"]
            band = self._get_threshold(ticker) / 2
            current_w = current_weights.get(ticker, 0.0)
            target_w = effective_target.get(ticker, 0.0)
            if abs(current_w - target_w) > band:
                filtered.append(order)
        return filtered

    def get_drift_report(self, portfolio: dict, prices: dict) -> dict[str, float]:
        """Return per-ticker drift from target (for diagnostics)."""
        current_weights = self._compute_current_weights(portfolio, prices)
        return {
            ticker: current_weights.get(ticker, 0.0) - target_weight
            for ticker, target_weight in self.target.items()
        }
