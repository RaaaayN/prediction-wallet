"""Local FastMCP server exposing market tools."""

from __future__ import annotations

from mcp.server.fastmcp import FastMCP

from config import TARGET_ALLOCATION
from services.market_service import MarketService

mcp = FastMCP("prediction-wallet")
_market = MarketService()


@mcp.tool(name="market_snapshot", description="Return prices and metrics for the given tickers.")
def market_snapshot(tickers: list[str] | None = None) -> dict:
    tickers = tickers or list(TARGET_ALLOCATION.keys())
    prices = _market.get_latest_prices(tickers)
    metrics = {}
    for ticker in tickers:
        df = _market.get_historical(ticker, days=90)
        if df is not None and not df.empty:
            from market.metrics import PortfolioMetrics

            metrics[ticker] = PortfolioMetrics().ticker_metrics(df)
    return {
        "prices": prices,
        "metrics": metrics,
        "refresh_status": _market.get_refresh_status(),
    }


if __name__ == "__main__":
    mcp.run(transport="stdio")
