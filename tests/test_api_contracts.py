from fastapi.testclient import TestClient
import config

from api.main import app


def test_openapi_generation_succeeds():
    client = TestClient(app)

    response = client.get("/openapi.json")

    assert response.status_code == 200
    assert response.json()["info"]["title"] == "Prediction Wallet API"


def test_market_status_matches_response_contract(monkeypatch):
    client = TestClient(app)

    monkeypatch.setattr(
        "db.repository.get_market_data_status",
        lambda: [
            {
                "ticker": "AAPL",
                "refreshed_at": "2026-04-18T09:30:00Z",
                "success": 1,
                "error": None,
            },
            {
                "ticker": "MSFT",
                "refreshed_at": "2026-04-18T09:31:00Z",
                "success": 1,
                "error": None,
            },
        ],
    )

    response = client.get("/api/market-status")

    assert response.status_code == 200
    assert response.json() == {
        "tickers": ["AAPL", "MSFT"],
        "last_refresh": {
            "AAPL": "2026-04-18T09:30:00Z",
            "MSFT": "2026-04-18T09:31:00Z",
        },
    }


def test_backtest_uses_backtester_output(monkeypatch):
    client = TestClient(app)
    monkeypatch.setattr(config, "API_KEY_ADMIN", "admin-key")
    monkeypatch.setattr(config, "API_KEY_TRADER", "")
    monkeypatch.setattr(config, "API_KEY_VIEWER", "")

    class DummyRuntimeContext:
        initial_capital = 123456.0
        target_allocation = {"AAPL": 1.0}

    class DummyService:
        def __init__(self, profile_name=None):
            self.runtime_context = DummyRuntimeContext()

        def load_portfolio(self):
            return {"positions": {"AAPL": 1.0}}

    class DummyResult:
        metrics = {"annualized_return": 0.1, "sharpe": 1.2}
        history = [{"date": "2026-04-18", "total_value": 123456.0}]
        data_hash = "hash-123"

    class DummyBacktester:
        def __init__(self, **kwargs):
            self.kwargs = kwargs

        def run(self, strategy_type):
            return DummyResult()

    monkeypatch.setattr("services.execution_service.ExecutionService", DummyService)
    monkeypatch.setattr("api.main._prefetch_price_history", lambda *args, **kwargs: None)
    monkeypatch.setattr("engine.backtest_v2.EventDrivenBacktester", DummyBacktester)

    response = client.get("/api/backtest?strategy=threshold&days=30", headers={"X-API-KEY": "admin-key"})

    assert response.status_code == 200
    assert response.json()["metrics"] == {"annualized_return": 0.1, "sharpe": 1.2}


def test_reset_uses_profile_initial_capital(monkeypatch):
    client = TestClient(app)
    monkeypatch.setattr(config, "API_KEY_ADMIN", "admin-key")
    monkeypatch.setattr(config, "API_KEY_TRADER", "")
    monkeypatch.setattr(config, "API_KEY_VIEWER", "")
    monkeypatch.setattr("api.main.stream_command", lambda args: iter(["ok"]))
    monkeypatch.setattr("portfolio_loader.load_profile", lambda name: {"initial_capital": 50000})

    response = client.post("/api/run/reset", json={"profile": "balanced"}, headers={"X-API-KEY": "admin-key"})

    assert response.status_code == 200


def test_experiments_uses_configured_tracking_uri(monkeypatch):
    client = TestClient(app)
    monkeypatch.setattr(config, "API_KEY_ADMIN", "admin-key")
    monkeypatch.setattr(config, "API_KEY_TRADER", "")
    monkeypatch.setattr(config, "API_KEY_VIEWER", "")

    calls = {}

    class DummySeries:
        def __init__(self, data):
            self.data = data

        def isoformat(self):
            return self.data

    def fake_set_tracking_uri(uri):
        calls["uri"] = uri

    monkeypatch.setattr("mlflow.set_tracking_uri", fake_set_tracking_uri)
    monkeypatch.setattr("mlflow.search_experiments", lambda: [])
    monkeypatch.setattr("pathlib.Path.exists", lambda self: True)

    response = client.get("/api/experiments", headers={"X-API-KEY": "admin-key"})

    assert response.status_code == 200
    assert calls["uri"].endswith("data/mlflow.db")
