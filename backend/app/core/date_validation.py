"""Date validation helpers shared across backend routes.

This is intentionally a second line of defense behind schema/UI validation.
If stale frontend code or legacy payloads bypass normal request validation,
these helpers ensure malformed backtest dates still fail as a client error
instead of bubbling up later as runtime parsing failures.
"""

from __future__ import annotations

from datetime import date
from typing import Optional

from fastapi import HTTPException


def coerce_backtest_date(value: object) -> Optional[str]:
    """Return a validated YYYY-MM-DD string or None for malformed legacy values."""
    if value in (None, ""):
        return None
    if not isinstance(value, str):
        return None
    if len(value) != 10 or value.count("-") != 2:
        return None
    try:
        return date.fromisoformat(value).isoformat()
    except ValueError:
        return None


def validate_backtest_date_range(
    backtest_from: Optional[str], backtest_to: Optional[str]
) -> None:
    """Validate backtest date inputs and ordering.

    Accepts missing values, but when both are present they must be valid
    ISO calendar dates in YYYY-MM-DD form and `backtest_to >= backtest_from`.
    """
    parsed_dates: dict[str, date] = {}

    for field_name, value in (
        ("backtest_from", backtest_from),
        ("backtest_to", backtest_to),
    ):
        if not value:
            continue
        normalized = coerce_backtest_date(value)
        if normalized is None:
            raise HTTPException(
                status_code=422,
                detail=f"Invalid {field_name}: '{value}'. Expected YYYY-MM-DD.",
            )
        parsed_dates[field_name] = date.fromisoformat(normalized)

    if (
        "backtest_from" in parsed_dates
        and "backtest_to" in parsed_dates
        and parsed_dates["backtest_to"] < parsed_dates["backtest_from"]
    ):
        raise HTTPException(
            status_code=422,
            detail="Invalid backtest date range: backtest_to must be on or after backtest_from.",
        )
