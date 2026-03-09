"""Time-based rebalancing: triggers on a fixed weekly or monthly schedule."""

from datetime import datetime, timedelta

from config import CALENDAR_FREQUENCY
from strategies.base import BaseStrategy


class CalendarStrategy(BaseStrategy):
    """Rebalance on a fixed calendar schedule, ignoring drift."""

    def __init__(self, frequency: str = CALENDAR_FREQUENCY, target_allocation=None):
        super().__init__(target_allocation)
        if frequency not in ("weekly", "monthly"):
            raise ValueError("frequency must be 'weekly' or 'monthly'")
        self.frequency = frequency

    def should_rebalance(self, portfolio: dict, prices: dict) -> bool:
        """
        Return True if enough time has elapsed since last rebalancing.
        Reads `portfolio['last_rebalanced']` (ISO date string or None).
        """
        last_str = portfolio.get("last_rebalanced")
        if not last_str:
            return True  # Never rebalanced → do it now

        last = datetime.fromisoformat(last_str)
        now = datetime.utcnow()

        if self.frequency == "weekly":
            return (now - last) >= timedelta(weeks=1)
        else:
            return (now - last) >= timedelta(days=30)

    def get_trades(self, portfolio: dict, prices: dict) -> list[dict]:
        """Return orders to restore target weights."""
        return self._compute_trade_orders(portfolio, prices)
