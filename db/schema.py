"""Schema initialisation: SQLite (default) or PostgreSQL when ``DATABASE_URL`` is set."""

from __future__ import annotations

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
    drift         REAL    NOT NULL,
    side          TEXT    DEFAULT 'long',
    idea_id       TEXT,
    gross_exposure REAL   DEFAULT 0.0,
    net_exposure   REAL   DEFAULT 0.0
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
    error        TEXT,
    side         TEXT    DEFAULT 'long',
    idea_id      TEXT,
    sleeve       TEXT    DEFAULT 'core_longs',
    exposure_before REAL DEFAULT 0.0,
    exposure_after  REAL DEFAULT 0.0,
    gross_impact REAL DEFAULT 0.0,
    net_impact   REAL    DEFAULT 0.0
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

CREATE TABLE IF NOT EXISTS cycle_events (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    cycle_id     TEXT    NOT NULL,
    event_type   TEXT    NOT NULL,
    payload_json TEXT    NOT NULL,
    created_at   TEXT    NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_cycle_events_cycle_id ON cycle_events(cycle_id);
CREATE INDEX IF NOT EXISTS idx_cycle_events_created_at ON cycle_events(created_at);

CREATE TABLE IF NOT EXISTS idea_book (
    idea_id            TEXT PRIMARY KEY,
    ticker             TEXT NOT NULL,
    side               TEXT NOT NULL,
    thesis             TEXT NOT NULL,
    catalyst           TEXT NOT NULL,
    time_horizon       TEXT NOT NULL,
    conviction         REAL NOT NULL,
    upside_case        TEXT,
    downside_case      TEXT,
    invalidation_rule  TEXT NOT NULL,
    status             TEXT NOT NULL,
    sleeve             TEXT DEFAULT 'core_longs',
    edge_source        TEXT DEFAULT '',
    why_now            TEXT DEFAULT '',
    key_risk           TEXT DEFAULT '',
    supporting_signals TEXT DEFAULT '[]',
    evidence_quality   TEXT DEFAULT 'medium',
    review_status      TEXT DEFAULT 'approved',
    origin_cycle_id    TEXT,
    llm_generated      INTEGER DEFAULT 0,
    source             TEXT DEFAULT 'profile_seed',
    crowded_score      REAL DEFAULT 0.0,
    short_squeeze_risk INTEGER DEFAULT 0,
    created_at         TEXT NOT NULL,
    updated_at         TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_idea_book_status ON idea_book(status);
CREATE INDEX IF NOT EXISTS idx_idea_book_ticker ON idea_book(ticker);
"""


POSTGRES_STATEMENTS: list[str] = [
    """
    CREATE TABLE IF NOT EXISTS portfolio_snapshots (
        id          SERIAL PRIMARY KEY,
        timestamp   TEXT    NOT NULL,
        cycle_id    TEXT    NOT NULL,
        total_value DOUBLE PRECISION NOT NULL,
        cash        DOUBLE PRECISION NOT NULL,
        peak_value  DOUBLE PRECISION NOT NULL,
        drawdown    DOUBLE PRECISION NOT NULL
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS positions (
        id            SERIAL PRIMARY KEY,
        snapshot_id   INTEGER NOT NULL REFERENCES portfolio_snapshots(id),
        ticker        TEXT NOT NULL,
        quantity      DOUBLE PRECISION NOT NULL,
        price         DOUBLE PRECISION NOT NULL,
        value         DOUBLE PRECISION NOT NULL,
        weight        DOUBLE PRECISION NOT NULL,
        target_weight DOUBLE PRECISION NOT NULL,
        drift         DOUBLE PRECISION NOT NULL,
        side          TEXT DEFAULT 'long',
        idea_id       TEXT,
        gross_exposure DOUBLE PRECISION DEFAULT 0.0,
        net_exposure   DOUBLE PRECISION DEFAULT 0.0
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS executions (
        id           SERIAL PRIMARY KEY,
        cycle_id     TEXT NOT NULL,
        trade_id     TEXT NOT NULL,
        timestamp    TEXT NOT NULL,
        ticker       TEXT NOT NULL,
        action       TEXT NOT NULL,
        quantity     DOUBLE PRECISION NOT NULL,
        market_price DOUBLE PRECISION NOT NULL,
        fill_price   DOUBLE PRECISION NOT NULL,
        cost         DOUBLE PRECISION NOT NULL,
        slippage     DOUBLE PRECISION NOT NULL,
        reason       TEXT,
        success      INTEGER NOT NULL,
        error        TEXT,
        weight_before DOUBLE PRECISION DEFAULT 0.0,
        target_weight DOUBLE PRECISION DEFAULT 0.0,
        drift_before DOUBLE PRECISION DEFAULT 0.0,
        slippage_pct DOUBLE PRECISION DEFAULT 0.0,
        notional     DOUBLE PRECISION DEFAULT 0.0,
        side         TEXT DEFAULT 'long',
        idea_id      TEXT,
        sleeve       TEXT DEFAULT 'core_longs',
        exposure_before DOUBLE PRECISION DEFAULT 0.0,
        exposure_after  DOUBLE PRECISION DEFAULT 0.0,
        gross_impact DOUBLE PRECISION DEFAULT 0.0,
        net_impact   DOUBLE PRECISION DEFAULT 0.0
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS agent_runs (
        id              SERIAL PRIMARY KEY,
        cycle_id        TEXT NOT NULL,
        timestamp       TEXT NOT NULL,
        strategy        TEXT,
        signal          INTEGER NOT NULL,
        analysis        TEXT,
        trades_count    INTEGER NOT NULL,
        report_path     TEXT,
        kill_switch     INTEGER NOT NULL,
        provider        TEXT,
        tool_calls      INTEGER DEFAULT 0,
        fetch_latency_ms DOUBLE PRECISION DEFAULT 0,
        errors_json     TEXT
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS market_data_status (
        ticker       TEXT PRIMARY KEY,
        refreshed_at TEXT NOT NULL,
        success      INTEGER NOT NULL,
        error        TEXT
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS decision_traces (
        id              SERIAL PRIMARY KEY,
        cycle_id        TEXT NOT NULL,
        stage           TEXT NOT NULL,
        payload_json    TEXT NOT NULL,
        validation_json TEXT,
        mcp_tools_json  TEXT,
        provider        TEXT,
        agent_backend   TEXT,
        execution_mode  TEXT,
        created_at      TEXT NOT NULL,
        event_type      TEXT,
        tags            TEXT
    )
    """,
    "CREATE INDEX IF NOT EXISTS idx_portfolio_snapshots_cycle_id ON portfolio_snapshots(cycle_id)",
    "CREATE INDEX IF NOT EXISTS idx_portfolio_snapshots_timestamp ON portfolio_snapshots(timestamp)",
    "CREATE INDEX IF NOT EXISTS idx_positions_snapshot_id ON positions(snapshot_id)",
    "CREATE INDEX IF NOT EXISTS idx_positions_ticker ON positions(ticker)",
    "CREATE INDEX IF NOT EXISTS idx_executions_cycle_id ON executions(cycle_id)",
    "CREATE INDEX IF NOT EXISTS idx_executions_timestamp ON executions(timestamp)",
    "CREATE INDEX IF NOT EXISTS idx_executions_ticker ON executions(ticker)",
    "CREATE INDEX IF NOT EXISTS idx_agent_runs_cycle_id ON agent_runs(cycle_id)",
    "CREATE INDEX IF NOT EXISTS idx_agent_runs_timestamp ON agent_runs(timestamp)",
    "CREATE INDEX IF NOT EXISTS idx_decision_traces_cycle_id ON decision_traces(cycle_id)",
    "CREATE INDEX IF NOT EXISTS idx_decision_traces_stage ON decision_traces(stage)",
    "CREATE INDEX IF NOT EXISTS idx_decision_traces_created_at ON decision_traces(created_at)",
    """
    CREATE TABLE IF NOT EXISTS cycle_events (
        id           SERIAL PRIMARY KEY,
        cycle_id     TEXT NOT NULL,
        event_type   TEXT NOT NULL,
        payload_json TEXT NOT NULL,
        created_at   TEXT NOT NULL
    )
    """,
    "CREATE INDEX IF NOT EXISTS idx_cycle_events_cycle_id ON cycle_events(cycle_id)",
    "CREATE INDEX IF NOT EXISTS idx_cycle_events_created_at ON cycle_events(created_at)",
    """
    CREATE TABLE IF NOT EXISTS idea_book (
        idea_id            TEXT PRIMARY KEY,
        ticker             TEXT NOT NULL,
        side               TEXT NOT NULL,
        thesis             TEXT NOT NULL,
        catalyst           TEXT NOT NULL,
        time_horizon       TEXT NOT NULL,
        conviction         DOUBLE PRECISION NOT NULL,
        upside_case        TEXT,
        downside_case      TEXT,
        invalidation_rule  TEXT NOT NULL,
        status             TEXT NOT NULL,
        sleeve             TEXT DEFAULT 'core_longs',
        source             TEXT DEFAULT 'profile_seed',
        crowded_score      DOUBLE PRECISION DEFAULT 0.0,
        short_squeeze_risk INTEGER DEFAULT 0,
        created_at         TEXT NOT NULL,
        updated_at         TEXT NOT NULL
    )
    """,
    "CREATE INDEX IF NOT EXISTS idx_idea_book_status ON idea_book(status)",
    "CREATE INDEX IF NOT EXISTS idx_idea_book_ticker ON idea_book(ticker)",
]


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
    "ALTER TABLE executions ADD COLUMN side TEXT DEFAULT 'long'",
    "ALTER TABLE executions ADD COLUMN idea_id TEXT",
    "ALTER TABLE executions ADD COLUMN sleeve TEXT DEFAULT 'core_longs'",
    "ALTER TABLE executions ADD COLUMN exposure_before REAL DEFAULT 0.0",
    "ALTER TABLE executions ADD COLUMN exposure_after REAL DEFAULT 0.0",
    "ALTER TABLE executions ADD COLUMN gross_impact REAL DEFAULT 0.0",
    "ALTER TABLE executions ADD COLUMN net_impact REAL DEFAULT 0.0",
]

_DECISION_TRACES_MIGRATIONS = [
    "ALTER TABLE decision_traces ADD COLUMN event_type TEXT",
    "ALTER TABLE decision_traces ADD COLUMN tags TEXT",
]

_POSITIONS_MIGRATIONS = [
    "ALTER TABLE positions ADD COLUMN side TEXT DEFAULT 'long'",
    "ALTER TABLE positions ADD COLUMN idea_id TEXT",
    "ALTER TABLE positions ADD COLUMN gross_exposure REAL DEFAULT 0.0",
    "ALTER TABLE positions ADD COLUMN net_exposure REAL DEFAULT 0.0",
]

_IDEA_BOOK_MIGRATIONS = [
    "ALTER TABLE idea_book ADD COLUMN edge_source TEXT DEFAULT ''",
    "ALTER TABLE idea_book ADD COLUMN why_now TEXT DEFAULT ''",
    "ALTER TABLE idea_book ADD COLUMN key_risk TEXT DEFAULT ''",
    "ALTER TABLE idea_book ADD COLUMN supporting_signals TEXT DEFAULT '[]'",
    "ALTER TABLE idea_book ADD COLUMN evidence_quality TEXT DEFAULT 'medium'",
    "ALTER TABLE idea_book ADD COLUMN review_status TEXT DEFAULT 'approved'",
    "ALTER TABLE idea_book ADD COLUMN origin_cycle_id TEXT",
    "ALTER TABLE idea_book ADD COLUMN llm_generated INTEGER DEFAULT 0",
]


def _init_postgres() -> None:
    from config import DATABASE_URL

    import psycopg

    url = DATABASE_URL or ""
    with psycopg.connect(url) as conn:
        for stmt in POSTGRES_STATEMENTS:
            conn.execute(stmt.strip())
        conn.commit()


def init_db(db_path: str | None = None) -> None:
    """Create tables. Uses PostgreSQL when ``DATABASE_URL`` is set, else SQLite at ``db_path``."""
    from config import MARKET_DB, USE_POSTGRES

    if USE_POSTGRES:
        _init_postgres()
        return
    path = db_path or MARKET_DB
    parent = os.path.dirname(path)
    if parent:
        os.makedirs(parent, exist_ok=True)
    with sqlite3.connect(path) as conn:
        conn.executescript(DDL)
        for stmt in _AGENT_RUNS_MIGRATIONS + _EXECUTIONS_MIGRATIONS + _DECISION_TRACES_MIGRATIONS + _POSITIONS_MIGRATIONS + _IDEA_BOOK_MIGRATIONS:
            try:
                conn.execute(stmt)
            except sqlite3.OperationalError:
                pass  # column already exists
        conn.commit()
