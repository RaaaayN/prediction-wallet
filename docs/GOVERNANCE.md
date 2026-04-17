# Governance Model

Prediction Wallet enforces a **three-layer deterministic policy engine** that validates every LLM decision before any trade executes. The AI proposes; the policy decides.

## Design Philosophy

The fundamental problem in AI portfolio management is not intelligence — it is accountability. Regulators, compliance officers, and portfolio managers need to answer: *why did this trade execute?* This engine makes that question answerable at every layer.

## The Five-Stage Cycle

Every rebalancing cycle passes through these stages in order:

```
┌─────────┐    ┌─────────┐    ┌──────────┐    ┌─────────┐    ┌───────┐
│ OBSERVE │───▶│ DECIDE  │───▶│ VALIDATE │───▶│ EXECUTE │───▶│ AUDIT │
│         │    │  (LLM)  │    │ (policy) │    │  (sim)  │    │  (DB) │
└─────────┘    └─────────┘    └──────────┘    └─────────┘    └───────┘
  Market +        Trade          3-layer          Slippage      Full
 portfolio       Decision        engine           applied       trace
 snapshot       (Pydantic)      runs here         + logged      stored
```

The `VALIDATE` stage is the core governance layer. It runs entirely in Python with no LLM involvement — deterministic, testable, reproducible.

## Policy Layers

### Layer 0 — Hard Violations (Cycle Abort)

These checks run first. Any failure aborts the entire cycle (`approved = False`). No trades execute.

| Rule | Trigger |
|------|---------|
| **Kill switch** | Portfolio drawdown ≥ 10% from peak |
| **Live mode blocked** | `EXECUTION_MODE=live` is not enabled |
| **Trade count exceeded** | `len(approved_trades) > MAX_TRADES_PER_CYCLE` |

When Layer 0 fires, the full violation set is written to `decision_traces` with `approved=false`. The cycle is closed and the next cycle starts fresh.

### Layer 1 — Market Context Soft Blocks (All Trades Blocked)

These checks apply to the entire decision, not individual trades. If triggered, the cycle is marked valid (`approved = True`) but all trades are rejected. This preserves cycle integrity while preventing bad-signal execution.

| Rule | Trigger | Configured via |
|------|---------|----------------|
| **Low confidence** | `decision.confidence < min_confidence` | `profiles/*.yaml → policy.min_confidence` |
| **Stale data** | `decision.data_freshness == "stale"` | `profiles/*.yaml → policy.stale_data_blocks: true` |

Example: a conservative profile sets `min_confidence: 0.7`. An LLM that returns confidence 0.65 will have all its trades soft-blocked — but the cycle audit record remains valid.

### Layer 2 — Per-Trade Soft Blocks (Individual Trade Rejected)

Each trade proposal is evaluated independently. Blocked trades are recorded with their rejection reason; other trades in the same decision may still execute.

| Rule | Check |
|------|-------|
| **Unknown ticker** | Ticker not in `TARGET_ALLOCATION` universe |
| **Off-plan trade** | Trade not in the deterministic rebalance plan (prevents LLM hallucination) |
| **Missing price** | Market price ≤ 0 for this ticker |
| **Notional cap** | `(price × qty) / portfolio_value > MAX_ORDER_FRACTION_OF_PORTFOLIO` |
| **Per-ticker cap** | Profile-level override: e.g., `BTC-USD` capped at 15% of portfolio |
| **Sector concentration** | Buy would push sector above `MAX_SECTOR_CONCENTRATION` (default 55%) |

## Example: Why Was This Trade Blocked?

**Scenario:** Agent proposes `BUY BTC-USD 2.5 shares` in a balanced profile.

1. Layer 0: drawdown = 6% → kill switch not active. ✓
2. Layer 1: confidence = 0.82, data fresh → no market block. ✓
3. Layer 2:
   - Ticker `BTC-USD` is in universe. ✓
   - Trade is in deterministic plan. ✓
   - Price = $45,000, qty = 2.5 → notional = $112,500. Portfolio = $500,000. Fraction = 22.5%.
   - `MAX_ORDER_FRACTION_OF_PORTFOLIO = 20%` → **BLOCKED**
   - Rejection: `"Trade exceeds notional cap (20%)."`

The rejection is stored in `decision_traces` with the full trade proposal. The agent can inspect this on the next cycle.

## Audit Trail

Every cycle writes a complete record to the `decision_traces` SQLite table:

```json
{
  "cycle_id": "2024-01-15T14:32:00",
  "stage": "validate",
  "approved": true,
  "allowed_trades": [{"action": "buy", "ticker": "AAPL", "quantity": 10}],
  "blocked_trades": [
    {
      "action": "buy",
      "ticker": "BTC-USD",
      "quantity": 2.5,
      "rejection_reason": "Trade exceeds notional cap (20%)."
    }
  ],
  "violations": []
}
```

This structure means every trade outcome — executed or blocked — is fully explainable from the database alone, with no LLM re-query required.

## Profile-Level Policy Configuration

Each `profiles/*.yaml` file can override policy parameters:

```yaml
policy:
  min_confidence: 0.65        # Layer 1: block all trades if confidence below this
  stale_data_blocks: true     # Layer 1: block all trades if market data is stale
  per_ticker_max_fraction:    # Layer 2: per-asset notional cap overrides
    BTC-USD: 0.15
    ETH-USD: 0.10
```

This means the governance rules are version-controlled alongside the portfolio mandate — changes to risk policy are tracked in git.
