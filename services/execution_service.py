"""Execution service with deterministic validation and persistence orchestration."""

from __future__ import annotations

from dataclasses import asdict

from config import (
    CRYPTO_TICKERS,
    INITIAL_CAPITAL,
    MAX_ORDER_FRACTION_OF_PORTFOLIO,
    MAX_TRADES_PER_CYCLE,
    SLIPPAGE_CRYPTO,
    SLIPPAGE_EQUITIES,
    TARGET_ALLOCATION,
)
from engine.orders import apply_slippage
from engine.portfolio import compute_portfolio_value, compute_pnl, compute_weights
from execution.persistence import PortfolioStore, TradeLogStore
from execution.types import TradeResult
from utils.time import utc_now_iso


MIN_ORDER_QUANTITY = 0.0001


class ExecutionService:
    """Owns portfolio state, trade logging and deterministic execution rules."""

    def __init__(
        self,
        portfolio_store: PortfolioStore | None = None,
        trade_log_store: TradeLogStore | None = None,
        execution_repo=None,
    ):
        self.portfolio_store = portfolio_store or PortfolioStore()
        self.trade_log_store = trade_log_store or TradeLogStore()
        self.execution_repo = execution_repo

    def load_portfolio(self) -> dict:
        return self.portfolio_store.load()

    def save_portfolio(self, portfolio: dict) -> None:
        self.portfolio_store.save(portfolio)

    def get_trade_history(self) -> list[dict]:
        return self.trade_log_store.read_all()

    def update_peak(self, current_value: float) -> None:
        portfolio = self.load_portfolio()
        if current_value > portfolio.get("peak_value", 0):
            portfolio["peak_value"] = current_value
        portfolio.setdefault("history", []).append(
            {"date": utc_now_iso(), "total_value": current_value}
        )
        self.save_portfolio(portfolio)

    def get_portfolio_value(self, prices: dict[str, float]) -> float:
        portfolio = self.load_portfolio()
        return compute_portfolio_value(portfolio.get("positions", {}), portfolio.get("cash", 0.0), prices)

    def portfolio_snapshot(self, prices: dict[str, float]) -> dict:
        portfolio = self.load_portfolio()
        positions = portfolio.get("positions", {})
        cash = portfolio.get("cash", 0.0)
        peak = portfolio.get("peak_value", cash)
        total = compute_portfolio_value(positions, cash, prices)
        weights = compute_weights(positions, prices, cash)
        weight_diff = {t: weights.get(t, 0.0) - TARGET_ALLOCATION.get(t, 0.0) for t in TARGET_ALLOCATION}
        pnl = compute_pnl(total, INITIAL_CAPITAL)
        return {
            "positions": positions,
            "cash": cash,
            "peak_value": peak,
            "total_value": total,
            "current_weights": weights,
            "target_weights": TARGET_ALLOCATION,
            "weight_deviation": weight_diff,
            "pnl_dollars": pnl["pnl_dollars"],
            "pnl_pct": pnl["pnl_pct"],
            "last_rebalanced": portfolio.get("last_rebalanced"),
        }

    def validate_order(
        self,
        action: str,
        ticker: str,
        quantity: float,
        portfolio: dict,
        market_price: float,
        trades_this_cycle: int = 0,
    ) -> str | None:
        if ticker not in TARGET_ALLOCATION:
            return f"Ticker '{ticker}' is not in the active target allocation."
        if action not in {"buy", "sell"}:
            return f"Unsupported action '{action}'."
        if quantity <= 0 or quantity < MIN_ORDER_QUANTITY:
            return "Quantity is too small."
        if market_price <= 0:
            return f"Could not get a valid price for {ticker}."
        if trades_this_cycle >= MAX_TRADES_PER_CYCLE:
            return f"Trade limit per cycle reached ({MAX_TRADES_PER_CYCLE})."

        total_value = compute_portfolio_value(portfolio.get("positions", {}), portfolio.get("cash", 0.0), {ticker: market_price})
        order_notional = quantity * market_price
        if total_value > 0 and order_notional / total_value > MAX_ORDER_FRACTION_OF_PORTFOLIO:
            return f"Order exceeds max notional limit ({MAX_ORDER_FRACTION_OF_PORTFOLIO:.0%} of portfolio)."

        if action == "sell" and portfolio.get("positions", {}).get(ticker, 0.0) <= 0:
            return f"No position to sell for {ticker}."
        return None

    def execute_order(
        self,
        order: dict,
        market_price: float,
        cycle_id: str = "",
        trades_this_cycle: int = 0,
    ) -> TradeResult:
        action = order["action"]
        ticker = order["ticker"]
        quantity = float(order["quantity"])
        reason = order.get("reason", "")

        portfolio = self.load_portfolio()
        validation_error = self.validate_order(action, ticker, quantity, portfolio, market_price, trades_this_cycle)
        timestamp = utc_now_iso()
        if validation_error:
            return TradeResult(
                trade_id="",
                action=action,
                ticker=ticker,
                quantity=0.0,
                market_price=market_price,
                fill_price=market_price,
                cost=0.0,
                timestamp=timestamp,
                reason=reason,
                success=False,
                error=validation_error,
            )

        fill_price = apply_slippage(
            market_price, action, ticker, CRYPTO_TICKERS, SLIPPAGE_EQUITIES, SLIPPAGE_CRYPTO
        )
        gross = fill_price * quantity

        if action == "buy":
            if portfolio["cash"] < gross:
                quantity = portfolio["cash"] / fill_price
                gross = fill_price * quantity
                if quantity < MIN_ORDER_QUANTITY:
                    return TradeResult(
                        trade_id="",
                        action=action,
                        ticker=ticker,
                        quantity=0.0,
                        market_price=market_price,
                        fill_price=fill_price,
                        cost=0.0,
                        timestamp=timestamp,
                        reason=reason,
                        success=False,
                        error="Insufficient cash",
                    )
            portfolio["cash"] -= gross
            portfolio["positions"][ticker] = portfolio["positions"].get(ticker, 0.0) + quantity
            cost = -gross
        else:
            held = portfolio["positions"].get(ticker, 0.0)
            quantity = min(quantity, held)
            if quantity < MIN_ORDER_QUANTITY:
                return TradeResult(
                    trade_id="",
                    action=action,
                    ticker=ticker,
                    quantity=0.0,
                    market_price=market_price,
                    fill_price=fill_price,
                    cost=0.0,
                    timestamp=timestamp,
                    reason=reason,
                    success=False,
                    error="No position to sell",
                )
            gross = fill_price * quantity
            portfolio["cash"] += gross
            portfolio["positions"][ticker] = held - quantity
            if portfolio["positions"][ticker] < MIN_ORDER_QUANTITY:
                del portfolio["positions"][ticker]
            cost = gross

        trade = TradeResult.build(
            action=action,
            ticker=ticker,
            quantity=quantity,
            market_price=market_price,
            fill_price=fill_price,
            cost=cost,
            timestamp=timestamp,
            reason=reason,
            success=True,
        )
        portfolio["last_rebalanced"] = timestamp
        self.save_portfolio(portfolio)
        self.trade_log_store.append(trade)
        if self.execution_repo is not None:
            self.execution_repo(trade, cycle_id=cycle_id)
        return trade

    def serialize_trade(self, trade: TradeResult) -> dict:
        return asdict(trade)
