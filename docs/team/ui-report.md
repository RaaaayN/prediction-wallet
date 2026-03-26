# UI Report — Prediction Wallet

Reports are append-only. Each session adds a dated section below.

---

## Session: 2026-03-24 16:30 — Propose UI improvements
**Last Updated:** 2026-03-24 16:30

### What Was Done

All changes applied to `ui/index.html`:

1. **Portfolio tab — PnL stat cards**: Expanded the 4-card header grid to 6 cards (2-col mobile, 6-col desktop). Added `PnL ($)` and `PnL (%)` cards that populate from `pf.pnl_dollars` / `pf.pnl_pct` (null-safe, shows `--` if unavailable). Drawdown card now color-codes dynamically: green (< 2%), yellow (2–5%), red (> 5%).

2. **Portfolio tab — Allocation donut chart**: New 4-column grid splits the tab into a 1-col donut panel and a 3-col positions table. Donut uses Chart.js doughnut type with 9-color palette, tooltip shows current vs target %, and a color-coded legend below shows per-ticker drift direction.

3. **History tab — Drawdown sub-chart**: Added a second canvas (`chart-drawdown`) below the portfolio value chart. Drawdown is computed in-browser from the snapshots series (peak-tracking formula). Red fill, 180px height.

4. **Traces tab — Stage filter**: Added a `<select>` dropdown (All / Observe / Decide / Validate / Execute / Audit) alongside the existing cycle_id text filter. `filterTraces()` now applies both filters. Useful when there are many traces from multiple cycles.

5. **Backtest tab (stub)**: New `Backtest` tab in the nav. Full UI: day-range selector, Run button, stat cards (Return, Sharpe, Max DD, Trades, Costs) per strategy, and an equity-curve Chart.js multi-line chart. Calls `GET /api/backtest?days=N`. Degrades gracefully: shows a clear error message if the endpoint doesn't exist yet.

### Open Issues

- `pf.pnl_dollars` / `pf.pnl_pct` — not confirmed in `portfolio.json` schema. Cards show `--` if absent. A backend check of `PortfolioStore` serialization would confirm if these fields are present.
- Backtest tab shows "endpoint not available" until team-backend adds `/api/backtest`.

### Blockers / Dependencies

- **Backtest tab functional** — blocked by: **team-backend** — needs `/api/backtest?days=N` endpoint that wraps `dashboard/backtest.py::run_strategy_comparison(days)` and returns JSON `{threshold: {...}, calendar: {...}, buy_and_hold: {...}}` with fields: `equity` (list of `{date, total_value}`), `cum_ret`, `sharpe`, `max_dd`, `n_trades`, `costs`.
- **PnL cards on Portfolio tab** — possible blocker: **team-backend** — confirm that `portfolio.json` includes `pnl_dollars` and `pnl_pct` fields, or add them to the `/api/portfolio` response.

### Recommendations for the Leader

1. **Backtest tab is ready on the frontend** — only the `/api/backtest` endpoint is missing. This is a minimal backend task (~20 lines in `api/main.py`). Once done, the Strategy Comparison feature is fully operational in the HTML UI, unlocking Streamlit retirement.

2. **Confirm PnL fields in `/api/portfolio`** — if `portfolio.json` doesn't include `pnl_dollars`/`pnl_pct`, the backend could compute them from `(total_value - initial_capital)` and add them to the API response.

3. **Future UI improvements** (not implemented, YAGNI for now):
   - Auto-refresh toggle (30s interval for portfolio and history tabs)
   - Dark/light theme toggle

---

## Session: 2026-03-24 17:00 — Performance metrics tab
**Last Updated:** 2026-03-24 17:00

### What Was Done

Added a new **Performance** tab to `ui/index.html` (7th tab, between Cycles and Backtest). All metrics are computed **client-side in JavaScript** from existing endpoints — no backend changes required.

**Data sources used:**
- `GET /api/snapshots?limit=500` — portfolio value timeseries
- `GET /api/executions?limit=500` — trade history

**Metrics computed:**

| Section | Metrics |
|---------|---------|
| Returns | Gross Return %, Net Return % (after costs), Annualized %, Volatility (ann.) |
| Risk-Adjusted | Sharpe Ratio (4.5% rf), Sortino Ratio, Calmar Ratio, Max Drawdown |
| Value at Risk | Parametric VaR 95%, Historical VaR 95%, CVaR 95% (Expected Shortfall), Historical VaR 99% |
| Trade Quality | Total Trades, Hit Ratio %, Total Costs $, Annualized Turnover % |

**Additional feature:** Rolling 30-day Sharpe chart (Chart.js line) at the bottom of the tab.

**UX details:**
- Period selector: 30d / 60d / 90d / 180d / 365d with Refresh button
- All stat cards are dynamically color-coded (green/yellow/red) based on magnitude thresholds
- Graceful empty state: shows "Not enough data" message if < 4 snapshots in period
- Connection error handled gracefully

### Open Issues

- `pf.pnl_dollars` / `pf.pnl_pct` — still unconfirmed in `portfolio.json` schema (from previous session).
- VaR metrics require sufficient snapshot history to be meaningful (> 20 snapshots). With sparse data, VaR estimates will be imprecise — this is a data availability issue, not a code bug.
- `hit_ratio` correctness depends on `success` field in executions being set by the simulator (confirmed by strategy report: set by simulator, not by actual outcome — limitation noted).

### Blockers / Dependencies

- (none) — Performance tab is fully functional using only existing endpoints.

### Recommendations for the Leader

1. **Backtest tab is now unblocked**: team-backend added `/api/backtest` endpoint (confirmed by Explore agent). The Backtest tab should now render equity curves and strategy comparison stats. Streamlit retirement is now feasible.

2. **`/api/performance` endpoint is no longer needed**: All performance metrics are now computed client-side. Backend effort saved.

3. **Next UI priority**: With Performance + Backtest + all core tabs implemented, the main remaining work is Streamlit retirement (delete `dashboard/`, `dashboard_main.py`, remove `streamlit` dep). This is a straightforward deletion — no new UI code needed.

---

## Session: 2026-03-25 — Trade history: event_type badges + drift_before/slippage_pct
**Last Updated:** 2026-03-25

### What Was Done

Updated the executions table in the History tab (`ui/index.html` — `loadHistory()` function).

**Three new data points per row:**

1. **`event_type` badge** (new column after Cycle): resolved client-side by fetching `GET /api/traces?limit=200` in parallel with the existing fetches, building a `cycle_id → event_type` lookup map, then calling `eventTypeBadge()` per row. Badge colors: yellow for "threshold", blue for "calendar", green for "manual", blue for any unknown value, `—` if no trace found. No backend change required.

2. **`drift_before` column** (after Qty): reads `e.drift_before` directly from the executions API response (already a migration column in the `executions` table). Displayed as a signed percentage (+X.X%), color-coded: red if overweight (> +1.5%), green if underweight (< −1.5%), gray otherwise.

3. **`slippage_pct` column** (after Slippage $): reads `e.slippage_pct` directly from the executions API response (migration column). Displayed as 3-decimal percentage (e.g. "0.050%"). Shows `—` if field is null (backward compat with rows created before the migration).

**Table now has 12 columns**: Time | Cycle | Event | Ticker | Action | Qty | Fill Price | Drift Before | Slippage $ | Slippage % | Cost | Status

**New helper added**: `eventTypeBadge(et)` function inserted before `loadPortfolio()`.

### Open Issues

- `event_type` field in `decision_traces` may be empty for older rows (pre-migration). Displays `—` gracefully in those cases.
- `drift_before` and `slippage_pct` will be `0.0` (not null) for rows written before the migration columns were added — these will show `+0.0%` and `0.000%` rather than `—`. Acceptable.

### Blockers / Dependencies

- (none)

### Recommendations for the Leader

1. Streamlit retirement is the next clean win — `dashboard/`, `dashboard_main.py`, and the `streamlit` dependency can be deleted without any UI rework now that the HTML/JS UI covers all views including Backtest.
2. Consider adding `event_type` to the `executions` table directly (team-backend) to avoid the extra `/api/traces` fetch in `loadHistory()` and make the join simpler.

---

## Session: 2026-03-26 — Correlation Heatmap tab
**Last Updated:** 2026-03-26

### What Was Done

Added a new **Correlation** tab (8th tab) to `ui/index.html` and a supporting `/api/correlation` endpoint to `api/main.py`.

**Backend (`api/main.py`):**
- New `GET /api/correlation?days=N` endpoint (default 90d, range 10–365).
- Reads portfolio positions from `portfolio.json`, fetches per-ticker `Close` prices via `MarketService.get_historical()`, computes `pct_change()` returns, then calls `engine.performance.rolling_correlation()`.
- Returns `{ tickers, matrix, days, n_obs }` — matrix is a 2D list of rounded float values.

**Frontend (`ui/index.html`):**
- New tab button: "Correlation" in the nav.
- CSS: `.heatmap-table`, `.heatmap-row-label` styles for the grid layout.
- HTML: tab div with window selector (30/60/90/180/365d), Refresh button, error/loading states, summary stats row, heatmap container, and a color-scale legend bar.
- JS `loadCorrelation()`:
  - Fetches `/api/correlation?days=N`
  - Renders 4 summary stat cards: Avg Pairwise Correlation (color-coded: green < 0.3, yellow 0.3–0.6, red > 0.6), Obs count, Highest pair, Lowest pair.
  - Renders an NxN heatmap table: negative → red (#f85149), zero → dark (#21262d), positive → blue (#58a6ff) with linear RGB interpolation. Diagonal cells are blue-tinted "1.000". Each cell has a tooltip showing ticker pair and value.
  - Linear gradient color-scale legend at bottom.

### Open Issues

- Heatmap is wide for large N (9 assets). On small screens, horizontal scroll on the card container handles this.
- Avg pairwise correlation thresholds (0.3 / 0.6) are reasonable heuristics, not portfolio-theory-backed. Adjustable if needed.

### Blockers / Dependencies

- (none) — tab is fully functional using only existing `MarketService` and `engine.performance.rolling_correlation`.

### Recommendations for the Leader

1. Correlation heatmap is a natural complement to the backtest tab for portfolio quality assessment. No further action needed from other agents.
2. If the market DB is empty (no price history loaded), the endpoint returns 503 with a clear message. Users should run `python main.py observe` to populate it first.

---

## Session: 2026-03-26 — Stress Test tab
**Last Updated:** 2026-03-26

### What Was Done

Added a new **Stress Test** tab (9th tab) to `ui/index.html`.

**Frontend only** — the `/api/stress` endpoint was already implemented by team-backend.

**Changes to `ui/index.html`:**

1. **Nav button**: Added `<button onclick="showTab('stress', this)">Stress Test</button>` after the Correlation button.

2. **Tab HTML** (`id="tab-stress"`): Header + description, Refresh button, error/loading states, a 2-col grid of scenario cards (`id="stress-cards"`), and a P&L bar chart canvas (`id="chart-stress"`).

3. **State**: Added `let stressChart = null;` alongside other chart state vars.

4. **`showTab` hook**: Added `if (name === 'stress') loadStress();` so the tab auto-loads on first visit.

5. **`loadStress()` function**: Fetches `GET /api/stress`, then:
   - Maps each scenario result to a card showing: human-readable label, description, kill switch badge (red "⚠ Kill Switch" / green "✓ Safe"), 4 stat cards (Before, After, P&L $, P&L %), and a mini "Weights After Shock (Top 4)" bar visualization.
   - Renders a Chart.js horizontal bar chart comparing P&L % across all 4 scenarios; kill-switch scenarios render in red, safe ones in blue.
   - Handles 4xx/5xx HTTP errors, network failures, and empty result sets gracefully with visible error messages.

**API response format consumed** (`list[dict]`):
- `scenario`, `description`, `portfolio_value_before`, `portfolio_value_after`, `pnl_dollars`, `pnl_pct`, `kill_switch_triggered`, `weights_after`

**Scenario label mapping** (hardcoded, matches backend `STRESS_SCENARIOS` names):
- `covid_march_2020` → "COVID-19 Crash"
- `gfc_2008` → "GFC 2008"
- `rate_shock_2022` → "Rate Shock 2022"
- `tech_selloff` → "Tech Selloff"

### Open Issues

- (none)

### Blockers / Dependencies

- (none) — tab is fully functional using the existing `/api/stress` endpoint.

### Recommendations for the Leader

1. **All user-facing tabs are now implemented**: Control, Portfolio, History, Agent Trace, Cycles, Performance, Backtest, Correlation, Stress Test. The HTML/JS UI is feature-complete relative to the Streamlit dashboard.
2. Streamlit retirement (`dashboard/`, `dashboard_main.py`, `streamlit` dep) is the natural next step if not already done.
