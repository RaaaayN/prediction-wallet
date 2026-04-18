# Institutional Trading Core & Execution

The Trading Core is a deterministic, event-driven Order Management System (OMS) and Portfolio Management System (PMS) designed for institutional-grade reliability and auditability.

---

## 🏗️ Architecture: Event-Driven Execution

The core is built as a series of persistent services that ensure every state transition is logged and every trade is explainable.

1.  **TradingCoreService**: The central orchestrator managing the lifecycle of trades.
2.  **Security Master**: Canonical repository of tradable instruments, integrated with the **Parquet Gold** layer for historical corporate actions.
3.  **Market Data Handler**: High-performance adapter providing snapshots with microsecond-level freshness tracking.
4.  **Order Management System (OMS)**: Handles the full state machine for orders (Pending, Open, Filled, Cancelled, Rejected).
5.  **Execution Simulation (Broker Adapters)**:
    - **Market Orders**: Immediate fill with volume-adjusted slippage.
    - **Limit Orders**: Fill only when price crosses the limit, accounting for queue priority.
    - **TWAP/VWAP Simulation**: Algorithmic execution simulation for large notional orders to minimize market impact.

---

## 📈 Realistic Backtesting v2

Our backtesting engine moves beyond simple daily rebalancing to event-driven market simulation.

- **Look-Ahead Bias Protection**: Strict temporal alignment ensures strategies only see data available *at the moment of decision*.
- **Realistic Fill Logic**: Uses bid/ask spreads and depth-of-book approximations from historical Parquet data.
- **Transaction Cost Analysis (TCA)**: Every backtest calculates arrival price, implementation shortfall, and execution slippage.
- **Survivorship Bias Mitigation**: The Security Master tracks inactive and delisted tickers.

---

## 🔄 The Institutional Trade Lifecycle

Every decision follows a governed path from research to reconciliation:

1.  **Strategy Generation**: The **Research Copilot** (LLM) or a Quantitative Model proposes a trade based on the current regime and signals.
2.  **Compliance Check**: The **Policy Engine** runs Layer 0-2 checks (Drawdown, Concentration, Universe).
3.  **Order Initialization**: The OMS creates a `Pending` order and assigns a unique `order_id`.
4.  **Execution Simulation**: The Broker Adapter applies the **Slippage & Fee Model** (Fixed fee + bps + Impact).
5.  **Ledger Application**: Successful fills atomically update the **Position Ledger** and **Cash Movements**.
6.  **Reconciliation**: The Middle Office service reconciles the simulator state with the persistent database ledger every cycle.

---

## 📊 Transaction Cost Analysis (TCA)

We measure execution quality through multiple benchmarks:

| Benchmark | Definition | Interpretation |
|-----------|------------|----------------|
| **Arrival Price** | Mid-price at the moment of order creation | The target price for the strategy. |
| **Implementation Shortfall** | `(Arrival Price - Executed Price) / Arrival Price` | Total cost of execution including delay and impact. |
| **VWAP Benchmark** | Executed price vs. Volume Weighted Average Price | Measure of execution relative to market volume. |
| **Slippage (bps)** | `|Executed - Market| / Market × 10,000` | Precision of the fill relative to the spot price. |

---

## 🛠️ Data Lineage & Persistence

- **Transaction Ledger**: Every trade is stored in `trade_executions_v2` with a link to the **MLflow Run ID**.
- **Audit Logs**: Every state transition in the OMS triggers an entry in `order_events`.
- **Snapshot Storage**: Portfolio states are snapshotted to **Parquet** every cycle for high-speed analytical replay.
