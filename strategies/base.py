"""Abstract base class for rebalancing strategies."""

from abc import ABC, abstractmethod

from config import TARGET_ALLOCATION


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

    def _compute_trade_orders(self, portfolio: dict, prices: dict) -> list[dict]:
        """
        Compute buy/sell orders needed to go from current weights to target weights.
        Returns: list of {"action", "ticker", "quantity", "reason"}
        """
        positions = portfolio.get("positions", {})
        cash = portfolio.get("cash", 0.0)

        market_values = {ticker: qty * prices.get(ticker, 0) for ticker, qty in positions.items()}
        total = sum(market_values.values()) + cash
        if total <= 0:
            return []

        trades = []
        for ticker, target_weight in self.target.items():
            current_value = market_values.get(ticker, 0.0)
            target_value = target_weight * total
            delta_value = target_value - current_value
            price = prices.get(ticker, 0)
            if price <= 0:
                continue
            quantity = abs(delta_value) / price
            if quantity < 0.001:
                continue
            action = "buy" if delta_value > 0 else "sell"
            current_weight = current_value / total
            reason = (
                f"Rebalance {ticker}: current weight {current_weight:.1%} → "
                f"target {target_weight:.1%} (delta ${delta_value:+,.0f})"
            )
            trades.append({"action": action, "ticker": ticker, "quantity": round(quantity, 6), "reason": reason})

        return trades
