from __future__ import annotations

from datetime import datetime, timezone


def utc_now() -> datetime:
    """Return the current timezone-aware UTC datetime."""

    return datetime.now(timezone.utc)


def utc_now_iso(*, timespec: str = "seconds") -> str:
    """Return the current UTC datetime as an ISO-8601 string."""

    return utc_now().isoformat(timespec=timespec)