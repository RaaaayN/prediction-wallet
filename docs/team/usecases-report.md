# Use-Cases Report — Prediction Wallet

Reports are append-only. Each session adds a dated section below.

---

## Session: 2026-03-25 — Evaluation of 15 new feature ideas
**Last Updated:** 2026-03-25

### Context

Evaluation of 15 new feature ideas submitted for review. No new audit of existing features in this session — see previous session for full current-state audit.

Evaluation framework: **Value** (what problem does it solve, who benefits) / **Complexity** (scope of code change) / **Risk** (what can break, production impact) / **Fit** (alignment with governed, auditable agent architecture).

### New Feature Evaluations

| # | Idea | Verdict | Value | Complexity | Risk | Notes |
|---|------|---------|-------|-----------|------|-------|
| 1 | Policy-as-code hiérarchique | **Accept** | H | M | L | Natural evolution of `ExecutionPolicyEngine`. Current engine is flat (~5 rules). Adding hierarchy (global → asset class → ticker → market context) is a contained `policies.py` change + YAML config. No schema changes. |
| 2 | Regime detection (HMM / clustering) | **Defer** | H | H | M | HMM introduces non-deterministic model state that is hard to audit. Simple vol-regime (high/low vol percentile) is a better entry point. Prerequisite: adaptive thresholds (#13) first, then escalate to HMM if needed. |
| 3 | Dynamic position sizing | **Accept** | H | M | L | `TickerMetrics.volatility_30d` is already computed. Inverse-vol weighting is 20 lines of engine code. Kelly + risk budgeting come later. Start scoped: inverse-vol sizing mode in `engine/orders.py`. |
| 4 | Risk parity / equal risk contribution | **Defer** | H | H | M | Requires covariance matrix estimation — unreliable on 90-day crypto history. `cvxpy` was just removed from deps. Prerequisite: longer data history + stable correlation module (#6 done first). |
| 5 | Stress testing par scénarios | **Accept** | H | M | L | Pure simulation. Extends `engine/backtest.py`. Scenario definitions are config (shocked returns, shocked vol, correlation spike). Zero production risk. Direct fit with existing infrastructure. |
| 6 | Corrélation dynamique + concentration risk | **Accept** | H | M | L | Rolling correlation matrix is standard pandas. The 50% tech concentration (AAPL/MSFT/GOOGL/AMZN/NVDA) is a documented risk with no policy check today. Start: sector hardcoding + concentration score. Plugs directly into policy engine as soft block. |
| 7 | Optimisation sous contraintes (cvxpy) | **Defer** | H | H | M | Adds opacity: an optimizer's solution path is harder to explain to an auditor than deterministic rules. `cvxpy` was deliberately removed. Would require a design decision before re-adding. Defer until #4 (risk parity) is designed — they share the same solver requirement. |
| 8 | Transaction cost model réaliste | **Accept** | M | L | L | `apply_slippage()` in `engine/orders.py` uses flat rates today. Making it vol-adjusted and size-adjusted is a drop-in improvement. Directly improves backtest accuracy. Zero production risk. |
| 9 | Multi-agent decision committee | **Defer** | H | VH | H | Wrong timing. Multiple concurrent LLM calls add latency, cost, and failure modes the policy engine must handle. Prerequisites: confidence scoring (#11) and structured explainability (#15) must be stable first. Revisit once single-agent baseline is fully hardened. |
| 10 | Skill registry / capability routing | **Defer** | M | H | L | Pure infrastructure with zero product value until #9 (multi-agent committee) exists. Building the registry before building the agents that use it is the wrong order. Prerequisite: #9. |
| 11 | Confidence scoring + decision uncertainty | **Accept** | H | M | M | Adding `confidence: float` and `data_freshness: str` to `TradeDecision` is a Pydantic model addition. Risk: LLM self-reported confidence is poorly calibrated — use as soft signal only (reduce size, not hard block). `contradiction_score` is premature without #9. `data_freshness` from `MarketDataStatus.refreshed_at` is immediately implementable and useful. |
| 12 | Event-driven memory / decision trace semantics | **Accept** | M | M | L | `decision_traces` table already exists. Adding `event_type` enum + `tags` JSON column is a schema migration + repository update. Semantic tagging enables analytics on agent behavior patterns. Contained, low risk. |
| 13 | Online learning / adaptive thresholds | **Defer** | H | M | M | Without regime context (#2), adaptive thresholds risk overfitting to recent noise (e.g., tightening thresholds during a high-vol event, then over-trading when vol normalizes). Simple vol-adjusted threshold (lookup, not learning) could be done now, but the full adaptive version needs #2 first. |
| 14 | Walk-forward backtesting | **Defer** | H | H | L | Requires significantly more historical data than 90 days (need multiple calibration + test windows). The current `engine/backtest.py` is in-sample. Build after stress testing (#5) to know which scenarios to validate walk-forward against. |
| 15 | Explainability structurée orientée audit | **Accept** | H | M | L | The clearest expression of "governed portfolio agent." Per-trade policy checks are already computed but not persisted at trade level. Start: `policy_checks_passed`, `policy_checks_failed`, `sizing_rationale` fields in `ExecutionResult`. LLM-generated memos (investment, risk, execution) are a secondary pass. |

### Summary

| Verdict | Ideas |
|---------|-------|
| **Accept (8)** | #1 policy-as-code, #3 dynamic sizing, #5 stress testing, #6 correlation/concentration, #8 realistic costs, #11 confidence scoring, #12 event semantics, #15 explainability |
| **Defer (7)** | #2 regime detection, #4 risk parity, #7 constraint optimization, #9 multi-agent committee, #10 skill registry, #13 adaptive thresholds, #14 walk-forward |
| **Reject (0)** | — (all 15 have genuine merit; the Defer verdicts are timing decisions, not value rejections) |

### Recommended Implementation Sequence (Accept items only)

The Accept items have dependencies on each other. This sequence minimizes rework:

| Step | Feature | Why this order |
|------|---------|---------------|
| 1st | **#15 Explainability** | Foundation. Every other feature becomes more debuggable when each trade has a structured audit trail. Also the most "on-brand" for this project. |
| 2nd | **#12 Event semantics** | DB schema change (add `event_type`, `tags`). Small scope. Enhances traceability for everything that follows. |
| 3rd | **#11 Confidence scoring** | Add `confidence`, `data_freshness` to `TradeDecision`. Pydantic model change only. Informs #1 (policy rules on confidence). |
| 4th | **#8 Realistic costs** | Quick win. Improve `apply_slippage()`. Benefits backtest accuracy immediately — #5 depends on it being realistic. |
| 5th | **#6 Correlation/concentration** | Addresses the documented 50% tech concentration risk. Produces data (`correlation_matrix`, `sector_exposure`) that #1 policy rules need. |
| 6th | **#5 Stress testing** | Extends `engine/backtest.py`. Zero risk. Validates the portfolio against crisis scenarios — the result informs which policy rules (#1) matter most. |
| 7th | **#1 Policy-as-code** | Now has the inputs it needs: concentration data (#6), confidence signal (#11), cost model (#8). Can define market-context rules backed by real data. |
| 8th | **#3 Dynamic sizing** | Last because it changes how target quantities are computed — the deepest change. Everything else builds on stable rebalancing logic first. |

### Open Issues

- None specific to this evaluation session.

### Blockers / Dependencies

- (none) — all evaluations made from current codebase state.

### Recommendations for the Leader

1. **No rejects** — all 15 ideas are strategically coherent with the project direction. The 7 Defers are timing decisions.

2. **The 8 Accept items form a coherent roadmap**. Implementing them in the sequence above avoids rework: each step produces data or contracts that the next step depends on.

3. **The 7 Defer items unlock progressively**: #6 (correlation) → #4 (risk parity) → #7 (constraint optimization) is a natural escalation from simple to complex portfolio math. Similarly, #11 (confidence) + #15 (explainability) → #9 (multi-agent) is the right path to multi-agent without premature complexity.

4. **Priority order for team-backend**: #15 → #12 → #11 (model/persistence changes). Then #8 (engine). Then #6 → #1 (policy evolution). These are self-contained `engine/` and `agents/` changes.

5. **Priority order for team-strategy**: #8 (cost model) → #5 (stress testing) → #3 (dynamic sizing). All `engine/` scope, no cross-agent coordination needed.

6. **#9 multi-agent committee** is the most architecturally ambitious idea. Don't start it until #11 + #15 are solid — you need confidence scoring and structured explainability to know what each sub-agent should produce and how to combine their outputs.

---
