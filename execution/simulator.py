"""Backward-compatible execution facade."""

from config import PORTFOLIO_FILE, TRADES_LOG
from execution.persistence import PortfolioStore, TradeLogStore
from execution.types import TradeResult
from services.execution_service import ExecutionService


class TradeSimulator:
    """Compatibility wrapper over ExecutionService."""

    def __init__(self, portfolio_file: str = PORTFOLIO_FILE, trades_log: str = TRADES_LOG):
        self._service = ExecutionService(
            portfolio_store=PortfolioStore(portfolio_file),
            trade_log_store=TradeLogStore(trades_log),
        )

    def load_portfolio(self) -> dict:
        return self._service.load_portfolio()

    def save_portfolio(self, portfolio: dict) -> None:
        self._service.save_portfolio(portfolio)

    def _default_portfolio(self) -> dict:
        return PortfolioStore.default_portfolio()

    def execute(
        self,
        action: str,
        ticker: str,
        quantity: float,
        market_price: float,
        reason: str = "",
        cycle_id: str = "",
    ) -> TradeResult:
        return self._service.execute_order(
            {
                "action": action,
                "ticker": ticker,
                "quantity": quantity,
                "reason": reason,
            },
            market_price=market_price,
            cycle_id=cycle_id,
        )

    def get_trade_history(self) -> list[dict]:
        return self._service.get_trade_history()

    def get_portfolio_value(self, prices: dict) -> float:
        return self._service.get_portfolio_value(prices)

    def update_peak(self, current_value: float) -> None:
        self._service.update_peak(current_value)
