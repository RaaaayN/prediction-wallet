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
    from config import INITIAL_CAPITAL, PORTFOLIO_FILE
    from services.execution_service import ExecutionService
    from services.market_service import MarketService
    try:
        with open(PORTFOLIO_FILE, encoding="utf-8") as f:
            data = json.load(f)
        tickers = list(data.get("positions", {}).keys())
        prices = MarketService().get_latest_prices(tickers) if tickers else {}
        snapshot = ExecutionService().portfolio_snapshot(prices)
        history = data.get("history", [])
        total_value = snapshot.get("total_value") or (history[-1]["total_value"] if history else data.get("cash", INITIAL_CAPITAL))
        pnl_dollars = total_value - INITIAL_CAPITAL
        data.update(snapshot)
        data["total_value"] = total_value
        data.setdefault("pnl_dollars", pnl_dollars)
        data.setdefault("pnl_pct", pnl_dollars / INITIAL_CAPITAL if INITIAL_CAPITAL > 0 else 0.0)
        return data
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
    import json
    from config import PORTFOLIO_FILE, TARGET_ALLOCATION
    from db.repository import get_latest_positions
    from services.execution_service import ExecutionService
    from services.market_service import MarketService

    latest = get_latest_positions()
    if latest:
        return latest

    try:
        with open(PORTFOLIO_FILE, encoding="utf-8") as f:
            portfolio = json.load(f)
    except FileNotFoundError:
        return []

    positions = portfolio.get("positions", {}) or {}
    if not positions:
        return []

    tickers = list(positions.keys())
    prices = MarketService().get_latest_prices(tickers)
    snapshot = ExecutionService().portfolio_snapshot(prices)
    current_weights = snapshot.get("current_weights", {})
    target_weights = snapshot.get("target_weights", TARGET_ALLOCATION)
    drifts = snapshot.get("weight_deviation", {})
    total_value = snapshot.get("total_value", 0.0) or 0.0
    position_sides = portfolio.get("position_sides", {}) or {}
    position_ideas = portfolio.get("position_ideas", {}) or {}

    rows = []
    for ticker in sorted(tickers):
        quantity = float(positions.get(ticker, 0.0))
        price = float(prices.get(ticker, 0.0))
        value = quantity * price
        rows.append(
            {
                "ticker": ticker,
                "quantity": quantity,
                "price": price,
                "value": value,
                "weight": float(current_weights.get(ticker, 0.0)),
                "target_weight": float(target_weights.get(ticker, 0.0)),
                "drift": float(drifts.get(ticker, 0.0)),
                "side": position_sides.get(ticker, "short" if quantity < 0 else "long"),
                "idea_id": position_ideas.get(ticker),
                "gross_exposure": abs(value) / total_value if total_value > 0 else 0.0,
                "net_exposure": value / total_value if total_value > 0 else 0.0,
            }
        )
    return rows


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


@app.get("/api/correlation")
async def get_correlation(days: int = Query(90, ge=10, le=365)):
    import json
    import pandas as pd
    from config import PORTFOLIO_FILE
    from engine.performance import rolling_correlation
    from services.market_service import MarketService
    try:
        with open(PORTFOLIO_FILE, encoding="utf-8") as f:
            portfolio = json.load(f)
    except FileNotFoundError:
        from fastapi import HTTPException
        raise HTTPException(status_code=503, detail="Portfolio not initialized. Run: python main.py init")
    tickers = list(portfolio.get("positions", {}).keys())
    if not tickers:
        from fastapi import HTTPException
        raise HTTPException(status_code=503, detail="Portfolio has no positions.")
    svc = MarketService()
    price_series: dict[str, "pd.Series"] = {}
    for ticker in tickers:
        hist = svc.get_historical(ticker, days=days)
        if not hist.empty and "Close" in hist.columns:
            price_series[ticker] = hist["Close"]
    if len(price_series) < 2:
        from fastapi import HTTPException
        raise HTTPException(status_code=503, detail="Insufficient market data for correlation.")
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
async def get_stress():
    import json
    from config import PORTFOLIO_FILE
    from engine.backtest import run_stress_test
    from services.market_service import MarketService
    try:
        with open(PORTFOLIO_FILE, encoding="utf-8") as f:
            portfolio = json.load(f)
    except FileNotFoundError:
        from fastapi import HTTPException
        raise HTTPException(status_code=503, detail="Portfolio not initialized. Run: python main.py init")
    tickers = list(portfolio.get("positions", {}).keys())
    if not tickers:
        from fastapi import HTTPException
        raise HTTPException(status_code=503, detail="Portfolio has no positions.")
    prices = MarketService().get_latest_prices(tickers)
    return run_stress_test(portfolio, prices)


@app.get("/api/config")
async def get_config():
    try:
        from config import (
            AGENT_BACKEND, AI_PROVIDER, EXECUTION_MODE, HEDGE_FUND_PROFILE, TARGET_ALLOCATION,
        )
        return {
            "ai_provider": AI_PROVIDER,
            "agent_backend": AGENT_BACKEND,
            "execution_mode": EXECUTION_MODE,
            "target_allocation": TARGET_ALLOCATION,
            "hedge_fund_enabled": bool(HEDGE_FUND_PROFILE),
        }
    except Exception as exc:
        return {"error": str(exc)}


@app.get("/api/idea-book")
async def get_idea_book(status: str | None = Query(None)):
    from services.idea_book_service import IdeaBookService

    svc = IdeaBookService()
    return [entry.model_dump() for entry in svc.list_entries(status=status)]


@app.get("/api/exposures")
async def get_exposures():
    import json
    from config import HEDGE_FUND_PROFILE, PORTFOLIO_FILE, SECTOR_MAP
    from engine.hedge_fund import compute_exposures
    from services.market_service import MarketService

    with open(PORTFOLIO_FILE, encoding="utf-8") as f:
        portfolio = json.load(f)
    tickers = list((portfolio.get("positions") or {}).keys())
    prices = MarketService().get_latest_prices(tickers) if tickers else {}
    beta_map = {ticker: (HEDGE_FUND_PROFILE.get("universe", {}).get(ticker, {}) or {}).get("beta", 1.0) for ticker in tickers}
    return compute_exposures(
        portfolio.get("positions", {}),
        prices,
        portfolio.get("cash", 0.0),
        position_sides=portfolio.get("position_sides", {}),
        sector_map=SECTOR_MAP,
        beta_map=beta_map,
    )


@app.get("/api/pnl-attribution")
async def get_pnl_attribution():
    import json
    from config import PORTFOLIO_FILE, SECTOR_MAP
    from db.repository import get_executions, get_idea_book
    from engine.hedge_fund import compute_pnl_attribution
    from services.market_service import MarketService

    with open(PORTFOLIO_FILE, encoding="utf-8") as f:
        portfolio = json.load(f)
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
        sector_map=SECTOR_MAP,
    )


@app.get("/api/book-risk")
async def get_book_risk():
    import json
    from config import HEDGE_FUND_PROFILE, PORTFOLIO_FILE, SECTOR_MAP
    from engine.hedge_fund import classify_book_risk, compute_exposures
    from portfolio_loader import get_active_profile
    from services.market_service import MarketService
    from agents.policies import PolicyConfig

    with open(PORTFOLIO_FILE, encoding="utf-8") as f:
        portfolio = json.load(f)
    tickers = list((portfolio.get("positions") or {}).keys())
    prices = MarketService().get_latest_prices(tickers) if tickers else {}
    universe = HEDGE_FUND_PROFILE.get("universe") or {}
    exposure = compute_exposures(
        portfolio.get("positions", {}),
        prices,
        portfolio.get("cash", 0.0),
        position_sides=portfolio.get("position_sides", {}),
        sector_map=SECTOR_MAP,
        beta_map={ticker: (meta or {}).get("beta", 1.0) for ticker, meta in universe.items()},
    )
    policy = PolicyConfig.from_profile(get_active_profile())
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
async def get_book_summary():
    exposure = await get_exposures()
    risk = await get_book_risk()
    attribution = await get_pnl_attribution()
    return {
        "exposures": exposure,
        "risk": risk,
        "pnl_attribution": attribution,
    }


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


@app.get("/api/monte-carlo")
async def get_monte_carlo(paths: int = Query(5000, ge=100, le=20000)):
    import json
    import numpy as np
    from config import PORTFOLIO_FILE
    from engine.monte_carlo import run_monte_carlo
    from services.market_service import MarketService
    try:
        with open(PORTFOLIO_FILE, encoding="utf-8") as f:
            portfolio = json.load(f)
    except FileNotFoundError:
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
async def get_regime(days: int = Query(180, ge=30, le=365)):
    import json
    from config import PORTFOLIO_FILE
    from engine.regime import get_current_regime
    try:
        with open(PORTFOLIO_FILE, encoding="utf-8") as f:
            portfolio = json.load(f)
    except FileNotFoundError:
        from fastapi import HTTPException
        raise HTTPException(status_code=503, detail="Portfolio not initialized.")
    tickers = list(portfolio.get("positions", {}).keys())
    if not tickers:
        from fastapi import HTTPException
        raise HTTPException(status_code=503, detail="Portfolio has no positions.")
    return get_current_regime(tickers, days=days)


@app.get("/api/events")
async def get_events(cycle_id: str | None = Query(None), limit: int = Query(100, ge=1, le=500)):
    from db.events import get_events as _get_events, get_recent_events
    if cycle_id:
        return _get_events(cycle_id)
    return get_recent_events(limit=limit)


@app.get("/api/events/replay/{cycle_id}")
async def replay_cycle(cycle_id: str):
    from db.events import replay_cycle as _replay
    return _replay(cycle_id)
