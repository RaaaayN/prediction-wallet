"""Reporting service wrapper."""

from __future__ import annotations

from config import TARGET_ALLOCATION
from market.metrics import PortfolioMetrics
from reporting.pdf_report import PDFReporter


class ReportingService:
    def __init__(self, reporter: PDFReporter | None = None, market_service=None, execution_service=None):
        self.reporter = reporter or PDFReporter()
        self.market_service = market_service
        self.execution_service = execution_service
        self.metrics = PortfolioMetrics()

    def generate_cycle_report(self, cycle_id: str) -> str:
        portfolio = self.execution_service.load_portfolio()
        prices = self.market_service.get_latest_prices(list(TARGET_ALLOCATION.keys()))
        trades = self.execution_service.get_trade_history()
        market_data = {}
        for ticker in TARGET_ALLOCATION:
            df = self.market_service.get_historical(ticker, days=90)
            if df is not None and not df.empty:
                market_data[ticker] = self.metrics.ticker_metrics(df)
        return self.reporter.generate(
            portfolio=portfolio,
            prices=prices,
            trades=trades,
            market_data=market_data,
            cycle_id=cycle_id,
        )
