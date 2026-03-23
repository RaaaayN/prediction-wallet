"""FastAPI backend for the Prediction Wallet governed agent UI."""

from __future__ import annotations

import json
import sqlite3
import sys
from pathlib import Path

from fastapi import FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from api.runner import build_cycle_args, stream_command

app = FastAPI(title="Prediction Wallet API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── helpers ──────────────────────────────────────────────────────────────────

def _db_path() -> str:
    from config import MARKET_DB
    return MARKET_DB


def _connect() -> sqlite3.Connection:
    conn = sqlite3.connect(_db_path())
    conn.row_factory = sqlite3.Row
    return conn


def _rows(query: str, params: tuple = ()) -> list[dict]:
    try:
        with _connect() as conn:
            return [dict(r) for r in conn.execute(query, params).fetchall()]
    except Exception as exc:
        return [{"error": str(exc)}]


# ── static UI ─────────────────────────────────────────────────────────────────

UI_DIR = PROJECT_ROOT / "ui"
app.mount("/static", StaticFiles(directory=str(UI_DIR)), name="static")


@app.get("/", include_in_schema=False)
async def root():
    return FileResponse(str(UI_DIR / "index.html"))


# ── data endpoints ────────────────────────────────────────────────────────────

@app.get("/api/portfolio")
async def get_portfolio():
    from config import PORTFOLIO_FILE
    try:
        with open(PORTFOLIO_FILE, encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        return {"error": "Portfolio not initialized. Run: python main.py init"}


@app.get("/api/snapshots")
async def get_snapshots(limit: int = Query(60, ge=1, le=500)):
    rows = _rows(
        "SELECT * FROM portfolio_snapshots ORDER BY timestamp DESC LIMIT ?",
        (limit,),
    )
    return list(reversed(rows))


@app.get("/api/runs")
async def get_runs(limit: int = Query(20, ge=1, le=200)):
    return _rows(
        "SELECT * FROM agent_runs ORDER BY timestamp DESC LIMIT ?",
        (limit,),
    )


@app.get("/api/executions")
async def get_executions(limit: int = Query(50, ge=1, le=500)):
    return _rows(
        "SELECT * FROM executions ORDER BY timestamp DESC LIMIT ?",
        (limit,),
    )


@app.get("/api/traces")
async def get_traces(
    limit: int = Query(100, ge=1, le=500),
    cycle_id: str | None = Query(None),
):
    if cycle_id:
        return _rows(
            "SELECT * FROM decision_traces WHERE cycle_id = ? ORDER BY created_at ASC LIMIT ?",
            (cycle_id, limit),
        )
    return _rows(
        "SELECT * FROM decision_traces ORDER BY created_at DESC LIMIT ?",
        (limit,),
    )


@app.get("/api/positions")
async def get_positions(cycle_id: str | None = Query(None)):
    if cycle_id:
        return _rows(
            """
            SELECT p.* FROM positions p
            JOIN portfolio_snapshots s ON p.snapshot_id = s.id
            WHERE s.cycle_id = ? ORDER BY p.ticker ASC
            """,
            (cycle_id,),
        )
    return _rows(
        """
        SELECT p.* FROM positions p
        JOIN portfolio_snapshots s ON p.snapshot_id = s.id
        WHERE s.id = (SELECT MAX(id) FROM portfolio_snapshots)
        ORDER BY p.ticker ASC
        """,
    )


@app.get("/api/market-status")
async def get_market_status():
    return _rows("SELECT * FROM market_data_status ORDER BY ticker ASC")


@app.get("/api/config")
async def get_config():
    try:
        from config import (
            AGENT_BACKEND, AI_PROVIDER, EXECUTION_MODE,
            MCP_PROFILE, TARGET_ALLOCATION,
        )
        return {
            "ai_provider": AI_PROVIDER,
            "agent_backend": AGENT_BACKEND,
            "execution_mode": EXECUTION_MODE,
            "mcp_profile": MCP_PROFILE,
            "target_allocation": TARGET_ALLOCATION,
        }
    except Exception as exc:
        return {"error": str(exc)}


# ── streaming command runner ──────────────────────────────────────────────────

class RunRequest(BaseModel):
    strategy: str = "threshold"
    mode: str = "simulate"
    mcp: str = "none"
    profile: str | None = None


VALID_STEPS = {"observe", "decide", "execute", "audit", "run-cycle", "report", "init"}


@app.post("/api/run/{step}")
async def run_step(step: str, req: RunRequest = RunRequest()):
    if step not in VALID_STEPS:
        from fastapi import HTTPException
        raise HTTPException(status_code=400, detail=f"Unknown step '{step}'")

    if step in ("report", "init"):
        args = ["main.py", step]
    else:
        args = build_cycle_args(step, req.strategy, req.mode, req.mcp, req.profile)

    return StreamingResponse(
        stream_command(args),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )
