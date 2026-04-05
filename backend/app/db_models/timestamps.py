"""Timestamp helpers for ORM models.

These models map to raw PostgreSQL tables declared with `TIMESTAMP` columns
without timezone. We therefore persist UTC timestamps as naive datetimes and
treat them consistently as UTC at the application boundary.
"""

from __future__ import annotations

from datetime import datetime, timezone


def utc_now_naive() -> datetime:
    """Return the current UTC time as a naive datetime.

    This matches the project's PostgreSQL schema, which uses `TIMESTAMP`
    rather than `TIMESTAMPTZ` for created/updated audit columns.
    """

    return datetime.now(timezone.utc).replace(tzinfo=None)
