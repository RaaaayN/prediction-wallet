# Prediction Wallet

[![Python 3.13+](https://img.shields.io/badge/python-3.13%2B-blue)](https://www.python.org/)
[![Tests](https://img.shields.io/badge/tests-passing-brightgreen)](https://github.com/features/actions)
[![License: MIT](https://img.shields.io/badge/license-MIT-lightgrey)](LICENSE)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.135-009688)](https://fastapi.tiangolo.com/)
[![Pydantic AI](https://img.shields.io/badge/Pydantic_AI-1.0-E92063)](https://ai.pydantic.dev/)

An **AI-governed portfolio rebalancing agent** that proves LLM decisions can be auditable, deterministic, and compliant.

Unlike freely-trading agents, every decision follows a strict five-stage governed cycle:

```
OBSERVE → DECIDE → VALIDATE → EXECUTE → AUDIT
(market)   (LLM)  (policy)  (trades)  (trace)
```

No trade executes without passing three deterministic policy layers. Every decision is logged with its full justification, weights, confidence score, and slippage — ready for a compliance audit.

**Why this matters:** Financial institutions don't reject AI — they reject opacity. This project builds the governance layer that makes AI portfolio management auditable.

---

## Key Results

- **Trading Core v1**: formal OMS and Aggregate Ledger as source of truth
- **Middle Office**: automatic reconciliation engine and Transaction Cost Analysis (TCA)
- **9 assets** across equities, bonds, and crypto — 4 configurable portfolio profiles
- **3-layer policy engine** blocks trades via hard rules (kill switch), market context (confidence, stale data), and per-trade constraints (sector concentration, notional caps)
- **Event sourcing + replay**: immutable `cycle_events` log reconstructs each governed cycle
- **Monte Carlo analytics**: forward distribution with Sharpe / max-drawdown confidence intervals
- **Regime-aware policy**: rolling volatility percentile classifies `bull / normal / bear / risk_off`
- **Async market pipeline**: parallel fetch path records per-ticker latency
- **OpenTelemetry-ready tracing**: cycle stage spans are emitted when OTel is available
- **Industrialized Risk**: Asset-class based stress tests and real-time drawdown monitoring
- **Full audit trail**: every cycle stage traced in SQLite (`decision_traces` table)
- **Kill switch**: deterministic drawdown guard halts all execution at ≥ 10%
- **30+ tests** covering policy engine, trading core, reconciliation, and risk

---

## Architecture

```
agents/
  portfolio_agent.py   — Pydantic AI orchestrator (PortfolioAgentService)
  models.py            — Pydantic schemas: CycleObservation, TradeDecision, CycleAudit
  policies.py          — ExecutionPolicyEngine (3-layer deterministic validation)
  deps.py              — AgentDependencies (dependency injection)

engine/
  portfolio.py         — compute_weights, compute_drift, compute_portfolio_value
  orders.py            — generate_rebalance_orders (tolerance bands, min notional)
  risk.py              — compute_drawdown, check_kill_switch, RiskLevel (OK/WARN/HALT)
  performance.py       — VaR (parametric + historical), CVaR, Sortino, Calmar, Sharpe
  backtest.py          — run_strategy_comparison (threshold / calendar / buy-and-hold)
  monte_carlo.py       — forward simulation + confidence intervals
  regime.py            — rolling volatility percentile regime detection

services/
  execution_service.py — ExecutionService (portfolio + orders)
  market_service.py    — MarketService (yfinance → SQLite, async fetch latency)
  reporting_service.py — ReportingService (PDF generation)

db/
  schema.py            — DDL: portfolio_snapshots, executions, agent_runs, decision_traces, cycle_events, idea_book
  events.py            — immutable event log + replay
  repository.py        — SQLite / PostgreSQL read/write (see `DATABASE_URL`)

runtime_context.py     — profile-scoped paths (portfolio, market DB) for multi-profile storage

frontend/              — Vite + React + TypeScript UI (primary)
ui/
  index.html           — legacy single-page UI (still served when Vite build absent)

strategies/
  threshold.py         — drift-based rebalancing (per-asset configurable bands)
  calendar.py          — calendar-based rebalancing (weekly / monthly)

profiles/
  balanced.yaml        — 50% equities, 30% bonds, 20% crypto
  conservative.yaml    — 60% bonds, 40% equities, no crypto
  growth.yaml          — 70% equities, 20% bonds, 10% crypto
  crypto_heavy.yaml    — 40% equities, 20% bonds, 40% crypto
```

---

## Quickstart

```bash
git clone https://github.com/your-username/prediction-wallet-1
cd prediction-wallet-1
python -m venv .venv && source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -e .

# Copy and configure environment
cp .env.example .env  # Set AI_PROVIDER, GEMINI_API_KEY or ANTHROPIC_API_KEY

# Initialize portfolio
python main.py init

# Run a full governed cycle
python main.py run-cycle --mode simulate

# Build the React UI (required for the default SPA at `/`)
cd frontend && npm ci && npm run build && cd ..

# Launch web UI
uvicorn api.main:app --reload
# Open http://localhost:8000
```

### Setup automatisé (recommandé)

Prérequis : [Docker](https://docs.docker.com/get-docker/), [uv](https://docs.astral.sh/uv/), Node.js 20+.

```bash
./scripts/setup.sh          # Postgres (docker compose) + DATABASE_URL + uv + schéma DB + main.py init + build frontend
./scripts/setup.sh --sqlite # Sans Docker : SQLite sous data/ (pas de DATABASE_URL ajouté)
```

Puis lance l’API : `uvicorn api.main:app --reload` et ouvre `http://localhost:8000`.

---

## CLI

```bash
# Individual cycle stages
python main.py observe          # Fetch market snapshot + portfolio state
python main.py decide           # LLM produces structured TradeDecision
python main.py execute          # Policy validates, then simulator executes
python main.py audit            # Write full CycleAudit to decision_traces

# Full cycle (all stages in sequence)
python main.py run-cycle --mode simulate
python main.py run-cycle --mode simulate --strategy calendar

# Portfolio profiles
python main.py run-cycle --profile growth
python main.py run-cycle --profile conservative

# PDF report
python main.py report

# Tests
pytest tests/ -v
```

---

## Web UI

```bash
cd frontend && npm ci && npm run build && cd ..
uvicorn api.main:app --reload
```

Open `http://localhost:8000`. The **Vite app** under `frontend/` is the primary UI (React Router). If `frontend/dist` is missing, the API falls back to `ui/index.html` or `ui-react/dist` when present.

| Area | Routes (examples) |
|------|-------------------|
| Overview / command | `/`, `/control` |
| Book & ideas | `/workspace`, `/book`, `/ideas`, `/blotter` |
| Risk | `/riskhub`, `/risk`, `/stress`, `/regime` |
| Analytics | `/analytics`, `/backtest`, `/correlation`, `/montecarlo` |
| Audit | `/audit`, `/traces`, `/runs`, `/history`, `/perf` |
| Legacy monolith | `ui/index.html` (all tabs in one page) at `/static/` assets |

---

## Configuration

Via `.env` or environment variables:

| Variable | Default | Description |
|----------|---------|-------------|
| `AI_PROVIDER` | `gemini` | `gemini` or `anthropic` |
| `TRADING_CORE_ENABLED` | `false` | Enable formal OMS and Ledger |
| `PORTFOLIO_PROFILE` | `balanced` | Active portfolio profile |
| `EXECUTION_MODE` | `simulate` | `simulate` or `paper` |
| `DATABASE_URL` | _(empty)_ | Set to use PostgreSQL (see `docker-compose.yml` example in `.env.example`) |

Portfolio profiles (`profiles/*.yaml`) define target allocations, drift thresholds, kill switch parameters, per-asset drift bands, and policy rules (confidence floor, sector caps, per-ticker notional limits). Hedge-fund fields live under `hedge_fund` in the profile YAML; the **Idea Book** API supports seeding, LLM candidate generation, review, and promotion (`/api/idea-book/*`).

---

## Governance Principles

- Only a structured `TradeDecision` (Pydantic-validated) can trigger execution
- **Hard violations** (kill switch active, live mode blocked, too many trades): entire cycle aborted
- **Market context soft blocks** (low confidence, stale data): all trades in cycle blocked, cycle marked valid
- **Per-trade soft blocks** (unknown ticker, missing price, notional cap, sector concentration): individual trade blocked, others proceed
- Every stage — observe / decide / validate / execute / audit — is written to `decision_traces`
- Every cycle is appended to immutable `cycle_events` and can be replayed from `/api/events/replay/{cycle_id}`
- Kill switch (drawdown ≥ 10%) is deterministic and blocks all execution regardless of LLM output

---

## Documentation

- [API Reference](docs/api.md) — Endpoints and JSON schemas
- [Governance Model](docs/GOVERNANCE.md) — Policy engine walkthrough
- [Risk Model](docs/RISK_MODEL.md) — VaR, stress tests, kill switch logic
- [Roadmap and implementation status](deep-research-report%20%281%29.md) — Target architecture plus current progress on Fondation, Trading Core, and next phases
- [Team reports](docs/team/lead-report.md) — Living implementation notes and status rollups across backend, strategy, and UI
- [Documentation Index](docs/INDEX.md) — Full doc map

---

## Stack

| Layer | Technology |
|-------|-----------|
| AI Agent | Pydantic AI + Google Gemini / Anthropic Claude |
| API | FastAPI + Uvicorn |
| Data | yfinance → SQLite (per profile) or PostgreSQL when `DATABASE_URL` is set |
| Risk Engine | NumPy + Pandas (pure Python) |
| Reporting | ReportLab (PDF) |
| Config | Pydantic Settings + YAML profiles |
| Tests | pytest |
