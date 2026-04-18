"""Database connections: SQLite (default) or PostgreSQL when ``DATABASE_URL`` is set."""

from __future__ import annotations

import threading
from collections.abc import Generator
from contextlib import contextmanager
from typing import Any

_init_lock = threading.Lock()
_sqlite_initialized: set[str] = set()
_pg_initialized = False

_sqlalchemy_engine: Any = None


def clear_connection_cache() -> None:
    """Reset the global connection state. Useful for unit tests with multiple DBs."""
    global _pg_initialized, _sqlite_initialized
    with _init_lock:
        _pg_initialized = False
        _sqlite_initialized = set()


def q(sql: str) -> str:
    """Adapt ``?`` placeholders to PostgreSQL ``%s`` when using Postgres."""
    from config import USE_POSTGRES
    if USE_POSTGRES:
        return sql.replace("?", "%s")
    return sql


def excluded_qualifier() -> str:
    """SQLite uses ``excluded``; PostgreSQL expects ``EXCLUDED`` for upsert rows."""
    from config import USE_POSTGRES
    return "EXCLUDED" if USE_POSTGRES else "excluded"


@contextmanager
def get_connection(db_path: str | None = None) -> Generator[Any, None, None]:
    """Yield a DB connection (sqlite3 or psycopg). Commits on successful exit for psycopg."""
    from db.schema import init_db
    import config
    
    # DYNAMIC RESOLUTION
    path = db_path or config.MARKET_DB
    use_pg = config.USE_POSTGRES
    db_url = config.DATABASE_URL
    
    global _pg_initialized
    if use_pg:
        with _init_lock:
            if not _pg_initialized:
                init_db(None)
                _pg_initialized = True
        import psycopg
        from psycopg.rows import dict_row

        with psycopg.connect(db_url or "", row_factory=dict_row) as conn:
            yield conn
        return

    with _init_lock:
        if path not in _sqlite_initialized:
            init_db(path)
            _sqlite_initialized.add(path)
    import sqlite3

    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
    finally:
        conn.close()


def get_sqlalchemy_engine() -> Any:
    """SQLAlchemy engine for pandas ``to_sql`` / ``read_sql`` when using PostgreSQL."""
    import config
    global _sqlalchemy_engine
    if not config.USE_POSTGRES:
        raise RuntimeError("get_sqlalchemy_engine() is only valid when DATABASE_URL is set")
    if _sqlalchemy_engine is None:
        from sqlalchemy import create_engine

        url = config.DATABASE_URL or ""
        if url.startswith("postgresql://") and not url.startswith("postgresql+psycopg://"):
            url = "postgresql+psycopg://" + url[len("postgresql://") :]
        _sqlalchemy_engine = create_engine(url, pool_pre_ping=True)
    return _sqlalchemy_engine
