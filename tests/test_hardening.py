"""Tests for the Hardening Production phase."""

import pytest
import sys
import time
import yaml
from fastapi.testclient import TestClient
from api.main import app
from main import build_parser
from portfolio_loader import get_active_profile
from services.health_service import HealthService
from services.back_office_service import BackOfficeService
from services.market_service import MarketService, market_cb
from services.execution_service import ExecutionService
from strategies import available_strategy_names
from db.schema import init_db
import config
import os
from pathlib import Path

client = TestClient(app)

@pytest.fixture
def db_path(tmp_path, monkeypatch):
    db_file = str(tmp_path / "test_hardening.db")
    monkeypatch.setattr(config, "USE_POSTGRES", False)
    monkeypatch.setattr(config, "DATABASE_URL", "")
    monkeypatch.setattr(config, "MARKET_DB", db_file)
    init_db(db_file)
    return db_file

def test_health_check(db_path, monkeypatch):
    """Verify health service and endpoint."""
    monkeypatch.setattr(config, "MARKET_DB", db_path)
    monkeypatch.setitem(sys.modules, "yfinance", object())
    
    svc = HealthService()
    health = svc.get_full_health()
    assert health["status"] == "up"
    assert "database" in health["checks"]
    
    response = client.get("/api/health")
    assert response.status_code == 200
    assert response.json()["status"] == "up"


def test_market_health_does_not_require_yfinance(db_path, monkeypatch):
    """Health checks should stay local even if yfinance is unavailable."""
    monkeypatch.setattr(config, "MARKET_DB", db_path)
    monkeypatch.setitem(sys.modules, "yfinance", object())

    svc = HealthService()
    check = svc.check_market_data()

    assert check["status"] == "up"
    assert check["provider"] == "local-cache"

def test_backup_logic(db_path, monkeypatch, tmp_path):
    """Verify that backup creates files and handles retention."""
    monkeypatch.setattr(config, "MARKET_DB", db_path)
    reports_dir = str(tmp_path / "reports")
    monkeypatch.setattr(config, "REPORTS_DIR", reports_dir)
    
    svc = BackOfficeService()
    
    # 1. Trigger backup
    result = svc.run_backup()
    assert result["status"] == "success"
    
    backup_path = Path(reports_dir) / "backups"
    assert (backup_path / result["db_snapshot"]).exists()
    assert (backup_path / result["ledger_export"]).exists()
    
    # 2. Test retention (keep last 7)
    for i in range(10):
        svc.run_backup()
        
    all_snaps = list(backup_path.glob("snapshot_*.db"))
    assert len(all_snaps) <= 7

def test_resilience_retry():
    """Verify retry decorator behavior."""
    from utils.resilience import retry
    
    attempts = 0
    
    @retry(max_attempts=3, base_delay=0.1)
    def failing_func():
        nonlocal attempts
        attempts += 1
        if attempts < 3:
            raise ValueError("Intermittent")
        return "success"
    
    result = failing_func()
    assert result == "success"
    assert attempts == 3


def test_open_circuit_fails_fast_without_retry(monkeypatch, db_path):
    """An open circuit should bypass retry backoff entirely."""
    monkeypatch.setattr(config, "MARKET_DB", db_path)

    import utils.resilience as resilience
    from services import market_service

    original_state = (market_cb.state, market_cb.failures, market_cb.last_failure_time)
    market_cb.state = "OPEN"
    market_cb.failures = market_cb.failure_threshold
    market_cb.last_failure_time = time.time()

    def fail_sleep(_seconds):
        raise AssertionError("retry backoff should not run when the circuit is open")

    monkeypatch.setattr(resilience.time, "sleep", fail_sleep)
    monkeypatch.setattr(market_service, "_require_yfinance", lambda: (_ for _ in ()).throw(AssertionError("yfinance should not be called")))

    try:
        with pytest.raises(RuntimeWarning):
            MarketService()._download("AAPL", "1d")
    finally:
        market_cb.state, market_cb.failures, market_cb.last_failure_time = original_state


def test_cli_strategy_choices_follow_registry():
    """CLI strategy validation should reflect the registered strategy names."""
    parser = build_parser()
    choices = None
    for action in parser._actions:
        if getattr(action, "dest", None) == "strategy":
            choices = action.choices
            break

    assert choices is not None
    assert set(choices) == set(available_strategy_names())

def test_status_endpoint(db_path, monkeypatch):
    """Verify consolidated status endpoint."""
    monkeypatch.setattr(config, "MARKET_DB", db_path)
    
    # Authenticated request (static admin key)
    monkeypatch.setattr(config, "API_KEY_ADMIN", "admin-test")
    
    response = client.get("/api/status", headers={"X-API-KEY": "admin-test"})
    assert response.status_code == 200
    data = response.json()
    assert "health" in data
    assert "backups" in data


def test_update_settings_writes_active_profile(monkeypatch, tmp_path):
    """Profile-specific risk settings should be written to the selected profile file."""
    profiles_dir = tmp_path / "profiles"
    profiles_dir.mkdir()
    balanced_path = profiles_dir / "balanced.yaml"
    growth_path = profiles_dir / "growth.yaml"

    balanced_path.write_text(
        yaml.safe_dump(
            {
                "name": "balanced",
                "initial_capital": 100000,
                "drift_threshold": 0.05,
                "kill_switch_drawdown": 0.10,
                "slippage_equities": 0.001,
                "slippage_crypto": 0.002,
                "target_allocation": {"AAPL": 1.0},
            },
            sort_keys=False,
        ),
        encoding="utf-8",
    )
    growth_path.write_text(
        yaml.safe_dump(
            {
                "name": "growth",
                "initial_capital": 100000,
                "drift_threshold": 0.07,
                "kill_switch_drawdown": 0.14,
                "slippage_equities": 0.001,
                "slippage_crypto": 0.002,
                "target_allocation": {"AAPL": 1.0},
            },
            sort_keys=False,
        ),
        encoding="utf-8",
    )

    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(config, "API_KEY_ADMIN", "admin-test")

    from settings import settings as app_settings

    monkeypatch.setattr(app_settings, "portfolio_profile", "balanced")

    response = client.post(
        "/api/settings",
        json={
            "portfolio_profile": "growth",
            "drift_threshold": 0.21,
            "kill_switch_drawdown": 0.44,
        },
        headers={"X-API-KEY": "admin-test"},
    )
    assert response.status_code == 200

    balanced = yaml.safe_load(balanced_path.read_text(encoding="utf-8"))
    growth = yaml.safe_load(growth_path.read_text(encoding="utf-8"))

    assert balanced["drift_threshold"] == 0.05
    assert balanced["kill_switch_drawdown"] == 0.10
    assert growth["drift_threshold"] == 0.21
    assert growth["kill_switch_drawdown"] == 0.44


def test_trade_preview_keeps_portfolio_value_consistent(monkeypatch, db_path):
    """Trade preview should preserve total book value apart from trading costs."""
    monkeypatch.setattr(config, "MARKET_DB", db_path)
    monkeypatch.setattr(config, "API_KEY_ADMIN", "admin-test")
    monkeypatch.setattr(config, "API_KEY_TRADER", "")
    monkeypatch.setattr(config, "API_KEY_VIEWER", "")

    class FakeExecutionService:
        def load_portfolio(self):
            return {"positions": {"MSFT": 10.0}, "cash": 9000.0}

        def portfolio_snapshot(self, price_map):
            return {
                "total_value": 10000.0,
                "cash": 9000.0,
                "current_weights": {"AAPL": 0.0},
            }

    class FakeMarketService:
        def get_latest_prices(self, tickers):
            return {ticker: 100.0 for ticker in tickers}

    monkeypatch.setattr("services.execution_service.ExecutionService", FakeExecutionService)
    monkeypatch.setattr("services.market_service.MarketService", FakeMarketService)

    response = client.post(
        "/api/trade/preview",
        json={"action": "buy", "ticker": "AAPL", "quantity": 10.0},
        headers={"X-API-KEY": "admin-test"},
    )
    assert response.status_code == 200
    data = response.json()

    assert data["portfolio_value"] == 10000.0
    assert data["cash_after"] == 8000.0
    assert data["new_weight"] == 0.1


def test_get_active_profile_prefers_runtime_env(monkeypatch):
    """Runtime profile changes should override the cached settings object."""
    from settings import settings as app_settings

    monkeypatch.setenv("PORTFOLIO_PROFILE", "growth")
    monkeypatch.setattr(app_settings, "portfolio_profile", "balanced")

    profile = get_active_profile()

    assert profile["name"] == "growth"


def test_execution_service_preserves_side_when_sell_does_not_flip(monkeypatch):
    """A short-side sell that leaves a positive quantity should stay long-labelled."""
    service = ExecutionService(profile_name="balanced")
    service.runtime_context = type(
        "Ctx",
        (),
        {
            "target_allocation": {"AAPL": 1.0},
            "initial_capital": 10000.0,
            "crypto_tickers": set(),
            "slippage_equities": 0.0,
            "slippage_crypto": 0.0,
            "sector_map": {"AAPL": "tech"},
            "hedge_fund_profile": {"universe": {"AAPL": {}}},
        },
    )()
    saved_portfolios = []
    service.load_portfolio = lambda: {
        "positions": {"AAPL": 10.0},
        "position_sides": {"AAPL": "long"},
        "average_costs": {"AAPL": 100.0},
        "position_ideas": {"AAPL": "idea-aapl"},
        "cash": 5000.0,
        "peak_value": 10000.0,
        "history": [],
    }
    service.save_portfolio = lambda portfolio: saved_portfolios.append(portfolio.copy())
    service.trade_log_store = type("TradeLog", (), {"append": lambda self, trade: None})()
    service.validate_order = lambda *args, **kwargs: None
    monkeypatch.setattr("services.execution_service.apply_slippage", lambda market_price, *args, **kwargs: market_price)

    result = service.execute_order(
        {
            "action": "sell",
            "ticker": "AAPL",
            "quantity": 4.0,
            "reason": "rebalance",
            "side": "short",
            "idea_id": "idea-aapl",
            "sleeve": "core_longs",
        },
        market_price=100.0,
    )

    assert result.success is True
    assert saved_portfolios[-1]["positions"]["AAPL"] == 6.0
    assert saved_portfolios[-1]["position_sides"]["AAPL"] == "long"
