# API Reference

Base URL: `http://localhost:8000`

All endpoints return JSON. The API is served by FastAPI — interactive docs available at `/docs` (Swagger UI) and `/redoc`.

---

## Agent Cycle

### `POST /api/run/{step}`

Stream a full or partial cycle via Server-Sent Events (SSE).

**Path parameters:** `step` ∈ `observe | decide | execute | audit | run-cycle | report | init`

**JSON body:**

```json
{
  "strategy": "threshold",
  "mode": "simulate",
  "profile": "balanced"
}
```

**Response:** SSE stream with stdout lines and a final `{"exit": 0}` event.

---

## Portfolio

### `GET /api/portfolio`

Returns the current portfolio state from `data/portfolio.json`.

**Response:**

```json
{
  "cash": 12500.00,
  "positions": {
    "AAPL": 45.2,
    "BTC-USD": 0.85
  },
  "history": [
    {"timestamp": "2024-01-15T14:00:00", "total_value": 103400.00}
  ],
  "total_value": 103400.00,
  "pnl_dollars": 3400.00,
  "pnl_pct": 0.034
}
```

### `GET /api/snapshots`

Returns portfolio value snapshots from the database.

**Query parameters:** `limit` (int, default 60, max 500)

**Response:** Array of snapshot records with `timestamp`, `total_value`, `cash`, `positions_json`.

---

## Executions & Traces

### `GET /api/executions`

Returns trade execution records.

**Query parameters:** `limit` (int, default 50, max 500)

**Response:**

```json
[
  {
    "cycle_id": "2024-01-15T14:32:00",
    "ticker": "AAPL",
    "action": "buy",
    "quantity": 10.0,
    "price": 143.20,
    "notional": 1432.00,
    "slippage_pct": 0.0008,
    "status": "executed"
  }
]
```

### `GET /api/traces`

Returns decision trace records (full policy evaluation per cycle).

**Query parameters:** `limit` (int, default 50)

### `GET /api/events`

Returns recent immutable cycle events, or all events for one `cycle_id`.

### `GET /api/events/replay/{cycle_id}`

Replays `cycle_started → ... → audit_complete` into a reconstructed cycle summary.

### `GET /api/runs`

Returns agent run summaries.

**Query parameters:** `limit` (int, default 20, max 200)

---

## Analytics

### `GET /api/performance`

Returns computed performance metrics from portfolio history.

**Response:**

```json
{
  "sharpe_ratio": 1.24,
  "sortino_ratio": 1.87,
  "calmar_ratio": 0.95,
  "max_drawdown": -0.083,
  "var_95_parametric": -0.021,
  "var_95_historical": -0.019,
  "cvar_95": -0.031,
  "total_return": 0.034,
  "annualized_return": 0.142
}
```

### `GET /api/correlation`

Returns the asset correlation matrix computed from historical returns.

**Response:**

```json
{
  "assets": ["AAPL", "MSFT", "BTC-USD", "..."],
  "matrix": [[1.0, 0.82, 0.41], [0.82, 1.0, 0.38], [0.41, 0.38, 1.0]]
}
```

### `GET /api/stress`

Runs all crisis stress scenarios against the current portfolio.

**Response:**

```json
[
  {
    "scenario": "COVID-19 Crash",
    "pnl_dollars": -28400.00,
    "pnl_pct": -0.284,
    "kill_switch_triggered": true
  },
  {
    "scenario": "Rate Shock 2022",
    "pnl_dollars": -9200.00,
    "pnl_pct": -0.092,
    "kill_switch_triggered": false
  }
]
```

### `GET /api/backtest`

Runs strategy comparison backtest.

**Query parameters:**

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `days` | int | 252 | Lookback period in trading days |
| `profile` | string | `balanced` | Portfolio profile |

**Response:**

```json
{
  "threshold": {"total_return": 0.087, "sharpe": 1.12, "max_drawdown": -0.061, "trades": 14},
  "calendar": {"total_return": 0.079, "sharpe": 1.04, "max_drawdown": -0.058, "trades": 12},
  "buy_and_hold": {"total_return": 0.103, "sharpe": 0.98, "max_drawdown": -0.082, "trades": 0}
}
```

### `GET /api/monte-carlo`

Runs a forward Monte Carlo portfolio simulation.

**Query parameters:** `paths` (int, default 5000, max 20000)

**Response fields:** `percentiles`, `prob_loss`, `prob_drawdown_10pct`, `expected_sharpe`, `expected_max_dd`, `confidence_intervals`, `path_sample`

### `GET /api/regime`

Returns the rolling market regime classification.

**Query parameters:** `days` (int, default 180)

---

## Key Pydantic Schemas

### `TradeDecision`

The structured output produced by the LLM agent, validated by Pydantic before policy evaluation:

```python
class TradeDecision(BaseModel):
    reasoning: str              # LLM justification for the decision
    approved_trades: list[TradeProposal]
    confidence: float           # 0.0–1.0 decision confidence score
    data_freshness: str         # "fresh" | "stale"
    rebalance_needed: bool
```

### `TradeProposal`

```python
class TradeProposal(BaseModel):
    action: Literal["buy", "sell", "hold"]
    ticker: str
    quantity: float
    rationale: str
```

### `PolicyEvaluation`

The output of `ExecutionPolicyEngine.evaluate()`:

```python
class PolicyEvaluation(BaseModel):
    approved: bool              # False = hard violation, cycle aborted
    allowed_trades: list[TradeProposal]
    blocked_trades: list[RejectedTrade]
    violations: list[PolicyViolation]   # Only populated on hard violations
```

### `RejectedTrade`

```python
class RejectedTrade(TradeProposal):
    rejection_reason: str       # Human-readable policy rejection message
```
