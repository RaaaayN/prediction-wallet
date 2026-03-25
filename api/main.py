"""FastAPI backend for the Prediction Wallet governed agent UI."""

from __future__ import annotations

import json
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
    from db.repository import get_snapshots as _get_snapshots
    return _get_snapshots(limit=limit)


@app.get("/api/runs")
async def get_runs(limit: int = Query(20, ge=1, le=200)):
    from db.repository import get_agent_runs
    return get_agent_runs(limit=limit)


@app.get("/api/executions")
async def get_executions(limit: int = Query(50, ge=1, le=500)):
    from db.repository import get_executions as _get_executions
    df = _get_executions(limit=limit)
    return df.to_dict(orient="records") if not df.empty else []


@app.get("/api/traces")
async def get_traces(
    limit: int = Query(100, ge=1, le=500),
    cycle_id: str | None = Query(None),
):
    from db.repository import get_decision_traces
    traces = get_decision_traces(limit=limit, cycle_id=cycle_id)
    return list(reversed(traces)) if cycle_id else traces  # cycle view: ASC; global: DESC


@app.get("/api/positions")
async def get_positions(cycle_id: str | None = Query(None)):
    if cycle_id:
        from db.repository import get_positions_by_cycle
        return get_positions_by_cycle(cycle_id=cycle_id)
    from db.repository import get_latest_positions
    return get_latest_positions()


@app.get("/api/market-status")
async def get_market_status():
    from db.repository import get_market_data_status
    return get_market_data_status()


@app.get("/api/backtest")
async def get_backtest(days: int = Query(90, ge=10, le=365)):
    from engine.backtest import run_strategy_comparison
    results = run_strategy_comparison(days=days)
    if results is None:
        from fastapi import HTTPException
        raise HTTPException(status_code=503, detail="Insufficient market data for backtest.")
    return results


@app.get("/api/config")
async def get_config():
    try:
        from config import (
            AGENT_BACKEND, AI_PROVIDER, EXECUTION_MODE, TARGET_ALLOCATION,
        )
        return {
            "ai_provider": AI_PROVIDER,
            "agent_backend": AGENT_BACKEND,
            "execution_mode": EXECUTION_MODE,
            "target_allocation": TARGET_ALLOCATION,
        }
    except Exception as exc:
        return {"error": str(exc)}


# ── streaming command runner ──────────────────────────────────────────────────

class RunRequest(BaseModel):
    strategy: str = "threshold"
    mode: str = "simulate"
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
        args = build_cycle_args(step, req.strategy, req.mode, req.profile)

    return StreamingResponse(
        stream_command(args),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )
