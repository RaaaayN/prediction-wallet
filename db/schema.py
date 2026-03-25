"""SQLite schema initialisation for structured persistence."""

import os
import sqlite3


DDL = """
CREATE TABLE IF NOT EXISTS portfolio_snapshots (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp   TEXT    NOT NULL,
    cycle_id    TEXT    NOT NULL,
    total_value REAL    NOT NULL,
    cash        REAL    NOT NULL,
    peak_value  REAL    NOT NULL,
    drawdown    REAL    NOT NULL
);

CREATE TABLE IF NOT EXISTS positions (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    snapshot_id   INTEGER NOT NULL REFERENCES portfolio_snapshots(id),
    ticker        TEXT    NOT NULL,
    quantity      REAL    NOT NULL,
    price         REAL    NOT NULL,
    value         REAL    NOT NULL,
    weight        REAL    NOT NULL,
    target_weight REAL    NOT NULL,
    drift         REAL    NOT NULL
);

CREATE TABLE IF NOT EXISTS executions (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    cycle_id     TEXT    NOT NULL,
    trade_id     TEXT    NOT NULL,
    timestamp    TEXT    NOT NULL,
    ticker       TEXT    NOT NULL,
    action       TEXT    NOT NULL,
    quantity     REAL    NOT NULL,
    market_price REAL    NOT NULL,
    fill_price   REAL    NOT NULL,
    cost         REAL    NOT NULL,
    slippage     REAL    NOT NULL,
    reason       TEXT,
    success      INTEGER NOT NULL,
    error        TEXT
);

CREATE TABLE IF NOT EXISTS agent_runs (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    cycle_id        TEXT    NOT NULL,
    timestamp       TEXT    NOT NULL,
    strategy        TEXT,
    signal          INTEGER NOT NULL,
    analysis        TEXT,
    trades_count    INTEGER NOT NULL,
    report_path     TEXT,
    kill_switch     INTEGER NOT NULL,
    provider        TEXT,
    tool_calls      INTEGER DEFAULT 0,
    fetch_latency_ms REAL DEFAULT 0,
    errors_json     TEXT
);

CREATE TABLE IF NOT EXISTS market_data_status (
    ticker       TEXT PRIMARY KEY,
    refreshed_at TEXT NOT NULL,
    success      INTEGER NOT NULL,
    error        TEXT
);

CREATE TABLE IF NOT EXISTS decision_traces (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    cycle_id        TEXT NOT NULL,
    stage           TEXT NOT NULL,
    payload_json    TEXT NOT NULL,
    validation_json TEXT,
    mcp_tools_json  TEXT,
    provider        TEXT,
    agent_backend   TEXT,
    execution_mode  TEXT,
    created_at      TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_portfolio_snapshots_cycle_id ON portfolio_snapshots(cycle_id);
CREATE INDEX IF NOT EXISTS idx_portfolio_snapshots_timestamp ON portfolio_snapshots(timestamp);
CREATE INDEX IF NOT EXISTS idx_positions_snapshot_id ON positions(snapshot_id);
CREATE INDEX IF NOT EXISTS idx_positions_ticker ON positions(ticker);
CREATE INDEX IF NOT EXISTS idx_executions_cycle_id ON executions(cycle_id);
CREATE INDEX IF NOT EXISTS idx_executions_timestamp ON executions(timestamp);
CREATE INDEX IF NOT EXISTS idx_executions_ticker ON executions(ticker);
CREATE INDEX IF NOT EXISTS idx_agent_runs_cycle_id ON agent_runs(cycle_id);
CREATE INDEX IF NOT EXISTS idx_agent_runs_timestamp ON agent_runs(timestamp);
CREATE INDEX IF NOT EXISTS idx_decision_traces_cycle_id ON decision_traces(cycle_id);
CREATE INDEX IF NOT EXISTS idx_decision_traces_stage ON decision_traces(stage);
CREATE INDEX IF NOT EXISTS idx_decision_traces_created_at ON decision_traces(created_at);
"""


_AGENT_RUNS_MIGRATIONS = [
    "ALTER TABLE agent_runs ADD COLUMN provider TEXT",
    "ALTER TABLE agent_runs ADD COLUMN tool_calls INTEGER DEFAULT 0",
    "ALTER TABLE agent_runs ADD COLUMN fetch_latency_ms REAL DEFAULT 0",
    "ALTER TABLE agent_runs ADD COLUMN errors_json TEXT",
]

_EXECUTIONS_MIGRATIONS = [
    "ALTER TABLE executions ADD COLUMN weight_before REAL DEFAULT 0.0",
    "ALTER TABLE executions ADD COLUMN target_weight REAL DEFAULT 0.0",
    "ALTER TABLE executions ADD COLUMN drift_before REAL DEFAULT 0.0",
    "ALTER TABLE executions ADD COLUMN slippage_pct REAL DEFAULT 0.0",
    "ALTER TABLE executions ADD COLUMN notional REAL DEFAULT 0.0",
]

_DECISION_TRACES_MIGRATIONS = [
    "ALTER TABLE decision_traces ADD COLUMN event_type TEXT",
    "ALTER TABLE decision_traces ADD COLUMN tags TEXT",
]


def init_db(db_path: str) -> None:
    os.makedirs(os.path.dirname(db_path), exist_ok=True)
    with sqlite3.connect(db_path) as conn:
        conn.executescript(DDL)
        for stmt in _AGENT_RUNS_MIGRATIONS + _EXECUTIONS_MIGRATIONS + _DECISION_TRACES_MIGRATIONS:
            try:
                conn.execute(stmt)
            except sqlite3.OperationalError:
                pass  # column already exists
        conn.commit()
