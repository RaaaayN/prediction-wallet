# Gemini CLI - Prediction Wallet Context

This project is an **AI-governed portfolio rebalancing agent** designed to demonstrate auditable, deterministic, and compliant LLM-driven financial decisions.

## Project Overview

- **Core Mission:** Prove that AI-driven portfolio management can be transparent and safe through a five-stage governed cycle: `OBSERVE → DECIDE → VALIDATE → EXECUTE → AUDIT`.
- **Key Technologies:**
  - **Runtime:** Python 3.13+
  - **AI Framework:** [Pydantic AI](https://ai.pydantic.dev/) (orchestrating Gemini or Anthropic Claude)
  - **Backend:** FastAPI + Uvicorn
  - **Data:** SQLite (event sourcing + state) + yfinance
  - **Analytics:** NumPy + Pandas (Risk/Performance metrics)
  - **Reporting:** ReportLab (PDF)

## Architectural Governance

The system strictly enforces a **3-layer deterministic policy engine** (`agents/policies.py`) that acts as a guardrail for the LLM:
1.  **Hard Violations:** Kill switch (drawdown ≥ 10%), blocked execution modes, or excessive trade counts abort the entire cycle.
2.  **Market Context Soft Blocks:** Low LLM confidence or stale market data blocks all trades but keeps the cycle valid.
3.  **Per-Trade Soft Blocks:** Ticker-specific rules (sector concentration, notional caps, short-squeeze flags) block individual trades while allowing others.

## Directory Structure

- `agents/`: Pydantic AI orchestrator, deterministic policy engine, and Pydantic models.
- `engine/`: Financial logic (risk, performance, Monte Carlo, regime detection, portfolio math).
- `services/`: Gateways for market data, simulated execution, and reporting.
- `db/`: SQLite repository, schema, and immutable event sourcing logic.
- `strategies/`: Rebalancing strategies (threshold-based and calendar-based).
- `profiles/`: YAML configurations for portfolio allocations and policy parameters.
- `ui/`: Single-page HTML/JS interface for real-time visualization.

## Development Workflows

### Environment Setup
```bash
# Recommendation: Use uv for dependency management
uv venv --python 3.13
source .venv/bin/activate
uv pip install -e .
cp .env.example .env  # Configure AI_PROVIDER and GEMINI_API_KEY
```

### Key Commands
- **Initialize:** `python main.py init`
- **Run Governed Cycle:** `python main.py run-cycle --mode simulate`
- **Start Web UI:** `uvicorn api.main:app --reload`
- **Generate Report:** `python main.py report`
- **Run Tests:** `pytest tests/ -v`

### Coding Standards
- **Strict Typing:** All new code must use Python type hints and pass static analysis.
- **Pydantic Models:** Use models in `agents/models.py` for all structured data passing between stages.
- **Determinism:** Financial calculations and policy enforcement MUST remain deterministic and separate from LLM logic.
- **Testing:** New features or bug fixes must include corresponding tests in `tests/`.

## Contextual Instructions
- **Safety First:** Never allow trade execution in `live` mode; it is blocked by default in `agents/policies.py`.
- **Auditable Logic:** Ensure every new stage or metric is logged to the `decision_traces` table via the `AuditRepositoryAdapter`.
- **Performance:** Async market data fetching is preferred (`market/fetcher.py`).
