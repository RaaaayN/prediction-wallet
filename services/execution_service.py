"""Execution service with deterministic validation and persistence orchestration."""

from __future__ import annotations

from dataclasses import asdict

from config import (
    MAX_ORDER_FRACTION_OF_PORTFOLIO,
    MAX_TRADES_PER_CYCLE,
)
from engine.hedge_fund import compute_exposures
from engine.orders import apply_slippage
from engine.projection import project_trade_state
from engine.portfolio import compute_portfolio_value, compute_pnl, compute_weights
from execution.persistence import PortfolioStore, TradeLogStore
from execution.types import TradeResult
from runtime_context import build_runtime_context
from utils.time import utc_now_iso


MIN_ORDER_QUANTITY = 0.0001


class ExecutionService:
    """Owns portfolio state, trade logging and deterministic execution rules."""

    def __init__(
        self,
        portfolio_store: PortfolioStore | None = None,
        trade_log_store: TradeLogStore | None = None,
        execution_repo=None,
        *,
        profile_name: str | None = None,
        runtime_context=None,
    ):
        self.runtime_context = runtime_context or build_runtime_context(profile_name)
        self.portfolio_store = portfolio_store or PortfolioStore(runtime_context=self.runtime_context)
        self.trade_log_store = trade_log_store or TradeLogStore(runtime_context=self.runtime_context)
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
        position_sides = portfolio.get("position_sides", {})
        average_costs = portfolio.get("average_costs", {})
        cash = portfolio.get("cash", 0.0)
        peak = portfolio.get("peak_value", cash)
        total = compute_portfolio_value(positions, cash, prices)
        weights = compute_weights(positions, prices, cash)
        target_allocation = self.runtime_context.target_allocation
        weight_diff = {t: weights.get(t, 0.0) - target_allocation.get(t, 0.0) for t in target_allocation}
        pnl = compute_pnl(total, self.runtime_context.initial_capital)
        return {
            "positions": positions,
            "position_sides": position_sides,
            "average_costs": average_costs,
            "cash": cash,
            "peak_value": peak,
            "total_value": total,
            "current_weights": weights,
            "target_weights": target_allocation,
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
        prices: dict[str, float] | None = None,
        trades_this_cycle: int = 0,
        bypass_allocation_check: bool = False,
    ) -> str | None:
        if not bypass_allocation_check and ticker not in self.runtime_context.target_allocation:
            return f"Ticker '{ticker}' is not in the active target allocation."
        if action not in {"buy", "sell"}:
            return f"Unsupported action '{action}'."
        if quantity <= 0 or quantity < MIN_ORDER_QUANTITY:
            return "Quantity is too small."
        if market_price <= 0:
            return f"Could not get a valid price for {ticker}."
        if trades_this_cycle >= MAX_TRADES_PER_CYCLE:
            return f"Trade limit per cycle reached ({MAX_TRADES_PER_CYCLE})."

        price_map = dict(prices or {})
        price_map.setdefault(ticker, market_price)
        total_value = compute_portfolio_value(portfolio.get("positions", {}), portfolio.get("cash", 0.0), price_map)
        order_notional = quantity * market_price
        if total_value > 0 and order_notional / total_value > MAX_ORDER_FRACTION_OF_PORTFOLIO:
            return f"Order exceeds max notional limit ({MAX_ORDER_FRACTION_OF_PORTFOLIO:.0%} of portfolio)."

        return None

    def execute_order(
        self,
        order: dict,
        market_price: float,
        prices: dict[str, float] | None = None,
        cycle_id: str = "",
        trades_this_cycle: int = 0,
        allow_unallocated: bool = False,
    ) -> TradeResult:
        action = order["action"]
        ticker = order["ticker"]
        quantity = float(order["quantity"])
        reason = order.get("reason", "")
        side = order.get("side", "long")
        idea_id = order.get("idea_id")
        sleeve = order.get("sleeve", "core_longs")

        portfolio = self.load_portfolio()
        portfolio.setdefault("position_sides", {})
        portfolio.setdefault("average_costs", {})
        portfolio.setdefault("position_ideas", {})
        portfolio_prices = dict(prices or {})
        portfolio_prices.setdefault(ticker, market_price)
        validation_error = self.validate_order(
            action,
            ticker,
            quantity,
            portfolio,
            market_price,
            prices=portfolio_prices,
            trades_this_cycle=trades_this_cycle,
            bypass_allocation_check=allow_unallocated,
        )
        timestamp = utc_now_iso()
        beta_map = {
            name: (self.runtime_context.hedge_fund_profile.get("universe", {}).get(name, {}) or {}).get("beta", 1.0)
            for name in set(portfolio.get("positions", {})) | {ticker}
        }
        current_exposure = compute_exposures(
            portfolio.get("positions", {}),
            portfolio_prices,
            portfolio.get("cash", 0.0),
            position_sides=portfolio.get("position_sides", {}),
            sector_map=self.runtime_context.sector_map,
            beta_map=beta_map,
        )
        exposure_before = current_exposure.get("single_name_concentration", {}).get(ticker, 0.0)
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
                side=side,
                idea_id=idea_id,
                sleeve=sleeve,
                exposure_before=exposure_before,
                exposure_after=exposure_before,
            )

        fill_price = apply_slippage(
            market_price,
            action,
            ticker,
            self.runtime_context.crypto_tickers,
            self.runtime_context.slippage_equities,
            self.runtime_context.slippage_crypto,
        )
        gross = fill_price * quantity

        held = float(portfolio["positions"].get(ticker, 0.0))
        current_side = portfolio["position_sides"].get(ticker, "short" if held < 0 else "long")
        average_cost = float(portfolio["average_costs"].get(ticker, market_price))

        if side == "short":
            if action == "sell":
                portfolio["cash"] += gross
                new_qty = held - quantity
                portfolio["positions"][ticker] = new_qty
                portfolio["position_sides"][ticker] = "short"
                portfolio["position_ideas"][ticker] = idea_id
                if held < 0:
                    portfolio["average_costs"][ticker] = ((abs(held) * average_cost) + gross) / max(abs(new_qty), MIN_ORDER_QUANTITY)
                else:
                    portfolio["average_costs"][ticker] = fill_price
                cost = gross
            else:  # buy to cover
                if held >= 0:
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
                        error="No short position to cover",
                        side=side,
                        idea_id=idea_id,
                        sleeve=sleeve,
                        exposure_before=exposure_before,
                        exposure_after=exposure_before,
                    )
                quantity = min(quantity, abs(held))
                gross = fill_price * quantity
                portfolio["cash"] -= gross
                new_qty = held + quantity
                if abs(new_qty) < MIN_ORDER_QUANTITY:
                    portfolio["positions"].pop(ticker, None)
                    portfolio["position_sides"].pop(ticker, None)
                    portfolio["average_costs"].pop(ticker, None)
                    portfolio["position_ideas"].pop(ticker, None)
                else:
                    portfolio["positions"][ticker] = new_qty
                cost = -gross
        else:
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
                            side=side,
                            idea_id=idea_id,
                            sleeve=sleeve,
                            exposure_before=exposure_before,
                            exposure_after=exposure_before,
                        )
                portfolio["cash"] -= gross
                portfolio["positions"][ticker] = held + quantity
                portfolio["position_sides"][ticker] = "long"
                portfolio["position_ideas"][ticker] = idea_id
                if held > 0:
                    portfolio["average_costs"][ticker] = ((held * average_cost) + gross) / max(held + quantity, MIN_ORDER_QUANTITY)
                else:
                    portfolio["average_costs"][ticker] = fill_price
                cost = -gross
            else:
                if held <= 0:
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
                        error="No long position to sell",
                        side=side,
                        idea_id=idea_id,
                        sleeve=sleeve,
                        exposure_before=exposure_before,
                        exposure_after=exposure_before,
                    )
                quantity = min(quantity, held)
                gross = fill_price * quantity
                portfolio["cash"] += gross
                portfolio["positions"][ticker] = held - quantity
                if portfolio["positions"][ticker] < MIN_ORDER_QUANTITY:
                    del portfolio["positions"][ticker]
                    portfolio["position_sides"].pop(ticker, None)
                    portfolio["average_costs"].pop(ticker, None)
                    portfolio["position_ideas"].pop(ticker, None)
                cost = gross

        updated_exposure = compute_exposures(
            portfolio.get("positions", {}),
            portfolio_prices,
            portfolio.get("cash", 0.0),
            position_sides=portfolio.get("position_sides", {}),
            sector_map=self.runtime_context.sector_map,
            beta_map=beta_map,
        )
        exposure_after = updated_exposure.get("single_name_concentration", {}).get(ticker, 0.0)
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
            side=side,
            idea_id=idea_id,
            sleeve=sleeve,
            exposure_before=exposure_before,
            exposure_after=exposure_after,
            gross_impact=exposure_after - exposure_before,
            net_impact=(quantity * fill_price / max(portfolio.get("peak_value", self.runtime_context.initial_capital), self.runtime_context.initial_capital)) * (1 if action == "buy" else -1),
        )
        portfolio["last_rebalanced"] = timestamp
        self.save_portfolio(portfolio)
        self.trade_log_store.append(trade)
        if self.execution_repo is not None:
            self.execution_repo(trade, cycle_id=cycle_id)
        return trade

    def serialize_trade(self, trade: TradeResult) -> dict:
        return asdict(trade)
