# Agent Team Design — Prediction Wallet
**Date:** 2026-03-24
**Status:** Approved

## Overview

A team of 5 Claude Code skill-agents coordinated via shared Markdown reports in `docs/team/`. Members work asynchronously and independently; the team leader (`/team-lead`) synthesizes on demand.

## Architecture

```
.claude/skills/
  team-backend.md        → backend agent  (invoked as /team-backend)
  team-ui.md             → UI agent       (invoked as /team-ui)
  team-strategy.md       → strategy agent (invoked as /team-strategy)
  team-usecases.md       → use-case agent (invoked as /team-usecases)
  team-lead.md           → team leader    (invoked as /team-lead)

docs/team/
  backend-report.md      → written/appended by team-backend
  ui-report.md           → written/appended by team-ui
  strategy-report.md     → written/appended by team-strategy
  usecases-report.md     → written/appended by team-usecases
  lead-report.md         → written/appended by team-lead
```

Each skill is invoked as `/<filename-stem>`, e.g., `/team-backend` maps to `.claude/skills/team-backend.md`.

## Coordination Protocol

1. User invokes a member agent (`/team-backend`, `/team-ui`, `/team-strategy`, `/team-usecases`) for a specific task.
2. **Before starting:** The member reads `docs/team/lead-report.md` (if it exists) to align with current priorities.
3. **Before starting:** The member also reads all peer reports (`docs/team/*.md`) to detect recently completed or in-progress work on overlapping files.
4. The member completes its task, then **mandatorily writes/appends its report** to `docs/team/<agent>-report.md` before ending. The session is not complete until the report is written.
5. When the user wants a synthesis, they invoke `/team-lead`.
6. The leader reads all available reports in `docs/team/`, synthesizes, and appends to `docs/team/lead-report.md`.

**Blocked agent rule:** If an agent detects a blocker that requires another agent to act first, it writes its partial findings, clearly marks the blocker in the report, and terminates. It does not retry or wait. The user or team-lead resolves the dependency and re-invokes the blocked agent in a new session.

## Agent Roles

### `/team-backend`
- **Scope:** `agents/`, `services/`, `engine/`, `db/`, `api/` (including `api/runner.py`)
- **Responsibilities:** identify bugs, technical debt, missing tests, performance issues; implement fixes when task is clear
- **Output:** `docs/team/backend-report.md`

### `/team-ui`
- **Scope:** `ui/index.html`, `dashboard/`
- **Note:** `api/runner.py` is exclusively in team-backend's scope. team-ui may read it and recommend changes via its report, but must not modify it.
- **Responsibilities:** improve design, UX, add views, fix visual bugs; can modify HTML/CSS/JS and dashboard files
- **Output:** `docs/team/ui-report.md`

### `/team-strategy`
- **Scope:** `engine/`, `strategies/`, `agents/policies.py`
- **Responsibilities:**
  - **Phase 1 (always):** Analyze code through the lens of banking best practices (risk-adjusted returns, position sizing, VaR, stress testing, multi-factor signals). Produce prioritized text recommendations.
  - **Phase 2 (only with explicit user approval in the same session):** Implement improvements in code. The user signals approval by saying "proceed with implementation" or equivalent. The agent must quote the approval phrase verbatim in its report before writing any code. Without this explicit approval, the agent stays in Phase 1 only.
- **Output:** `docs/team/strategy-report.md`

### `/team-usecases`
- **Scope:** entire project (read-only)
- **Responsibilities:**
  - Audit existing features: useful / useless / redundant
  - Filter new feature ideas: business value, complexity, risk — accept or reject with rationale
  - Does **not** modify code — produces only structured evaluations
  - Does **not** set implementation priorities (that is team-lead's role)
- **Output:** `docs/team/usecases-report.md`

### `/team-lead` (invoked manually)
- **Scope:** `docs/team/*.md` (all member reports, read-only)
- **Responsibilities:**
  - Read all available reports and check their `Last Updated` timestamps — flag reports older than 3 sessions as potentially stale
  - Identify cross-agent dependencies (e.g., team-strategy blocked by team-backend fix)
  - Defer to team-usecases' evaluations for feature value decisions; do not independently re-assess feature utility
  - Produce synthesis: team status, top 3 priorities, risks, action plan
  - Does **not** modify code
- **Output:** `docs/team/lead-report.md`

## Report Format

### Member reports (`docs/team/<agent>-report.md`)

Reports are **appended** — each session adds a new dated section. Do not overwrite previous sessions.

```markdown
## Session: YYYY-MM-DD HH:MM — <short task description>
**Last Updated:** YYYY-MM-DD HH:MM

### What Was Done
- ...

### Open Issues
- ...

### Blockers / Dependencies
- (none) OR (blocked by: <agent> — <description>)

### Recommendations for the Leader
- ...
```

### Leader report (`docs/team/lead-report.md`)

Leader reports are also **appended** — each invocation adds a new dated section.

```markdown
## Lead Report: YYYY-MM-DD HH:MM
**Last Updated:** YYYY-MM-DD HH:MM

### Team Status
| Agent | Last Session | Last Updated | Status |
|-------|-------------|-------------|--------|
| backend | ... | ... | current / stale |
| ui | ... | ... | current / stale |
| strategy | ... | ... | current / stale |
| usecases | ... | ... | current / stale |

### Top 3 Priorities
1. ...
2. ...
3. ...

### Critical Dependencies
- ...

### Identified Risks
- ...

### Recommended Action Plan
- ...
```

## End-of-Session Checklist (enforced in every member skill)

Before ending a session, every member agent must confirm:
1. All file edits are complete
2. Report file exists at `docs/team/<agent>-report.md`
3. Report section includes: Last Updated timestamp, What Was Done, Open Issues, Blockers/Dependencies, Recommendations for the Leader
4. If blocked: blocker is explicitly described; session is terminated without retrying

## Scope Boundaries

| Agent | Can modify code? | Scope |
|-------|-----------------|-------|
| team-backend | Yes | `agents/`, `services/`, `engine/`, `db/`, `api/` (incl. `api/runner.py`) |
| team-ui | Yes | `ui/`, `dashboard/` (NOT `api/runner.py`) |
| team-strategy | Yes (phase 2 only, explicit user approval required) | `engine/`, `strategies/`, `agents/policies.py` |
| team-usecases | No | Evaluations only, entire project read access |
| team-lead | No | Synthesis only, `docs/team/` read access |

**Conflict rule:** When a file is ambiguously in two scopes, ownership follows file type — Python backend files belong to team-backend, HTML/CSS/JS/dashboard files belong to team-ui. The non-owner agent may read and recommend via report only.

## Files to Create

- `.claude/skills/team-backend.md`
- `.claude/skills/team-ui.md`
- `.claude/skills/team-strategy.md`
- `.claude/skills/team-usecases.md`
- `.claude/skills/team-lead.md`
- `docs/team/` directory (created by first agent run)
