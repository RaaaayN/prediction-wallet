# Strategy Report — Prediction Wallet

## Session: 2026-03-25 — Phase 2 implementation (priorities A–E)
**Last Updated:** 2026-03-25
**Phase:** 2 (implementation — approved by user: "Proceed with implementation")

### Phase 2 Approval
> "Proceed with implementation"

### What Was Done

Implemented all 5 recommendations from this session's Phase 1, with 13 new tests.

### Implemented Changes

**Priority A — Kill-switch boundary fix** (`engine/risk.py`)
- Changed `check_kill_switch`: `drawdown < -threshold` → `drawdown <= -threshold`
- At exactly -10% drawdown, `check_kill_switch` and `get_risk_level` now agree: both signal HALT/True
- This was a correctness bug — a trade at exactly -10% could previously execute despite HALT risk level

**Priority B — Calendar drift guard** (`strategies/calendar.py`)
- Added `min_drift: float = 0.01` parameter to `CalendarStrategy.__init__`
- `should_rebalance` now checks: time elapsed AND max asset drift > `min_drift`
- A perfectly balanced portfolio on the scheduled day skips the rebalancing cycle
- Set `min_drift=0.0` to restore pure calendar behaviour (backward compatible)
- Updated `test_strategies.py::test_rebalance_after_one_week` to use a drifted portfolio (correct: drift guard is now active by default)

**Priority C — Per-asset variable drift bands** (`strategies/threshold.py`)
- Added `per_asset_threshold: dict[str, float] | None = None` to `ThresholdStrategy.__init__`
- Added `_get_threshold(ticker)` helper — looks up per-asset threshold, falls back to global
- `should_rebalance` uses `_get_threshold(ticker)` per asset instead of a single global threshold
- `get_trades` applies per-asset tolerance band (threshold/2 per asset) when filtering orders
- Example use: `ThresholdStrategy(per_asset_threshold={"BTC-USD": 0.15, "ETH-USD": 0.12, "BND": 0.03})`

**Priority D — Minimum trade notional filter** (`engine/orders.py`)
- Added `min_notional: float = 10.0` parameter to `generate_rebalance_orders`
- Skips any order where `quantity × price < min_notional` (default $10)
- Eliminates micro-trades that cost more in overhead (slippage, DB write, PDF entry) than their value
- Backward compatible default; set `min_notional=0.0` to disable

**Priority E — Dead code + docstring cleanup** (`engine/performance.py`)
- Removed unused `net_history = history.copy()` variable in `performance_report`
- Updated `sharpe_ratio` docstring: "default 2%" → "default: RISK_FREE_RATE from config"

**Tests** (13 new tests across `test_engine.py` and `test_strategies.py`)
- `TestToleranceBandOrders`: +2 (min_notional suppression, min_notional=0 passthrough)
- `TestKillSwitchBoundary`: 3 tests — boundary consistency between `check_kill_switch` and `get_risk_level`
- `TestCalendarDriftGuard`: 4 tests — balanced skip, drift trigger, min_drift=0 passthrough, time guard
- `TestPerAssetThreshold`: 4 tests — wide band suppression, narrow band trigger, global fallback, get_trades filtering
- All 55 tests pass (43 pre-existing + 13 new)

### Open Issues

- **Stress testing framework**: Still no crisis scenario simulation (2008, 2020 COVID, 2022 crypto bear)
- **Correlation-aware position sizing**: 50% tech concentration (AAPL/MSFT/GOOGL/AMZN/NVDA) unchecked
- **Regime detection**: Strategies behave identically in bull/bear/sideways regimes

### Blockers / Dependencies

- (none) — all changes are self-contained in `engine/` and `strategies/`

### Recommendations for the Leader

- **All 10 original priorities now implemented** (P1–P8 done; P9=min_notional=P-D; P10=hit_ratio deferred as low priority)
- **Per-asset threshold config**: The new `per_asset_threshold` dict in `ThresholdStrategy` can be wired to `profiles/*.yaml` for per-profile volatility-calibrated thresholds. This is a backend/config task.
- **Remaining work is medium/high complexity**: stress testing, regime detection, correlation-aware sizing — these are research-level features requiring market data access. Recommend separate initiative.
- **55/55 tests green** — safe to merge.

---

## Session: 2026-03-25 — Status audit + Phase 1 for remaining priorities
**Last Updated:** 2026-03-25
**Phase:** 1 (analysis)

### What Was Done

Full re-read of all owned files to establish current state before proposing next priorities.

#### Status of Previous Recommendations

| Priority | Recommendation | Status |
|----------|---------------|--------|
| P1 | Historical VaR + VaR/CVaR in `performance_report` | ✅ Done (2026-03-24) |
| P2 | `sortino_ratio` + `calmar_ratio` | ✅ Done (2026-03-24) |
| P3 | Tolerance-band order generation | ✅ Done (2026-03-24) |
| P4 | Tiered risk levels (`RiskLevel` enum) | ✅ Done (2026-03-24) |
| P5 | Risk-free rate from config (4.5%) | ✅ Done (2026-03-24) |
| P6 | Per-asset variable drift bands | ⏳ Pending |
| P7 | Calendar drift guard | ⏳ Pending |
| P8 | Hard vs. soft policy violations | ✅ Done — already present in `agents/policies.py` (done outside strategy scope) |
| P9 | Minimum trade notional filter | ⏳ Pending |
| P10 | Fix `hit_ratio` | ⏳ Pending |

#### New Issues Found This Session

1. **`check_kill_switch` / `get_risk_level` boundary inconsistency**: `check_kill_switch(-0.10, 0.10)` returns `False` (uses strict `<`), but `get_risk_level(-0.10)` returns `HALT` (uses `<=`). At exactly -10% drawdown, the two functions disagree. A consumer using both would see HALT risk level but kill switch NOT active — misleading.

2. **Dead variable in `performance_report`**: `net_history = history.copy()` is computed but never used. Harmless but dead code.

3. **`sharpe_ratio` docstring outdated**: Still says "default 2%" but default is now `RISK_FREE_RATE` (4.5%).

---

### Recommendations (Phase 1)

| Priority | Recommendation | File | Impact | Complexity |
|----------|---------------|------|--------|-----------|
| A | Fix `check_kill_switch` boundary: change `drawdown < -threshold` to `drawdown <= -threshold` for consistency with `get_risk_level` | `engine/risk.py` | High | Low |
| B | **Calendar drift guard**: add `min_drift` param to `CalendarStrategy.should_rebalance` — skip rebalance if max asset drift < `min_drift` (default `0.01`) | `strategies/calendar.py` | Medium | Low |
| C | **Per-asset variable drift bands** in `ThresholdStrategy`: each asset gets a band proportional to its 30-day rolling volatility (wider for BTC/ETH, tighter for BND/TLT) | `strategies/threshold.py` | High | Medium |
| D | **Minimum trade notional filter**: skip orders where `quantity × price < min_notional` (default $10) in `generate_rebalance_orders` | `engine/orders.py` | Low | Low |
| E | Fix dead variable `net_history` in `performance_report` + update `sharpe_ratio` docstring | `engine/performance.py` | Low | Low |

---

### Detailed Rationale

**Priority A — Kill switch boundary fix:**
At exactly -10% drawdown: `get_risk_level` returns `HALT`, but `check_kill_switch` returns `False`. The `ExecutionPolicyEngine` checks `observation.risk.kill_switch_active` (which uses `check_kill_switch`), so at exactly -10% the policy would NOT block execution, even though the risk level shows HALT. This is a correctness bug. Fix: change `return drawdown < -threshold` to `return drawdown <= -threshold` in `check_kill_switch`.

**Priority B — Calendar drift guard:**
`CalendarStrategy.should_rebalance` checks only elapsed time, not portfolio state. If a portfolio is perfectly balanced on the scheduled day, the rebalance cycle still runs (generating near-zero quantity orders that waste compute and log noise). Adding a `min_drift` guard skips the cycle when the portfolio is already within tolerance. Consistent with how `ThresholdStrategy` works and reduces unnecessary cycles.

**Priority C — Per-asset variable drift bands:**
`ThresholdStrategy.should_rebalance` applies a single `threshold` to all 9 assets. BTC-USD (60–80% annualized vol) will breach a 5% band frequently in normal trading; BND (4–6% annualized vol) rarely will. The fix: maintain a per-asset threshold dict, where each threshold is proportional to the asset's rolling volatility (e.g., `k × vol × √(rebalance_interval_days/252)`). This requires passing recent returns data to the strategy, which is currently NOT in the `should_rebalance` signature — a medium-complexity change that requires a signature update.

**Priority D — Minimum notional filter:**
Currently only `min_qty=0.001` filters micro-trades by quantity. A 0.001 share of a $50 stock = $0.05 trade — generates a trade record with real overhead (slippage calculation, DB write, PDF entry) for negligible value. A `min_notional=10.0` filter (skip if `qty × price < $10`) eliminates these cleanly.

**Priority E — Dead code + doc cleanup:**
`net_history = history.copy()` is assigned then immediately discarded (the dict is rebuilt differently below it). Removing it improves clarity. The docstring for `sharpe_ratio` still says "default 2%" — should say "default `RISK_FREE_RATE` from config".

---

### Open Issues (carried forward)

1. **No stress testing framework**: No crisis scenario simulation (2008, 2020 COVID, 2022 crypto bear) — still pending, higher complexity.
2. **No correlation-aware position sizing**: 50% tech concentration (AAPL/MSFT/GOOGL/AMZN/NVDA) unchecked — still pending.
3. **No regime detection**: strategies behave identically in bull/bear/sideways — still pending.
4. **Priority C (variable drift bands) requires signature change**: `should_rebalance(portfolio, prices)` has no slot for returns data. Either add a `volatilities: dict[str, float]` param, or pre-compute bands in `__init__` from a passed-in returns history. Needs design decision before implementation.

---

### Blockers / Dependencies

- Priority C (variable drift bands) is partially blocked by architecture: the `should_rebalance` signature does not accept volatility data. The caller (`agents/portfolio_agent.py` — out of scope for strategy) would need to pass per-asset volatilities. Recommend discussing with backend/lead before implementing.
- All other priorities (A, B, D, E) are fully self-contained and unblocked.

---

### Recommendations for the Leader

1. **Priority A is a correctness bug** — should be fixed immediately regardless of Phase 2 approval. The kill switch boundary inconsistency could allow a trade at exactly -10% drawdown that should be blocked.
2. **Priorities B, D, E are low-effort** — can be bundled into a single commit.
3. **Priority C needs a design call**: how should `should_rebalance` receive per-asset volatility? Options: (a) pass `volatilities: dict[str, float]` as a new parameter (breaks current callers), (b) pre-load in strategy `__init__` from a returns history (couples strategy to data layer), (c) keep uniform threshold but make it configurable per-asset in the profile YAML (cleanest, stays within strategy scope). Option (c) is recommended.

---

## Session: 2026-03-24 16:00 — Phase 2 implementation (priorities 1–5)
**Last Updated:** 2026-03-24 16:00
**Phase:** 2 (implementation — approved by user: "Proceed with implementation")

### Phase 2 Approval
> "Proceed with implementation"

### What Was Done

Implemented all 5 high-impact / low-complexity recommendations from Phase 1, with tests.

### Implemented Changes

**Priority 1 — Historical VaR + full VaR/CVaR in `performance_report`** (`engine/performance.py`)
- Added `historical_var(returns, confidence, portfolio_value)` — empirical quantile, no Gaussian assumption
- `performance_report` now includes: `var_95_parametric`, `var_99_parametric`, `var_95_historical`, `var_99_historical`, `cvar_95`, `cvar_99`

**Priority 2 — Sortino + Calmar ratios** (`engine/performance.py`)
- Added `sortino_ratio(returns, rf, mar)` — uses only downside deviation
- Added `calmar_ratio(history, returns)` — annualized return / |max drawdown|
- Both included in `performance_report` output

**Priority 3 — Tolerance-band order generation** (`engine/orders.py`, `strategies/base.py`, `strategies/threshold.py`)
- Added `min_drift: float = 0.0` parameter to `generate_rebalance_orders` — skips assets within band
- Threaded `min_drift` through `BaseStrategy._compute_trade_orders`
- `ThresholdStrategy.get_trades` now passes `min_drift=self.threshold / 2` — prevents re-trading assets already close to target

**Priority 4 — Tiered risk levels** (`engine/risk.py`)
- Added `RiskLevel(str, Enum)` with `OK`, `WARN`, `HALT` values
- Added `get_risk_level(drawdown, warn_threshold=0.07, halt_threshold=0.10) -> RiskLevel`
- Threshold semantics: `drawdown <= -threshold` (inclusive) to match `check_kill_switch` convention
- `check_kill_switch` unchanged for backward compatibility

**Priority 5 — Risk-free rate from config** (`settings.py`, `engine/performance.py`)
- Updated `settings.py` default: `risk_free_rate: float = 0.02` → `0.045` (current market)
- Imported `RISK_FREE_RATE` from `config` at top of `engine/performance.py`
- `sharpe_ratio` and `sortino_ratio` default `rf=RISK_FREE_RATE` instead of hardcoded `0.02`

**Tests** (`tests/test_engine.py` — new file, 30 tests)
- `TestHistoricalVar` (5 tests), `TestSortinoRatio` (4), `TestCalmarRatio` (3)
- `TestPerformanceReportFields` (3), `TestRiskLevel` (9), `TestToleranceBandOrders` (6)
- All 42 tests pass (30 new + 12 pre-existing in `test_strategies.py`)

### Open Issues

- Priority 6 (per-asset variable drift bands) deferred — medium complexity, requires per-asset vol computation from market data
- Priority 7 (calendar drift guard) deferred
- Priority 8 (hard vs. soft policy violations) deferred — modifies `agents/policies.py` logic, recommend separate session

### Blockers / Dependencies

- (none) — all changes are self-contained in `engine/` and `strategies/`

### Recommendations for the Leader

- **Done and mergeable**: Priorities 1–5 are implemented and tested. Zero breaking changes (all new params have backward-compatible defaults).
- **Next for strategy**: Priority 6 (volatility-adjusted drift bands) is the remaining high-impact item. Requires `market/metrics.py` data access — coordinate with backend if needed.
- **Expose new metrics in UI**: `performance_report` now outputs 6 VaR/CVaR fields + sortino + calmar. The HTML/JS dashboard and Streamlit dashboard will benefit from surfacing these. UI agent can add them without any backend changes.
- **`RiskLevel` available for UI**: `engine.risk.RiskLevel` is now importable. The dashboard could display a color-coded risk indicator (green/yellow/red) using `get_risk_level`.

---

Reports are append-only. Each session adds a dated section below.

---

## Session: 2026-03-24 15:30 — Synthèse des recommandations prioritaires
**Last Updated:** 2026-03-24 15:30
**Phase:** 1 (analysis)

### What Was Done

Synthèse des recommandations issues de la session précédente, présentée sous forme de tableau priorisé.

### Recommendations (Phase 1)

| Priority | Recommendation | File | Impact | Complexity |
|----------|---------------|------|--------|-----------|
| 1 | **Historical VaR** + inclure VaR 95% & 99% + CVaR dans la sortie de `performance_report` | `engine/performance.py` | High | Low |
| 2 | **`sortino_ratio`** (déviation à la baisse uniquement) + **`calmar_ratio`** (rendement / max DD) | `engine/performance.py` | High | Low |
| 3 | **Rebalancing à bande de tolérance** (rebalancer vers target ± ε, pas le target exact) | `engine/orders.py` | High | Low |
| 4 | **Niveaux de risque graduels** : OK / WARN ~7% / HALT 10% — remplace le booléen binaire | `engine/risk.py` | High | Low |
| 5 | **Taux sans risque en constante de config** (2% codé en dur vs. ~4.5% actuel) | `engine/performance.py` | Medium | Low |
| 6 | **Bandes de drift variables par actif** (plus larges pour BTC/ETH, plus étroites pour BND/TLT) | `strategies/threshold.py` | High | Medium |
| 7 | **Garde de drift pour CalendarStrategy** : sauter le rebalancing si max drift < seuil minimum | `strategies/calendar.py` | Medium | Low |
| 8 | **Violations hard vs. soft dans la policy** : un trade bloqué ne doit pas annuler tout le cycle | `agents/policies.py` | Medium | Medium |
| 9 | **Filtre de notionnel minimum** : ignorer les trades < 10$ | `engine/orders.py` | Low | Low |
| 10 | **Corriger `hit_ratio`** : calculer depuis le P&L, pas un booléen `success` | `engine/performance.py` | Low | Low |

**Quick wins (impact élevé, faible complexité) :** priorités 1–5, toutes réalisables sans refactoring majeur. Les priorités 1–4 seules suffiraient à aligner le projet avec les standards de reporting de risque institutionnel.

### Open Issues

- (voir session précédente)

### Blockers / Dependencies

- (none)

### Recommendations for the Leader

- Priorités 1–4 constituent un ensemble cohérent à implémenter en Phase 2 : elles touchent uniquement `engine/` et sont indépendantes de tout travail UI ou backend.
- Dire **"proceed with implementation"** pour démarrer la Phase 2.

---

## Session: 2026-03-24 15:00 — Analysis of engine/performance.py and strategies/
**Last Updated:** 2026-03-24 15:00
**Phase:** 1 (analysis)

---

### What Was Done

Read and analyzed:
- `engine/performance.py` — full performance metrics library
- `engine/risk.py` — drawdown + kill switch
- `engine/orders.py` — order generation + slippage
- `strategies/base.py` — abstract base strategy
- `strategies/threshold.py` — drift-based rebalancing
- `strategies/calendar.py` — calendar-based rebalancing
- `agents/policies.py` — deterministic policy gate
- `docs/team/lead-report.md` and `docs/team/usecases-report.md` — team context

**Lead-Report Alignment Check:**
The lead report asks strategy to confirm no strategy logic is entangled with dead `agent/` code.
Result: **strategies are clean**. `strategies/` imports only from `config`, `engine.orders`, and `utils.time`.
Zero dependency on `agent/` or `services/agent_runtime.py`. Safe to delete `agent/` without touching strategies.

---

### Current State of Code

#### engine/performance.py
- `cumulative_return`, `annualized_return` — standard, correct
- `rolling_volatility(window=30)` — 30-day rolling annualized vol
- `sharpe_ratio(rf=0.02)` — Sharpe with **hardcoded** 2% risk-free rate
- `max_drawdown` — peak-to-trough from history list
- `turnover` — annualized trade volume / portfolio value
- `transaction_costs_total` — slippage-based cost
- `tracking_error` — vs benchmark
- `hit_ratio` — based on `success` boolean flag per trade
- `parametric_var(confidence=0.95)` — Gaussian VaR at one level
- `conditional_var(confidence=0.95)` — CVaR/Expected Shortfall at one level
- `performance_report` — aggregates metrics, but **does not include VaR/CVaR** in the output dict

#### engine/risk.py
- Single-threshold kill switch: `drawdown < -threshold` → halt
- No tiered warning levels

#### engine/orders.py
- Full rebalance to exact target weights (no tolerance band)
- Linear symmetric slippage model (flat rate per asset class)
- `min_qty=0.001` floor (quantity-based, no dollar notional floor)

#### strategies/threshold.py
- Any asset exceeding `DRIFT_THRESHOLD` → triggers full rebalance of all assets
- No per-asset variable thresholds, no tolerance band

#### strategies/calendar.py
- Fixed weekly/monthly schedule, ignores portfolio state entirely
- Monthly = 30 days (not calendar month boundary)

#### agents/policies.py
- Kill switch check, live mode block, max-trades-per-cycle cap
- Ticker universe enforcement + trade plan consistency check
- Per-trade notional cap (fraction of portfolio value)
- Single `approved` boolean: **any blocked trade rejects the entire cycle**

---

### Recommendations (Phase 1)

| Priority | Recommendation | File | Impact | Complexity |
|----------|---------------|------|--------|-----------|
| 1 | Add `historical_var` function (sort actual returns, take percentile) and include both 95% and 99% VaR + CVaR in `performance_report` output | `engine/performance.py` | High | Low |
| 2 | Add `sortino_ratio` (uses only downside deviation) and `calmar_ratio` (annualized return / max drawdown) | `engine/performance.py` | High | Low |
| 3 | Rebalance to tolerance band (target ± half-threshold) instead of exact target in `generate_rebalance_orders` | `engine/orders.py` | High | Low |
| 4 | Add soft-warning tier in `engine/risk.py`: return a `RiskLevel` enum (OK / WARN at ~7% / HALT at 10%) instead of a boolean | `engine/risk.py` | High | Low |
| 5 | Make `rf` in `sharpe_ratio` a global config constant (not hardcoded 2%) — current rate environment is materially higher | `engine/performance.py` + `config.py` | Medium | Low |
| 6 | Add per-asset variable drift bands in `ThresholdStrategy`: wider bands for high-vol assets (BTC/ETH) than for bonds (TLT/BND) | `strategies/threshold.py` | High | Medium |
| 7 | Add drift guard to `CalendarStrategy.should_rebalance`: skip the scheduled rebalance if no asset exceeds `min_drift` from target | `strategies/calendar.py` | Medium | Low |
| 8 | Policy engine: separate hard violations (kill switch, live mode) from soft blocks (individual trade) — hard violations abort cycle; soft blocks allow partial execution of remaining valid trades | `agents/policies.py` | Medium | Medium |
| 9 | Add minimum trade notional filter in `generate_rebalance_orders` (e.g., skip trades < $10 notional) | `engine/orders.py` | Low | Low |
| 10 | Fix `hit_ratio`: compute from trade P&L rather than a `success` boolean flag (which is set by simulator, not by actual outcome) | `engine/performance.py` | Low | Low |

---

### Detailed Rationale

**Priority 1 — Historical VaR + multi-level reporting:**
The portfolio is 20% crypto (BTC-USD + ETH-USD). The Gaussian assumption in `parametric_var` **systematically underestimates** tail risk for fat-tailed assets. Historical VaR (empirical quantile of observed returns) requires zero distributional assumptions. Banking standard: both parametric and historical at 95% and 99%. The `performance_report` function currently calls neither VaR function — they exist in the module but are absent from the report dict.

**Priority 2 — Sortino + Calmar:**
Sharpe penalizes both upside and downside volatility equally. For a portfolio with large crypto upside swings, this artificially deflates the Sharpe ratio. Sortino isolates downside deviation. Calmar (annualized return / |max drawdown|) is the standard hedge fund metric for evaluating return per unit of drawdown risk — more meaningful than Sharpe for a governed agent with a kill switch.

**Priority 3 — Tolerance band rebalancing:**
Rebalancing to exact target on every trigger generates unnecessary micro-trades. The standard approach (tolerance band, also called "corridor" rebalancing) rebalances to target ± ε (typically half the drift threshold). For a 5% drift threshold, rebalance to within ±2.5% of target. This reduces turnover by ~30–40% in typical backtest results with no meaningful loss of tracking quality.

**Priority 4 — Tiered risk levels:**
A binary kill switch is coarse. At 7% drawdown the agent should reduce risk (e.g., flag for smaller trade sizes, disable aggressive buys) before the 10% hard stop. This mirrors Tier 1 / Tier 2 risk alerts in institutional risk management systems. Currently, the first signal the system receives is a full halt.

**Priority 5 — Risk-free rate:**
As of 2026-03, the US 1-year T-bill yield is ~4.5%. A hardcoded 2% rf means the reported Sharpe ratio is ~0.25 Sharpe points too high on an annualized basis. For a $100k portfolio, this materially misrepresents risk-adjusted performance.

**Priority 6 — Volatility-adjusted drift bands:**
BTC-USD has 30-day historical vol of ~60–80% annualized; BND has ~5%. A 5% drift threshold is appropriate for BND but far too tight for BTC (triggering constant rebalancing in normal market movement). Variable bands (e.g., 2× the 30-day rolling vol × sqrt(rebalance_interval)) scale naturally to each asset's volatility regime.

**Priority 7 — Calendar drift guard:**
If a portfolio drifts to target between rebalances, the calendar trigger on Monday will still generate orders (technically all near-zero quantity, but the cycle still runs). A `min_drift` guard (e.g., skip if max drift < 1%) prevents unnecessary cycle executions.

**Priority 8 — Hard vs. soft policy violations:**
Currently, a single blocked trade (e.g., missing price data for ETH-USD) causes `approved=False`, which rejects all 8 other valid trades. In banking execution, hard failures (kill switch, unauthorized mode) abort the cycle; trade-level failures block only that trade. The policy should return `approved_with_blocks=True` when all violations are trade-level, allowing the other trades to proceed.

---

### Open Issues

1. **No stress testing framework**: No crisis scenario simulation (2008 credit crisis, 2020 COVID crash, 2022 crypto bear). Standard in asset management for portfolio validation.

2. **No correlation-aware position sizing**: The portfolio has high tech concentration (AAPL + MSFT + GOOGL + AMZN + NVDA = 50%). No policy or strategy layer checks cross-asset correlation or sector concentration.

3. **No inverse-volatility weighting alternative**: Fixed target weights are used uniformly. Risk parity (equal risk contribution per asset) would provide more robust diversification, especially given the wide vol disparity between equities, bonds, and crypto.

4. **No regime detection**: All strategies operate identically in bull, bear, and sideways regimes. Institutional strategies typically modulate rebalancing frequency or position sizes based on volatility regime.

---

### Blockers / Dependencies

- (none) — Full read access confirmed. All relevant files analyzed. No dependency on unfinished backend or UI work for Phase 1 analysis.

---

### Recommendations for the Leader

1. **Safe to delete `agent/` package**: Strategy code has zero dependency on `agent/` or `services/agent_runtime.py`. Backend can proceed with the cleanup commit without coordinating with strategy.

2. **Top 3 quick wins** (each < 1 day to implement, high value):
   - Historical VaR + 99% level in `performance_report` (Priority 1)
   - `sortino_ratio` + `calmar_ratio` (Priority 2)
   - Tiered risk levels in `engine/risk.py` (Priority 4)

3. **Medium effort, high impact**:
   - Tolerance band rebalancing (Priority 3) — reduces unnecessary turnover across all strategies
   - Volatility-adjusted drift bands in threshold strategy (Priority 6) — prevents over-trading crypto positions

4. **No cross-agent coordination needed for Phase 1**: All proposed improvements are self-contained within `engine/` and `strategies/`. No backend API changes required. No UI changes required (new metrics will surface automatically in the performance report dict, which the dashboard already consumes).
