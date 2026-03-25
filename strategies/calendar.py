"""Time-based rebalancing: triggers on a fixed weekly or monthly schedule."""

from datetime import datetime, timedelta

from config import CALENDAR_FREQUENCY
from strategies.base import BaseStrategy
from utils.time import utc_now


class CalendarStrategy(BaseStrategy):
    """Rebalance on a fixed calendar schedule with an optional drift guard."""

    def __init__(self, frequency: str = CALENDAR_FREQUENCY, target_allocation=None, min_drift: float = 0.01):
        super().__init__(target_allocation)
        if frequency not in ("weekly", "monthly"):
            raise ValueError("frequency must be 'weekly' or 'monthly'")
        self.frequency = frequency
        self.min_drift = min_drift

    def should_rebalance(self, portfolio: dict, prices: dict) -> bool:
        """Return True if schedule elapsed AND at least one asset exceeds min_drift from target.

        The drift guard prevents unnecessary cycles when the portfolio is already
        well-balanced on the scheduled day (e.g. markets moved it back to target).
        Set min_drift=0.0 to disable the guard and restore pure calendar behaviour.
        """
        last_str = portfolio.get("last_rebalanced")
        if not last_str:
            return True

        last = datetime.fromisoformat(last_str)
        now = utc_now()
        if last.tzinfo is None:
            last = last.replace(tzinfo=now.tzinfo)

        if self.frequency == "weekly":
            time_elapsed = (now - last) >= timedelta(weeks=1)
        else:
            time_elapsed = (now - last) >= timedelta(days=30)

        if not time_elapsed:
            return False

        if self.min_drift > 0.0:
            current_weights = self._compute_current_weights(portfolio, prices)
            if current_weights:
                max_drift = max(
                    abs(current_weights.get(ticker, 0.0) - target_w)
                    for ticker, target_w in self.target.items()
                )
                if max_drift <= self.min_drift:
                    return False

        return True

    def get_trades(self, portfolio: dict, prices: dict) -> list[dict]:
        return self._compute_trade_orders(portfolio, prices)
