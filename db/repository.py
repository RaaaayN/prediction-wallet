"""Repository layer for structured persistence (SQLite or PostgreSQL)."""

from __future__ import annotations

import json
from contextlib import contextmanager
from typing import Any

import pandas as pd

from config import MARKET_DB, USE_POSTGRES
from db.connection import excluded_qualifier, get_connection, get_sqlalchemy_engine, q
from engine.hedge_fund import compute_exposures
from engine.portfolio import compute_drift, compute_portfolio_value, compute_weights
from engine.risk import compute_drawdown
from runtime_context import build_runtime_context
from utils.time import utc_now_iso


def _resolve_context(runtime_context=None, profile_name: str | None = None):
    if runtime_context is not None:
        return runtime_context
    return build_runtime_context(profile_name)


def _resolve_db_path(db_path: str | None = None, *, runtime_context=None, profile_name: str | None = None) -> str:
    if USE_POSTGRES:
        return MARKET_DB
    if db_path:
        return db_path
    ctx = _resolve_context(runtime_context, profile_name)
    return ctx.market_db


def _row_pk(row: Any, key: str = "id") -> int:
    if row is None:
        raise RuntimeError("INSERT returned no row")
    if isinstance(row, dict):
        return int(row[key])
    return int(row[key])


def save_snapshot(
    portfolio: dict,
    prices: dict,
    cycle_id: str,
    db_path: str | None = None,
    *,
    runtime_context=None,
    profile_name: str | None = None,
) -> int:
    context = _resolve_context(runtime_context, profile_name)
    resolved = _resolve_db_path(db_path, runtime_context=context, profile_name=profile_name)
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
        beta_map={
            ticker: (context.hedge_fund_profile.get("universe", {}).get(ticker, {}) or {}).get("beta", 1.0)
            for ticker in positions
        },
    )
    ts = utc_now_iso()

    with get_connection(resolved) as conn:
        cur = conn.execute(
            q(
                """
            INSERT INTO portfolio_snapshots (timestamp, cycle_id, total_value, cash, peak_value, drawdown)
            VALUES (?, ?, ?, ?, ?, ?)
            RETURNING id
            """
            ),
            (ts, cycle_id, total, cash, peak, drawdown),
        )
        snapshot_id = _row_pk(cur.fetchone())
        for ticker, qty in positions.items():
            price = prices.get(ticker, 0.0)
            side = position_sides.get(ticker, "short" if qty < 0 else "long")
            conn.execute(
                q(
                    """
                INSERT INTO positions (snapshot_id, ticker, quantity, price, value, weight, target_weight, drift, side, idea_id, gross_exposure, net_exposure)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """
                ),
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


def save_execution(
    trade_result,
    cycle_id: str,
    db_path: str | None = None,
    *,
    runtime_context=None,
    profile_name: str | None = None,
) -> int:
    resolved = _resolve_db_path(db_path, runtime_context=runtime_context, profile_name=profile_name)
    trade = trade_result.__dict__ if hasattr(trade_result, "__dict__") else trade_result
    slippage = abs(trade.get("fill_price", 0.0) - trade.get("market_price", 0.0)) * abs(trade.get("quantity", 0.0))
    with get_connection(resolved) as conn:
        cur = conn.execute(
            q(
                """
            INSERT INTO executions
                (cycle_id, trade_id, timestamp, ticker, action, quantity, market_price, fill_price, cost, slippage,
                 reason, success, error, weight_before, target_weight, drift_before, slippage_pct, notional,
                 side, idea_id, sleeve, exposure_before, exposure_after, gross_impact, net_impact)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            RETURNING id
            """
            ),
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
        rid = _row_pk(cur.fetchone())
        conn.commit()
    return rid


def save_agent_run(
    state: dict,
    db_path: str | None = None,
    *,
    runtime_context=None,
    profile_name: str | None = None,
) -> int:
    resolved = _resolve_db_path(db_path, runtime_context=runtime_context, profile_name=profile_name)
    obs = state.get("observability", {})
    with get_connection(resolved) as conn:
        cur = conn.execute(
            q(
                """
            INSERT INTO agent_runs
                (cycle_id, timestamp, strategy, signal, analysis, trades_count, report_path, kill_switch, provider, tool_calls, fetch_latency_ms, errors_json)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            RETURNING id
            """
            ),
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
                json.dumps(
                    state.get("errors", [])
                    + [e.get("error", "") for e in obs.get("data_errors", []) if e.get("error")]
                ),
            ),
        )
        rid = _row_pk(cur.fetchone())
        conn.commit()
    return rid


def get_history(
    days: int = 90,
    db_path: str | None = None,
    *,
    runtime_context=None,
    profile_name: str | None = None,
) -> pd.DataFrame:
    resolved = _resolve_db_path(db_path, runtime_context=runtime_context, profile_name=profile_name)
    try:
        if USE_POSTGRES:
            from sqlalchemy import text

            eng = get_sqlalchemy_engine()
            stmt = text(
                """
                SELECT * FROM portfolio_snapshots
                WHERE timestamp::timestamptz >= (CURRENT_TIMESTAMP AT TIME ZONE 'UTC' - (CAST(:d AS INTEGER) * INTERVAL '1 day'))
                ORDER BY timestamp ASC
                """
            )
            return pd.read_sql_query(stmt, eng, params={"d": days})
        with get_connection(resolved) as conn:
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


def get_executions(
    limit: int = 100,
    db_path: str | None = None,
    *,
    runtime_context=None,
    profile_name: str | None = None,
) -> pd.DataFrame:
    resolved = _resolve_db_path(db_path, runtime_context=runtime_context, profile_name=profile_name)
    try:
        if USE_POSTGRES:
            from sqlalchemy import text

            eng = get_sqlalchemy_engine()
            stmt = text("SELECT * FROM executions ORDER BY timestamp DESC LIMIT :lim")
            return pd.read_sql_query(stmt, eng, params={"lim": limit})
        with get_connection(resolved) as conn:
            return pd.read_sql_query(
                "SELECT * FROM executions ORDER BY timestamp DESC LIMIT ?",
                conn,
                params=(limit,),
            )
    except Exception:
        return pd.DataFrame()


def get_agent_runs(
    limit: int = 20,
    db_path: str | None = None,
    *,
    runtime_context=None,
    profile_name: str | None = None,
) -> list[dict]:
    resolved = _resolve_db_path(db_path, runtime_context=runtime_context, profile_name=profile_name)
    try:
        with get_connection(resolved) as conn:
            rows = conn.execute(q("SELECT * FROM agent_runs ORDER BY timestamp DESC LIMIT ?"), (limit,)).fetchall()
        return [dict(r) for r in rows]
    except Exception:
        return []


def get_positions_by_cycle(
    cycle_id: str,
    db_path: str | None = None,
    *,
    runtime_context=None,
    profile_name: str | None = None,
) -> list[dict]:
    resolved = _resolve_db_path(db_path, runtime_context=runtime_context, profile_name=profile_name)
    try:
        with get_connection(resolved) as conn:
            rows = conn.execute(
                q(
                    """
                SELECT p.*
                FROM positions p
                JOIN portfolio_snapshots s ON p.snapshot_id = s.id
                WHERE s.cycle_id = ?
                ORDER BY p.ticker ASC
                """
                ),
                (cycle_id,),
            ).fetchall()
        return [dict(r) for r in rows]
    except Exception:
        return []


def get_market_data_status(
    db_path: str | None = None,
    *,
    runtime_context=None,
    profile_name: str | None = None,
) -> list[dict]:
    resolved = _resolve_db_path(db_path, runtime_context=runtime_context, profile_name=profile_name)
    try:
        with get_connection(resolved) as conn:
            rows = conn.execute(q("SELECT * FROM market_data_status ORDER BY ticker ASC")).fetchall()
        return [dict(r) for r in rows]
    except Exception:
        return []


def save_decision_trace(
    trace: dict,
    db_path: str | None = None,
    *,
    runtime_context=None,
    profile_name: str | None = None,
) -> int:
    resolved = _resolve_db_path(db_path, runtime_context=runtime_context, profile_name=profile_name)
    with get_connection(resolved) as conn:
        cur = conn.execute(
            q(
                """
            INSERT INTO decision_traces
                (cycle_id, stage, payload_json, validation_json, mcp_tools_json, provider, agent_backend, execution_mode, created_at, event_type, tags)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            RETURNING id
            """
            ),
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
        rid = _row_pk(cur.fetchone())
        conn.commit()
    return rid


def get_decision_traces(
    limit: int = 100,
    cycle_id: str | None = None,
    db_path: str | None = None,
    *,
    runtime_context=None,
    profile_name: str | None = None,
) -> list[dict]:
    resolved = _resolve_db_path(db_path, runtime_context=runtime_context, profile_name=profile_name)
    try:
        with get_connection(resolved) as conn:
            if cycle_id:
                rows = conn.execute(
                    q("SELECT * FROM decision_traces WHERE cycle_id = ? ORDER BY created_at DESC LIMIT ?"),
                    (cycle_id, limit),
                ).fetchall()
            else:
                rows = conn.execute(q("SELECT * FROM decision_traces ORDER BY created_at DESC LIMIT ?"), (limit,)).fetchall()
        return [dict(r) for r in rows]
    except Exception:
        return []


def get_snapshots(
    limit: int = 60,
    db_path: str | None = None,
    *,
    runtime_context=None,
    profile_name: str | None = None,
) -> list[dict]:
    resolved = _resolve_db_path(db_path, runtime_context=runtime_context, profile_name=profile_name)
    try:
        with get_connection(resolved) as conn:
            rows = conn.execute(q("SELECT * FROM portfolio_snapshots ORDER BY timestamp DESC LIMIT ?"), (limit,)).fetchall()
        return list(reversed([dict(r) for r in rows]))
    except Exception:
        return []


def get_latest_positions(
    db_path: str | None = None,
    *,
    runtime_context=None,
    profile_name: str | None = None,
) -> list[dict]:
    resolved = _resolve_db_path(db_path, runtime_context=runtime_context, profile_name=profile_name)
    try:
        with get_connection(resolved) as conn:
            rows = conn.execute(
                q(
                    """
                SELECT p.* FROM positions p
                JOIN portfolio_snapshots s ON p.snapshot_id = s.id
                WHERE s.id = (SELECT MAX(id) FROM portfolio_snapshots)
                ORDER BY p.ticker ASC
                """
                ),
            ).fetchall()
        return [dict(r) for r in rows]
    except Exception:
        return []


def upsert_idea_book(
    entries: list[dict],
    db_path: str | None = None,
    *,
    runtime_context=None,
    profile_name: str | None = None,
) -> None:
    resolved = _resolve_db_path(db_path, runtime_context=runtime_context, profile_name=profile_name)
    ts = utc_now_iso()
    ex = excluded_qualifier()
    sql = f"""
                INSERT INTO idea_book
                    (idea_id, ticker, side, thesis, catalyst, time_horizon, conviction, upside_case, downside_case,
                     invalidation_rule, status, sleeve, edge_source, why_now, key_risk, supporting_signals,
                     evidence_quality, review_status, origin_cycle_id, llm_generated, source, crowded_score,
                     short_squeeze_risk, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT (idea_id) DO UPDATE SET
                    ticker={ex}.ticker,
                    side={ex}.side,
                    thesis={ex}.thesis,
                    catalyst={ex}.catalyst,
                    time_horizon={ex}.time_horizon,
                    conviction={ex}.conviction,
                    upside_case={ex}.upside_case,
                    downside_case={ex}.downside_case,
                    invalidation_rule={ex}.invalidation_rule,
                    status={ex}.status,
                    sleeve={ex}.sleeve,
                    edge_source={ex}.edge_source,
                    why_now={ex}.why_now,
                    key_risk={ex}.key_risk,
                    supporting_signals={ex}.supporting_signals,
                    evidence_quality={ex}.evidence_quality,
                    review_status={ex}.review_status,
                    origin_cycle_id={ex}.origin_cycle_id,
                    llm_generated={ex}.llm_generated,
                    source={ex}.source,
                    crowded_score={ex}.crowded_score,
                    short_squeeze_risk={ex}.short_squeeze_risk,
                    updated_at={ex}.updated_at
                """
    with get_connection(resolved) as conn:
        for entry in entries:
            conn.execute(
                q(sql),
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
    resolved = _resolve_db_path(db_path, runtime_context=runtime_context, profile_name=profile_name)
    try:
        with get_connection(resolved) as conn:
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
            rows = conn.execute(q(query), tuple(params)).fetchall()
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
    resolved = _resolve_db_path(db_path, runtime_context=runtime_context, profile_name=profile_name)
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
    with get_connection(resolved) as conn:
        cur = conn.execute(
            q(f"UPDATE idea_book SET {', '.join(assignments)} WHERE idea_id = ?"),
            tuple(params),
        )
        conn.commit()
    return cur.rowcount > 0
