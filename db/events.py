"""Immutable event log — audit-grade event sourcing for cycle replay."""

from __future__ import annotations

import json
from typing import Literal

from config import MARKET_DB, USE_POSTGRES
from db.connection import get_connection, q
from db.schema import init_db
from runtime_context import build_runtime_context
from utils.time import utc_now_iso

EventType = Literal[
    "cycle_started",
    "observation_captured",
    "decision_made",
    "policy_evaluated",
    "trade_executed",
    "audit_complete",
    "cycle_failed",
]


def _events_db_path(
    db_path: str | None,
    *,
    runtime_context=None,
    profile_name: str | None = None,
) -> str:
    if USE_POSTGRES:
        return MARKET_DB
    return db_path or (runtime_context or build_runtime_context(profile_name)).market_db


def save_event(
    cycle_id: str,
    event_type: EventType,
    payload: dict,
    db_path: str | None = None,
    *,
    runtime_context=None,
    profile_name: str | None = None,
) -> None:
    """Append an event to the immutable event log."""
    resolved = _events_db_path(db_path, runtime_context=runtime_context, profile_name=profile_name)
    init_db(None if USE_POSTGRES else resolved)
    with get_connection(resolved) as conn:
        conn.execute(
            q("INSERT INTO cycle_events (cycle_id, event_type, payload_json, created_at) VALUES (?,?,?,?)"),
            (cycle_id, event_type, json.dumps(payload), utc_now_iso()),
        )
        conn.commit()


def get_events(
    cycle_id: str,
    db_path: str | None = None,
    *,
    runtime_context=None,
    profile_name: str | None = None,
) -> list[dict]:
    """Return all events for a cycle, ordered chronologically."""
    resolved = _events_db_path(db_path, runtime_context=runtime_context, profile_name=profile_name)
    init_db(None if USE_POSTGRES else resolved)
    with get_connection(resolved) as conn:
        rows = conn.execute(
            q("SELECT * FROM cycle_events WHERE cycle_id = ? ORDER BY created_at ASC"),
            (cycle_id,),
        ).fetchall()
    return [
        {
            "id": r["id"],
            "cycle_id": r["cycle_id"],
            "event_type": r["event_type"],
            "payload": json.loads(r["payload_json"]),
            "created_at": r["created_at"],
        }
        for r in rows
    ]


def get_recent_events(
    limit: int = 100,
    db_path: str | None = None,
    *,
    runtime_context=None,
    profile_name: str | None = None,
) -> list[dict]:
    """Return the most recent events across all cycles."""
    resolved = _events_db_path(db_path, runtime_context=runtime_context, profile_name=profile_name)
    init_db(None if USE_POSTGRES else resolved)
    with get_connection(resolved) as conn:
        rows = conn.execute(q("SELECT * FROM cycle_events ORDER BY created_at DESC LIMIT ?"), (limit,)).fetchall()
    return [
        {
            "id": r["id"],
            "cycle_id": r["cycle_id"],
            "event_type": r["event_type"],
            "payload": json.loads(r["payload_json"]),
            "created_at": r["created_at"],
        }
        for r in rows
    ]


def replay_cycle(
    cycle_id: str,
    db_path: str | None = None,
    *,
    runtime_context=None,
    profile_name: str | None = None,
) -> dict:
    """Reconstruct cycle state by replaying its event log."""
    resolved = _events_db_path(db_path, runtime_context=runtime_context, profile_name=profile_name)
    events = get_events(cycle_id, db_path=resolved, runtime_context=runtime_context, profile_name=profile_name)
    state: dict = {
        "cycle_id": cycle_id,
        "events": events,
        "stages_completed": [],
        "replayed": bool(events),
    }
    for evt in events:
        state["stages_completed"].append(evt["event_type"])
        if evt["event_type"] == "cycle_started":
            state["strategy_name"] = evt["payload"].get("strategy")
            state["execution_mode"] = evt["payload"].get("mode")
        if evt["event_type"] == "observation_captured":
            state["portfolio_value"] = evt["payload"].get("portfolio_value")
            state["tickers"] = evt["payload"].get("tickers", [])
            state["kill_switch_active"] = evt["payload"].get("kill_switch", False)
        elif evt["event_type"] == "decision_made":
            state["confidence"] = evt["payload"].get("confidence")
            state["trades_proposed"] = evt["payload"].get("trades_count", 0)
            state["rebalance_needed"] = evt["payload"].get("rebalance_needed", False)
        elif evt["event_type"] == "policy_evaluated":
            state["trades_allowed"] = evt["payload"].get("allowed")
            state["trades_blocked"] = evt["payload"].get("blocked")
            state["policy_approved"] = evt["payload"].get("approved")
            state["violations"] = evt["payload"].get("violations", 0)
        elif evt["event_type"] == "trade_executed":
            state["executed_count"] = evt["payload"].get("executed_count", 0)
            state["total_notional"] = evt["payload"].get("total_notional", 0.0)
        elif evt["event_type"] == "audit_complete":
            state["total_duration_ms"] = evt["payload"].get("total_ms")
            state["completed"] = True
        elif evt["event_type"] == "cycle_failed":
            state["completed"] = False
            state["error"] = evt["payload"].get("error")
    return state
