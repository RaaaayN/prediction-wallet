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


def test_cli_observe_runs_without_model_key():
    result = subprocess.run(
        [sys.executable, "main.py", "observe"],
        capture_output=True,
        text=True,
        cwd="C:\\Users\\rayan\\OneDrive\\Documents\\GitHub\\prediction-wallet-1",
    )
    assert result.returncode == 0
    assert "\"cycle_id\"" in result.stdout
