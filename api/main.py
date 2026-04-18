"""FastAPI backend for the Prediction Wallet governed agent UI."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from time import perf_counter

from fastapi import Body, FastAPI, Query, Request, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from api.runner import build_cycle_args, stream_command
from api.auth import Role, User, get_current_user, requires_role
from api.middle_office import router as middle_office_router
from api.models import (
    ConfigResponse, PortfolioResponse, PositionRow, 
    MarketStatusResponse, OnboardingStatusResponse,
    InstrumentRow, TradingCoreOrderRow, TradingCoreExecutionRow,
    TradingCorePositionRow, CashMovementRow
)
from config import ALLOWED_ORIGINS
from utils.telemetry import trace_request

app = FastAPI(title="Prediction Wallet API")

app.include_router(middle_office_router)

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


app = FastAPI(title="Prediction Wallet API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_methods=["*"],
    allow_headers=["*"],
)


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
        history = data.get("history", [])
        total_value = snapshot.get("total_value") or (history[-1]["total_value"] if history else data.get("cash", initial_capital))
        pnl_dollars = total_value - initial_capital
        
        data.update(snapshot)
        data["total_value"] = total_value
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


@app.get("/api/traces")
async def get_traces(
    limit: int = Query(100, ge=1, le=500),
    cycle_id: str | None = Query(None),
    _: User = Depends(get_current_user),
):
    from db.repository import get_decision_traces
    traces = get_decision_traces(limit=limit, cycle_id=cycle_id)
    return list(reversed(traces)) if cycle_id else traces  # cycle view: ASC; global: DESC


@app.get("/api/positions", response_model=list[PositionRow])
async def get_positions(cycle_id: str | None = Query(None), _: User = Depends(get_current_user)):
    if cycle_id:
        from db.repository import get_positions_by_cycle
        return get_positions_by_cycle(cycle_id=cycle_id)
    
    from db.repository import get_latest_positions
    from services.execution_service import ExecutionService
    from services.market_service import MarketService

    latest = get_latest_positions()
    if latest:
        return latest

    try:
        svc = ExecutionService()
        portfolio = svc.load_portfolio()
    except Exception:
        return []

    positions = portfolio.get("positions", {}) or {}
    if not positions:
        return []

    tickers = list(positions.keys())
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


@app.get("/api/market-status", response_model=MarketStatusResponse)
async def get_market_status(_: User = Depends(get_current_user)):
    from db.repository import get_market_data_status

    rows = get_market_data_status()
    return {
        "tickers": [row["ticker"] for row in rows],
        "last_refresh": {row["ticker"]: row["refreshed_at"] for row in rows},
    }

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



@app.get("/api/backtest")
async def get_backtest(days: int = Query(90, ge=10, le=365), _: User = Depends(get_current_user)):
    from engine.backtest import run_strategy_comparison
    from services.execution_service import ExecutionService
    
    svc = ExecutionService()
    _prefetch_price_history(list(svc.runtime_context.target_allocation.keys()), min_days=days + 30)
    results = run_strategy_comparison(days=days)
    if results is None:
        from fastapi import HTTPException
        raise HTTPException(
            status_code=503,
            detail="Insufficient market data for backtest. Check network / yfinance, then retry.",
        )
    return results


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
            result.append({
                "name": name,
                "label": meta["label"],
                "description": meta["description"],
                "risk_level": meta["risk_level"],
                "strategy_type": meta["strategy_type"],
                "typical_aum": meta["typical_aum"],
                "initial_capital": profile.get("initial_capital", 100000),
                "tickers": list(profile.get("target_allocation", {}).keys()),
            })
        except Exception:
            pass
    return result


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

    new_portfolio_value = portfolio_value + (cash_after - cash)
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

class RunRequest(BaseModel):
    strategy: str = "threshold"
    mode: str = "simulate"
    profile: str | None = None
    initial_capital: float | None = None


VALID_STEPS = {"observe", "decide", "execute", "audit", "run-cycle", "report", "init"}


@app.post("/api/run/{step}")
async def run_step(step: str, req: RunRequest = RunRequest(), _: User = Depends(requires_role([Role.ADMIN, Role.TRADER]))):
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
