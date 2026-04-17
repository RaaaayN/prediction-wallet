"""Database connections: SQLite (default) or PostgreSQL when ``DATABASE_URL`` is set."""

from __future__ import annotations

import threading
from collections.abc import Generator
from contextlib import contextmanager
from typing import Any

from config import DATABASE_URL, MARKET_DB, USE_POSTGRES

_init_lock = threading.Lock()
_sqlite_initialized: set[str] = set()
_pg_initialized = False

_sqlalchemy_engine: Any = None


def q(sql: str) -> str:
    """Adapt ``?`` placeholders to PostgreSQL ``%s`` when using Postgres."""
    if USE_POSTGRES:
        return sql.replace("?", "%s")
    return sql


def excluded_qualifier() -> str:
    """SQLite uses ``excluded``; PostgreSQL expects ``EXCLUDED`` for upsert rows."""
    return "EXCLUDED" if USE_POSTGRES else "excluded"


@contextmanager
def get_connection(db_path: str = MARKET_DB) -> Generator[Any, None, None]:
    """Yield a DB connection (sqlite3 or psycopg). Commits on successful exit for psycopg."""
    from db.schema import init_db

    global _pg_initialized
    if USE_POSTGRES:
        with _init_lock:
            if not _pg_initialized:
                init_db(None)
                _pg_initialized = True
        import psycopg
        from psycopg.rows import dict_row

        with psycopg.connect(DATABASE_URL or "", row_factory=dict_row) as conn:
            yield conn
        return

    with _init_lock:
        if db_path not in _sqlite_initialized:
            init_db(db_path)
            _sqlite_initialized.add(db_path)
    import sqlite3

    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
    finally:
        conn.close()


def get_sqlalchemy_engine() -> Any:
    """SQLAlchemy engine for pandas ``to_sql`` / ``read_sql`` when using PostgreSQL."""
    global _sqlalchemy_engine
    if not USE_POSTGRES:
        raise RuntimeError("get_sqlalchemy_engine() is only valid when DATABASE_URL is set")
    if _sqlalchemy_engine is None:
        from sqlalchemy import create_engine

        url = DATABASE_URL or ""
        if url.startswith("postgresql://") and not url.startswith("postgresql+psycopg://"):
            url = "postgresql+psycopg://" + url[len("postgresql://") :]
        _sqlalchemy_engine = create_engine(url, pool_pre_ping=True)
    return _sqlalchemy_engine
