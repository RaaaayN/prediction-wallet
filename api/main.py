"""FastAPI backend for the Prediction Wallet governed agent UI."""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from time import perf_counter

from fastapi import Body, FastAPI, Query, Request, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
from typing import Any

PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from api.runner import build_cycle_args, stream_command
from api.auth import Role, User, get_current_user, requires_role
from api.middle_office import router as middle_office_router
from services.health_service import HealthService
from api.models import (
    ConfigResponse, PortfolioResponse, PositionRow, 
    MarketStatusResponse, OnboardingStatusResponse,
    InstrumentRow, TradingCoreOrderRow, TradingCoreExecutionRow,
    TradingCorePositionRow, CashMovementRow, CashMovementRequest,
    SettingsResponse, SettingsUpdateRequest,
    StrategyInfo, ExperimentRow, ReportInfo
)
from config import ALLOWED_ORIGINS
from utils.telemetry import trace_request

app = FastAPI(title="Prediction Wallet API", version="1.0.0")

app.include_router(middle_office_router)

@app.get("/api/health")
async def health_check():
    """Consolidated health check for monitoring systems."""
    svc = HealthService()
    health = svc.get_full_health()
    if health["status"] == "down":
        from fastapi.responses import JSONResponse
        return JSONResponse(content=health, status_code=503)
    return health

@app.get("/api/ready")
async def readiness_check():
    """Quick check if the API and database are reachable."""
    svc = HealthService()
    db_health = svc.check_database()
    if db_health["status"] == "down":
        from fastapi import HTTPException
        raise HTTPException(status_code=503, detail="Database unreachable")
    return {"status": "ready"}

@app.get("/api/status")
async def get_system_status(_: User = Depends(requires_role([Role.VIEWER, Role.TRADER, Role.ADMIN]))):
    """Consolidated system status dashboard data."""
    from db.repository import (
        get_connection, q, get_latest_reconciliation_run, 
        get_nav_history
    )
    from services.health_service import HealthService
    
    health_svc = HealthService()
    
    # 1. Last Rebalance
    with get_connection() as conn:
        last_run = conn.execute(q("SELECT * FROM agent_runs ORDER BY timestamp DESC LIMIT 1")).fetchone()
        
    # 2. Last Reconciliation
    last_recon = get_latest_reconciliation_run()
    
    # 3. Last NAV
    nav_hist = get_nav_history(limit=1)
    last_nav = nav_hist[0] if nav_hist else None
    
    # 4. Backup Status
    from config import REPORTS_DIR
    backup_dir = Path(REPORTS_DIR) / "backups"
    backups = sorted(list(backup_dir.glob("snapshot_*.db"))) if backup_dir.exists() else []
    
    return {
        "health": health_svc.get_full_health(),
        "last_rebalance": dict(last_run) if last_run else None,
        "last_reconciliation": last_recon,
        "last_nav": last_nav,
        "backups": {
            "count": len(backups),
            "latest": backups[-1].name if backups else None
        }
    }

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_methods=["*"],
    allow_headers=["*"],
)


def _prefetch_price_history(tickers: list[str], *, min_days: int, period: str = "2y") -> None:
    """Warm the market cache for tickers when OHLCV is missing (yfinance on first hit)."""
    if not tickers:
        return
    from services.market_service import MarketService

    svc = MarketService()
    need: list[str] = []
    for t in tickers:
        hist = svc.get_historical(t, days=min_days + 90)
        if hist is None or hist.empty or "Close" not in hist.columns:
            need.append(t)
    if not need:
        return
    try:
        svc.fetch_and_store(need, period=period, force=False)
    except Exception:
        pass


@app.middleware("http")
async def request_logging_middleware(request: Request, call_next):
    """Structured JSON logging and OTel tracing for each request."""
    start_time = perf_counter()
    method = request.method
    path = request.url.path
    
    with trace_request(method, path):
        response = await call_next(request)
        duration_ms = round((perf_counter() - start_time) * 1000, 2)
        
        # Structured log line
        log_record = {
            "type": "access",
            "method": method,
            "path": path,
            "status": response.status_code,
            "duration_ms": duration_ms,
            "client": request.client.host if request.client else "unknown"
        }
        print(json.dumps(log_record))
        
        return response


class IdeaGenerationRequest(BaseModel):
    cycle_id: str | None = None
    max_candidates: int = 3


class IdeaReviewRequest(BaseModel):
    review_status: str


class IdeaPromoteRequest(BaseModel):
    status: str


# ── static UI ─────────────────────────────────────────────────────────────────

FRONTEND_DIST = PROJECT_ROOT / "frontend" / "dist"
FRONTEND_INDEX = FRONTEND_DIST / "index.html"
FRONTEND_ASSETS = FRONTEND_DIST / "assets"
LEGACY_UI_DIR = PROJECT_ROOT / "ui"
UI_REACT_DIST = PROJECT_ROOT / "ui-react" / "dist"
UI_REACT_INDEX = UI_REACT_DIST / "index.html"
UI_REACT_ASSETS = UI_REACT_DIST / "assets"

if LEGACY_UI_DIR.is_dir():
    app.mount("/static", StaticFiles(directory=str(LEGACY_UI_DIR)), name="static")
if FRONTEND_ASSETS.is_dir():
    app.mount("/assets", StaticFiles(directory=str(FRONTEND_ASSETS)), name="vite_assets")
elif UI_REACT_ASSETS.is_dir():
    app.mount("/assets", StaticFiles(directory=str(UI_REACT_ASSETS)), name="react_assets")


@app.get("/", include_in_schema=False)
async def root():
    if FRONTEND_INDEX.is_file():
        return FileResponse(str(FRONTEND_INDEX))
    if UI_REACT_INDEX.is_file():
        return FileResponse(str(UI_REACT_INDEX))
    legacy = LEGACY_UI_DIR / "index.html"
    if legacy.is_file():
        return FileResponse(str(legacy))
    return {
        "error": "No UI found. Build the Vite app (cd frontend && npm ci && npm run build) "
        "or add ui/index.html / ui-react/dist."
    }


# ── data endpoints ────────────────────────────────────────────────────────────

@app.get("/api/portfolio", response_model=PortfolioResponse)
async def get_portfolio(_: User = Depends(get_current_user)):
    from services.execution_service import ExecutionService
    from services.market_service import MarketService
    try:
        svc = ExecutionService()
        data = svc.load_portfolio()
        tickers = list(data.get("positions", {}).keys())
        prices = MarketService().get_latest_prices(tickers) if tickers else {}
        snapshot = svc.portfolio_snapshot(prices)
        
        initial_capital = svc.runtime_context.initial_capital
        
        from db.repository import get_snapshots
        db_snapshots = get_snapshots(limit=100)
        if db_snapshots:
            history = [{"date": s["timestamp"], "total_value": s["total_value"]} for s in db_snapshots]
        else:
            history = data.get("history", [])

        total_value = snapshot.get("total_value") or (history[-1]["total_value"] if history else data.get("cash", initial_capital))
        pnl_dollars = total_value - initial_capital
        
        data.update(snapshot)
        data["total_value"] = total_value
        data["peak_value"] = data.get("peak_value", total_value)
        data["target_weights"] = snapshot.get("target_weights", svc.runtime_context.target_allocation)
        data.setdefault("pnl_dollars", pnl_dollars)
        data.setdefault("pnl_pct", pnl_dollars / initial_capital if initial_capital > 0 else 0.0)
        return data
    except Exception as exc:
        from fastapi import HTTPException
        if "not initialized" in str(exc).lower():
             raise HTTPException(status_code=404, detail="Portfolio not initialized. Run: python main.py init")
        raise HTTPException(status_code=500, detail=str(exc))


@app.get("/api/snapshots")
async def get_snapshots(limit: int = Query(60, ge=1, le=500), _: User = Depends(get_current_user)):
    from db.repository import get_snapshots as _get_snapshots
    return _get_snapshots(limit=limit)


@app.get("/api/runs")
async def get_runs(limit: int = Query(20, ge=1, le=200), _: User = Depends(get_current_user)):
    from db.repository import get_agent_runs
    return get_agent_runs(limit=limit)


@app.get("/api/executions")
async def get_executions(limit: int = Query(50, ge=1, le=500), _: User = Depends(get_current_user)):
    from db.repository import get_executions as _get_executions
    df = _get_executions(limit=limit)
    return df.to_dict(orient="records") if not df.empty else []


@app.get("/api/audit/traces")
async def get_traces_api(
    limit: int = Query(100, ge=1, le=500),
    cycle_id: str | None = Query(None),
    _: User = Depends(get_current_user),
):
    from db.repository import get_decision_traces
    traces = get_decision_traces(limit=limit, cycle_id=cycle_id)
    return {"traces": list(reversed(traces)) if cycle_id else traces}


@app.get("/api/audit/governance")
async def get_governance_api(profile: str | None = Query(None), _: User = Depends(get_current_user)):
    from services.governance_service import GovernanceService
    gov = GovernanceService(profile_name=profile)
    return gov.generate_governance_report()


@app.get("/api/reports", response_model=list[ReportInfo])
async def list_reports(profile: str | None = Query(None), _: User = Depends(get_current_user)):
    from settings import settings
    import os
    from datetime import datetime

    # Resolve reports directory
    if profile:
        reports_dir = Path("data/profiles") / profile / "reports"
    else:
        profile_name = os.getenv("PORTFOLIO_PROFILE") or settings.portfolio_profile
        reports_dir = Path("data/profiles") / profile_name / "reports"

    if not reports_dir.exists():
        return []

    reports = []
    for f in reports_dir.glob("*.pdf"):
        stat = f.stat()
        reports.append({
            "filename": f.name,
            "size_bytes": stat.st_size,
            "created_at": datetime.fromtimestamp(stat.st_mtime).isoformat(),
            "url": f"/api/reports/download/{f.name}?profile={profile or ''}"
        })

    # Sort by date descending
    reports.sort(key=lambda x: x["created_at"], reverse=True)
    return reports


@app.get("/api/reports/download/{filename}")
async def download_report(filename: str, profile: str | None = Query(None), _: User = Depends(get_current_user)):
    from settings import settings
    import os

    if profile:
        reports_dir = Path("data/profiles") / profile / "reports"
    else:
        profile_name = os.getenv("PORTFOLIO_PROFILE") or settings.portfolio_profile
        reports_dir = Path("data/profiles") / profile_name / "reports"

    file_path = reports_dir / filename
    if not file_path.exists():
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="Report not found")

    return FileResponse(str(file_path), media_type="application/pdf", filename=filename)



class BacktestRequest(BaseModel):
    strategy_name: str
    days: int
    run_name: str | None = None
    strategy_params: dict[str, Any] = Field(default_factory=dict)


class RunRequest(BaseModel):
    strategy: str = "threshold"
    mode: str = "simulate"
    profile: str | None = None
    initial_capital: float | None = None


@app.post("/api/runner/backtest")
async def run_backtest_api(req: BacktestRequest, profile: str | None = Query(None), _: User = Depends(get_current_user)):
    from engine.backtest_v2 import EventDrivenBacktester
    from services.mlflow_service import MLflowService
    import mlflow

    # Safety: End any active runs that might have leaked from previous crashes on this thread
    try:
        if mlflow.active_run():
            mlflow.end_run()
    except Exception:
        pass

    # Use profile-specific data for the simulation with custom parameter overrides
    tester = EventDrivenBacktester(days=req.days, profile_name=profile)
    result = tester.run(
        strategy_type=req.strategy_name, 
        strategy_params=req.strategy_params
    )

    # Log to MLflow
    mlflow_svc = MLflowService()
    
    # Merge for tracking
    tracking_params = {
        "strategy_type": req.strategy_name,
        "days": req.days,
        "profile": profile or "balanced"
    }
    tracking_params.update(req.strategy_params)
    
    run_name = req.run_name or f"{req.strategy_name}_{req.days}d"
    mlflow_svc.log_backtest(result, tracking_params, run_name=run_name)

    # Convert result to dict for JSON
    return {
        "strategy_name": result.strategy_name,
        "metrics": result.metrics,
        "history": result.history,
        "trades": result.trades,
        "risk_violations": result.risk_violations,
        "data_hash": result.data_hash
    }


@app.get("/api/positions", response_model=list[PositionRow])
async def get_positions(cycle_id: str | None = Query(None), _: User = Depends(get_current_user)):
    from db.repository import get_positions_by_cycle, get_latest_positions, get_trading_core_positions
    from services.execution_service import ExecutionService
    from services.market_service import MarketService

    if cycle_id:
        return get_positions_by_cycle(cycle_id=cycle_id)
    
    # 1. Try modern position_ledger (canonical truth)
    tc_positions = get_trading_core_positions()
    
    # 2. Try legacy positions table as fallback
    legacy_positions = get_latest_positions() if not tc_positions else []
    
    # 3. Last fallback: live JSON (useful right after init)
    svc = ExecutionService()
    try:
        portfolio = svc.load_portfolio()
    except Exception:
        portfolio = {}

    positions_map = portfolio.get("positions", {}) or {}
    
    # Normalize data source
    if tc_positions:
        # Map Trading Core positions (symbol -> qty)
        positions_map = {p["symbol"]: p["quantity"] for p in tc_positions}
    elif legacy_positions:
        # Map legacy DB positions
        positions_map = {p["ticker"]: p["quantity"] for p in legacy_positions}

    if not positions_map:
        return []

    # Compute fresh snapshot for weights/drifts
    tickers = list(positions_map.keys())
    prices = MarketService().get_latest_prices(tickers)
    snapshot = svc.portfolio_snapshot(prices)
    current_weights = snapshot.get("current_weights", {})
    target_weights = snapshot.get("target_weights", svc.runtime_context.target_allocation)
    drifts = snapshot.get("weight_deviation", {})
    total_value = snapshot.get("total_value", 0.0) or 0.0
    position_sides = portfolio.get("position_sides", {}) or {}
    position_ideas = portfolio.get("position_ideas", {}) or {}

    rows = []
    for ticker in sorted(tickers):
        quantity = float(positions_map.get(ticker, 0.0))
        price = float(prices.get(ticker, 0.0))
        value = quantity * price
        
        # Determine side: prefer ledger if available, else JSON, else infer
        side = "long"
        if tc_positions:
             # In v1 TC, quantity < 0 implies short
             side = "short" if quantity < 0 else "long"
        else:
             side = position_sides.get(ticker, "short" if quantity < 0 else "long")

        rows.append(
            {
                "ticker": ticker,
                "quantity": quantity,
                "price": price,
                "value": value,
                "weight": float(current_weights.get(ticker, 0.0)),
                "target_weight": float(target_weights.get(ticker, 0.0)),
                "drift": float(drifts.get(ticker, 0.0)),
                "side": side,
                "idea_id": position_ideas.get(ticker),
                "gross_exposure": abs(value) / total_value if total_value > 0 else 0.0,
                "net_exposure": value / total_value if total_value > 0 else 0.0,
            }
        )
    return rows


@app.get("/api/market-status", response_model=MarketStatusResponse)
async def get_market_status(_: User = Depends(get_current_user)):
    from db.repository import get_market_data_status

    rows = get_market_data_status()
    return {
        "tickers": [row["ticker"] for row in rows],
        "last_refresh": {row["ticker"]: row["refreshed_at"] for row in rows},
    }


@app.get("/api/market/snapshot")
async def get_market_snapshot(profile: str | None = Query(None), _: User = Depends(get_current_user)):
    from services.market_service import MarketService
    from db.repository import get_market_data_status
    
    svc = MarketService(profile_name=profile)
    tickers = list(svc.runtime_context.target_allocation.keys())
    prices = svc.get_latest_prices(tickers)
    refresh_rows = get_market_data_status()
    
    # Map to frontend expected structure
    refresh_status = []
    for row in refresh_rows:
        refresh_status.append({
            "ticker": row["ticker"],
            "refreshed_at": row["refreshed_at"],
            "success": bool(row["success"])
        })
        
    return {
        "prices": prices,
        "metrics": {}, # Add aggregate metrics if available
        "refresh_status": refresh_status
    }


@app.get("/api/market/sentiment")
async def get_market_sentiment(profile: str | None = Query(None), _: User = Depends(get_current_user)):
    from services.news_service import NewsSentimentService
    from services.market_service import MarketService
    
    svc = MarketService(profile_name=profile)
    tickers = list(svc.runtime_context.target_allocation.keys())
    
    # Use mock for speed if no real keys
    news_svc = NewsSentimentService()
    results = []
    # Limit to top 8 tickers to avoid timeout
    for t in tickers[:8]:
        results.append(news_svc.get_ticker_sentiment(t))
    
    return results


@app.post("/api/market/refresh")
async def refresh_market_data(profile: str | None = Query(None), _: User = Depends(requires_role([Role.ADMIN, Role.TRADER]))):
    from services.market_service import MarketService
    svc = MarketService(profile_name=profile)
    tickers = list(svc.runtime_context.target_allocation.keys())
    if not tickers:
        return {"ok": True, "message": "No tickers to refresh."}
    
    svc.fetch_and_store(tickers, force=True)
    return {"ok": True, "message": f"Refreshed {len(tickers)} tickers for {profile or 'active profile'}."}

# ── trading-core ──────────────────────────────────────────────────────────────

@app.get("/api/trading-core/instruments", response_model=list[InstrumentRow])
async def get_tc_instruments(_: User = Depends(requires_role([Role.VIEWER, Role.TRADER, Role.ADMIN]))):
    """List all known instruments in the Trading Core."""
    from db.repository import get_trading_core_instruments
    return get_trading_core_instruments()


@app.get("/api/trading-core/positions", response_model=list[TradingCorePositionRow])
async def get_tc_positions(_: User = Depends(requires_role([Role.VIEWER, Role.TRADER, Role.ADMIN]))):
    """Get active aggregate positions from the Trading Core ledger."""
    from db.repository import get_trading_core_positions
    return get_trading_core_positions()


@app.get("/api/trading-core/orders", response_model=list[TradingCoreOrderRow])
async def get_tc_orders(
    cycle_id: str | None = Query(None),
    limit: int = 100,
    _: User = Depends(requires_role([Role.VIEWER, Role.TRADER, Role.ADMIN])),
):
    """Get recent orders, optionally filtered by cycle_id."""
    from db.repository import get_trading_core_orders
    return get_trading_core_orders(cycle_id=cycle_id, limit=limit)


@app.get("/api/trading-core/executions", response_model=list[TradingCoreExecutionRow])
async def get_tc_executions(
    cycle_id: str | None = Query(None),
    order_id: str | None = Query(None),
    limit: int = 100,
    _: User = Depends(requires_role([Role.VIEWER, Role.TRADER, Role.ADMIN])),
):
    """Get recent executions, optionally filtered by cycle_id or order_id."""
    from db.repository import get_trading_core_executions
    return get_trading_core_executions(cycle_id=cycle_id, order_id=order_id, limit=limit)


@app.get("/api/trading-core/cash-movements", response_model=list[CashMovementRow])
async def get_tc_cash_movements(
    cycle_id: str | None = Query(None),
    limit: int = 100,
    _: User = Depends(requires_role([Role.VIEWER, Role.TRADER, Role.ADMIN])),
):
    """Get cash movement history from the Trading Core ledger."""
    from db.repository import get_trading_core_cash_movements
    return get_trading_core_cash_movements(cycle_id=cycle_id, limit=limit)


@app.post("/api/trading-core/cash-movements")
async def create_tc_cash_movement(
    req: CashMovementRequest,
    profile: str | None = Query(None),
    _: User = Depends(requires_role([Role.ADMIN]))
):
    from db.repository import save_cash_movement
    from utils.time import utc_now_iso
    import uuid
    
    movement = {
        "cash_movement_id": f"manual_{uuid.uuid4().hex[:8]}",
        "movement_type": req.movement_type,
        "amount": req.amount,
        "currency": "USD",
        "created_at": utc_now_iso(),
        "description": req.description or "Manual cash movement via UI"
    }
    save_cash_movement(movement, profile_name=profile)
    return {"ok": True, "message": f"Cash movement of {req.amount} recorded."}



@app.get("/api/backtest")
async def get_backtest(
    strategy: str = Query("threshold"),
    days: int = Query(90, ge=10, le=365),
    profile: str | None = Query(None),
    _: User = Depends(get_current_user)
):
    from engine.backtest_v2 import EventDrivenBacktester
    from services.execution_service import ExecutionService
    
    svc = ExecutionService(profile_name=profile)
    tickers = list(svc.runtime_context.target_allocation.keys())
    if tickers:
        _prefetch_price_history(tickers, min_days=days + 30)
    
    tester = EventDrivenBacktester(days=days, profile_name=profile)
    res = tester.run(strategy_type=strategy)
    
    # Return full report including history for charting
    return {
        "strategy": strategy,
        "days": days,
        "metrics": res.metrics,
        "history": res.history,
        "data_hash": res.data_hash
    }


@app.post("/api/runner/observe")
async def observe_api(req: RunRequest, profile: str | None = Query(None), _: User = Depends(get_current_user)):
    from agents.portfolio_agent import PortfolioAgentService
    svc = PortfolioAgentService(profile_name=profile)
    return svc.observe(strategy_name=req.strategy, execution_mode=req.mode)


@app.get("/api/correlation")
async def get_correlation(days: int = Query(90, ge=10, le=365), _: User = Depends(get_current_user)):
    import pandas as pd
    from engine.performance import rolling_correlation
    from services.execution_service import ExecutionService
    from services.market_service import MarketService
    try:
        svc = ExecutionService()
        portfolio = svc.load_portfolio()
    except Exception:
        from fastapi import HTTPException
        raise HTTPException(status_code=503, detail="Portfolio not initialized. Run: python main.py init")
    tickers = list(portfolio.get("positions", {}).keys())
    if not tickers:
        return {
            "tickers": [],
            "matrix": [],
            "days": days,
            "n_obs": 0,
            "detail": "Portfolio has no holdings yet. Run: uv run python main.py init (requires yfinance).",
        }
    _prefetch_price_history(tickers, min_days=days)
    svc = MarketService()
    price_series: dict[str, "pd.Series"] = {}
    for ticker in tickers:
        hist = svc.get_historical(ticker, days=days)
        if not hist.empty and "Close" in hist.columns:
            price_series[ticker] = hist["Close"]
    if len(price_series) < 2:
        from fastapi import HTTPException
        raise HTTPException(
            status_code=503,
            detail="Insufficient market data for correlation after prefetch. Check network / yfinance.",
        )
    prices_df = pd.DataFrame(price_series).dropna()
    returns_df = prices_df.pct_change().dropna()
    corr = rolling_correlation(returns_df, window=min(days, len(returns_df)))
    if corr.empty:
        from fastapi import HTTPException
        raise HTTPException(status_code=503, detail="Not enough return data to compute correlation.")
    return {
        "tickers": list(corr.columns),
        "matrix": [[round(v, 4) for v in row] for row in corr.values.tolist()],
        "days": days,
        "n_obs": len(returns_df),
    }


@app.get("/api/stress")
async def get_stress(_: User = Depends(get_current_user)):
    from engine.stress_testing import run_stress_test_v2
    from services.execution_service import ExecutionService
    from services.market_service import MarketService
    try:
        svc = ExecutionService()
        portfolio = svc.load_portfolio()
    except Exception:
        from fastapi import HTTPException
        raise HTTPException(status_code=503, detail="Portfolio not initialized. Run: python main.py init")
    tickers = list(portfolio.get("positions", {}).keys())
    if tickers:
        _prefetch_price_history(tickers, min_days=30)
    prices = MarketService().get_latest_prices(tickers)
    return run_stress_test_v2(portfolio, prices)


@app.get("/api/config", response_model=ConfigResponse)
async def get_config(_: User = Depends(get_current_user)):
    try:
        from services.execution_service import ExecutionService
        svc = ExecutionService()
        ctx = svc.runtime_context
        from config import AGENT_BACKEND, AI_PROVIDER, EXECUTION_MODE
        return {
            "ai_provider": AI_PROVIDER,
            "agent_backend": AGENT_BACKEND,
            "execution_mode": EXECUTION_MODE,
            "target_allocation": ctx.target_allocation,
            "hedge_fund_enabled": bool(ctx.hedge_fund_profile),
        }
    except Exception as exc:
        from fastapi import HTTPException
        raise HTTPException(status_code=500, detail=str(exc))


# ── onboarding ────────────────────────────────────────────────────────────────

@app.get("/api/onboarding/status", response_model=OnboardingStatusResponse)
async def onboarding_status(_: User = Depends(get_current_user)):
    from services.execution_service import ExecutionService
    try:
        svc = ExecutionService()
        data = svc.load_portfolio()
        positions = data.get("positions", {})
        return {
            "needs_onboarding": len(positions) == 0,
            "profile": svc.runtime_context.profile_name,
            "positions_count": len(positions),
        }
    except Exception:
        import os
        return {"needs_onboarding": True, "profile": os.getenv("PORTFOLIO_PROFILE", "balanced"), "positions_count": 0}


@app.get("/api/onboarding/profiles")
async def onboarding_profiles(_: User = Depends(get_current_user)):
    from portfolio_loader import load_profile
    from runtime_context import build_runtime_context

    PROFILE_METADATA = {
        "balanced": {
            "label": "Balanced Fund",
            "risk_level": "Medium",
            "strategy_type": "Multi-Asset Balanced",
            "typical_aum": "$100K+",
            "description": "Diversified multi-asset portfolio blending equities, bonds, and crypto for risk-adjusted returns.",
        },
        "conservative": {
            "label": "Conservative Income",
            "risk_level": "Low",
            "strategy_type": "Bond-Tilted Conservative",
            "typical_aum": "$250K+",
            "description": "Capital preservation focus with heavy allocation to investment-grade bonds and blue-chip equities.",
        },
        "growth": {
            "label": "Growth Equity",
            "risk_level": "High",
            "strategy_type": "Equity Growth",
            "typical_aum": "$100K+",
            "description": "High-conviction equity strategy targeting long-term capital appreciation via secular growth themes.",
        },
        "crypto_heavy": {
            "label": "Digital Asset Blend",
            "risk_level": "Very High",
            "strategy_type": "Digital Asset Blend",
            "typical_aum": "$50K+",
            "description": "Aggressive exposure to digital assets alongside tech equities for maximum upside potential.",
        },
        "long_short_equity": {
            "label": "Long/Short Equity",
            "risk_level": "High",
            "strategy_type": "Long/Short Equity Hedge Fund",
            "typical_aum": "$1M+",
            "description": "Institutional-grade L/S strategy with gross/net exposure controls, sleeves, and alpha generation via shorting.",
        },
    }

    result = []
    for name, meta in PROFILE_METADATA.items():
        try:
            profile = load_profile(name)
            
            # Check for existing data
            has_data = False
            try:
                ctx = build_runtime_context(name, ensure_storage=False)
                p_path = Path(ctx.portfolio_file)
                if p_path.exists():
                    with open(p_path, "r", encoding="utf-8") as f:
                        data = json.load(f)
                        # Has data if it has positions or history
                        has_data = bool(data.get("positions")) or len(data.get("history", [])) > 0
            except Exception:
                pass

            result.append({
                "name": name,
                "label": meta["label"],
                "description": meta["description"],
                "risk_level": meta["risk_level"],
                "strategy_type": meta["strategy_type"],
                "typical_aum": meta["typical_aum"],
                "initial_capital": profile.get("initial_capital", 100000),
                "tickers": list(profile.get("target_allocation", {}).keys()),
                "has_existing_data": has_data,
            })
        except Exception:
            pass
    return result


@app.post("/api/onboarding/resume")
async def resume_fund(req: RunRequest, _: User = Depends(get_current_user)):
    if not req.profile:
        from fastapi import HTTPException
        raise HTTPException(status_code=400, detail="Profile name required")
    
    from dotenv import set_key
    from settings import settings
    
    # Persist the choice
    set_key(".env", "PORTFOLIO_PROFILE", req.profile)
    settings.portfolio_profile = req.profile
    
    return {"ok": True, "message": f"Fund {req.profile} resumed."}


@app.get("/api/strategies", response_model=list[StrategyInfo])
async def get_strategies(_: User = Depends(get_current_user)):
    from portfolio_loader import get_active_profile
    from strategies import STRATEGY_REGISTRY

    profile = get_active_profile()
    active_strategy = profile.get("strategy_name", "threshold")

    result = []

    # 1. Threshold
    result.append({
        "name": "threshold",
        "description": "Pure quantitative rebalancing based on drift from target allocation.",
        "is_active": active_strategy == "threshold",
        "params": {
            "drift_threshold": profile.get("drift_threshold", 0.05),
            "per_asset_threshold": profile.get("per_asset_threshold", {})
        }
    })

    # 2. Ensemble
    result.append({
        "name": "ensemble",
        "description": "Quantitative Drift + NLP Sentiment overlay using FinBERT.",
        "is_active": active_strategy == "ensemble",
        "params": {
            "drift_threshold": profile.get("drift_threshold", 0.05),
            "sentiment_weight": profile.get("sentiment_weight", 0.2)
        }
    })

    # 3. Calendar
    result.append({
        "name": "calendar",
        "description": "Time-based rebalancing (Weekly/Monthly) with a secondary drift check.",
        "is_active": active_strategy == "calendar",
        "params": {
            "frequency": profile.get("calendar_frequency", "weekly"),
            "drift_threshold": profile.get("drift_threshold", 0.01)
        }
    })

    return result


@app.post("/api/strategies/params")
async def update_strategy_params(
    strategy: str = Query(...), 
    params: dict = Body(...), 
    _: User = Depends(requires_role([Role.ADMIN]))
):
    import os
    import yaml
    from portfolio_loader import load_profile
    from settings import settings
    
    profile_name = os.getenv("PORTFOLIO_PROFILE") or settings.portfolio_profile
    profile_path = Path("profiles") / f"{profile_name}.yaml"
    
    if not profile_path.exists():
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="Active profile file not found.")
        
    with open(profile_path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f)
        
    # Update common params (top level in YAML)
    if "drift_threshold" in params:
        data["drift_threshold"] = float(params["drift_threshold"])
    
    # Update strategy specific
    if strategy == "ensemble" and "sentiment_weight" in params:
        data["sentiment_weight"] = float(params["sentiment_weight"])
    
    if strategy == "calendar" and "frequency" in params:
        data["calendar_frequency"] = str(params["frequency"])
        
    with open(profile_path, "w", encoding="utf-8") as f:
        yaml.safe_dump(data, f)
        
    return {"ok": True, "message": f"Parameters for {strategy} updated in {profile_name}.yaml"}


@app.get("/api/experiments", response_model=list[ExperimentRow])
async def get_experiments(_: User = Depends(get_current_user)):
    from services.mlflow_service import MLflowService
    import mlflow
    
    try:
        # Initialize service to set correct tracking URI and ensure env consistency
        MLflowService()
        
        all_runs = []
        experiments = mlflow.search_experiments()
        for exp in experiments:
            runs = mlflow.search_runs(experiment_ids=[exp.experiment_id])
            for _, run in runs.iterrows():
                # Convert MLflow run row to ExperimentRow
                all_runs.append({
                    "run_id": run["run_id"],
                    "experiment_id": exp.experiment_id,
                    "name": run.get("tags.mlflow.runName", "Unnamed Run"),
                    "status": run["status"],
                    "start_time": run["start_time"].isoformat() if hasattr(run["start_time"], "isoformat") else str(run["start_time"]),
                    "end_time": run["end_time"].isoformat() if hasattr(run["end_time"], "isoformat") and run["end_time"] else None,
                    "metrics": {k.replace("metrics.", ""): v for k, v in run.items() if k.startswith("metrics.")},
                    "params": {k.replace("params.", ""): str(v) for k, v in run.items() if k.startswith("params.")}
                })
        
        # Sort by start time descending
        all_runs.sort(key=lambda x: x["start_time"], reverse=True)
        return all_runs[:50]
    except Exception:
        return []


@app.post("/api/experiments/{run_id}/deploy")
async def deploy_experiment_run(run_id: str, _: User = Depends(requires_role([Role.ADMIN]))):
    """Import parameters from an MLflow run and apply them to the active profile."""
    from services.mlflow_service import MLflowService
    import yaml
    import os
    from settings import settings
    
    try:
        svc = MLflowService()
        params = svc.get_run_params(run_id)
        
        # Strategy type is stored as a param usually
        strat_type = params.get("strategy_type") or "threshold"
        
        profile_name = os.getenv("PORTFOLIO_PROFILE") or settings.portfolio_profile
        profile_path = Path("profiles") / f"{profile_name}.yaml"
        
        if not profile_path.exists():
            from fastapi import HTTPException
            raise HTTPException(status_code=404, detail="Active profile file not found.")
            
        with open(profile_path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)
            
        # Update strategy name and pertinent params
        data["strategy_name"] = strat_type
        
        # Mapping MLflow string params back to YAML types
        if "drift_threshold" in params:
            data["drift_threshold"] = float(params["drift_threshold"])
        if "sentiment_weight" in params:
            data["sentiment_weight"] = float(params["sentiment_weight"])
        if "calendar_frequency" in params:
            data["calendar_frequency"] = params["calendar_frequency"]
            
        with open(profile_path, "w", encoding="utf-8") as f:
            yaml.safe_dump(data, f)
            
        return {
            "ok": True, 
            "message": f"Successfully deployed model from run {run_id[:8]} to profile {profile_name}",
            "applied_params": {k: v for k, v in params.items() if k in ["strategy_type", "drift_threshold", "sentiment_weight", "calendar_frequency"]}
        }
    except Exception as e:
        from fastapi import HTTPException
        raise HTTPException(status_code=500, detail=f"Deployment failed: {str(e)}")


# ── events ───────────────────────────────────────────────────────────────────


@app.get("/api/settings", response_model=SettingsResponse)
async def get_app_settings(_: User = Depends(get_current_user)):
    from settings import settings
    from portfolio_loader import get_active_profile
    profile = get_active_profile()
    
    return {
        "ai_provider": settings.ai_provider,
        "gemini_model": settings.gemini_model,
        "claude_model": settings.claude_model,
        "has_gemini_key": bool(settings.gemini_api_key),
        "has_anthropic_key": bool(settings.anthropic_api_key),
        "execution_mode": settings.execution_mode,
        "agent_backend": settings.agent_backend,
        "trading_core_enabled": settings.trading_core_enabled,
        "portfolio_profile": settings.portfolio_profile,
        "max_trades_per_cycle": settings.max_trades_per_cycle,
        "max_order_fraction_of_portfolio": settings.max_order_fraction_of_portfolio,
        "benchmark_ticker": settings.benchmark_ticker,
        "market_data_ttl_seconds": settings.market_data_ttl_seconds,
        "risk_free_rate": settings.risk_free_rate,
        # Profile specific
        "drift_threshold": profile.get("drift_threshold", 0.05),
        "kill_switch_drawdown": profile.get("kill_switch_drawdown", 0.10),
    }


@app.post("/api/settings")
async def update_app_settings(req: SettingsUpdateRequest, _: User = Depends(requires_role([Role.ADMIN]))):
    try:
        import os
        import yaml
        from dotenv import set_key
        from settings import settings
        from portfolio_loader import load_profile
        
        env_file = ".env"
        
        # Update .env for global settings
        if req.ai_provider is not None:
            set_key(env_file, "AI_PROVIDER", req.ai_provider)
        if req.gemini_model is not None:
            set_key(env_file, "GEMINI_MODEL", req.gemini_model)
        if req.claude_model is not None:
            set_key(env_file, "CLAUDE_MODEL", req.claude_model)
        if req.gemini_api_key is not None:
            set_key(env_file, "GEMINI_API_KEY", req.gemini_api_key)
        if req.anthropic_api_key is not None:
            set_key(env_file, "ANTHROPIC_API_KEY", req.anthropic_api_key)
        if req.execution_mode is not None:
            set_key(env_file, "EXECUTION_MODE", req.execution_mode)
        if req.agent_backend is not None:
            set_key(env_file, "AGENT_BACKEND", req.agent_backend)
        if req.trading_core_enabled is not None:
            set_key(env_file, "TRADING_CORE_ENABLED", str(req.trading_core_enabled).lower())
        if req.portfolio_profile is not None:
            set_key(env_file, "PORTFOLIO_PROFILE", req.portfolio_profile)
            settings.portfolio_profile = req.portfolio_profile
        if req.max_trades_per_cycle is not None:
            set_key(env_file, "MAX_TRADES_PER_CYCLE", str(req.max_trades_per_cycle))
        if req.max_order_fraction_of_portfolio is not None:
            set_key(env_file, "MAX_ORDER_FRACTION_OF_PORTFOLIO", str(req.max_order_fraction_of_portfolio))
        if req.benchmark_ticker is not None:
            set_key(env_file, "BENCHMARK_TICKER", req.benchmark_ticker)
        if req.market_data_ttl_seconds is not None:
            set_key(env_file, "MARKET_DATA_TTL_SECONDS", str(req.market_data_ttl_seconds))
        if req.risk_free_rate is not None:
            set_key(env_file, "RISK_FREE_RATE", str(req.risk_free_rate))

        # Update profile YAML for risk settings
        if req.drift_threshold is not None or req.kill_switch_drawdown is not None:
            profile_name = req.portfolio_profile or settings.portfolio_profile
            profile_path = Path("profiles") / f"{profile_name}.yaml"
            if profile_path.exists():
                with open(profile_path, "r", encoding="utf-8") as f:
                    profile_data = yaml.safe_load(f) or {}
                
                if req.drift_threshold is not None:
                    profile_data["drift_threshold"] = req.drift_threshold
                if req.kill_switch_drawdown is not None:
                    profile_data["kill_switch_drawdown"] = req.kill_switch_drawdown
                    
                with open(profile_path, "w", encoding="utf-8") as f:
                    yaml.dump(profile_data, f, sort_keys=False)

        return {"ok": True, "message": "Settings updated. Some changes may require a restart to take full effect."}
    except Exception as e:
        print(f"ERROR updating settings: {e}")
        from fastapi import HTTPException
        raise HTTPException(status_code=500, detail=str(e))


# ── manual trade endpoints ─────────────────────────────────────────────────────

class TradePreviewRequest(BaseModel):
    action: str
    ticker: str
    quantity: float


class TradeOpinionRequest(BaseModel):
    action: str
    ticker: str
    quantity: float
    current_price: float


class TradeExecuteRequest(BaseModel):
    action: str
    ticker: str
    quantity: float
    reason: str | None = "Manual trade"


@app.post("/api/trade/preview")
async def trade_preview(req: TradePreviewRequest, _: User = Depends(requires_role([Role.ADMIN, Role.TRADER]))):
    from fastapi import HTTPException
    from services.execution_service import ExecutionService
    from services.market_service import MarketService

    svc = ExecutionService()
    portfolio = svc.load_portfolio()
    positions = portfolio.get("positions", {})
    try:
        price_map = MarketService().get_latest_prices(list(positions.keys()) + [req.ticker])
    except Exception:
        price_map = {}
    current_price = price_map.get(req.ticker)
    if not current_price or current_price <= 0:
        raise HTTPException(status_code=422, detail=f"Could not fetch price for ticker '{req.ticker}'")

    snapshot = svc.portfolio_snapshot(price_map)
    portfolio_value = snapshot["total_value"]
    cash = snapshot["cash"]
    current_holding = float(positions.get(req.ticker, 0.0))
    current_weight = snapshot["current_weights"].get(req.ticker, 0.0)

    estimated_cost = req.quantity * current_price
    if req.action == "buy":
        new_holding = current_holding + req.quantity
        cash_after = cash - estimated_cost
    else:
        new_holding = current_holding - req.quantity
        cash_after = cash + estimated_cost

    other_holdings_value = portfolio_value - cash - (current_holding * current_price)
    new_portfolio_value = cash_after + other_holdings_value + (new_holding * current_price)
    new_weight = (new_holding * current_price / new_portfolio_value) if new_portfolio_value > 0 else 0.0

    return {
        "current_price": current_price,
        "estimated_cost": round(estimated_cost, 2),
        "current_holding": current_holding,
        "current_weight": round(current_weight, 4),
        "new_weight": round(new_weight, 4),
        "cash_after": round(cash_after, 2),
        "portfolio_value": round(portfolio_value, 2),
        "available_cash": round(cash, 2),
    }


@app.post("/api/trade/opinion")
async def trade_opinion(req: TradeOpinionRequest, _: User = Depends(requires_role([Role.ADMIN, Role.TRADER]))):
    import re
    from services.execution_service import ExecutionService
    from services.market_service import MarketService

    svc = ExecutionService()
    portfolio = svc.load_portfolio()
    positions = portfolio.get("positions", {})
    try:
        price_map = MarketService().get_latest_prices(list(positions.keys()) + [req.ticker])
    except Exception:
        price_map = {}
    snapshot = svc.portfolio_snapshot(price_map)

    top_positions = sorted(positions.items(), key=lambda x: -abs(float(x[1])))[:5]
    top_str = ", ".join(f"{t}={v:.0f}sh" for t, v in top_positions)

    prompt = (
        f"You are a portfolio risk analyst at a hedge fund. Evaluate this proposed manual trade:\n\n"
        f"Action: {req.action.upper()} {req.quantity} shares of {req.ticker} at ${req.current_price:.2f}\n"
        f"Estimated notional: ${req.quantity * req.current_price:,.0f}\n"
        f"Portfolio value: ${snapshot['total_value']:,.0f}\n"
        f"Available cash: ${snapshot['cash']:,.0f}\n"
        f"Current {req.ticker} weight: {snapshot['current_weights'].get(req.ticker, 0.0):.1%}\n"
        f"Top positions: {top_str or 'none'}\n\n"
        f"Respond ONLY with valid JSON (no markdown, no explanation outside JSON):\n"
        f'{{"recommendation": "APPROVE" or "CAUTION" or "REJECT", '
        f'"rationale": "2-3 sentence analysis", '
        f'"confidence": 0.0-1.0, '
        f'"risk_flags": ["list", "of", "risks"], '
        f'"market_context": "1 sentence market note"}}'
    )

    fallback = {
        "recommendation": "CAUTION",
        "rationale": "AI opinion unavailable. Proceed with caution.",
        "confidence": 0.5,
        "risk_flags": [],
        "market_context": "",
    }

    try:
        from config import AI_PROVIDER
        if AI_PROVIDER == "anthropic":
            import anthropic as _anthropic
            from settings import Settings
            s = Settings()
            client = _anthropic.Anthropic(api_key=s.anthropic_api_key)
            msg = client.messages.create(
                model=s.claude_model,
                max_tokens=512,
                messages=[{"role": "user", "content": prompt}],
            )
            raw = msg.content[0].text
        else:
            import google.generativeai as genai
            from settings import Settings
            s = Settings()
            genai.configure(api_key=s.gemini_api_key)
            model = genai.GenerativeModel(s.gemini_model)
            raw = model.generate_content(prompt).text

        json_match = re.search(r'\{.*\}', raw, re.DOTALL)
        if json_match:
            return json.loads(json_match.group())
        return fallback
    except Exception as exc:
        fallback["rationale"] = f"AI opinion unavailable: {exc}"
        return fallback


@app.post("/api/trade/execute")
async def trade_execute(req: TradeExecuteRequest, _: User = Depends(requires_role([Role.ADMIN, Role.TRADER]))):
    from dataclasses import asdict
    from fastapi import HTTPException
    from services.execution_service import ExecutionService
    from services.market_service import MarketService
    from db.repository import save_execution
    from utils.time import utc_now_iso

    svc = ExecutionService()
    portfolio = svc.load_portfolio()
    positions = portfolio.get("positions", {})
    try:
        price_map = MarketService().get_latest_prices(list(positions.keys()) + [req.ticker])
    except Exception:
        price_map = {}
    current_price = price_map.get(req.ticker)
    if not current_price or current_price <= 0:
        raise HTTPException(status_code=422, detail=f"Could not fetch price for ticker '{req.ticker}'")

    from datetime import date
    cycle_id = f"manual-{date.today().isoformat()}"
    order = {
        "action": req.action,
        "ticker": req.ticker,
        "quantity": float(req.quantity),
        "reason": req.reason or "Manual trade",
        "side": "long",
        "sleeve": "manual",
    }
    result = svc.execute_order(order, current_price, prices=price_map, cycle_id=cycle_id, allow_unallocated=True)
    try:
        save_execution(asdict(result), cycle_id)
    except Exception:
        pass
    return asdict(result)


@app.get("/api/idea-book")
async def get_idea_book(
    status: str | None = Query(None),
    review_status: str | None = Query(None),
    llm_generated: bool | None = Query(None),
    _: User = Depends(get_current_user),
):
    from services.idea_book_service import IdeaBookService

    svc = IdeaBookService()
    return [
        entry.model_dump()
        for entry in svc.list_entries(status=status, review_status=review_status, llm_generated=llm_generated)
    ]


def _load_idea_metrics() -> dict[str, dict]:
    from services.execution_service import ExecutionService
    from market.metrics import PortfolioMetrics
    from services.market_service import MarketService

    try:
        svc_exec = ExecutionService()
        tickers = list((svc_exec.runtime_context.hedge_fund_profile.get("universe") or {}).keys())
    except Exception:
        tickers = []
    
    svc = MarketService()
    metrics: dict[str, dict] = {}
    for ticker in tickers:
        hist = svc.get_historical(ticker, days=90)
        if hist is None or getattr(hist, "empty", True):
            continue
        metrics[ticker] = PortfolioMetrics().ticker_metrics(hist)
    return metrics


@app.post("/api/idea-book/generate")
async def generate_idea_book_candidates(req: IdeaGenerationRequest = Body(...), _: User = Depends(requires_role([Role.ADMIN, Role.TRADER]))):
    from services.idea_book_service import IdeaBookService

    svc = IdeaBookService()
    generated = svc.generate_candidates(
        _load_idea_metrics(),
        cycle_id=req.cycle_id,
        max_candidates=req.max_candidates,
    )
    return [entry.model_dump() for entry in generated]


@app.post("/api/idea-book/{idea_id}/review")
async def review_idea_book_entry(idea_id: str, req: IdeaReviewRequest = Body(...), _: User = Depends(requires_role([Role.ADMIN, Role.TRADER]))):
    from fastapi import HTTPException
    from services.idea_book_service import IdeaBookService

    if req.review_status not in {"pending_review", "approved", "rejected"}:
        raise HTTPException(status_code=400, detail="Invalid review_status.")
    svc = IdeaBookService()
    if not svc.review_entry(idea_id, req.review_status):
        raise HTTPException(status_code=404, detail="Idea not found.")
    return {"ok": True, "idea_id": idea_id, "review_status": req.review_status}


@app.post("/api/idea-book/{idea_id}/promote")
async def promote_idea_book_entry(idea_id: str, req: IdeaPromoteRequest = Body(...), _: User = Depends(requires_role([Role.ADMIN, Role.TRADER]))):
    from fastapi import HTTPException
    from services.idea_book_service import IdeaBookService

    if req.status not in {"candidate", "watchlist", "investable", "portfolio"}:
        raise HTTPException(status_code=400, detail="Invalid status.")
    svc = IdeaBookService()
    if not svc.promote_entry(idea_id, req.status):
        raise HTTPException(status_code=404, detail="Idea not found.")
    return {"ok": True, "idea_id": idea_id, "status": req.status, "review_status": "approved"}


@app.get("/api/exposures")
async def get_exposures(_: User = Depends(get_current_user)):
    from engine.hedge_fund import compute_exposures
    from services.execution_service import ExecutionService
    from services.market_service import MarketService

    try:
        svc = ExecutionService()
        portfolio = svc.load_portfolio()
    except Exception:
        return {}

    tickers = list((portfolio.get("positions") or {}).keys())
    prices = MarketService().get_latest_prices(tickers) if tickers else {}
    ctx = svc.runtime_context
    beta_map = {ticker: (ctx.hedge_fund_profile.get("universe", {}).get(ticker, {}) or {}).get("beta", 1.0) for ticker in tickers}
    return compute_exposures(
        portfolio.get("positions", {}),
        prices,
        portfolio.get("cash", 0.0),
        position_sides=portfolio.get("position_sides", {}),
        sector_map=ctx.sector_map,
        beta_map=beta_map,
    )


@app.get("/api/pnl-attribution")
async def get_pnl_attribution(_: User = Depends(get_current_user)):
    from db.repository import get_executions, get_idea_book
    from engine.hedge_fund import compute_pnl_attribution
    from services.execution_service import ExecutionService
    from services.market_service import MarketService

    try:
        svc = ExecutionService()
        portfolio = svc.load_portfolio()
    except Exception:
        return {}
    
    tickers = list((portfolio.get("positions") or {}).keys())
    prices = MarketService().get_latest_prices(tickers) if tickers else {}
    executions = get_executions(limit=500)
    idea_lookup = {row["idea_id"]: row for row in get_idea_book() if row.get("idea_id")}
    return compute_pnl_attribution(
        positions=portfolio.get("positions", {}),
        prices=prices,
        average_costs=portfolio.get("average_costs", {}),
        position_sides=portfolio.get("position_sides", {}),
        executions=executions.to_dict(orient="records") if not executions.empty else [],
        idea_lookup=idea_lookup,
        sector_map=svc.runtime_context.sector_map,
    )


@app.get("/api/book-risk")
async def get_book_risk(_: User = Depends(get_current_user)):
    from engine.hedge_fund import classify_book_risk, compute_exposures
    from services.execution_service import ExecutionService
    from services.market_service import MarketService
    from agents.policies import PolicyConfig

    try:
        svc = ExecutionService()
        portfolio = svc.load_portfolio()
    except Exception:
        return {}
        
    tickers = list((portfolio.get("positions") or {}).keys())
    prices = MarketService().get_latest_prices(tickers) if tickers else {}
    ctx = svc.runtime_context
    universe = ctx.hedge_fund_profile.get("universe") or {}
    exposure = compute_exposures(
        portfolio.get("positions", {}),
        prices,
        portfolio.get("cash", 0.0),
        position_sides=portfolio.get("position_sides", {}),
        sector_map=ctx.sector_map,
        beta_map={ticker: (meta or {}).get("beta", 1.0) for ticker, meta in universe.items()},
    )
    policy = PolicyConfig.from_profile(ctx.profile)
    return classify_book_risk(
        exposure,
        gross_limit=policy.gross_exposure_limit,
        net_min=policy.net_exposure_min,
        net_max=policy.net_exposure_max,
        max_sector_gross=policy.max_sector_gross,
        max_sector_net=policy.max_sector_net,
        max_single_name_long=policy.max_single_name_long,
        max_single_name_short=policy.max_single_name_short,
        crowded_scores={ticker: float((meta or {}).get("crowded_score", 0.0)) for ticker, meta in universe.items()},
        short_squeeze_names={ticker for ticker, meta in universe.items() if (meta or {}).get("short_squeeze_risk")},
        position_sides=portfolio.get("position_sides", {}),
    )


@app.get("/api/book-summary")
async def get_book_summary(_: User = Depends(get_current_user)):
    exposure = await get_exposures()
    risk = await get_book_risk()
    attribution = await get_pnl_attribution()
    return {
        "exposures": exposure,
        "risk": risk,
        "pnl_attribution": attribution,
    }


# ── streaming command runner ──────────────────────────────────────────────────

VALID_STEPS = {"observe", "decide", "execute", "audit", "run-cycle", "report", "init", "reset"}


@app.post("/api/run/{step}")
async def run_step(step: str, req: RunRequest = Body(default_factory=RunRequest), _: User = Depends(requires_role([Role.ADMIN, Role.TRADER]))):
    if step not in VALID_STEPS:
        from fastapi import HTTPException
        raise HTTPException(status_code=400, detail=f"Unknown step '{step}'")

    if step == "init":
        args = ["main.py"]
        if req.profile:
            args += ["--profile", req.profile]
        args += ["init", "--force"]
        if req.initial_capital:
            args += ["--initial-capital", str(req.initial_capital)]
    elif step == "reset":
        # Reset is a specialized init that clears everything
        args = ["main.py"]
        if req.profile:
            args += ["--profile", req.profile]
        from portfolio_loader import load_profile

        reset_profile = req.profile or os.getenv("PORTFOLIO_PROFILE") or "balanced"
        profile_capital = load_profile(reset_profile).get("initial_capital")
        args += ["init", "--force", "--initial-capital", str(profile_capital)]
    elif step == "report":
        args = ["main.py", "report"]
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


@app.get("/api/monte-carlo")
async def get_monte_carlo(paths: int = Query(5000, ge=100, le=20000), _: User = Depends(get_current_user)):
    import numpy as np
    from engine.monte_carlo import run_monte_carlo
    from services.execution_service import ExecutionService
    from services.market_service import MarketService
    try:
        svc = ExecutionService()
        portfolio = svc.load_portfolio()
    except Exception:
        from fastapi import HTTPException
        raise HTTPException(status_code=503, detail="Portfolio not initialized.")
    tickers = list(portfolio.get("positions", {}).keys())
    if not tickers:
        from fastapi import HTTPException
        raise HTTPException(status_code=503, detail="Portfolio has no positions.")
    svc = MarketService()
    prices = svc.get_latest_prices(tickers)
    # Build historical returns per ticker
    historical_returns: dict[str, list[float]] = {}
    for ticker in tickers:
        hist = svc.get_historical(ticker, days=252)
        if not hist.empty and "Close" in hist.columns:
            rets = hist["Close"].pct_change().dropna().tolist()
            if len(rets) >= 30:
                historical_returns[ticker] = rets
    if not historical_returns:
        from fastapi import HTTPException
        raise HTTPException(status_code=503, detail="Insufficient historical data.")
    result = run_monte_carlo(portfolio, prices, historical_returns, n_paths=paths)

    # Add convenience fields for frontend
    result["expected_value"] = result["percentiles"].get("p50")
    result["var_95"] = result["percentiles"].get("p5")

    # Convert numpy types for JSON serialization
    def _clean(obj):
        if isinstance(obj, (np.floating, np.integer)):
            return float(obj)
        if isinstance(obj, np.ndarray):
            return obj.tolist()
        if isinstance(obj, dict):
            return {k: _clean(v) for k, v in obj.items()}
        if isinstance(obj, list):
            return [_clean(x) for x in obj]
        return obj
    return _clean(result)


@app.get("/api/regime")
async def get_regime(days: int = Query(180, ge=30, le=365), _: User = Depends(get_current_user)):
    from engine.regime import get_current_regime
    from services.execution_service import ExecutionService
    try:
        svc = ExecutionService()
        portfolio = svc.load_portfolio()
    except Exception:
        from fastapi import HTTPException
        raise HTTPException(status_code=503, detail="Portfolio not initialized.")
    tickers = list(portfolio.get("positions", {}).keys())
    if not tickers:
        from fastapi import HTTPException
        raise HTTPException(status_code=503, detail="Portfolio has no positions.")
    return get_current_regime(tickers, days=days)


@app.get("/api/events")
async def get_events(cycle_id: str | None = Query(None), limit: int = Query(100, ge=1, le=500), _: User = Depends(get_current_user)):
    from db.events import get_events as _get_events, get_recent_events
    if cycle_id:
        return _get_events(cycle_id)
    return get_recent_events(limit=limit)


@app.get("/api/events/replay/{cycle_id}")
async def replay_cycle(cycle_id: str, _: User = Depends(get_current_user)):
    from db.events import replay_cycle as _replay
    return _replay(cycle_id)


# ── SPA fallback (must be registered after all /api routes) ───────────────────


@app.get("/{full_path:path}", include_in_schema=False)
async def spa_fallback(full_path: str):
    from fastapi import HTTPException

    if full_path.startswith("api/"):
        raise HTTPException(status_code=404, detail="Not Found")
    if FRONTEND_INDEX.is_file():
        return FileResponse(str(FRONTEND_INDEX))
    if UI_REACT_INDEX.is_file():
        return FileResponse(str(UI_REACT_INDEX))
    legacy = LEGACY_UI_DIR / "index.html"
    if legacy.is_file():
        return FileResponse(str(legacy))
    raise HTTPException(
        status_code=503,
        detail="Frontend not built. Run: cd frontend && npm ci && npm run build",
    )
