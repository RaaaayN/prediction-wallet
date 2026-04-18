# Gemini CLI - Prediction Wallet Context

This project is an **institutional-grade research and autonomous portfolio management platform** designed to demonstrate auditable, deterministic, and compliant LLM-driven financial decisions.

## Project Overview

- **Core Mission:** Bridge the gap between AI innovation and hedge-fund-level rigor through a five-stage governed cycle (`OBSERVE → DECIDE → VALIDATE → EXECUTE → AUDIT`) and a robust MLOps framework.
- **Key Technologies:**
  - **Runtime:** Python 3.13+
  - **AI Framework:** [Pydantic AI](https://ai.pydantic.dev/) (orchestrating Gemini or Anthropic Claude)
  - **MLOps:** **MLflow** (Experiment Tracking, Model Registry), **DVC** (Data Versioning)
  - **Data Layer:** **Apache Parquet** (Bronze/Silver/Gold), PostgreSQL (Metadata), SQLite (Event Sourcing)
  - **NLP:** **FinBERT** for financial sentiment analysis
  - **Analytics:** NumPy + Pandas + Scipy (Risk, Performance, Backtesting v2)
  - **Serving:** FastAPI + BentoML + Vite/React

## Architectural Governance

The system strictly enforces a **multi-layer deterministic policy engine** and a **governed research workflow**:
1.  **Deterministic Guardrails:** Hard/Soft blocks in `agents/policies.py` ensure trade compliance and risk mitigation.
2.  **Scientific Validation:** Mandatory walk-forward or CPCV validation for all strategies.
3.  **Auditable Lineage:** DVC + MLflow ensure every decision can be traced back to the exact code, data version, and model weights used.

## Directory Structure

- `agents/`: Pydantic AI research copilots and deterministic policy engine.
- `engine/`: Financial logic (Realistic Backtesting v2, Risk Engine, Performance, Monte Carlo).
- `trading_core/`: Persistent OMS, Ledger, and Security Master.
- `ml/`: Model training pipelines, FinBERT integration, and experiment logic.
- `data/`: Ingestion pipelines and versioned Parquet storage (Bronze/Silver/Gold).
- `services/`: Gateways for market data, execution, and reporting.
- `db/`: PostgreSQL metadata, SQLite event sourcing, and IAM.
- `api/`: FastAPI endpoints with RBAC.
- `frontend/`: Vite + React + TypeScript UI for real-time visualization and analytics.

## Development Workflows

### Environment Setup
```bash
# Recommendation: Use uv for dependency management
uv venv --python 3.13
source .venv/bin/activate
uv pip install -e .
cp .env.example .env  # Configure AI_PROVIDER, GEMINI_API_KEY, MLFLOW_TRACKING_URI
```

### Key Commands
- **Initialize:** `python main.py init`
- **Run Governed Cycle:** `python main.py run-cycle --mode simulate`
- **MLflow UI:** `mlflow ui`
- **Research Backtest:** `python main.py research-backtest --strategy ensemble --days 90`
- **Governance Report:** `python main.py governance-report`
- **Start Web UI:** `uvicorn api.main:app --reload`
- **Run Tests:** `pytest tests/ -v`

### Coding Standards
- **Strict Typing:** All new code must use Python type hints and pass static analysis.
- **Reproducibility:** Fix random seeds and version all datasets with DVC.
- **Determinism:** Financial calculations and policy enforcement MUST remain deterministic and separate from LLM logic.
- **Testing:** New features must include unit tests and, where applicable, backtest validation tests.

## Contextual Instructions
- **Safety First:** Execution in `live` mode is strictly blocked by default in `agents/policies.py`.
- **Auditable Logic:** Ensure every new stage or metric is logged to `decision_traces` and tracked in MLflow.
- **Data Integrity:** Prefer Parquet for large-scale analytical data; use PostgreSQL/SQLite for transactional metadata.
