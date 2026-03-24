# Lead Report — Prediction Wallet

Reports are append-only. Each session adds a dated section below.

---

## Lead Report: 2026-03-24 14:00
**Last Updated:** 2026-03-24

### Team Status
| Agent | Last Session | Last Updated | Status |
|-------|-------------|-------------|--------|
| backend | — | — | No sessions yet |
| ui | — | — | No sessions yet |
| strategy | — | — | No sessions yet |
| usecases | 2026-03-24 — Full Feature Audit | 2026-03-24 | Current |

### Cross-Agent Dependencies

- **usecases → backend**: The `agent/` package and `services/agent_runtime.py` are dead code per usecases. Deletion is a backend task (safe refactor, zero callers confirmed). This is the highest-impact cleanup action and unblocks CLAUDE.md accuracy.
- **usecases → ui**: The Streamlit dashboard (`dashboard/`) is redundant with the HTML/JS UI per usecases. Migration of the Strategy Comparison backtest page to HTML/JS is a UI task that must precede any Streamlit retirement.
- **usecases → backend + ui**: `LocalResearchGateway` feeds the agent a misleading "research_summary" signal. Removing it touches both the service layer (backend) and potentially the MCP wiring (backend/api).
- **No backend/ui/strategy reports yet**: Cannot assess technical quality, implementation risk, or in-progress work for those agents. Priorities below are derived solely from usecases findings.

### Top 3 Priorities

1. **[team-backend]** — Delete `agent/` package and `services/agent_runtime.py` — Zero callers confirmed by usecases grep. These files are silently importable dead code that could mislead contributors. Single cleanup commit. Unblocks CLAUDE.md update.

2. **[team-ui]** — Port Strategy Comparison (backtest) to HTML/JS UI, then retire Streamlit dashboard — The HTML/JS UI is the recommended path (SSE, cleaner design). The only unique Streamlit value is `dashboard/backtest.py`. Migrating it eliminates the dual-UI maintenance burden (every DB schema change currently requires two UI updates).

3. **[team-backend]** — Remove `LocalResearchGateway` and the `local` MCP tools, or replace with a real data source — The `research_summary` injected into agent prompts is trivially derived from data the agent already has. This actively degrades decision quality by presenting reformatted metrics as external research signal. Either cut it entirely or wire to a real API (Finnhub, Alpha Vantage).

### Identified Risks

- **CLAUDE.md drift**: Architecture section still documents `agent/` and `AgentCycleService` as "maintained for compatibility." After the cleanup commit, this must be updated — otherwise onboarding risk persists.
- **Dual-UI schema drift**: Until Streamlit is retired, any `decision_traces` or `agent_runs` schema change will silently break dashboard views that aren't updated.
- **MCP latency with no value**: Running `--use-mcp local` adds subprocess overhead (MCP server spawn + two tool calls) while providing zero incremental data over native tools. Users running the full cycle with `--use-mcp local` incur cost for nothing.
- **Backend/UI/Strategy agents have no reports**: Cannot cross-validate usecases verdicts against implementation complexity. Recommend running `/team-backend`, `/team-ui`, and `/team-strategy` before acting on priorities 1–3 above.

### Recommended Action Plan

**Phase 1 — Cleanup (no feature risk, run next):**
- Run `/team-backend` to get technical assessment of the `agent/` deletion scope and any hidden dependencies before deleting.
- Run `/team-strategy` to confirm no strategy logic accidentally resides in the `agent/` package.
- Delete `agent/` + `services/agent_runtime.py` + update CLAUDE.md in a single commit.
- Remove `LocalResearchGateway` and stop injecting `research_summary` into agent prompts.

**Phase 2 — UI consolidation (medium effort):**
- Run `/team-ui` to get current state of the HTML/JS UI and assess effort to port backtest.
- Port `dashboard/backtest.py` strategy comparison to the HTML/JS UI (new `/backtest` endpoint + UI panel).
- Retire `dashboard/`, `dashboard_main.py`, and Streamlit dependency.

**Phase 3 — MCP (deferred):**
- Keep MCP framework in place as a future extensibility point.
- Remove or disable the `local` profile until `research_summary` is wired to a real data source.

### Stale Reports
- **backend**: No sessions yet — recommend running `/team-backend` before Phase 1 deletions.
- **ui**: No sessions yet — recommend running `/team-ui` before Phase 2 migration.
- **strategy**: No sessions yet — recommend running `/team-strategy` to confirm no strategy logic is entangled with dead `agent/` code.

---

## Lead Report: 2026-03-24 14:30
**Last Updated:** 2026-03-24

### Context

Detailed Phase 1 plan requested. Based on current reports (usecases only).

### Do You Need to Re-run Agents First?

**No — you can proceed directly to Phase 1 without running any agent.**

Rationale:
- **team-usecases already performed grep verification** on every deletion target: zero external callers for `agent/` and `services/agent_runtime.py`, confirmed.
- **CLAUDE.md has already been updated** — references to `agent/` and `AgentCycleService` removed. The "CLAUDE.md drift" risk from the previous report is resolved.
- Phase 1 contains **no logic changes** — only deletions and wiring removals. There is no risk of accidentally altering the critical path (`PortfolioAgentService`).
- The only slightly surgical change (LocalResearchGateway) is handled by grep-before-delete in the plan below.

**When to re-run agents (later, not now):**
- Run `/team-backend` after Phase 1 to get a clean baseline for Phase 2 planning.
- Run `/team-strategy` and `/team-ui` before Phase 2 (backtest migration).

---

### Phase 1 — Complete Step-by-Step Plan

#### Step 1 — Delete the `agent/` package (dead LangGraph code)

Files to delete:
```
agent/__init__.py          (if present)
agent/graph.py
agent/nodes.py
agent/tools.py
agent/state.py
agent/llm.py
agent/prompts.py
agent/__pycache__/         (directory)
```

**Verification before deleting:**
```bash
grep -r "from agent" . --include="*.py" | grep -v "^./agent/"
grep -r "import agent" . --include="*.py" | grep -v "^./agent/"
```
Both should return empty. If not, stop and investigate.

**Risk:** None. usecases confirmed zero external imports.

---

#### Step 2 — Delete `services/agent_runtime.py`

File to delete:
```
services/agent_runtime.py
services/__pycache__/agent_runtime.cpython-*.pyc
```

**Verification before deleting:**
```bash
grep -r "agent_runtime" . --include="*.py"
grep -r "AgentCycleService" . --include="*.py"
```
Both should return empty. If not, stop and investigate.

**Risk:** None. usecases confirmed never imported outside its own file.

---

#### Step 3 — Remove `LocalResearchGateway`

This step requires grepping before acting because the gateway is wired into the agent's dependency injection.

**Grep first:**
```bash
grep -rn "LocalResearchGateway\|research_service\|research_summary" . --include="*.py"
```

Expected wiring points (from usecases):
- `services/research_service.py` — the gateway itself → **delete this file**
- `agents/deps.py` — likely injects `research_summary` into `AgentDependencies` → **remove the field and its construction**
- `agents/models.py` — may have `research_summary: str` in `CycleObservation` → **remove the field**
- `main.py` / `api/runner.py` — may import and pass `LocalResearchGateway` → **remove the import and argument**

**Order of operations:**
1. Delete `services/research_service.py`
2. Edit `agents/deps.py`: remove `research_summary` from `AgentDependencies`
3. Edit `agents/models.py`: remove `research_summary` field from `CycleObservation` (if present)
4. Edit callers (`main.py`, `api/runner.py`): remove construction and passing of `LocalResearchGateway`

**Risk:** Low. The agent will simply stop receiving the misleading `research_summary` field. Existing decision logic is unaffected — this is a context *reduction*, not a change to business logic.

---

#### Step 4 — Disable MCP local tools (`research_summary`)

The MCP *framework* stays intact. Only the two specific tools are addressed.

In `integrations/mcp/server.py`:
- Remove or comment out the `local_research_summary` tool handler
- Optionally remove `local_market_snapshot` (redundant with native `get_market_snapshot`)

In the MCP profile config (likely `profiles/` or `settings.py`):
- Mark the `local` MCP profile as disabled or remove it

**If you prefer a conservative approach:** just remove `local_research_summary` and leave `local_market_snapshot` in place for now. The research gateway is the harmful one; the market snapshot is merely redundant.

**Risk:** Zero. The `local` profile adds latency with no data value. Removing it only improves cycle performance.

---

#### Step 5 — Commit

All four steps above can be committed as a single cleanup commit:
```
chore: remove dead LangGraph agent code and LocalResearchGateway

- Delete agent/ package (graph, nodes, tools, state, llm, prompts)
- Delete services/agent_runtime.py (AgentCycleService)
- Remove LocalResearchGateway and research_summary from agent context
- Disable MCP local research_summary tool

Per usecases audit 2026-03-24: zero external callers confirmed.
PortfolioAgentService critical path unaffected.
```

---

#### Post-Phase-1 Verification

```bash
pytest tests/ -v
python main.py run-cycle --mode simulate
```

Both must pass cleanly before the commit is finalized.

---

### Team Status (updated)
| Agent | Last Session | Last Updated | Status |
|-------|-------------|-------------|--------|
| backend | — | — | No sessions yet |
| ui | — | — | No sessions yet |
| strategy | — | — | No sessions yet |
| usecases | 2026-03-24 — Full Feature Audit | 2026-03-24 | Current |

### Notes
- CLAUDE.md already updated (previous session) — no architecture doc work needed in Phase 1.
- Phase 2 (backtest migration + Streamlit retirement) should not start until `/team-ui` has run.
- Phase 3 (MCP upgrade or removal) is deferred indefinitely until a real data source is identified.
