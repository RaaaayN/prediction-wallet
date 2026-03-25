"""Tests for ExecutionPolicyEngine hard/soft violation semantics."""
from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from agents.models import TradeDecision, TradeProposal
from agents.policies import ExecutionPolicyEngine
from config import MAX_ORDER_FRACTION_OF_PORTFOLIO, MAX_TRADES_PER_CYCLE, TARGET_ALLOCATION

_VALID_TICKER = next(iter(TARGET_ALLOCATION))  # first ticker in universe (e.g. AAPL)
_VALID_PRICE = 150.0
_VALID_QTY = 1.0


def _make_obs(
    kill_switch: bool = False,
    prices: dict | None = None,
    trade_plan: list | None = None,
    total_value: float = 100_000.0,
) -> MagicMock:
    obs = MagicMock()
    obs.risk.kill_switch_active = kill_switch
    obs.market.prices = prices if prices is not None else {_VALID_TICKER: _VALID_PRICE}
    obs.trade_plan = trade_plan if trade_plan is not None else []
    obs.portfolio.total_value = total_value
    return obs


def _make_trade(
    ticker: str = _VALID_TICKER,
    action: str = "buy",
    quantity: float = _VALID_QTY,
    reason: str = "test",
) -> TradeProposal:
    return TradeProposal(action=action, ticker=ticker, quantity=quantity, reason=reason)


def _make_decision(trades: list[TradeProposal]) -> TradeDecision:
    return TradeDecision(
        cycle_id="test",
        summary="test",
        market_outlook="neutral",
        rationale="test",
        rebalance_needed=bool(trades),
        approved_trades=trades,
        rejected_trades=[],
        risk_flags=[],
    )


engine = ExecutionPolicyEngine()


# ── Hard violation tests ───────────────────────────────────────────────────────

def test_kill_switch_is_hard_violation():
    trade = _make_trade()
    obs = _make_obs(kill_switch=True, prices={_VALID_TICKER: _VALID_PRICE}, trade_plan=[trade])
    result = engine.evaluate(_make_decision([trade]), obs, "simulate")

    assert result.approved is False
    assert result.allowed_trades == []
    assert result.blocked_trades == []  # early return — no trade evaluation
    assert any(v.code == "kill_switch_active" for v in result.violations)


def test_live_mode_is_hard_violation():
    obs = _make_obs()
    result = engine.evaluate(_make_decision([]), obs, "live")

    assert result.approved is False
    assert result.violations[0].code == "live_blocked"


def test_too_many_trades_is_hard_violation():
    trades = [_make_trade(reason=str(i)) for i in range(MAX_TRADES_PER_CYCLE + 1)]
    obs = _make_obs()
    result = engine.evaluate(_make_decision(trades), obs, "simulate")

    assert result.approved is False
    assert any(v.code == "too_many_trades" for v in result.violations)


def test_kill_switch_beats_valid_trades():
    """Hard violation prevents execution even when all trades would otherwise pass."""
    trade = _make_trade()
    obs = _make_obs(
        kill_switch=True,
        prices={_VALID_TICKER: _VALID_PRICE},
        trade_plan=[trade],
    )
    result = engine.evaluate(_make_decision([trade]), obs, "simulate")

    assert result.approved is False
    assert result.allowed_trades == []


# ── Soft block tests ───────────────────────────────────────────────────────────

def test_missing_price_blocks_only_that_trade():
    """A trade with price=0 is blocked but approved=True; other trades are unaffected."""
    trade = _make_trade()
    obs = _make_obs(prices={_VALID_TICKER: 0.0}, trade_plan=[trade])
    result = engine.evaluate(_make_decision([trade]), obs, "simulate")

    assert result.approved is True
    assert result.allowed_trades == []
    assert result.blocked_trades[0].ticker == _VALID_TICKER
    assert result.violations == []


def test_unknown_ticker_blocks_only_that_trade():
    valid_trade = _make_trade()
    invalid_trade = _make_trade(ticker="TSLA")  # not in TARGET_ALLOCATION
    obs = _make_obs(
        prices={_VALID_TICKER: _VALID_PRICE},
        trade_plan=[valid_trade],
    )
    result = engine.evaluate(_make_decision([valid_trade, invalid_trade]), obs, "simulate")

    assert result.approved is True
    assert len(result.allowed_trades) == 1
    assert result.allowed_trades[0].ticker == _VALID_TICKER
    assert result.blocked_trades[0].ticker == "TSLA"
    assert result.violations == []


def test_trade_not_in_plan_is_soft_block():
    trade = _make_trade()
    obs = _make_obs(
        prices={_VALID_TICKER: _VALID_PRICE},
        trade_plan=[],  # empty plan → trade not in plan_index
    )
    result = engine.evaluate(_make_decision([trade]), obs, "simulate")

    assert result.approved is True
    assert result.allowed_trades == []
    assert "not in the deterministic trade plan" in result.blocked_trades[0].rejection_reason


def test_notional_cap_is_soft_block():
    qty = (MAX_ORDER_FRACTION_OF_PORTFOLIO * 100_000.0 / _VALID_PRICE) + 1.0
    trade = _make_trade(quantity=qty)
    obs = _make_obs(prices={_VALID_TICKER: _VALID_PRICE}, trade_plan=[trade])
    result = engine.evaluate(_make_decision([trade]), obs, "simulate")

    assert result.approved is True
    assert result.blocked_trades[0].ticker == _VALID_TICKER
    assert "notional cap" in result.blocked_trades[0].rejection_reason


def test_all_valid_trades_approved():
    trade = _make_trade()
    obs = _make_obs(prices={_VALID_TICKER: _VALID_PRICE}, trade_plan=[trade])
    result = engine.evaluate(_make_decision([trade]), obs, "simulate")

    assert result.approved is True
    assert len(result.allowed_trades) == 1
    assert result.blocked_trades == []
    assert result.violations == []


def test_no_trades_is_approved():
    obs = _make_obs()
    result = engine.evaluate(_make_decision([]), obs, "simulate")

    assert result.approved is True
    assert result.allowed_trades == []
    assert result.violations == []
