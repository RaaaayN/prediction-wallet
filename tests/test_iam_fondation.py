"""Tests for the Database-backed IAM system (Fondation phase)."""

import pytest
from fastapi.testclient import TestClient
from api.main import app
from db.schema import init_db
import config
import os

client = TestClient(app)

@pytest.fixture
def db_path(tmp_path, monkeypatch):
    db_file = str(tmp_path / "test_iam.db")
    monkeypatch.setattr(config, "USE_POSTGRES", False)
    monkeypatch.setattr(config, "DATABASE_URL", "")
    monkeypatch.setattr(config, "MARKET_DB", db_file)
    init_db(db_file)
    return db_file

def test_db_user_auth(db_path, monkeypatch):
    """Verify that a user in the database can authenticate."""
    from db.repository import create_user
    
    # 1. Setup Test DB and unset static keys
    monkeypatch.setattr(config, "MARKET_DB", db_path)
    monkeypatch.setattr(config, "API_KEY_ADMIN", "")
    monkeypatch.setattr(config, "API_KEY_TRADER", "")
    monkeypatch.setattr(config, "API_KEY_VIEWER", "")

    # 2. Create a trader user in DB
    test_key = "tk_trader_123"
    create_user({
        "api_key": test_key,
        "username": "test_trader",
        "role": "trader",
        "is_active": 1,
        "is_service_account": 0
    }, db_path=db_path)

    # 3. Authenticate with DB key
    response = client.get("/api/config", headers={"X-API-KEY": test_key})
    assert response.status_code == 200
    assert response.json()["execution_mode"] is not None

def test_db_user_role_enforcement(db_path, monkeypatch):
    """Verify that DB user roles are enforced."""
    from db.repository import create_user
    
    monkeypatch.setattr(config, "MARKET_DB", db_path)
    monkeypatch.setattr(config, "API_KEY_ADMIN", "")

    # 1. Create a viewer user
    viewer_key = "tk_viewer_456"
    create_user({
        "api_key": viewer_key,
        "username": "test_viewer",
        "role": "viewer",
        "is_active": 1
    }, db_path=db_path)

    # 2. Try to access admin endpoint (run-cycle)
    response = client.post("/api/run/run-cycle", json={}, headers={"X-API-KEY": viewer_key})
    assert response.status_code == 403

def test_inactive_db_user(db_path, monkeypatch):
    """Verify that inactive DB users cannot authenticate."""
    from db.repository import create_user, get_connection, q
    
    monkeypatch.setattr(config, "MARKET_DB", db_path)
    
    # Create an inactive user
    key = "tk_inactive"
    create_user({
        "api_key": key,
        "username": "lazy_user",
        "role": "admin",
        "is_active": 0
    }, db_path=db_path)

    # Authenticate (should fail because get_user_by_api_key filters by is_active=1)
    response = client.get("/api/config", headers={"X-API-KEY": key})
    assert response.status_code == 403

def test_fallback_to_static_keys(db_path, monkeypatch):
    """Verify that static config keys still work (backward compatibility)."""
    monkeypatch.setattr(config, "MARKET_DB", db_path)
    monkeypatch.setattr(config, "API_KEY_ADMIN", "static-admin-key")

    # DB is empty, should fallback to static
    response = client.get("/api/config", headers={"X-API-KEY": "static-admin-key"})
    assert response.status_code == 200
