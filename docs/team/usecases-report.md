# Use-Cases Report — Prediction Wallet

Reports are append-only. Each session adds a dated section below.

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
