# Backend Report — Prediction Wallet

Reports are append-only. Each session adds a dated section below.

---

## Session: 2026-03-24 16:00 — Dead code cleanup + backend hardening
**Last Updated:** 2026-03-24 16:00

### What Was Done

**Deletions (zero-caller confirmed, in sync with usecases + lead reports):**
- Deleted `agent/` package entirely (7 files: graph.py, nodes.py, tools.py, state.py, llm.py, prompts.py, __init__.py) — dead LangGraph layer, all nodes were no-ops
- Deleted `services/agent_runtime.py` — AgentCycleService, never imported by any caller
- Deleted `services/research_service.py` — LocalResearchGateway, reformatted data the agent already has

**LocalResearchGateway removal (cascading):**
- Removed `ResearchGateway` Protocol from `services/gateways.py`
- Removed `research_gateway` field from `agents/deps.py` (AgentDependencies)
- Removed `research_gateway` parameter from `PortfolioAgentService.__init__`
- Removed `self.research_gateway.summarize()` call in `observe()` — MarketSnapshot.research_summary now defaults to `""`
- Removed `ctx.deps.research_gateway.summarize()` call in `get_market_snapshot` tool
- Updated `tests/test_portfolio_agent.py` to remove import and usage

**API hardening:**
- Fixed `api/main.py._connect()`: now calls `init_db()` before connecting — previously bypassed schema initialization, would silently fail on a fresh DB
- Fixed `api/runner.py`: replaced deprecated `asyncio.get_event_loop()` with `asyncio.get_running_loop()` (Python 3.10+ requirement)

**CLAUDE.md:**
- Removed references to `agent/`, `services/agent_runtime.py`, `services/research_service.py`
- Removed "LangGraph maintained for compat" line — Pydantic AI is now sole critical path

**Verification:** All 6 tests in `test_portfolio_agent.py` + `test_trace_and_cli.py` pass.

### Open Issues

1. **`api/main.py` duplicates repository queries**: The API layer contains raw SQL for snapshots, runs, executions, traces, positions. These duplicate logic already in `db/repository.py`. Should delegate to repository functions. Low urgency (no bug, just tech debt).

2. **`db/repository._connect()` calls `init_db()` on every operation**: Minor overhead — schema init + migrations run on each DB call. Acceptable for current volume; becomes a concern under concurrent load. Recommend a module-level init-once flag.

3. **`agents/policies.py`: single `approved` boolean blocks all trades**: One blocked trade (e.g., missing price for ETH-USD) sets `approved=False` and rejects all 8 valid trades. Institutional standard: hard violations (kill switch, live mode) abort cycle; trade-level failures block only that trade. Strategy report flagged this as Priority 8.

4. **`CycleAudit.errors` is always `[]`**: No code path populates this field. It appears in the legacy dict but is never written to. Either populate it or remove the field to avoid misleading consumers.

5. **`MarketSnapshot.research_summary` field still present in models.py**: Now always `""`. Could be removed from the model entirely to avoid confusion, but this is a UI-visible field change — flag for team-ui to assess impact before removing.

6. **`api/runner.py` subprocess has no cancellation on SSE disconnect**: If a client disconnects mid-stream, the subprocess continues running. For long `run-cycle` commands this wastes resources. A `asyncio.CancelledError` handler + `proc.terminate()` would fix this, but requires the process handle to be accessible from the async task.

### Blockers / Dependencies

- (none) — All changes are self-contained within backend scope.

### Recommendations for the Leader

1. **Phase 1 complete**: Dead code deleted, research gateway removed, API hardened. CLAUDE.md is now accurate. Safe to merge this session's changes.

2. **Next backend priority**: Fix policy engine hard/soft violation split (`agents/policies.py`). Strategy report Priority 8. This is a pure backend change with no UI impact. High value: prevents a single bad ticker from blocking an entire rebalance cycle.

3. **Coordinate with team-ui before removing `MarketSnapshot.research_summary`**: The field is now always empty (`""`). The HTML/JS UI may be rendering it. Verify and remove together in a coordinated change.

4. **`api/main.py` raw SQL**: Medium-priority tech debt. Recommend routing API data reads through `db/repository.py` functions. Eliminates risk of DB schema drift silently breaking API endpoints.

5. **Strategy report engine improvements**: Priorities 1–5 from the strategy report are self-contained `engine/` changes. No coordination with backend needed for those — team-strategy can proceed independently.
