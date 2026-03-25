"""Repository layer for structured SQLite persistence."""

from __future__ import annotations

import json
import sqlite3

import pandas as pd

from config import MARKET_DB, TARGET_ALLOCATION
from db.schema import init_db
from engine.portfolio import compute_drift, compute_portfolio_value, compute_weights
from engine.risk import compute_drawdown
from utils.time import utc_now_iso

_DB_INITIALIZED: set[str] = set()


def _connect(db_path: str = MARKET_DB) -> sqlite3.Connection:
    if db_path not in _DB_INITIALIZED:
        init_db(db_path)
        _DB_INITIALIZED.add(db_path)
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn


def save_snapshot(portfolio: dict, prices: dict, cycle_id: str, db_path: str = MARKET_DB) -> int:
    positions = portfolio.get("positions", {})
    cash = portfolio.get("cash", 0.0)
    peak = portfolio.get("peak_value", cash)
    total = compute_portfolio_value(positions, cash, prices)
    drawdown = compute_drawdown(total, peak)
    weights = compute_weights(positions, prices, cash)
    drifts = compute_drift(weights, TARGET_ALLOCATION)
    ts = utc_now_iso()

    with _connect(db_path) as conn:
        cur = conn.execute(
            """
            INSERT INTO portfolio_snapshots (timestamp, cycle_id, total_value, cash, peak_value, drawdown)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (ts, cycle_id, total, cash, peak, drawdown),
        )
        snapshot_id = cur.lastrowid
        for ticker, qty in positions.items():
            price = prices.get(ticker, 0.0)
            conn.execute(
                """
                INSERT INTO positions (snapshot_id, ticker, quantity, price, value, weight, target_weight, drift)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    snapshot_id,
                    ticker,
                    qty,
                    price,
                    qty * price,
                    weights.get(ticker, 0.0),
                    TARGET_ALLOCATION.get(ticker, 0.0),
                    drifts.get(ticker, 0.0),
                ),
            )
        conn.commit()
    return snapshot_id


def save_execution(trade_result, cycle_id: str, db_path: str = MARKET_DB) -> int:
    trade = trade_result.__dict__ if hasattr(trade_result, "__dict__") else trade_result
    slippage = abs(trade.get("fill_price", 0.0) - trade.get("market_price", 0.0)) * abs(trade.get("quantity", 0.0))
    with _connect(db_path) as conn:
        cur = conn.execute(
            """
            INSERT INTO executions
                (cycle_id, trade_id, timestamp, ticker, action, quantity, market_price, fill_price, cost, slippage, reason, success, error)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                cycle_id,
                trade.get("trade_id", ""),
                trade.get("timestamp", utc_now_iso()),
                trade.get("ticker", ""),
                trade.get("action", ""),
                trade.get("quantity", 0.0),
                trade.get("market_price", 0.0),
                trade.get("fill_price", 0.0),
                trade.get("cost", 0.0),
                slippage,
                trade.get("reason", ""),
                int(bool(trade.get("success", False))),
                trade.get("error", ""),
            ),
        )
        conn.commit()
    return cur.lastrowid


def save_agent_run(state: dict, db_path: str = MARKET_DB) -> int:
    obs = state.get("observability", {})
    with _connect(db_path) as conn:
        cur = conn.execute(
            """
            INSERT INTO agent_runs
                (cycle_id, timestamp, strategy, signal, analysis, trades_count, report_path, kill_switch, provider, tool_calls, fetch_latency_ms, errors_json)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                state.get("cycle_id", ""),
                utc_now_iso(),
                state.get("strategy_name", "threshold"),
                int(bool(state.get("strategy_signal", False))),
                state.get("analysis", ""),
                len(state.get("trades_executed", [])),
                state.get("report_path"),
                int(bool(state.get("kill_switch_active", False))),
                obs.get("provider"),
                obs.get("tool_calls", 0),
                obs.get("fetch_latency_ms", 0.0),
                json.dumps(state.get("errors", []) + [e.get("error", "") for e in obs.get("data_errors", []) if e.get("error")]),
            ),
        )
        conn.commit()
    return cur.lastrowid


def get_history(days: int = 90, db_path: str = MARKET_DB) -> pd.DataFrame:
    try:
        with _connect(db_path) as conn:
            return pd.read_sql_query(
                """
                SELECT * FROM portfolio_snapshots
                WHERE timestamp >= datetime('now', ?)
                ORDER BY timestamp ASC
                """,
                conn,
                params=(f"-{days} days",),
            )
    except Exception:
        return pd.DataFrame()


def get_executions(limit: int = 100, db_path: str = MARKET_DB) -> pd.DataFrame:
    try:
        with _connect(db_path) as conn:
            return pd.read_sql_query(
                "SELECT * FROM executions ORDER BY timestamp DESC LIMIT ?",
                conn,
                params=(limit,),
            )
    except Exception:
        return pd.DataFrame()


def get_agent_runs(limit: int = 20, db_path: str = MARKET_DB) -> list[dict]:
    try:
        with _connect(db_path) as conn:
            rows = conn.execute("SELECT * FROM agent_runs ORDER BY timestamp DESC LIMIT ?", (limit,)).fetchall()
        return [dict(r) for r in rows]
    except Exception:
        return []


def get_positions_by_cycle(cycle_id: str, db_path: str = MARKET_DB) -> list[dict]:
    try:
        with _connect(db_path) as conn:
            rows = conn.execute(
                """
                SELECT p.*
                FROM positions p
                JOIN portfolio_snapshots s ON p.snapshot_id = s.id
                WHERE s.cycle_id = ?
                ORDER BY p.ticker ASC
                """,
                (cycle_id,),
            ).fetchall()
        return [dict(r) for r in rows]
    except Exception:
        return []


def get_market_data_status(db_path: str = MARKET_DB) -> list[dict]:
    try:
        with _connect(db_path) as conn:
            rows = conn.execute("SELECT * FROM market_data_status ORDER BY ticker ASC").fetchall()
        return [dict(r) for r in rows]
    except Exception:
        return []


def save_decision_trace(trace: dict, db_path: str = MARKET_DB) -> int:
    with _connect(db_path) as conn:
        cur = conn.execute(
            """
            INSERT INTO decision_traces
                (cycle_id, stage, payload_json, validation_json, mcp_tools_json, provider, agent_backend, execution_mode, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                trace.get("cycle_id", ""),
                trace.get("stage", ""),
                trace.get("payload_json", "{}"),
                trace.get("validation_json"),
                trace.get("mcp_tools_json"),
                trace.get("provider"),
                trace.get("agent_backend"),
                trace.get("execution_mode"),
                utc_now_iso(),
            ),
        )
        conn.commit()
    return cur.lastrowid


def get_decision_traces(limit: int = 100, cycle_id: str | None = None, db_path: str = MARKET_DB) -> list[dict]:
    try:
        with _connect(db_path) as conn:
            if cycle_id:
                rows = conn.execute(
                    "SELECT * FROM decision_traces WHERE cycle_id = ? ORDER BY created_at DESC LIMIT ?",
                    (cycle_id, limit),
                ).fetchall()
            else:
                rows = conn.execute(
                    "SELECT * FROM decision_traces ORDER BY created_at DESC LIMIT ?",
                    (limit,),
                ).fetchall()
        return [dict(r) for r in rows]
    except Exception:
        return []


def get_snapshots(limit: int = 60, db_path: str = MARKET_DB) -> list[dict]:
    try:
        with _connect(db_path) as conn:
            rows = conn.execute(
                "SELECT * FROM portfolio_snapshots ORDER BY timestamp DESC LIMIT ?",
                (limit,),
            ).fetchall()
        return list(reversed([dict(r) for r in rows]))  # ASC for timeline charts
    except Exception:
        return []


def get_latest_positions(db_path: str = MARKET_DB) -> list[dict]:
    try:
        with _connect(db_path) as conn:
            rows = conn.execute(
                """
                SELECT p.* FROM positions p
                JOIN portfolio_snapshots s ON p.snapshot_id = s.id
                WHERE s.id = (SELECT MAX(id) FROM portfolio_snapshots)
                ORDER BY p.ticker ASC
                """,
            ).fetchall()
        return [dict(r) for r in rows]
    except Exception:
        return []
