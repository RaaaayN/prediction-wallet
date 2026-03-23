"""Timezone-aware UTC helpers."""

from __future__ import annotations

from datetime import UTC, datetime


def utc_now() -> datetime:
    """Return an aware UTC datetime."""
    return datetime.now(UTC)


def utc_now_iso() -> str:
    """Return an ISO8601 UTC timestamp."""
    return utc_now().isoformat()


def utc_today_str() -> str:
    """Return the current UTC date as YYYY-MM-DD."""
    return utc_now().strftime("%Y-%m-%d")
