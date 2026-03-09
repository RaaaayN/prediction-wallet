"""Simulated order execution with slippage modeling."""

import json
import uuid
from dataclasses import dataclass, asdict
from datetime import datetime

from config import (
    PORTFOLIO_FILE,
    TRADES_LOG,
    SLIPPAGE_EQUITIES,
    SLIPPAGE_CRYPTO,
    CRYPTO_TICKERS,
    INITIAL_CAPITAL,
    TARGET_ALLOCATION,
)
from engine.orders import apply_slippage as _apply_slippage


@dataclass
class TradeResult:
    trade_id: str
    action: str
    ticker: str
    quantity: float
    market_price: float
    fill_price: float
    cost: float          # negative = cash outflow (buy), positive = cash inflow (sell)
    timestamp: str
    reason: str
    success: bool
    error: str = ""


class TradeSimulator:
    """Execute simulated trades with slippage and persist to portfolio.json + trades.log."""

    def __init__(self, portfolio_file: str = PORTFOLIO_FILE, trades_log: str = TRADES_LOG):
        self.portfolio_file = portfolio_file
        self.trades_log = trades_log

    # ------------------------------------------------------------------
    # Portfolio I/O
    # ------------------------------------------------------------------

    def load_portfolio(self) -> dict:
        try:
            with open(self.portfolio_file) as f:
                return json.load(f)
        except FileNotFoundError:
            return self._default_portfolio()

    def save_portfolio(self, portfolio: dict) -> None:
        import os
        os.makedirs(os.path.dirname(self.portfolio_file), exist_ok=True)
        with open(self.portfolio_file, "w") as f:
            json.dump(portfolio, f, indent=2, default=str)

    def _default_portfolio(self) -> dict:
        return {
            "positions": {},          # ticker → quantity
            "cash": INITIAL_CAPITAL,
            "peak_value": INITIAL_CAPITAL,
            "last_rebalanced": None,
            "history": [],            # list of {date, total_value}
            "created_at": datetime.utcnow().isoformat(),
        }

    # ------------------------------------------------------------------
    # Execution
    # ------------------------------------------------------------------

    def execute(
        self,
        action: str,
        ticker: str,
        quantity: float,
        market_price: float,
        reason: str = "",
        cycle_id: str = "",
    ) -> TradeResult:
        """
        Apply slippage, update portfolio.json, append to trades.log.
        action: "buy" | "sell"
        """
        trade_id = str(uuid.uuid4())[:8]
        timestamp = datetime.utcnow().isoformat()

        # Slippage
        fill_price = _apply_slippage(
            market_price, action, ticker, CRYPTO_TICKERS, SLIPPAGE_EQUITIES, SLIPPAGE_CRYPTO
        )

        gross = fill_price * quantity

        portfolio = self.load_portfolio()

        if action == "buy":
            if portfolio["cash"] < gross:
                # Scale down to available cash
                quantity = portfolio["cash"] / fill_price
                gross = fill_price * quantity
                if quantity < 0.0001:
                    return TradeResult(
                        trade_id=trade_id, action=action, ticker=ticker,
                        quantity=0, market_price=market_price, fill_price=fill_price,
                        cost=0, timestamp=timestamp, reason=reason,
                        success=False, error="Insufficient cash"
                    )
            portfolio["cash"] -= gross
            portfolio["positions"][ticker] = portfolio["positions"].get(ticker, 0) + quantity
            cost = -gross

        elif action == "sell":
            held = portfolio["positions"].get(ticker, 0)
            quantity = min(quantity, held)
            if quantity <= 0:
                return TradeResult(
                    trade_id=trade_id, action=action, ticker=ticker,
                    quantity=0, market_price=market_price, fill_price=fill_price,
                    cost=0, timestamp=timestamp, reason=reason,
                    success=False, error="No position to sell"
                )
            gross = fill_price * quantity
            portfolio["cash"] += gross
            portfolio["positions"][ticker] = held - quantity
            if portfolio["positions"][ticker] < 0.0001:
                del portfolio["positions"][ticker]
            cost = gross

        else:
            raise ValueError(f"Unknown action: {action}")

        # Update peak
        prices_approx = {t: fill_price if t == ticker else 0 for t in portfolio["positions"]}
        # We don't have all prices here — peak update happens in kill_switch or observe node
        # Just record history entry with current cash + known position value
        portfolio["last_rebalanced"] = timestamp

        self.save_portfolio(portfolio)

        result = TradeResult(
            trade_id=trade_id, action=action, ticker=ticker,
            quantity=quantity, market_price=market_price, fill_price=fill_price,
            cost=cost, timestamp=timestamp, reason=reason, success=True
        )
        self._log_trade(result, cycle_id=cycle_id)
        return result

    def _log_trade(self, result: TradeResult, cycle_id: str = "") -> None:
        import os
        os.makedirs(os.path.dirname(self.trades_log), exist_ok=True)
        with open(self.trades_log, "a") as f:
            f.write(json.dumps(asdict(result)) + "\n")
        try:
            from db.repository import save_execution
            save_execution(result, cycle_id=cycle_id)
        except Exception:
            pass  # DB persistence is non-blocking

    def get_trade_history(self) -> list[dict]:
        try:
            with open(self.trades_log) as f:
                return [json.loads(line) for line in f if line.strip()]
        except FileNotFoundError:
            return []

    def get_portfolio_value(self, prices: dict) -> float:
        portfolio = self.load_portfolio()
        value = portfolio["cash"]
        for ticker, qty in portfolio["positions"].items():
            value += qty * prices.get(ticker, 0)
        return value

    def update_peak(self, current_value: float) -> None:
        portfolio = self.load_portfolio()
        if current_value > portfolio.get("peak_value", 0):
            portfolio["peak_value"] = current_value
        # Append history
        portfolio.setdefault("history", []).append(
            {"date": datetime.utcnow().isoformat(), "total_value": current_value}
        )
        self.save_portfolio(portfolio)
