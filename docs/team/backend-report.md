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

## Session: 2026-03-25 10:00 — Policy split + backend hardening (phase 2)
**Last Updated:** 2026-03-25 10:00

### What Was Done

**P4 — db/repository.py init-once optimization:**
- Added module-level `_DB_INITIALIZED: set[str]` — `init_db()` now runs exactly once per DB path per process instead of on every connection. Tests unaffected (each uses a unique temp path).

**P1 — agents/policies.py hard/soft violation split (critical correctness fix):**
- Hard violations (kill_switch_active, live_blocked, too_many_trades): return early with `approved=False`, `allowed_trades=[]`, no per-trade evaluation
- Soft blocks (bad ticker, not in plan, missing price, notional cap): placed in `blocked_trades` only — `approved=True`, other valid trades still execute
- No model schema changes (`PolicyEvaluation` unchanged); only semantics of `approved` corrected

**P2 — agents/portfolio_agent.py — CycleAudit.errors populated:**
- Added `errors=` to `CycleAudit(...)` constructor in `audit()`: collects hard violation messages + non-empty error strings from failed executions

**P5 — SQL deduplication (api/main.py + db/repository.py):**
- Added `get_snapshots(limit)` and `get_latest_positions()` to `db/repository.py`
- All 6 data endpoints in `api/main.py` now delegate to repository functions
- Removed `_connect()` and `_rows()` helpers from API layer; removed unused `sqlite3` import
- `/api/traces` cycle-specific path returns ASC (reversed from repository DESC) to match previous behaviour

**P3 — api/runner.py SSE subprocess cleanup on disconnect:**
- Added `proc_ref: list[Popen]` pattern: worker thread populates it before blocking on stdout
- `stream_command` wrapped in `try/finally`: calls `proc_ref[0].terminate()` when async generator closes (client disconnect or normal completion)
- `if proc_ref:` guard handles the race where disconnect occurs before thread starts

**Tests:**
- Updated `test_policy_blocks_trade_outside_plan` in `test_portfolio_agent.py`: soft block now correctly asserts `approved is True`
- Added `tests/test_policies.py` with 10 tests covering all hard/soft violation paths
- **All 81 tests pass**

### Open Issues

1. **`MarketSnapshot.research_summary`** — field present in `agents/models.py`, always `""`. Remove after team-ui confirms it is not rendered in the HTML/JS UI.
2. **`run_cycle` and `run_cycle_dict` still pass `mcp_profile`** — the MCP profile parameter was removed from `run_cycle`/`run_cycle_dict` signatures in a previous session but the internal `audit()` call still references `mcp_profile`. Verify parameter threading is consistent.
3. **`db/repository._connect()` thread safety** — `_DB_INITIALIZED.add()` is GIL-protected but not explicitly thread-safe. Acceptable under CPython; document as assumption.
4. **No test for `CycleAudit.errors` population** — test added in plan but not yet implemented (deferred to next session or team-lead discretion).

### Blockers / Dependencies

- (none) — All changes are self-contained within backend scope.

### Recommendations for the Leader

1. **Policy fix is ready to merge** — critical correctness bug resolved. A missing price for one asset (e.g. ETH-USD weekend gap) no longer silently halts all 8 other valid trades.
2. **Coordinate `research_summary` removal with team-ui** before removing the field from `agents/models.py`.
3. **Next backend priority**: add test coverage for `CycleAudit.errors`, then verify `run_cycle`/`run_cycle_dict` mcp_profile parameter threading.
4. **No engine/ changes this session** — strategy report P6/P7 remain open for team-strategy.
