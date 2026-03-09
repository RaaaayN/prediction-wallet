"""Claude tools exposed to the agent via the Anthropic tool_use API."""

import json
from datetime import datetime

from config import TARGET_ALLOCATION, CRYPTO_TICKERS
from engine.portfolio import compute_weights as _compute_weights
from execution.simulator import TradeSimulator
from execution.kill_switch import KillSwitch
from market.fetcher import MarketDataService
from market.metrics import PortfolioMetrics
from reporting.pdf_report import PDFReporter

_simulator = TradeSimulator()
_fetcher = MarketDataService()
_kill_switch = KillSwitch()
_reporter = PDFReporter()
_metrics = PortfolioMetrics()

# ---------------------------------------------------------------------------
# Tool schemas (Anthropic tool_use format)
# ---------------------------------------------------------------------------

TOOL_SCHEMAS = [
    {
        "name": "get_portfolio_state",
        "description": (
            "Returns current portfolio: positions (ticker→quantity), cash balance, "
            "total market value, current vs target weights, P&L, and drawdown from peak."
        ),
        "input_schema": {
            "type": "object",
            "properties": {},
            "required": [],
        },
    },
    {
        "name": "get_market_data",
        "description": (
            "Returns latest price, 30-day annualized volatility, YTD return, and Sharpe ratio "
            "for the specified tickers."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "tickers": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "List of ticker symbols, e.g. [\"AAPL\", \"BTC-USD\"]",
                }
            },
            "required": ["tickers"],
        },
    },
    {
        "name": "execute_trade",
        "description": (
            "Simulate a buy or sell order with realistic slippage. "
            "Updates portfolio.json and appends to trades.log."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "action": {"type": "string", "enum": ["buy", "sell"]},
                "ticker": {"type": "string", "description": "Ticker symbol"},
                "quantity": {"type": "number", "description": "Number of shares/units"},
                "reason": {"type": "string", "description": "Justification for this trade"},
            },
            "required": ["action", "ticker", "quantity", "reason"],
        },
    },
    {
        "name": "generate_report",
        "description": "Generate a PDF audit report for this rebalancing cycle. Returns the file path.",
        "input_schema": {
            "type": "object",
            "properties": {
                "cycle_id": {"type": "string", "description": "Cycle UUID for the report filename"},
            },
            "required": ["cycle_id"],
        },
    },
    {
        "name": "get_performance_metrics",
        "description": (
            "Returns comprehensive portfolio performance metrics: cumulative return (gross/net), "
            "annualized return, volatility, Sharpe ratio, max drawdown, turnover, "
            "transaction costs, and hit ratio."
        ),
        "input_schema": {
            "type": "object",
            "properties": {},
            "required": [],
        },
    },
]


# ---------------------------------------------------------------------------
# Tool implementations
# ---------------------------------------------------------------------------

def get_portfolio_state() -> dict:
    """Return current portfolio state with weights and metrics."""
    portfolio = _simulator.load_portfolio()
    prices = _fetcher.get_latest_prices(list(TARGET_ALLOCATION.keys()))

    positions = portfolio.get("positions", {})
    cash = portfolio.get("cash", 0.0)
    peak = portfolio.get("peak_value", cash)

    market_values = {t: qty * prices.get(t, 0) for t, qty in positions.items()}
    total = sum(market_values.values()) + cash

    current_weights = _compute_weights(positions, prices, cash)

    weight_diff = {
        t: current_weights.get(t, 0.0) - TARGET_ALLOCATION.get(t, 0.0)
        for t in TARGET_ALLOCATION
    }

    drawdown = _metrics.current_drawdown(total, peak)

    pnl = total - portfolio.get("cash", 0) - sum(
        qty * prices.get(t, 0) for t, qty in positions.items()
    ) if False else (total - peak if peak > 0 else 0)  # simplified: unrealized vs peak

    return {
        "positions": positions,
        "prices": prices,
        "market_values": market_values,
        "cash": cash,
        "total_value": total,
        "peak_value": peak,
        "drawdown": drawdown,
        "current_weights": current_weights,
        "target_weights": TARGET_ALLOCATION,
        "weight_deviation": weight_diff,
        "last_rebalanced": portfolio.get("last_rebalanced"),
    }


def get_market_data(tickers: list[str]) -> dict:
    """Return price, volatility, YTD return, and Sharpe per ticker."""
    result = {}
    for ticker in tickers:
        df = _fetcher.get_historical(ticker, days=252)
        if df is not None and not df.empty:
            result[ticker] = _metrics.ticker_metrics(df)
        else:
            result[ticker] = {"error": f"No data for {ticker}"}
    return result


def execute_trade(action: str, ticker: str, quantity: float, reason: str) -> dict:
    """Execute a simulated trade and return the result."""
    prices = _fetcher.get_latest_prices([ticker])
    market_price = prices.get(ticker, 0)
    if market_price <= 0:
        return {"success": False, "error": f"Could not get price for {ticker}"}

    result = _simulator.execute(action, ticker, quantity, market_price, reason)

    # Update peak after trade
    all_prices = _fetcher.get_latest_prices(list(TARGET_ALLOCATION.keys()))
    portfolio = _simulator.load_portfolio()
    total = portfolio["cash"] + sum(
        qty * all_prices.get(t, 0) for t, qty in portfolio["positions"].items()
    )
    _simulator.update_peak(total)

    return {
        "trade_id": result.trade_id,
        "action": result.action,
        "ticker": result.ticker,
        "quantity": result.quantity,
        "fill_price": result.fill_price,
        "cost": result.cost,
        "timestamp": result.timestamp,
        "success": result.success,
        "error": result.error,
    }


def get_performance_metrics() -> dict:
    """Return comprehensive performance metrics for the current portfolio history."""
    from engine.performance import performance_report as _perf_report

    portfolio = _simulator.load_portfolio()
    history = portfolio.get("history", [])
    trades = _simulator.get_trade_history()

    if not history:
        return {"error": "No portfolio history available yet. Run at least one agent cycle first."}

    report = _perf_report(history=history, trades=trades)

    # Format percentages for readability
    return {
        k: (f"{v:.2%}" if isinstance(v, float) and "return" in k or "drawdown" in k or "volatility" in k or "error" in k else
            f"${v:,.2f}" if isinstance(v, float) and "cost" in k else
            round(v, 4) if isinstance(v, float) else v)
        for k, v in report.items()
    }


def generate_report(cycle_id: str) -> str:
    """Generate PDF report and return file path."""
    portfolio = _simulator.load_portfolio()
    prices = _fetcher.get_latest_prices(list(TARGET_ALLOCATION.keys()))
    trades = _simulator.get_trade_history()

    # Compute metrics for report
    market_data = {}
    for ticker in TARGET_ALLOCATION:
        df = _fetcher.get_historical(ticker, days=90)
        if df is not None and not df.empty:
            market_data[ticker] = _metrics.ticker_metrics(df)

    path = _reporter.generate(
        portfolio=portfolio,
        prices=prices,
        trades=trades,
        market_data=market_data,
        cycle_id=cycle_id,
    )
    return path


# ---------------------------------------------------------------------------
# Dispatcher: routes tool_name + tool_input → result
# ---------------------------------------------------------------------------

def dispatch_tool(tool_name: str, tool_input: dict) -> str:
    """Call the appropriate tool function and return JSON string result."""
    try:
        if tool_name == "get_portfolio_state":
            result = get_portfolio_state()
        elif tool_name == "get_market_data":
            result = get_market_data(tool_input["tickers"])
        elif tool_name == "execute_trade":
            result = execute_trade(
                action=tool_input["action"],
                ticker=tool_input["ticker"],
                quantity=float(tool_input["quantity"]),
                reason=tool_input.get("reason", ""),
            )
        elif tool_name == "generate_report":
            result = {"path": generate_report(tool_input["cycle_id"])}
        elif tool_name == "get_performance_metrics":
            result = get_performance_metrics()
        else:
            result = {"error": f"Unknown tool: {tool_name}"}
    except Exception as exc:
        result = {"error": str(exc)}

    return json.dumps(result, default=str)
