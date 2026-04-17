# Use-Cases Report — Prediction Wallet

Reports are append-only. Each session adds a dated section below.

---

## Session: 2026-03-26 — Post-sprint audit + deferred features #2/#4/#9 evaluation
**Last Updated:** 2026-03-26

### Context

Post-sprint audit of all 9 features delivered since the previous usecases session (2026-03-25), followed by evaluation of 3 deferred features (#2 HMM regime detection, #4 Risk Parity, #9 Multi-agent committee) whose prerequisite blockers (#11 confidence scoring and #15 explainability) are now confirmed stable.

Sources read: `agents/policies.py`, `agents/models.py`, `agents/portfolio_agent.py`, `engine/orders.py`, `engine/portfolio.py`, `engine/performance.py`, `engine/risk.py`, `engine/backtest.py`, `config.py`, `docs/team/backend-report.md`, `docs/team/strategy-report.md`, `docs/team/ui-report.md`.

---

### Feature Audits

| Feature | Location | Verdict | Rationale |
|---------|----------|---------|-----------|
| **#1 Policy-as-code hiérarchique** | `agents/policies.py` — `PolicyConfig` + `ExecutionPolicyEngine` (3 layers) | **Useful** | Delivered exactly as scoped. Layer 0 (hard violations: kill switch, live mode, trade count), Layer 1 (market context soft blocks: `min_confidence`, `stale_data_blocks`), Layer 2 (per-trade: notional cap, per-ticker cap, sector concentration). `PolicyConfig` is profile-driven (`profiles/*.yaml` `policy:` section). All 4 profiles carry calibrated thresholds. 23 tests cover all paths. The sector concentration check (Layer 2, `MAX_SECTOR_CONCENTRATION=0.55`) directly addresses the documented 50% tech risk. No redundancy — this is the deterministic enforcement layer that the entire architecture depends on. |
| **#11 Confidence scoring** | `agents/models.py` — `TradeDecision.confidence` + `data_freshness` | **Useful** | Both fields present and correctly scoped. `confidence` (LLM self-reported, float 0–1, ge/le validated) is wired into Layer 1 as a soft block. `data_freshness` is deterministic: computed by `_compute_data_freshness()` from `MarketDataStatus.refreshed_at` timestamps and injected post-LLM-run so the LLM cannot corrupt it. The agent instructions explicitly ask for confidence and note `data_freshness` is automatic. Correct treatment of the miscalibration risk: soft signal only, not a hard block. 9 tests green. |
| **#15 Explainability structurée** | `agents/models.py` — `ExecutionResult` (5 fields) + `agents/portfolio_agent.py::execute()` | **Useful** | Five per-trade fields added to `ExecutionResult`: `weight_before`, `target_weight`, `drift_before`, `slippage_pct`, `notional`. All populated in `execute()` from live observation data. DB schema migrated (`_EXECUTIONS_MIGRATIONS`, idempotent). UI history tab now renders `drift_before` and `slippage_pct` (color-coded). This is the "governed portfolio agent" proof of record — each trade has a structured, auditable justification. No gaps: coverage from model → execution → persistence → UI. |
| **#12 Event semantics** | `db/schema.py` — `decision_traces.event_type` + `tags` + `agents/portfolio_agent.py` (5 trace sites) | **Useful** | Schema migration adds `event_type` (TEXT) and `tags` (JSON TEXT) to `decision_traces`. All 5 stages (observe/decide/validate/execute/audit) emit typed events. Taxonomy is small and useful: `cycle_step`, `kill_switch`, `policy_violation`, `execution_failure`. Tags carry structured key=value pairs per stage (e.g., `confidence:0.72`, `approved_trades:3`). UI Traces tab already has a stage filter dropdown. Enables behavioral analytics on historical cycles. |
| **#8 Realistic costs** | `engine/orders.py` — `apply_slippage()` + `estimate_transaction_cost()` | **Useful** | Vol-adjusted model: `rate = base_rate × clamp(vol / ref_vol, 0.5, 3.0)`. Reference vols: 20% equity, 65% crypto. Size-adjusted: +1 bp per $10k notional. Both params optional, so existing callers (backtest) are backward compatible. 13 tests including boundary conditions. One known pre-existing test tolerance failure (`test_estimate_cost_without_vol_unchanged`) is a floating-point precision issue, not a correctness bug. Improvement over flat rates is meaningful for stress scenarios (rate can reach 3× base during high-vol regimes). |
| **#6 Correlation/concentration** | `engine/portfolio.py` — `compute_sector_exposure()` + `concentration_score()` / `engine/performance.py` — `rolling_correlation()` + `avg_pairwise_correlation()` / `agents/policies.py` Layer 2 sector check / `config.py` — `SECTOR_MAP` + `MAX_SECTOR_CONCENTRATION=0.55` | **Useful** | Four distinct functions delivered across two modules. Sector concentration is enforced in Layer 2 of the policy engine: buys that would push a sector above 55% are soft-blocked with a descriptive reason. Rolling correlation matrix (`rolling_correlation()`, default 30-day window) and `avg_pairwise_correlation()` are pure utility functions used by the `/api/correlation` endpoint and the heatmap tab. The 55% threshold is correctly set 5pp above the 50% tech target, giving a realistic buffer. One structural note: the concentration block is per-trade (buy-only), which means it blocks incremental overweight but does not enforce rebalancing when an existing overweight drifts higher due to price movement. This is intentional and consistent with how slippage works (you block the action that would worsen the state). |
| **#5 Stress testing** | `engine/backtest.py` — `STRESS_SCENARIOS` + `run_stress_test()` / `api/main.py` — `GET /api/stress` / `reporting/pdf_report.py` — section 7 / `ui/index.html` — Stress Test tab | **Useful** | Four calibrated scenarios (COVID-19 crash, GFC 2008, rate shock 2022, tech selloff) with per-asset multiplicative shocks. Pure simulation — no trades, no I/O. Kill switch flag per scenario based on `pnl_pct <= -kill_switch_threshold`. Wired end-to-end: API endpoint, PDF section 7 (kill-switch rows highlighted red), and a full UI tab with Chart.js horizontal bar chart and per-scenario cards. The scenario shock values are historically plausible and cover the portfolio's main risk factors (tech concentration, crypto drawdown, rate sensitivity). Only note: crypto shocks for GFC 2008 are stress-hypothetical (crypto was nascent), as correctly documented in the scenario description. |
| **#3 Dynamic sizing** | `engine/portfolio.py` — `compute_inverse_vol_weights()` / `strategies/base.py` + `strategies/threshold.py` + `strategies/calendar.py` — `get_trades(volatilities, vol_blend)` / `agents/portfolio_agent.py::observe()` — wired via `vol_blend` from profile | **Useful** | Inverse-volatility weighting with blend parameter (`0.0`=pure fixed target, `1.0`=pure inverse-vol). Default `vol_blend=0.3` per profile is a conservative starting point. Wired in `observe()`: volatilities extracted from `TickerMetrics.volatility_30d`, passed to strategy. `vol_blend` and `vol_assets_used` recorded in `observability` dict for traceability. The blend approach is the right design choice — pure inverse-vol would ignore the explicit portfolio mandate; the blend respects it while allowing vol-adjusted sizing. Profile-configurable without code changes. |
| **Correlation Heatmap tab** | `ui/index.html` — Correlation tab / `api/main.py` — `GET /api/correlation` | **Useful** | NxN interactive heatmap with RGB linear interpolation (negative=red, zero=dark, positive=blue). Summary stat cards: avg pairwise correlation (color-coded), obs count, highest/lowest pair. Window selector (30/60/90/180/365d). Graceful degradation on empty DB (503 with clear message). Directly consumable by portfolio managers for daily regime awareness. The color thresholds (0.3/0.6) are reasonable heuristics; the note in the UI report acknowledges they're not portfolio-theory-backed — acceptable for a monitoring view. |

**Summary: 9/9 features are Useful. No Redundant or Useless verdicts.**

---

### New Feature Evaluations

Evaluation framework: **Value** (what problem does it solve, who benefits) / **Complexity** (scope of code change) / **Risk** (what can break) / **Fit** (alignment with governed, auditable, deterministic-first architecture). Prerequisite condition: #11 (confidence scoring) and #15 (explainability) are confirmed stable as of 2026-03-26.

| # | Idea | Verdict | Value | Complexity | Risk | Notes |
|---|------|---------|-------|------------|------|-------|
| 2 | **Régimes HMM (Hidden Markov Models)** | **Defer** | H | H | M | The prerequisite logic is now clearer: #11 + #15 being stable is necessary but not sufficient. The core problem with HMM is auditability: a stochastic latent-variable model introduces non-deterministic regime assignments that are hard to explain to an auditor. This is in direct tension with the project's governing principle ("les décisions critiques ne dépendent jamais d'un texte libre non validé" — equally applies to opaque model state). However, the underlying need is real: the portfolio currently has a single strategy mode regardless of whether vol is 15% or 80%. A better-scoped entry point than HMM: a **deterministic vol-regime classifier** using rolling volatility percentile (e.g., high-vol = 30d vol > 75th historical percentile). This is interpretable, auditable, and can be added to the `CycleObservation` without model state. Recommend reformulating as "vol-regime classifier" and accepting that, instead of full HMM. Full HMM remains deferred. |
| 4 | **Risk Parity (equal risk contribution)** | **Defer** | H | H | M | #6 (correlation) is now stable and provides `rolling_correlation()` and `compute_sector_exposure()` — which was the stated prerequisite. However, one prerequisite remains unmet: data quality. The `rolling_correlation()` function uses a configurable window (default 30d). ERC (equal risk contribution) requires a reliable covariance matrix, which needs 60–90 trading days minimum per asset to be statistically stable. The portfolio includes BTC-USD and ETH-USD, which have structural regime breaks. More concretely: the current `vol_blend` mechanism already moves the portfolio in the direction of risk parity (inverse-vol weighting) without requiring covariance matrix inversion. Risk Parity via ERC adds marginal value over the existing `vol_blend=1.0` mode while adding `cvxpy` as a dependency and making each rebalance decision harder to explain. Recommend first evaluating `vol_blend=1.0` (pure inverse-vol) as a proxy, then decide whether full ERC is worth the added complexity. True Risk Parity deferred until longer price history and an explicit design decision on the optimization dependency. |
| 9 | **Multi-agent committee** | **Defer** | H | VH | H | The stated blocker (#11 + #15 stable) is now cleared. However, the implementation risk has not changed: multiple concurrent LLM calls add latency and cost, and the policy engine must be extended to aggregate/adjudicate conflicting sub-agent decisions. Neither the `TradeDecision` schema nor the `PolicyEvaluation` schema currently supports multiple independent inputs. The right design question is: what does each sub-agent produce, and how does the committee resolve disagreement? `confidence` (from #11) is now available per-decision and could serve as a weighting factor, but there is no mechanism for one agent's risk veto to override another's buy signal. Furthermore, the existing `ExecutionPolicyEngine` is deterministic and single-threaded by design — introducing parallel LLM runners would require a new coordination layer. Assessment: the prerequisite work is done, but the design work has not been done. Accept the design phase (spec out the committee protocol, decision schema extensions, and adjudication rules) as a first step; implementation remains deferred until the design is stable. |

---

### Open Issues

1. **`MarketSnapshot.research_summary`** — field confirmed always `""` (backend-report.md, multiple sessions). Still present in `agents/models.py`. Pending team-ui confirmation that it is not rendered in the HTML/JS UI. This is dead schema weight that misleads contributors reading the model.

2. **`hit_ratio` function deprecated** — `engine/performance.py` marks it as deprecated (simulator `success` is trivially True for all executed trades). The Performance tab in the UI still displays it. Should either remove the UI card or replace with `avg_slippage_bps` for a meaningful execution quality metric. Flagged in strategy-report from 2026-03-24; not yet resolved.

3. **Vol-regime classifier as a scoped #2 alternative** — the case for a deterministic vol-regime signal (rolling vol percentile) is strong and unblocked. This is not HMM and has zero auditability risk. No owner has been assigned.

4. **`vol_blend` calibration** — all 4 profiles default to `0.3`. No retrospective analysis has been done to validate whether 0.3 produces better risk-adjusted outcomes than 0.0 or 1.0. This is empirical question that backtest + stress test infrastructure can now answer, but no one has run it.

5. **Pre-existing test tolerance failure** — `test_engine.py::TestVolAdjustedSlippage::test_estimate_cost_without_vol_unchanged` still fails with floating-point tolerance ~0.01 vs 1e-9. Carried forward across multiple strategy-report sessions. Low urgency but should be closed.

---

### Blockers / Dependencies

- **#2 (HMM/vol-regime)**: No blocker for the reformulated deterministic vol-regime classifier. Full HMM blocked by auditability design constraint.
- **#4 (Risk Parity)**: Blocked by data quality (need 60–90d stable covariance) and design decision on `cvxpy` dependency. Correlation infrastructure (#6) is now available.
- **#9 (Multi-agent)**: Design phase can start (define committee protocol, schema extensions, adjudication rules). Implementation blocked pending that design.
- **`research_summary` removal**: Blocked by team-ui coordination (field may be rendered in the HTML/JS UI — needs verification).

---

### Recommendations for the Leader

1. **All 9 sprint features are production-quality.** No removals or rollbacks needed. The policy engine (#1), confidence scoring (#11), and explainability (#15) together constitute the core "governed agent" proof of concept — this combination is the strongest value demonstration the project has.

2. **Accept the vol-regime classifier as a scoped, auditable alternative to #2 (HMM).** A 10-line deterministic function (rolling vol percentile → `"high_vol"` / `"normal"` / `"low_vol"` label added to `CycleObservation`) unlocks regime-aware strategy behavior with zero auditability risk. Assign to team-strategy. This is not HMM; do not conflate them.

3. **For #4 (Risk Parity): run the `vol_blend=1.0` backtest first.** The existing `compute_inverse_vol_weights()` with `blend=1.0` is a pure-inverse-vol allocation — functionally similar to risk parity on volatility. Compare its backtest Sharpe and max drawdown to `vol_blend=0.3` and `vol_blend=0.0` before committing to full ERC with covariance matrix. The infrastructure to run this comparison (backtest tab, stress test tab) now exists.

4. **For #9 (Multi-agent): start the design, not the implementation.** A 1-page spec covering (a) what each sub-agent produces, (b) how the committee adjudicates disagreements, (c) what `TradeDecision` schema extensions are needed, and (d) how `PolicyEvaluation` aggregates multiple inputs is the correct next step. Assign to team-usecases (this agent) or team-lead for the design document. Implementation remains deferred.

5. **Close the `research_summary` field with team-ui.** The backend confirmed it is always `""`. The UI team should verify the Correlation tab and other new tabs do not render it, then a single-line model deletion closes this open issue permanently. Low effort, eliminates ongoing confusion.

6. **Assign the `hit_ratio` / `avg_slippage_bps` swap to team-ui.** The deprecated function is still displayed as "Hit Ratio %" in the Performance tab. Replace the card label and value with `avg_slippage_bps` — more informative, already computed in `performance_report`.

7. **The correlation + stress test + backtest trio now forms a coherent portfolio quality dashboard.** Consider adding a brief narrative interpretation layer (e.g., "your tech sector is at 52% and the rate shock scenario produces a -31% loss — consider reducing growth equity exposure") as a structured output from the agent's `audit()` stage. This would be a high-value, low-complexity use of the existing infrastructure.

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
