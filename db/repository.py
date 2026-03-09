"""Repository layer — CRUD operations on market.db structured tables."""

from __future__ import annotations

import sqlite3
from datetime import datetime, timezone

import pandas as pd

from config import MARKET_DB, TARGET_ALLOCATION
from db.schema import init_db
from engine.portfolio import compute_weights, compute_drift, compute_portfolio_value
from engine.risk import compute_drawdown


def _connect(db_path: str = MARKET_DB) -> sqlite3.Connection:
    """Return a connection with row_factory set to dict-like rows."""
    init_db(db_path)
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn


# ---------------------------------------------------------------------------
# Writes
# ---------------------------------------------------------------------------


def save_snapshot(portfolio: dict, prices: dict, cycle_id: str, db_path: str = MARKET_DB) -> int:
    """Persist a portfolio snapshot and its per-ticker positions.

    Returns:
        snapshot_id (INTEGER PRIMARY KEY) of the inserted row
    """
    positions = portfolio.get("positions", {})
    cash = portfolio.get("cash", 0.0)
    peak = portfolio.get("peak_value", cash)
    total = compute_portfolio_value(positions, cash, prices)
    drawdown = compute_drawdown(total, peak)
    weights = compute_weights(positions, prices, cash)
    drifts = compute_drift(weights, TARGET_ALLOCATION)
    ts = datetime.now(timezone.utc).isoformat()

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
            value = qty * price
            weight = weights.get(ticker, 0.0)
            target_weight = TARGET_ALLOCATION.get(ticker, 0.0)
            drift = drifts.get(ticker, 0.0)
            conn.execute(
                """
                INSERT INTO positions (snapshot_id, ticker, quantity, price, value, weight, target_weight, drift)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (snapshot_id, ticker, qty, price, value, weight, target_weight, drift),
            )
        conn.commit()

    return snapshot_id


def save_execution(trade_result, cycle_id: str, db_path: str = MARKET_DB) -> int:
    """Persist a single trade execution.

    *trade_result* can be a TradeResult dataclass or a plain dict.

    Returns:
        row id of inserted execution
    """
    if hasattr(trade_result, "__dict__"):
        t = trade_result.__dict__
    else:
        t = trade_result

    slippage = abs(t.get("fill_price", 0.0) - t.get("market_price", 0.0)) * abs(t.get("quantity", 0.0))

    with _connect(db_path) as conn:
        cur = conn.execute(
            """
            INSERT INTO executions
                (cycle_id, trade_id, timestamp, ticker, action, quantity,
                 market_price, fill_price, cost, slippage, reason, success, error)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                cycle_id,
                t.get("trade_id", ""),
                t.get("timestamp", datetime.now(timezone.utc).isoformat()),
                t.get("ticker", ""),
                t.get("action", ""),
                t.get("quantity", 0.0),
                t.get("market_price", 0.0),
                t.get("fill_price", 0.0),
                t.get("cost", 0.0),
                slippage,
                t.get("reason", ""),
                int(bool(t.get("success", False))),
                t.get("error", ""),
            ),
        )
        row_id = cur.lastrowid
        conn.commit()

    return row_id


def save_agent_run(state: dict, db_path: str = MARKET_DB) -> int:
    """Persist a summary of one agent run cycle.

    Returns:
        row id of inserted agent_run
    """
    trades_executed = state.get("trades_executed", [])
    with _connect(db_path) as conn:
        cur = conn.execute(
            """
            INSERT INTO agent_runs
                (cycle_id, timestamp, strategy, signal, analysis, trades_count, report_path, kill_switch)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                state.get("cycle_id", ""),
                datetime.now(timezone.utc).isoformat(),
                state.get("strategy_name", "threshold"),
                int(bool(state.get("strategy_signal", False))),
                state.get("analysis", ""),
                len(trades_executed),
                state.get("report_path"),
                int(bool(state.get("kill_switch_active", False))),
            ),
        )
        row_id = cur.lastrowid
        conn.commit()

    return row_id


# ---------------------------------------------------------------------------
# Reads
# ---------------------------------------------------------------------------


def get_history(days: int = 90, db_path: str = MARKET_DB) -> pd.DataFrame:
    """Return portfolio_snapshots for the last *days* calendar days.

    Returns:
        DataFrame with columns: id, timestamp, cycle_id, total_value, cash, peak_value, drawdown
        Sorted ascending by timestamp.
    """
    try:
        with _connect(db_path) as conn:
            df = pd.read_sql_query(
                """
                SELECT * FROM portfolio_snapshots
                WHERE timestamp >= datetime('now', ?)
                ORDER BY timestamp ASC
                """,
                conn,
                params=(f"-{days} days",),
            )
        return df
    except Exception:
        return pd.DataFrame()


def get_executions(limit: int = 100, db_path: str = MARKET_DB) -> pd.DataFrame:
    """Return the most recent *limit* executions.

    Returns:
        DataFrame sorted by timestamp descending.
    """
    try:
        with _connect(db_path) as conn:
            df = pd.read_sql_query(
                "SELECT * FROM executions ORDER BY timestamp DESC LIMIT ?",
                conn,
                params=(limit,),
            )
        return df
    except Exception:
        return pd.DataFrame()


def get_agent_runs(limit: int = 20, db_path: str = MARKET_DB) -> list[dict]:
    """Return the most recent *limit* agent run summaries.

    Returns:
        List of dicts, most recent first.
    """
    try:
        with _connect(db_path) as conn:
            rows = conn.execute(
                "SELECT * FROM agent_runs ORDER BY timestamp DESC LIMIT ?", (limit,)
            ).fetchall()
        return [dict(r) for r in rows]
    except Exception:
        return []


def get_positions_by_cycle(cycle_id: str, db_path: str = MARKET_DB) -> list[dict]:
    """Return all position rows for a given cycle_id.

    Joins positions with the portfolio_snapshot for that cycle.

    Returns:
        List of dicts with position details.
    """
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
