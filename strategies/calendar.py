"""Time-based rebalancing: triggers on a fixed weekly or monthly schedule."""

from datetime import datetime, timedelta

from config import CALENDAR_FREQUENCY
from strategies.base import BaseStrategy
from utils.time import utc_now


class CalendarStrategy(BaseStrategy):
    """Rebalance on a fixed calendar schedule, ignoring drift."""

    def __init__(self, frequency: str = CALENDAR_FREQUENCY, target_allocation=None):
        super().__init__(target_allocation)
        if frequency not in ("weekly", "monthly"):
            raise ValueError("frequency must be 'weekly' or 'monthly'")
        self.frequency = frequency

    def should_rebalance(self, portfolio: dict, prices: dict) -> bool:
        last_str = portfolio.get("last_rebalanced")
        if not last_str:
            return True

        last = datetime.fromisoformat(last_str)
        now = utc_now()
        if last.tzinfo is None:
            last = last.replace(tzinfo=now.tzinfo)

        if self.frequency == "weekly":
            return (now - last) >= timedelta(weeks=1)
        return (now - last) >= timedelta(days=30)

    def get_trades(self, portfolio: dict, prices: dict) -> list[dict]:
        return self._compute_trade_orders(portfolio, prices)
