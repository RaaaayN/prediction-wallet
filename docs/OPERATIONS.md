# Operations Guide

This guide covers the day-to-day operations for managing the institutional-grade research and portfolio management stack.

---

## 📈 MLflow Experiment Tracking

Every research backtest is logged to MLflow for systematic tracking and comparison.

### Launching the MLflow UI
To view your experiments, metrics, and artifacts, run:
```bash
mlflow ui --backend-store-uri sqlite:///data/mlflow.db
```
Open `http://localhost:5000` in your browser.

### Promoting a Strategy
Successful strategies can be promoted to **Champion** status via the MLflow Model Registry UI. This tags the specific run as the "Production" version, which can then be referenced by automated rebalancing jobs.

---

## 📊 DVC Data Versioning

We use DVC to ensure that every backtest result is linked to an immutable data snapshot.

### Versioning a New Dataset
1.  Add new Parquet files to `data/lake/`.
2.  Track the changes:
    ```bash
    dvc add data/lake/
    ```
3.  Commit the `.dvc` metadata to git:
    ```bash
    git add data/lake.dvc
    git commit -m "Add updated market data snapshot"
    ```

### Reproducing Data
To retrieve the exact data snapshot associated with a specific git commit:
```bash
git checkout <commit_hash>
dvc checkout
```

---

## 🛡️ Governance & Auditing

The system provides built-in tools for compliance monitoring and audit reporting.

### Generating a Governance Report
To aggregate recent risk violations and check strategy lineage, run:
```bash
python main.py governance-report --profile balanced
```

### Research Backtests
To run a research experiment via the CLI (orchestrated by the Research Copilot):
```bash
python main.py research-backtest --strategy ensemble --days 180 --gold-dataset my_gold_ds
```

---

## 🚀 CI/CD Pipeline

The project includes a multi-stage CI pipeline managed via GitHub Actions (`.github/workflows/test.yml`).

### Running Pipeline Locally
Before submitting a PR, ensure all checks pass:
1.  **Linting**: `ruff check .`
2.  **Type Checking**: `mypy . --ignore-missing-imports`
3.  **Security**: `bandit -r . -x ./tests`
4.  **Tests**: `pytest tests/`
