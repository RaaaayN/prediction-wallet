# Institutional Governance & Control

Prediction Wallet enforces a multi-layered governance framework that bridges the gap between AI-driven research and institutional-grade execution. Our philosophy is: **"AI for research operations, not unchecked trading autonomy."**

## Governance Pillars

The platform rests on four pillars of governance to ensure every decision is auditable, reproducible, and compliant:

1.  **Deterministic Guardrails**: A three-layer policy engine that validates every LLM decision before any trade executes.
2.  **Scientific Validation**: Mandatory walk-forward and Combinatorial Purged Cross-Validation (CPCV) to prevent backtest overfitting.
3.  **MLOps Lineage**: Full tracking of data, code, and model versions via **DVC** and **MLflow**.
4.  **Operational Audit**: Immutable event sourcing and persistent decision traces.

---

## 🛡️ The Five-Stage Governed Cycle

Every rebalancing cycle passes through these stages in order:

```
┌─────────┐    ┌─────────┐    ┌──────────┐    ┌─────────┐    ┌───────┐
│ OBSERVE │───▶│ DECIDE  │───▶│ VALIDATE │───▶│ EXECUTE │───▶│ AUDIT │
│         │    │  (LLM)  │    │ (policy) │    │  (sim)  │    │  (DB) │
└─────────┘    └─────────┘    └──────────┘    └─────────┘    └───────┘
  Market +        Research       3-layer          Realistic     Full
 portfolio        Copilot        engine           Slippage      Lineage
 snapshot       (Strategy)      runs here         + Fees        stored
```

The `VALIDATE` stage is the core governance layer. It runs entirely in Python with no LLM involvement — deterministic, testable, reproducible.

---

## 🧱 The Three-Layer Policy Engine

### Layer 0 — Hard Violations (Cycle Abort)
Checks for catastrophic failures or unauthorized states. Any failure aborts the entire cycle.

- **Kill Switch**: Triggered if portfolio drawdown ≥ 10% from peak.
- **Execution Mode**: Blocks execution if `EXECUTION_MODE` is set to `live` (unauthorized).
- **Trade Volume**: Limits the total number of trades per cycle to prevent high-frequency "hallucinations."

### Layer 1 — Market Context Soft Blocks (All Trades Blocked)
Evaluates the validity of the decision environment. If triggered, the cycle is valid but all trades are rejected.

- **Confidence Floor**: `decision.confidence < min_confidence` (e.g., 0.70).
- **Data Freshness**: Blocks all trades if market data is stale.
- **Regime Check**: Blocks trades if the market regime is classified as `risk_off` (e.g., extreme volatility).

### Layer 2 — Per-Trade Soft Blocks (Individual Trade Rejected)
Validates individual trade proposals against the portfolio mandate.

- **Universe Check**: Ticker must be in the `TARGET_ALLOCATION` universe.
- **Notional Cap**: Prevents any single trade from exceeding a percentage of total portfolio value.
- **Sector Concentration**: Prevents buys that would push a sector above a defined limit (default 55%).
- **Slippage Tolerance**: Rejects trades where the estimated slippage exceeds a threshold.

---

## 🧪 Scientific Validation & Anti-Overfitting

To ensure strategies are robust and not just "lucky," the platform enforces institutional validation protocols:

- **Realistic Backtesting**: Every backtest includes slippage models, transaction fees (TCA), and realistic fill logic.
- **Walk-Forward Validation**: Strategies are tested on rolling windows of data they haven't seen during training.
- **Combinatorial Purged CV (CPCV)**: A robust cross-validation method that accounts for temporal dependencies and prevents data leakage, significantly reducing the "Probability of Backtest Overfitting."

---

## 📑 MLOps Governance (Lineage & Reproducibility)

Institutional grade requires that every result be reproducible. We achieve this through:

- **Data Versioning (DVC)**: Every dataset (Bronze/Silver/Gold) is versioned and hashed. We know exactly which data snapshot was used for every experiment.
- **Experiment Tracking (MLflow)**: Every research run logs its code version, hyper-parameters, data version, and performance metrics.
- **Model Registry**: Only models that have passed the "Scientific Validation" jalon can be promoted to the registry for paper trading or simulation.

---

## 🔍 Audit & Compliance

Every cycle writes a complete record to the `decision_traces` table and is tracked in **MLflow**:

```json
{
  "cycle_id": "2024-01-15T14:32:00",
  "stage": "validate",
  "approved": true,
  "mlflow_run_id": "8b2a3c...",
  "dvc_data_hash": "e9f1a2...",
  "allowed_trades": [{"action": "buy", "ticker": "AAPL", "quantity": 10}],
  "blocked_trades": [
    {
      "action": "buy",
      "ticker": "BTC-USD",
      "quantity": 2.5,
      "rejection_reason": "Trade exceeds notional cap (20%)."
    }
  ],
  "violations": []
}
```

This lineage ensures that years later, we can explain exactly why a trade was executed, which model proposed it, and what data justified that decision.
