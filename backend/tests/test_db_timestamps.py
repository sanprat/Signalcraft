from __future__ import annotations

from datetime import datetime, timedelta, timezone

from app.db_models.timestamps import utc_now_naive


def test_utc_now_naive_returns_naive_datetime():
    value = utc_now_naive()

    assert isinstance(value, datetime)
    assert value.tzinfo is None


def test_utc_now_naive_tracks_current_utc_time():
    value = utc_now_naive()
    now_utc_naive = datetime.now(timezone.utc).replace(tzinfo=None)

    assert abs(now_utc_naive - value) < timedelta(seconds=5)
