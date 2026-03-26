"""Tests for trace persistence and CLI entrypoints."""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile

from db.repository import get_decision_traces, save_decision_trace
from db.schema import init_db


def test_save_and_get_decision_trace():
    tmpdir = tempfile.mkdtemp()
    db_path = f"{tmpdir}/market.db"
    init_db(db_path)
    save_decision_trace(
        {
            "cycle_id": "cycle-1",
            "stage": "decide",
            "payload_json": json.dumps({"ok": True}),
            "validation_json": json.dumps({}),
            "mcp_tools_json": json.dumps(["local_market_snapshot"]),
            "provider": "gemini",
            "agent_backend": "pydantic-ai",
            "execution_mode": "simulate",
        },
        db_path=db_path,
    )
    traces = get_decision_traces(db_path=db_path)
    assert len(traces) == 1
    assert traces[0]["cycle_id"] == "cycle-1"


def test_event_type_and_tags_saved():
    """event_type and tags are persisted and returned by get_decision_traces."""
    tmpdir = tempfile.mkdtemp()
    db_path = f"{tmpdir}/market.db"
    init_db(db_path)
    tags = ["strategy:threshold", "mode:simulate", "signal:True"]
    save_decision_trace(
        {
            "cycle_id": "cycle-evt",
            "stage": "observe",
            "payload_json": json.dumps({}),
            "provider": "gemini",
            "agent_backend": "pydantic-ai",
            "execution_mode": "simulate",
            "event_type": "cycle_step",
            "tags": json.dumps(tags),
        },
        db_path=db_path,
    )
    traces = get_decision_traces(db_path=db_path)
    assert len(traces) == 1
    trace = traces[0]
    assert trace["event_type"] == "cycle_step"
    assert json.loads(trace["tags"]) == tags


def test_event_type_defaults_to_none_when_omitted():
    """Traces saved without event_type have NULL in the DB (None in Python)."""
    tmpdir = tempfile.mkdtemp()
    db_path = f"{tmpdir}/market.db"
    init_db(db_path)
    save_decision_trace(
        {
            "cycle_id": "cycle-old",
            "stage": "decide",
            "payload_json": json.dumps({}),
        },
        db_path=db_path,
    )
    traces = get_decision_traces(db_path=db_path)
    assert traces[0]["event_type"] is None
    assert traces[0]["tags"] is None


def test_kill_switch_event_type_roundtrip():
    """A trace with event_type='kill_switch' is stored and returned correctly."""
    tmpdir = tempfile.mkdtemp()
    db_path = f"{tmpdir}/market.db"
    init_db(db_path)
    save_decision_trace(
        {
            "cycle_id": "cycle-ks",
            "stage": "validate",
            "payload_json": json.dumps({}),
            "event_type": "kill_switch",
            "tags": json.dumps(["approved:False", "violations:1"]),
        },
        db_path=db_path,
    )
    traces = get_decision_traces(db_path=db_path, cycle_id="cycle-ks")
    assert len(traces) == 1
    assert traces[0]["event_type"] == "kill_switch"
    assert "approved:False" in json.loads(traces[0]["tags"])


def test_cli_observe_runs_without_model_key():
    result = subprocess.run(
        [sys.executable, "main.py", "observe"],
        capture_output=True,
        text=True,
        cwd="C:\\Users\\rayan\\OneDrive\\Documents\\GitHub\\prediction-wallet-1",
    )
    assert result.returncode == 0
    assert "\"cycle_id\"" in result.stdout
