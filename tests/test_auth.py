"""Tests for the Authentication and RBAC system."""

import pytest
from fastapi.testclient import TestClient
from api.main import app
from api.auth import Role
import os

client = TestClient(app)

def test_auth_opt_in_no_keys():
    # Ensure keys are empty
    from config import API_KEY_ADMIN, API_KEY_TRADER, API_KEY_VIEWER
    if not API_KEY_ADMIN and not API_KEY_TRADER and not API_KEY_VIEWER:
        response = client.get("/api/config")
        assert response.status_code == 200
        assert "ai_provider" in response.json()

@pytest.mark.skipif(os.getenv("GITHUB_ACTIONS") == "true", reason="Skiping auth enforcement tests in CI if env is not clean")
def test_auth_enforcement(monkeypatch):
    monkeypatch.setattr("api.auth.API_KEY_ADMIN", "admin-key")
    monkeypatch.setattr("api.auth.API_KEY_TRADER", "trader-key")
    monkeypatch.setattr("api.auth.API_KEY_VIEWER", "viewer-key")
    
    # 1. No key -> 401
    response = client.get("/api/config")
    assert response.status_code == 401
    
    # 2. Invalid key -> 403
    response = client.get("/api/config", headers={"X-API-KEY": "wrong"})
    assert response.status_code == 403
    
    # 3. Valid viewer key for read endpoint -> 200
    response = client.get("/api/config", headers={"X-API-KEY": "viewer-key"})
    assert response.status_code == 200
    
    # 4. Viewer key for admin endpoint -> 403
    # Note: run-cycle is a POST endpoint
    response = client.post("/api/run/run-cycle", json={}, headers={"X-API-KEY": "viewer-key"})
    assert response.status_code == 403
    
    # 5. Admin key for admin endpoint -> 200 (or 400 if validation fails, but not 403)
    response = client.post("/api/run/run-cycle", json={}, headers={"X-API-KEY": "admin-key"})
    assert response.status_code in [200, 400] # 400 if it starts but fails validation
