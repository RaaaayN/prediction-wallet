"""Tests for ExecutionPolicyEngine hard/soft violation semantics."""
from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from agents.models import TradeDecision, TradeProposal
from agents.policies import ExecutionPolicyEngine, PolicyConfig
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


# ── PolicyConfig tests ─────────────────────────────────────────────────────────

def test_policy_config_defaults_are_neutral():
    """Default PolicyConfig disables all optional checks."""
    cfg = PolicyConfig()
    assert cfg.min_confidence == 0.0
    assert cfg.stale_data_blocks is False
    assert cfg.per_ticker_max_fraction == {}


def test_policy_config_from_profile_parses_values():
    """PolicyConfig.from_profile() reads the policy: block correctly."""
    profile = {
        "policy": {
            "min_confidence": 0.3,
            "stale_data_blocks": True,
            "per_ticker_max_fraction": {"BTC-USD": 0.15},
        }
    }
    cfg = PolicyConfig.from_profile(profile)
    assert cfg.min_confidence == 0.3
    assert cfg.stale_data_blocks is True
    assert cfg.per_ticker_max_fraction == {"BTC-USD": 0.15}


def test_policy_config_from_profile_missing_policy_section():
    """Profile without policy: section produces neutral defaults."""
    cfg = PolicyConfig.from_profile({"target_allocation": {}})
    assert cfg.min_confidence == 0.0
    assert cfg.stale_data_blocks is False


# ── Layer 1: market context tests ─────────────────────────────────────────────

def test_low_confidence_soft_blocks_all_trades():
    """When decision.confidence < min_confidence, all trades are soft-blocked."""
    cfg = PolicyConfig(min_confidence=0.5)
    eng = ExecutionPolicyEngine(cfg)
    trade = _make_trade()
    obs = _make_obs(prices={_VALID_TICKER: _VALID_PRICE}, trade_plan=[trade])
    decision = _make_decision([trade])
    decision = decision.model_copy(update={"confidence": 0.2})

    result = eng.evaluate(decision, obs, "simulate")

    assert result.approved is True   # soft block, not hard abort
    assert result.allowed_trades == []
    assert len(result.blocked_trades) == 1
    assert result.blocked_trades[0].ticker == _VALID_TICKER
    assert "confidence" in result.blocked_trades[0].rejection_reason.lower()
    assert result.violations == []


def test_sufficient_confidence_passes_through():
    """When decision.confidence >= min_confidence, the market context check passes."""
    cfg = PolicyConfig(min_confidence=0.3)
    eng = ExecutionPolicyEngine(cfg)
    trade = _make_trade()
    obs = _make_obs(prices={_VALID_TICKER: _VALID_PRICE}, trade_plan=[trade])
    decision = _make_decision([trade])
    decision = decision.model_copy(update={"confidence": 0.8})

    result = eng.evaluate(decision, obs, "simulate")

    assert result.approved is True
    assert len(result.allowed_trades) == 1


def test_stale_data_blocks_all_trades_when_enabled():
    """stale_data_blocks=True + data_freshness='stale' → all trades soft-blocked."""
    cfg = PolicyConfig(stale_data_blocks=True)
    eng = ExecutionPolicyEngine(cfg)
    trade = _make_trade()
    obs = _make_obs(prices={_VALID_TICKER: _VALID_PRICE}, trade_plan=[trade])
    decision = _make_decision([trade])
    decision = decision.model_copy(update={"data_freshness": "stale"})

    result = eng.evaluate(decision, obs, "simulate")

    assert result.approved is True
    assert result.allowed_trades == []
    assert "stale" in result.blocked_trades[0].rejection_reason.lower()


def test_stale_data_does_not_block_when_disabled():
    """stale_data_blocks=False (default) ignores data_freshness."""
    cfg = PolicyConfig(stale_data_blocks=False)
    eng = ExecutionPolicyEngine(cfg)
    trade = _make_trade()
    obs = _make_obs(prices={_VALID_TICKER: _VALID_PRICE}, trade_plan=[trade])
    decision = _make_decision([trade])
    decision = decision.model_copy(update={"data_freshness": "stale"})

    result = eng.evaluate(decision, obs, "simulate")

    assert result.approved is True
    assert len(result.allowed_trades) == 1


def test_partial_freshness_does_not_block():
    """data_freshness='partial' never triggers stale_data_blocks (only 'stale' does)."""
    cfg = PolicyConfig(stale_data_blocks=True)
    eng = ExecutionPolicyEngine(cfg)
    trade = _make_trade()
    obs = _make_obs(prices={_VALID_TICKER: _VALID_PRICE}, trade_plan=[trade])
    decision = _make_decision([trade])
    decision = decision.model_copy(update={"data_freshness": "partial"})

    result = eng.evaluate(decision, obs, "simulate")

    assert result.approved is True
    assert len(result.allowed_trades) == 1


def test_layer1_soft_block_does_not_prevent_hard_violations():
    """Kill switch (hard violation) takes priority over low confidence (soft block)."""
    cfg = PolicyConfig(min_confidence=0.9)
    eng = ExecutionPolicyEngine(cfg)
    trade = _make_trade()
    obs = _make_obs(kill_switch=True, prices={_VALID_TICKER: _VALID_PRICE}, trade_plan=[trade])
    decision = _make_decision([trade])
    decision = decision.model_copy(update={"confidence": 0.1})

    result = eng.evaluate(decision, obs, "simulate")

    assert result.approved is False  # hard violation wins
    assert any(v.code == "kill_switch_active" for v in result.violations)


# ── Layer 2: per-ticker cap tests ─────────────────────────────────────────────

def test_per_ticker_cap_blocks_oversized_trade():
    """A trade within the global cap but exceeding a per-ticker cap is soft-blocked."""
    tight_cap = 0.001  # 0.1% — tiny cap
    cfg = PolicyConfig(per_ticker_max_fraction={_VALID_TICKER: tight_cap})
    eng = ExecutionPolicyEngine(cfg)
    trade = _make_trade(quantity=10.0)  # 10 shares × $150 = $1500 = 1.5% > 0.1%
    obs = _make_obs(prices={_VALID_TICKER: _VALID_PRICE}, trade_plan=[trade])

    result = eng.evaluate(_make_decision([trade]), obs, "simulate")

    assert result.approved is True
    assert result.allowed_trades == []
    assert "per-ticker" in result.blocked_trades[0].rejection_reason.lower()


def test_per_ticker_cap_passes_small_trade():
    """A trade within both global and per-ticker caps is allowed."""
    cfg = PolicyConfig(per_ticker_max_fraction={_VALID_TICKER: 0.10})  # 10% cap
    eng = ExecutionPolicyEngine(cfg)
    # 1 share × $150 = $150 = 0.15% of $100k — well within 10%
    trade = _make_trade(quantity=1.0)
    obs = _make_obs(prices={_VALID_TICKER: _VALID_PRICE}, trade_plan=[trade])

    result = eng.evaluate(_make_decision([trade]), obs, "simulate")

    assert result.approved is True
    assert len(result.allowed_trades) == 1


def test_per_ticker_cap_only_applies_to_configured_tickers():
    """Tickers without a per-ticker cap entry are evaluated against global cap only."""
    cfg = PolicyConfig(per_ticker_max_fraction={"MSFT": 0.001})  # tight cap on MSFT only
    eng = ExecutionPolicyEngine(cfg)
    trade = _make_trade(ticker=_VALID_TICKER, quantity=1.0)  # AAPL, no per-ticker cap
    obs = _make_obs(prices={_VALID_TICKER: _VALID_PRICE}, trade_plan=[trade])

    result = eng.evaluate(_make_decision([trade]), obs, "simulate")

    assert result.approved is True
    assert len(result.allowed_trades) == 1


def test_profile_policy_config_from_all_profiles():
    """PolicyConfig.from_profile loads without error for all four YAML profiles."""
    from portfolio_loader import load_profile
    for name in ("balanced", "conservative", "growth", "crypto_heavy"):
        profile = load_profile(name)
        cfg = PolicyConfig.from_profile(profile)
        assert isinstance(cfg.min_confidence, float)
        assert isinstance(cfg.stale_data_blocks, bool)
        assert isinstance(cfg.per_ticker_max_fraction, dict)
