from fastapi.testclient import TestClient

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
