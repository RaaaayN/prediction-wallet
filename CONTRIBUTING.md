# Contributing

## Setup

```bash
git clone https://github.com/your-username/prediction-wallet-1
cd prediction-wallet-1

# Create virtual environment
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate

# Install dependencies
pip install -e ".[dev]"

# Configure environment
cp .env.example .env
# Set AI_PROVIDER=gemini and GEMINI_API_KEY, or AI_PROVIDER=anthropic and ANTHROPIC_API_KEY
```

## Running Tests

```bash
pytest tests/ -v

# Run a specific test file
pytest tests/test_engine.py -v
pytest tests/test_policies.py -v
```

## Project Structure

When adding a feature, place it in the right layer:

| Layer | Location | Purpose |
|-------|----------|---------|
| Pure finance logic | `engine/` | No I/O, no dependencies — pure functions |
| Agent orchestration | `agents/` | Pydantic AI, decision schemas, policy engine |
| Data access | `db/` | SQLite reads/writes only |
| External services | `services/` | yfinance, PDF generation |
| API endpoints | `api/` | FastAPI routes only — no business logic |

## Key Rules

- New engine functions must have corresponding tests in `tests/test_engine.py`
- Any change to the policy engine (`agents/policies.py`) must update `tests/test_policies.py`
- If a change affects the audit trail (what gets written to `decision_traces`), update `docs/GOVERNANCE.md`
- No LLM calls in `engine/` — that layer must remain deterministic and testable

## Adding a Portfolio Profile

Create `profiles/my_profile.yaml` following the structure of `profiles/balanced.yaml`. The profile is auto-discovered by `portfolio_loader.py`.

## Running the UI

```bash
# Start the API server
uvicorn api.main:app --reload

# Open in browser
open http://localhost:8000
```
