"""SQLite schema initialisation for structured persistence."""

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
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    cycle_id     TEXT    NOT NULL,
    timestamp    TEXT    NOT NULL,
    strategy     TEXT,
    signal       INTEGER NOT NULL,
    analysis     TEXT,
    trades_count INTEGER NOT NULL,
    report_path  TEXT,
    kill_switch  INTEGER NOT NULL
);
"""


def init_db(db_path: str) -> None:
    """Create all tables in *db_path* if they do not already exist."""
    import os
    os.makedirs(os.path.dirname(db_path), exist_ok=True)
    with sqlite3.connect(db_path) as conn:
        conn.executescript(DDL)
        conn.commit()
