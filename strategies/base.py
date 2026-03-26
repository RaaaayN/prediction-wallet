"""Abstract base class for rebalancing strategies."""

from abc import ABC, abstractmethod

from config import TARGET_ALLOCATION
from engine.orders import generate_rebalance_orders as _generate_orders


class BaseStrategy(ABC):
    """All rebalancing strategies must implement this interface."""

    def __init__(self, target_allocation: dict[str, float] | None = None):
        self.target = target_allocation or TARGET_ALLOCATION

    @abstractmethod
    def should_rebalance(self, portfolio: dict, prices: dict) -> bool:
        """Return True if a rebalancing cycle should be triggered."""
        ...

    @abstractmethod
    def get_trades(self, portfolio: dict, prices: dict) -> list[dict]:
        """
        Return a list of trade orders to restore target weights.
        Each order: {"action": "buy"|"sell", "ticker": str, "quantity": float, "reason": str}
        """
        ...

    # ------------------------------------------------------------------
    # Shared helpers
    # ------------------------------------------------------------------

    def _compute_current_weights(self, portfolio: dict, prices: dict) -> dict[str, float]:
        """Compute current portfolio weights from positions and prices."""
        positions = portfolio.get("positions", {})
        cash = portfolio.get("cash", 0.0)

        market_values = {ticker: qty * prices.get(ticker, 0) for ticker, qty in positions.items()}
        total = sum(market_values.values()) + cash
        if total <= 0:
            return {}

        weights = {ticker: mv / total for ticker, mv in market_values.items()}
        return weights

    def _compute_trade_orders(
        self,
        portfolio: dict,
        prices: dict,
        min_drift: float = 0.0,
        volatilities: dict[str, float] | None = None,
        vol_blend: float = 1.0,
    ) -> list[dict]:
        """
        Compute buy/sell orders needed to go from current weights to target weights.

        Args:
            min_drift: skip assets whose |current_weight - target_weight| <= min_drift (tolerance band)
            volatilities: optional ticker → annualised 30-day vol. When provided, target weights
                are adjusted via inverse-volatility weighting (higher-vol assets get less capital).
            vol_blend: 0.0 = pure fixed target, 1.0 = pure inverse-vol, values in between blend.
                       Only used when volatilities is provided.

        Returns: list of {"action", "ticker", "quantity", "reason"}
        """
        target = self.target
        if volatilities:
            from engine.portfolio import compute_inverse_vol_weights
            target = compute_inverse_vol_weights(volatilities, self.target, blend=vol_blend)
        return _generate_orders(portfolio, prices, target, min_qty=0.001, min_drift=min_drift)
