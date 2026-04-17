from __future__ import annotations

import json
import tempfile
from pathlib import Path

from fastapi.testclient import TestClient

from api.main import app
from db.repository import upsert_idea_book
from db.schema import init_db
from engine.hedge_fund import (
    build_position_intents,
    classify_book_risk,
    compute_exposures,
    compute_pnl_attribution,
    convert_intents_to_trade_plan,
)


def test_compute_exposures_supports_long_short_book():
    exposure = compute_exposures(
        {"AAPL": 100.0, "GOOGL": -40.0},
        {"AAPL": 100.0, "GOOGL": 100.0},
        2_000.0,
        position_sides={"AAPL": "long", "GOOGL": "short"},
        sector_map={"AAPL": "tech", "GOOGL": "tech"},
        beta_map={"AAPL": 1.1, "GOOGL": 1.2},
    )

    assert exposure["gross_exposure"] == 0.875
    assert exposure["net_exposure"] == 0.375
    assert exposure["long_exposure"] == 0.625
    assert exposure["short_exposure"] == 0.25
    assert exposure["sector_gross"]["tech"] == 0.875
    assert exposure["top5_concentration"] == 0.875


def test_classify_book_risk_detects_breaches_and_flags():
    exposure = {
        "gross_exposure": 1.9,
        "net_exposure": 0.95,
        "sector_gross": {"tech": 0.8},
        "sector_net": {"tech": 0.5},
        "single_name_concentration": {"NVDA": 0.25, "AAPL": 0.35},
    }
    risk = classify_book_risk(
        exposure,
        gross_limit=1.8,
        net_max=0.9,
        max_sector_gross=0.7,
        max_sector_net=0.45,
        max_single_name_long=0.30,
        max_single_name_short=0.20,
        crowded_scores={"NVDA": 0.8},
        short_squeeze_names={"NVDA"},
        position_sides={"NVDA": "short", "AAPL": "long"},
    )

    assert any("Gross exposure" in msg for msg in risk["breaches"])
    assert any("Net exposure" in msg for msg in risk["breaches"])
    assert "NVDA" in risk["crowded_names"]
    assert "NVDA" in risk["short_squeeze_names"]


def test_build_position_intents_and_trade_plan_from_ideas():
    ideas = [
        {
            "idea_id": "idea-aapl",
            "ticker": "AAPL",
            "side": "long",
            "conviction": 0.72,
            "status": "investable",
            "sleeve": "core_longs",
        },
        {
            "idea_id": "idea-googl-short",
            "ticker": "GOOGL",
            "side": "short",
            "conviction": 0.60,
            "status": "investable",
            "sleeve": "shorts",
        },
    ]
    intents = build_position_intents(
        ideas,
        conviction_to_size={"high": 0.12, "medium": 0.08, "low": 0.04},
        price_metrics={
            "AAPL": {"volatility_30d": 0.18},
            "GOOGL": {"volatility_30d": 0.22},
        },
        sector_gross={"tech": 0.25},
        sector_map={"AAPL": "tech", "GOOGL": "tech"},
    )
    trade_plan = convert_intents_to_trade_plan(
        intents,
        positions={},
        prices={"AAPL": 100.0, "GOOGL": 100.0},
        cash=100_000.0,
    )

    assert len(intents) == 2
    assert {intent["side"] for intent in intents} == {"long", "short"}
    assert any(trade["side"] == "short" and trade["action"] == "sell" for trade in trade_plan)
    assert any(trade["idea_id"] == "idea-aapl" for trade in trade_plan)


def test_compute_pnl_attribution_groups_by_side_sector_and_idea():
    attribution = compute_pnl_attribution(
        positions={"AAPL": 10.0, "GOOGL": -5.0},
        prices={"AAPL": 110.0, "GOOGL": 90.0},
        average_costs={"AAPL": 100.0, "GOOGL": 100.0},
        position_sides={"AAPL": "long", "GOOGL": "short"},
        executions=[
            {"ticker": "AAPL", "action": "buy", "notional": 1_000.0, "side": "long", "success": True, "idea_id": "idea-aapl", "sleeve": "core_longs"},
            {"ticker": "GOOGL", "action": "sell", "notional": 500.0, "side": "short", "success": True, "idea_id": "idea-googl", "sleeve": "shorts"},
        ],
        idea_lookup={
            "idea-aapl": {"ticker": "AAPL", "sleeve": "core_longs", "status": "portfolio"},
            "idea-googl": {"ticker": "GOOGL", "sleeve": "shorts", "status": "portfolio"},
        },
        sector_map={"AAPL": "tech", "GOOGL": "tech"},
    )

    assert attribution["realized_total"] == -500.0
    assert attribution["unrealized_total"] == 150.0
    assert "long" in attribution["by_side"]
    assert "short" in attribution["by_side"]
    assert attribution["by_idea"]["idea-aapl"] == -900.0
    assert attribution["by_sleeve"]["shorts"] == 550.0


def test_api_hedge_fund_endpoints_return_payloads(monkeypatch, tmp_path: Path):
    portfolio_path = tmp_path / "portfolio.json"
    db_path = tmp_path / "market.db"
    init_db(str(db_path))
    portfolio_path.write_text(json.dumps({
        "positions": {"AAPL": 10.0, "GOOGL": -5.0},
        "position_sides": {"AAPL": "long", "GOOGL": "short"},
        "average_costs": {"AAPL": 100.0, "GOOGL": 100.0},
        "cash": 1000.0,
        "peak_value": 2000.0,
        "history": [],
    }), encoding="utf-8")
    upsert_idea_book([
        {
            "idea_id": "idea-aapl",
            "ticker": "AAPL",
            "side": "long",
            "thesis": "Quality compounder",
            "catalyst": "Results",
            "time_horizon": "3m",
            "conviction": 0.7,
            "upside_case": "Re-rating",
            "downside_case": "Demand slowdown",
            "invalidation_rule": "Margin compression",
            "status": "portfolio",
            "sleeve": "core_longs",
        }
    ], db_path=str(db_path))

    import api.main as api_main
    import config as config_module
    import db.repository as repository_module
    import settings as settings_module

    monkeypatch.setattr(settings_module.settings, "portfolio_file", str(portfolio_path))
    monkeypatch.setattr(settings_module.settings, "market_db", str(db_path))
    monkeypatch.setattr(config_module, "PORTFOLIO_FILE", str(portfolio_path))
    monkeypatch.setattr(config_module, "MARKET_DB", str(db_path))
    monkeypatch.setattr(repository_module, "MARKET_DB", str(db_path))
    monkeypatch.setattr(api_main, "PROJECT_ROOT", Path(api_main.PROJECT_ROOT))

    from services.market_service import MarketService

    monkeypatch.setattr(
        MarketService,
        "get_latest_prices",
        lambda self, tickers: {ticker: 100.0 for ticker in tickers},
    )

    client = TestClient(app)

    idea_book = client.get("/api/idea-book")
    exposures = client.get("/api/exposures")
    pnl = client.get("/api/pnl-attribution")
    risk = client.get("/api/book-risk")

    assert idea_book.status_code == 200
    assert exposures.status_code == 200
    assert pnl.status_code == 200
    assert risk.status_code == 200
    assert isinstance(idea_book.json(), list)
    assert "gross_exposure" in exposures.json()
    assert "by_side" in pnl.json()
    assert "exposure" in risk.json()


def test_api_positions_falls_back_to_current_portfolio(monkeypatch, tmp_path: Path):
    portfolio_path = tmp_path / "portfolio.json"
    db_path = tmp_path / "market.db"
    init_db(str(db_path))
    portfolio_path.write_text(json.dumps({
        "positions": {"AAPL": 10.0},
        "position_sides": {"AAPL": "long"},
        "average_costs": {"AAPL": 100.0},
        "cash": 1000.0,
        "peak_value": 2000.0,
        "history": [],
    }), encoding="utf-8")

    import config as config_module
    import db.repository as repository_module
    import settings as settings_module

    monkeypatch.setattr(settings_module.settings, "portfolio_file", str(portfolio_path))
    monkeypatch.setattr(settings_module.settings, "market_db", str(db_path))
    monkeypatch.setattr(config_module, "PORTFOLIO_FILE", str(portfolio_path))
    monkeypatch.setattr(config_module, "MARKET_DB", str(db_path))
    monkeypatch.setattr(repository_module, "MARKET_DB", str(db_path))

    from services.market_service import MarketService

    monkeypatch.setattr(
        MarketService,
        "get_latest_prices",
        lambda self, tickers: {ticker: 100.0 for ticker in tickers},
    )

    client = TestClient(app)
    response = client.get("/api/positions")

    assert response.status_code == 200
    payload = response.json()
    assert len(payload) == 1
    assert payload[0]["ticker"] == "AAPL"
    assert payload[0]["quantity"] == 10.0
