"""Repository layer for structured SQLite persistence."""

from __future__ import annotations

import json
import sqlite3

import pandas as pd

from db.schema import init_db
from engine.hedge_fund import compute_exposures
from engine.portfolio import compute_drift, compute_portfolio_value, compute_weights
from engine.risk import compute_drawdown
from runtime_context import build_runtime_context
from utils.time import utc_now_iso

_DB_INITIALIZED: set[str] = set()


def _resolve_context(runtime_context=None, profile_name: str | None = None):
    return runtime_context or build_runtime_context(profile_name)


def _resolve_db_path(db_path: str | None = None, *, runtime_context=None, profile_name: str | None = None) -> str:
    if db_path:
        return db_path
    context = _resolve_context(runtime_context, profile_name)
    return context.market_db


def _connect(db_path: str | None = None, *, runtime_context=None, profile_name: str | None = None) -> sqlite3.Connection:
    resolved_db_path = _resolve_db_path(db_path, runtime_context=runtime_context, profile_name=profile_name)
    init_db(resolved_db_path)
    if resolved_db_path not in _DB_INITIALIZED:
        _DB_INITIALIZED.add(resolved_db_path)
    conn = sqlite3.connect(resolved_db_path)
    conn.row_factory = sqlite3.Row
    return conn


def save_snapshot(portfolio: dict, prices: dict, cycle_id: str, db_path: str | None = None, *, runtime_context=None, profile_name: str | None = None) -> int:
    context = _resolve_context(runtime_context, profile_name)
    resolved_db_path = _resolve_db_path(db_path, runtime_context=context)
    positions = portfolio.get("positions", {})
    position_sides = portfolio.get("position_sides", {})
    cash = portfolio.get("cash", 0.0)
    peak = portfolio.get("peak_value", cash)
    total = compute_portfolio_value(positions, cash, prices)
    drawdown = compute_drawdown(total, peak)
    weights = compute_weights(positions, prices, cash)
    drifts = compute_drift(weights, context.target_allocation)
    exposure = compute_exposures(
        positions,
        prices,
        cash,
        position_sides=position_sides,
        sector_map=context.sector_map,
        beta_map={ticker: (context.hedge_fund_profile.get("universe", {}).get(ticker, {}) or {}).get("beta", 1.0) for ticker in positions},
    )
    ts = utc_now_iso()

    with _connect(resolved_db_path) as conn:
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
            side = position_sides.get(ticker, "short" if qty < 0 else "long")
            conn.execute(
                """
                INSERT INTO positions (snapshot_id, ticker, quantity, price, value, weight, target_weight, drift, side, idea_id, gross_exposure, net_exposure)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    snapshot_id,
                    ticker,
                    qty,
                    price,
                    qty * price,
                    weights.get(ticker, 0.0),
                    context.target_allocation.get(ticker, 0.0),
                    drifts.get(ticker, 0.0),
                    side,
                    (portfolio.get("position_ideas") or {}).get(ticker),
                    exposure.get("single_name_concentration", {}).get(ticker, 0.0),
                    (qty * price) / total if total else 0.0,
                ),
            )
        conn.commit()
    return snapshot_id


def save_execution(trade_result, cycle_id: str, db_path: str | None = None, *, runtime_context=None, profile_name: str | None = None) -> int:
    resolved_db_path = _resolve_db_path(db_path, runtime_context=runtime_context, profile_name=profile_name)
    trade = trade_result.__dict__ if hasattr(trade_result, "__dict__") else trade_result
    slippage = abs(trade.get("fill_price", 0.0) - trade.get("market_price", 0.0)) * abs(trade.get("quantity", 0.0))
    with _connect(resolved_db_path) as conn:
        cur = conn.execute(
            """
            INSERT INTO executions
                (cycle_id, trade_id, timestamp, ticker, action, quantity, market_price, fill_price, cost, slippage,
                 reason, success, error, weight_before, target_weight, drift_before, slippage_pct, notional,
                 side, idea_id, sleeve, exposure_before, exposure_after, gross_impact, net_impact)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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
                trade.get("weight_before", 0.0),
                trade.get("target_weight", 0.0),
                trade.get("drift_before", 0.0),
                trade.get("slippage_pct", 0.0),
                trade.get("notional", 0.0),
                trade.get("side", "long"),
                trade.get("idea_id"),
                trade.get("sleeve", "core_longs"),
                trade.get("exposure_before", 0.0),
                trade.get("exposure_after", 0.0),
                trade.get("gross_impact", 0.0),
                trade.get("net_impact", 0.0),
            ),
        )
        conn.commit()
    return cur.lastrowid


def save_agent_run(state: dict, db_path: str | None = None, *, runtime_context=None, profile_name: str | None = None) -> int:
    resolved_db_path = _resolve_db_path(db_path, runtime_context=runtime_context, profile_name=profile_name)
    obs = state.get("observability", {})
    with _connect(resolved_db_path) as conn:
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


def get_history(days: int = 90, db_path: str | None = None, *, runtime_context=None, profile_name: str | None = None) -> pd.DataFrame:
    resolved_db_path = _resolve_db_path(db_path, runtime_context=runtime_context, profile_name=profile_name)
    try:
        with _connect(resolved_db_path) as conn:
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


def get_executions(limit: int = 100, db_path: str | None = None, *, runtime_context=None, profile_name: str | None = None) -> pd.DataFrame:
    resolved_db_path = _resolve_db_path(db_path, runtime_context=runtime_context, profile_name=profile_name)
    try:
        with _connect(resolved_db_path) as conn:
            return pd.read_sql_query(
                "SELECT * FROM executions ORDER BY timestamp DESC LIMIT ?",
                conn,
                params=(limit,),
            )
    except Exception:
        return pd.DataFrame()


def get_agent_runs(limit: int = 20, db_path: str | None = None, *, runtime_context=None, profile_name: str | None = None) -> list[dict]:
    resolved_db_path = _resolve_db_path(db_path, runtime_context=runtime_context, profile_name=profile_name)
    try:
        with _connect(resolved_db_path) as conn:
            rows = conn.execute("SELECT * FROM agent_runs ORDER BY timestamp DESC LIMIT ?", (limit,)).fetchall()
        return [dict(r) for r in rows]
    except Exception:
        return []


def get_positions_by_cycle(cycle_id: str, db_path: str | None = None, *, runtime_context=None, profile_name: str | None = None) -> list[dict]:
    resolved_db_path = _resolve_db_path(db_path, runtime_context=runtime_context, profile_name=profile_name)
    try:
        with _connect(resolved_db_path) as conn:
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


def get_market_data_status(db_path: str | None = None, *, runtime_context=None, profile_name: str | None = None) -> list[dict]:
    resolved_db_path = _resolve_db_path(db_path, runtime_context=runtime_context, profile_name=profile_name)
    try:
        with _connect(resolved_db_path) as conn:
            rows = conn.execute("SELECT * FROM market_data_status ORDER BY ticker ASC").fetchall()
        return [dict(r) for r in rows]
    except Exception:
        return []


def save_decision_trace(trace: dict, db_path: str | None = None, *, runtime_context=None, profile_name: str | None = None) -> int:
    resolved_db_path = _resolve_db_path(db_path, runtime_context=runtime_context, profile_name=profile_name)
    with _connect(resolved_db_path) as conn:
        cur = conn.execute(
            """
            INSERT INTO decision_traces
                (cycle_id, stage, payload_json, validation_json, mcp_tools_json, provider, agent_backend, execution_mode, created_at, event_type, tags)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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
                trace.get("event_type"),
                trace.get("tags"),
            ),
        )
        conn.commit()
    return cur.lastrowid


def get_decision_traces(limit: int = 100, cycle_id: str | None = None, db_path: str | None = None, *, runtime_context=None, profile_name: str | None = None) -> list[dict]:
    resolved_db_path = _resolve_db_path(db_path, runtime_context=runtime_context, profile_name=profile_name)
    try:
        with _connect(resolved_db_path) as conn:
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


def get_snapshots(limit: int = 60, db_path: str | None = None, *, runtime_context=None, profile_name: str | None = None) -> list[dict]:
    resolved_db_path = _resolve_db_path(db_path, runtime_context=runtime_context, profile_name=profile_name)
    try:
        with _connect(resolved_db_path) as conn:
            rows = conn.execute(
                "SELECT * FROM portfolio_snapshots ORDER BY timestamp DESC LIMIT ?",
                (limit,),
            ).fetchall()
        return list(reversed([dict(r) for r in rows]))
    except Exception:
        return []


def get_latest_positions(db_path: str | None = None, *, runtime_context=None, profile_name: str | None = None) -> list[dict]:
    resolved_db_path = _resolve_db_path(db_path, runtime_context=runtime_context, profile_name=profile_name)
    try:
        with _connect(resolved_db_path) as conn:
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


def upsert_idea_book(entries: list[dict], db_path: str | None = None, *, runtime_context=None, profile_name: str | None = None) -> None:
    resolved_db_path = _resolve_db_path(db_path, runtime_context=runtime_context, profile_name=profile_name)
    ts = utc_now_iso()
    with _connect(resolved_db_path) as conn:
        for entry in entries:
            conn.execute(
                """
                INSERT INTO idea_book
                    (idea_id, ticker, side, thesis, catalyst, time_horizon, conviction, upside_case, downside_case,
                     invalidation_rule, status, sleeve, edge_source, why_now, key_risk, supporting_signals,
                     evidence_quality, review_status, origin_cycle_id, llm_generated, source, crowded_score,
                     short_squeeze_risk, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(idea_id) DO UPDATE SET
                    ticker=excluded.ticker,
                    side=excluded.side,
                    thesis=excluded.thesis,
                    catalyst=excluded.catalyst,
                    time_horizon=excluded.time_horizon,
                    conviction=excluded.conviction,
                    upside_case=excluded.upside_case,
                    downside_case=excluded.downside_case,
                    invalidation_rule=excluded.invalidation_rule,
                    status=excluded.status,
                    sleeve=excluded.sleeve,
                    edge_source=excluded.edge_source,
                    why_now=excluded.why_now,
                    key_risk=excluded.key_risk,
                    supporting_signals=excluded.supporting_signals,
                    evidence_quality=excluded.evidence_quality,
                    review_status=excluded.review_status,
                    origin_cycle_id=excluded.origin_cycle_id,
                    llm_generated=excluded.llm_generated,
                    source=excluded.source,
                    crowded_score=excluded.crowded_score,
                    short_squeeze_risk=excluded.short_squeeze_risk,
                    updated_at=excluded.updated_at
                """,
                (
                    entry.get("idea_id"),
                    entry.get("ticker"),
                    entry.get("side", "long"),
                    entry.get("thesis", ""),
                    entry.get("catalyst", ""),
                    entry.get("time_horizon", ""),
                    float(entry.get("conviction", 0.5)),
                    entry.get("upside_case", ""),
                    entry.get("downside_case", ""),
                    entry.get("invalidation_rule", ""),
                    entry.get("status", "watchlist"),
                    entry.get("sleeve", "core_longs"),
                    entry.get("edge_source", ""),
                    entry.get("why_now", ""),
                    entry.get("key_risk", ""),
                    json.dumps(entry.get("supporting_signals", [])),
                    entry.get("evidence_quality", "medium"),
                    entry.get("review_status", "approved"),
                    entry.get("origin_cycle_id"),
                    int(bool(entry.get("llm_generated", False))),
                    entry.get("source", "profile_seed"),
                    float(entry.get("crowded_score", 0.0)),
                    int(bool(entry.get("short_squeeze_risk", False))),
                    ts,
                    ts,
                ),
            )
        conn.commit()


def get_idea_book(
    status: str | None = None,
    review_status: str | None = None,
    llm_generated: bool | None = None,
    db_path: str | None = None,
    *,
    runtime_context=None,
    profile_name: str | None = None,
) -> list[dict]:
    resolved_db_path = _resolve_db_path(db_path, runtime_context=runtime_context, profile_name=profile_name)
    try:
        with _connect(resolved_db_path) as conn:
            where: list[str] = []
            params: list[object] = []
            if status:
                where.append("status = ?")
                params.append(status)
            if review_status:
                where.append("review_status = ?")
                params.append(review_status)
            if llm_generated is not None:
                where.append("llm_generated = ?")
                params.append(int(llm_generated))
            query = "SELECT * FROM idea_book"
            if where:
                query += " WHERE " + " AND ".join(where)
            query += " ORDER BY conviction DESC, ticker ASC"
            rows = conn.execute(query, tuple(params)).fetchall()
        payload = [dict(r) for r in rows]
        for row in payload:
            signals = row.get("supporting_signals")
            if isinstance(signals, str):
                try:
                    row["supporting_signals"] = json.loads(signals)
                except json.JSONDecodeError:
                    row["supporting_signals"] = []
            row["llm_generated"] = bool(row.get("llm_generated", 0))
            row["short_squeeze_risk"] = bool(row.get("short_squeeze_risk", 0))
        return payload
    except Exception:
        return []


def update_idea_book_entry(
    idea_id: str,
    *,
    review_status: str | None = None,
    status: str | None = None,
    db_path: str | None = None,
    runtime_context=None,
    profile_name: str | None = None,
) -> bool:
    resolved_db_path = _resolve_db_path(db_path, runtime_context=runtime_context, profile_name=profile_name)
    assignments: list[str] = []
    params: list[object] = []
    if review_status is not None:
        assignments.append("review_status = ?")
        params.append(review_status)
    if status is not None:
        assignments.append("status = ?")
        params.append(status)
    if not assignments:
        return False
    assignments.append("updated_at = ?")
    params.append(utc_now_iso())
    params.append(idea_id)
    with _connect(resolved_db_path) as conn:
        cur = conn.execute(
            f"UPDATE idea_book SET {', '.join(assignments)} WHERE idea_id = ?",
            tuple(params),
        )
        conn.commit()
    return cur.rowcount > 0
