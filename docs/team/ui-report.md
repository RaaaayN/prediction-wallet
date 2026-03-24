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
   - Performance metrics tab (Sharpe, VaR, CVaR, Sortino, Calmar) — would need `/api/performance` endpoint
   - Auto-refresh toggle (30s interval for portfolio and history tabs)
   - Dark/light theme toggle
