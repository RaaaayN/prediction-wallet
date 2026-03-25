# Use-Cases Report — Prediction Wallet

Reports are append-only. Each session adds a dated section below.

---

## Session: 2026-03-25 — Post-cleanup audit (all previous recommendations verified)
**Last Updated:** 2026-03-25

### Context

Full re-audit after a significant cleanup sprint. All seven recommendations from the previous session (2026-03-24) have been implemented. This session verifies their completion, re-evaluates the full feature set in its current state, and surfaces one new category of issues: dead `pyproject.toml` dependencies.

### Previous Recommendations — Completion Status

| Recommendation | Status |
|---------------|--------|
| Delete `agent/` package | ✅ Deleted |
| Delete `services/agent_runtime.py` | ✅ Deleted |
| Delete `services/research_service.py` + remove `research_summary` from models | ✅ Done — `MarketSnapshot.research_summary` field removed entirely |
| Retire Streamlit dashboard (`dashboard/`) | ✅ Deleted — `dashboard_main.py` also removed |
| Port backtest to HTML/JS UI + add `/api/backtest` endpoint | ✅ Done — `engine/backtest.py` (moved from dashboard), `/api/backtest` endpoint live |
| Remove MCP `local` profile / `integrations/mcp/` | ✅ Deleted — `mcp_profile` parameter removed from CLI and agent |
| Update CLAUDE.md | ✅ Done — references to dead code removed, architecture now accurate |

### Feature Audits

| Feature | Location | Verdict | Rationale |
|---------|----------|---------|-----------|
| Pydantic AI agent | `agents/portfolio_agent.py`, `agents/models.py`, `agents/policies.py`, `agents/deps.py` | **Useful** | Sole critical path. Observe/decide/validate/execute/audit cycle clean and traceable. No dead code found. |
| Gateway protocols | `services/gateways.py` | **Useful** | Clean Protocol definitions (MarketDataGateway, PortfolioRepository, ExecutionGateway, AuditRepository). `ResearchGateway` removed. Remaining four are actively implemented. |
| Engine (financial math) | `engine/portfolio.py`, `engine/orders.py`, `engine/risk.py`, `engine/performance.py` | **Useful** | Core math. All significantly improved this sprint: tolerance bands, min_notional, tiered RiskLevel, historical VaR, Sortino, Calmar, kill switch boundary fix. |
| Backtest engine | `engine/backtest.py` | **Useful** | Moved from `dashboard/backtest.py` to `engine/` — correct location. Called by `/api/backtest`. Strategy comparison (threshold / calendar / buy-and-hold) now available in HTML/JS UI. |
| SQLite persistence | `db/schema.py`, `db/repository.py` | **Useful** | Audit trail intact. Init-once optimization (2026-03-25) reduces connection overhead. |
| Trade execution layer | `execution/simulator.py`, `execution/persistence.py`, `execution/kill_switch.py`, `execution/types.py` | **Useful** | File-backed portfolio state (portfolio.json) + SQLite-backed audit. Kill switch boundary inconsistency fixed (2026-03-25). |
| Service layer | `services/execution_service.py`, `services/market_service.py`, `services/reporting_service.py` | **Useful** | Clean service separation. No dead code. |
| Strategies | `strategies/threshold.py`, `strategies/calendar.py` | **Useful** | Both improved: per-asset drift bands, calendar drift guard, tolerance-band rebalancing. |
| Market data | `market/fetcher.py`, `market/metrics.py` | **Useful** | yfinance → SQLite pipeline. Used by agent and backtest. |
| PDF reporting | `reporting/pdf_report.py`, `services/reporting_service.py` | **Useful** | Generated each audit step. Durable per-cycle artifact. |
| Portfolio profiles | `profiles/*.yaml`, `portfolio_loader.py`, `settings.py` | **Useful** | 4 profiles. Now supports `per_asset_threshold` in YAML. Runtime switching via env var or `--profile`. |
| FastAPI + HTML/JS UI | `api/main.py`, `api/runner.py`, `ui/index.html` | **Useful** | Now the **only UI**. Backtest, Performance, Trace, Portfolio, History tabs all functional. SSE subprocess cleanup on disconnect added. |
| Test suite | `tests/` (8 files) | **Useful** | Expanded from 36 to 81 tests. New `test_engine.py` (30 tests), `test_policies.py` (10 tests). All 81 pass per backend report. |
| `pyproject.toml` dependencies | `pyproject.toml` | **Useless (8 dead deps)** | See "Open Issues" below. Eight packages listed as direct dependencies have zero imports in the codebase. Combined install weight is significant. |

### Dead Dependencies Audit (pyproject.toml)

| Dependency | Why It Was Added | Current Status | Verdict |
|-----------|-----------------|----------------|---------|
| `streamlit>=1.40.0` | Streamlit dashboard | Dashboard deleted | **Remove** |
| `plotly>=5.18.0` | Streamlit dashboard charts | No imports anywhere | **Remove** |
| `langgraph>=0.2.0` | LangGraph agent | `agent/` package deleted | **Remove** |
| `langchain-anthropic>=0.3.0` | LangGraph agent | `agent/` package deleted | **Remove** |
| `langchain-core>=0.3.0` | LangGraph agent | `agent/` package deleted | **Remove** |
| `mcp[cli]>=1.14.1` | MCP integration | `integrations/mcp/` deleted | **Remove** |
| `PyPortfolioOpt>=1.5.5` | Portfolio optimization (never used) | Zero imports — was never used | **Remove** |
| `cvxpy>=1.4.0` | Convex optimization (used by PyPortfolioOpt) | Zero imports — was never used | **Remove** |

**Note on `google-genai`**: Not imported directly in project code (Pydantic AI uses it internally). It is correctly listed as a direct dep since `pydantic_ai.models.google.GoogleModel` is initialized explicitly in `portfolio_agent.py`. **Keep**.

### New Feature Evaluations

*(No new features proposed in this session — audit-only request.)*

### Open Issues

1. **8 dead dependencies in `pyproject.toml`**: `streamlit`, `plotly`, `langgraph`, `langchain-anthropic`, `langchain-core`, `mcp[cli]`, `PyPortfolioOpt`, `cvxpy`. All have zero imports in the current codebase. Removing them reduces install time, reduces transitive dependency surface, and removes misleading signals about what the project uses. This is a one-line-per-package edit in `pyproject.toml`.

2. **`hit_ratio` still based on `success` boolean** (strategy report P10, deferred): `performance_report` computes hit ratio as fraction of trades where `success=True`. This flag is set by the simulator at execution time, not by actual outcome measurement. True hit ratio requires comparing fill price vs. later market price. Low urgency, but misleading for performance reporting.

3. **No test for `CycleAudit.errors` population** (carried from backend): `errors=[v.message for v in policy.violations]` is correct code but untested. Low risk; a single test case (hard violation → error populated) would close this.

4. **`db/repository._connect()` thread safety** (carried from backend): `_DB_INITIALIZED.add()` is GIL-protected under CPython. Acceptable assumption; documented in backend report. No action needed unless concurrency model changes.

5. **`portfolio_loader.py` not in CLAUDE.md architecture section**: The file exists and is used by `settings.py`, but is not listed in the architecture section. Minor documentation gap.

### Blockers / Dependencies

- (none) — Full read access confirmed. No missing information.

### Recommendations for the Leader

1. **Remove 8 dead `pyproject.toml` deps** — this is a 1-minute backend task: delete 8 lines from `pyproject.toml`, run `uv sync`. Zero code changes, zero risk, significant install overhead reduction. Highest value-to-effort ratio of anything currently open.

2. **Architecture is now clean** — the codebase accurately reflects CLAUDE.md. No hidden dead code layers remain. This is the first session where there is nothing actively misleading or redundant in the project structure.

3. **`hit_ratio` fix is low priority but worth scheduling** — it's a performance reporting accuracy issue, not a functional bug. A future strategy session could fix it once P&L tracking is available per execution.

4. **The HTML/JS UI is feature-complete** — Portfolio, Allocation (donut), History (drawdown sub-chart), Performance (12 metrics, rolling Sharpe), Traces (stage filter), Cycles, Backtest (all 3 strategies). No further UI gaps identified. Future UI work should be demand-driven, not speculative.

---

## Session: 2026-03-24 — Full Feature Audit (existing codebase)
**Last Updated:** 2026-03-24

### Feature Audits

| Feature | Location | Verdict | Rationale |
|---------|----------|---------|-----------|
| Pydantic AI portfolio agent | `agents/portfolio_agent.py`, `agents/models.py`, `agents/policies.py`, `agents/deps.py` | **Useful** | Primary critical path. Every CLI command and the web UI flows through `PortfolioAgentService`. Observe → decide → validate → execute → audit cycle is clean and traceable. |
| Engine (portfolio math) | `engine/portfolio.py`, `engine/orders.py`, `engine/risk.py`, `engine/performance.py` | **Useful** | Core financial computation. Used by strategies, execution service, dashboard, and backtest. No dead code detected. |
| SQLite persistence layer | `db/schema.py`, `db/repository.py` | **Useful** | Audit trail (decision_traces, agent_runs, executions, portfolio_snapshots). Core to the governed-agent architecture. |
| Trade execution + kill switch | `execution/simulator.py`, `execution/persistence.py`, `execution/kill_switch.py`, `execution/types.py` | **Useful** | File-backed portfolio state (portfolio.json + trades.log) still active via `PortfolioStore`/`TradeLogStore`. Kill switch is non-negotiable safety mechanism. |
| Service layer | `services/execution_service.py`, `services/market_service.py`, `services/reporting_service.py` | **Useful** | Clean separation between agent tools and infrastructure. Well-used. |
| Strategies (threshold + calendar) | `strategies/threshold.py`, `strategies/calendar.py` | **Useful** | Two distinct rebalancing strategies, switchable at CLI. Used in observe step and backtest. |
| Market data (fetcher + metrics) | `market/fetcher.py`, `market/metrics.py` | **Useful** | yfinance → SQLite pipeline. Sharpe, volatility, drawdown metrics consumed by agent. |
| PDF audit reports | `reporting/pdf_report.py`, `services/reporting_service.py` | **Useful** | Generated each cycle in the audit step. Provides a durable artifact per cycle. |
| Portfolio profiles (YAML) | `profiles/*.yaml`, `portfolio_loader.py`, `settings.py` | **Useful** | 4 profiles (balanced, conservative, growth, crypto_heavy). Clean runtime switching via env var or `--profile` flag. |
| FastAPI backend + HTML/JS UI | `api/main.py`, `api/runner.py`, `ui/index.html` | **Useful** | Modern, real-time SSE streaming. Well-designed dark-theme interface. Active — this is the recommended UI path. |
| Streamlit dashboard | `dashboard/ui.py`, `dashboard/data.py`, `dashboard/app.py`, `dashboard_main.py` | **Redundant** | Substantially overlaps with the HTML/JS UI (portfolio overview, trade history, agent traces, run-agent). Unique value: Strategy Comparison page (`dashboard/backtest.py`). Without that page, the entire Streamlit dashboard is redundant. Maintenance cost: two separate UIs to keep aligned with DB schema. |
| Strategy comparison backtest | `dashboard/backtest.py` | **Useful** | Unique feature with no equivalent in the HTML/JS UI. Deterministic threshold vs. calendar vs. buy-and-hold simulation against historical data. Worth preserving even if Streamlit is cut. |
| MCP integration | `integrations/mcp/registry.py`, `integrations/mcp/server.py` | **Useful** | Architecturally sound extensibility layer. Enables future real-data research tools. However, the *current* tools (`market_snapshot`, `research_summary`) duplicate what native agent tools already provide. |
| LocalResearchGateway | `services/research_service.py` | **Useless** | `summarize()` formats already-available metrics (volatility level + YTD return) into a string. Generates zero additional insight. The agent already has full metrics via `get_market_snapshot`. This is a placeholder that was never upgraded to real research. |
| MCP local tools (market_snapshot, research_summary) | `integrations/mcp/server.py` | **Redundant** | `market_snapshot` replicates what `get_market_snapshot` agent tool already does. `research_summary` just calls `LocalResearchGateway.summarize()` (itself useless). The MCP *framework* is useful; these specific tools are not. |
| Legacy LangGraph agent (`agent/` package) | `agent/graph.py`, `agent/nodes.py`, `agent/tools.py`, `agent/state.py`, `agent/llm.py`, `agent/prompts.py` | **Useless** | Entirely dead code. `agent/graph.py` delegates to Pydantic AI. `agent/nodes.py` nodes (`decide_node`, `execute_node`, `audit_node`, `alert_node`) return `state` unchanged — no-ops. `agent/tools.py` (`ToolRuntime`) raises `RuntimeError` on dispatch. `agent/llm.py` raw API clients used only by `AgentCycleService`. Zero imports from outside this package in tests or main flows. |
| AgentCycleService (LangGraph orchestration) | `services/agent_runtime.py` | **Useless** | Never imported by any caller outside its own file (confirmed by grep). Was the pre-Pydantic AI critical path; now fully superseded. Drags in `agent/llm.py` and `agent/prompts.py` as dead dependencies. |

### New Feature Evaluations

*(No new features proposed in this session — audit-only request.)*

### Open Issues

1. **Dual-UI maintenance burden**: Two UIs (Streamlit + HTML/JS) serve the same core views. Every schema change (DB column, new trace field) must be reflected in both. This is ongoing overhead with no user benefit if both target the same user.

2. **`LocalResearchGateway` dilutes agent context**: The `research_summary` field passed to the agent contains only "elevated volatility, YTD +X%" — essentially reformatted metrics the agent already sees. This can confuse more than it helps. If the agent trusts the research summary as external signal, it's being misled by trivially derived data.

3. **Dead legacy code not gated**: The `agent/` package and `services/agent_runtime.py` are importable and pass `import` checks silently. They do not raise errors until dispatched. A developer could accidentally rely on them, especially `observe_node`/`analyze_node` which silently double-run the observe cycle.

4. **MCP tools provide no incremental value**: With `--use-mcp local`, the agent invokes `local_market_snapshot` and `local_research_summary` via subprocess MCP, which recomputes data already present in the native `get_market_snapshot` tool. Net effect: added latency, no new information.

### Blockers / Dependencies

- (none) — Full read access confirmed. All key files reviewed.

### Recommendations for the Leader

1. **Delete `agent/` package and `services/agent_runtime.py`**: Zero callers. The "kept for compatibility" note in CLAUDE.md should be removed. This is pure maintenance risk — a developer could reactivate a dead path. Recommend a single cleanup commit.

2. **Delete or replace `LocalResearchGateway`**: Either (a) remove it and stop injecting `research_summary` into agent prompts entirely, or (b) replace with a real external data source (news API, earnings calendar). A placeholder that pretends to be research is worse than no research signal.

3. **Consolidate UIs — keep HTML/JS, migrate backtest**: The FastAPI + HTML/JS UI is the better long-term choice (real-time SSE, cleaner design, no Streamlit dependency). Recommend porting the Strategy Comparison page to the HTML/JS UI, then retiring the Streamlit dashboard. This removes a major maintenance burden.

4. **Upgrade MCP local tools or remove them**: The `local` MCP profile adds subprocess overhead with no incremental data. Either (a) remove the `local` profile and keep MCP as a future extensibility point only, or (b) wire `research_summary` to a real data source (Finnhub, Alpha Vantage) to justify the MCP overhead.

5. **CLAUDE.md outdated on agent architecture**: The architecture section still references `agent/` nodes and `services/agent_runtime.py` as maintained-for-compat. These are now dead code and the CLAUDE.md claim is misleading. Update after cleanup.
