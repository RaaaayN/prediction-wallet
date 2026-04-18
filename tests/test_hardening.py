"""Tests for the Hardening Production phase."""

import pytest
from fastapi.testclient import TestClient
from api.main import app
from services.health_service import HealthService
from services.back_office_service import BackOfficeService
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
    
    svc = HealthService()
    health = svc.get_full_health()
    assert health["status"] == "up"
    assert "database" in health["checks"]
    
    response = client.get("/api/health")
    assert response.status_code == 200
    assert response.json()["status"] == "up"

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
