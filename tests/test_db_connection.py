"""Tests for DB connection helpers (SQLite mode)."""

import pytest

import db.connection as connection_module


def test_q_sqlite_no_change(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(connection_module, "USE_POSTGRES", False)
    assert connection_module.q("SELECT * FROM t WHERE a = ? AND b = ?") == "SELECT * FROM t WHERE a = ? AND b = ?"


def test_q_postgres_placeholders(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(connection_module, "USE_POSTGRES", True)
    assert connection_module.q("SELECT * FROM t WHERE a = ?") == "SELECT * FROM t WHERE a = %s"


def test_excluded_qualifier(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(connection_module, "USE_POSTGRES", False)
    assert connection_module.excluded_qualifier() == "excluded"
    monkeypatch.setattr(connection_module, "USE_POSTGRES", True)
    assert connection_module.excluded_qualifier() == "EXCLUDED"
