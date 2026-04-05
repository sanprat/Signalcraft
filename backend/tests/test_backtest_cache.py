"""
Tests for the backtest-cache key builder and Redis helpers.

Mocks the Redis client and parquet file system so tests run without
an actual Redis server or candle data.
"""

from datetime import date, timedelta
from unittest.mock import MagicMock, patch

import pytest

from app.core.backtest_cache import (
    BACKTEST_ENGINE_VERSION,
    assemble_cache_payload,
    build_cache_key,
    build_deterministic_backtest_id,
    get_cached_backtest,
    purge_backtest_cache,
    register_cache_key_for_strategy,
    rebuild_artifacts_from_cache,
    set_cached_backtest,
    _resolve_effective_dates,
)

# ── Fixtures ─────────────────────────────────────────────────────────────────

SAMPLE_STRATEGY = {
    "name": "Test SMA Cross",
    "symbols": ["RELIANCE", "TCS"],
    "timeframe": "5min",
    "entry_logic": "ALL",
    "exit_logic": "ANY",
    "entry_conditions": [],
    "exit_rules": [],
    "risk": {"max_trades_per_day": 0, "max_loss_per_day": 0, "quantity": 1, "reentry_after_sl": False},
    "backtest_from": "2024-01-01",
    "backtest_to": "2024-06-30",
}

SAMPLE_CACHE_PAYLOAD = {
    "summary": {
        "backtest_id": "abc1234567",
        "total_trades": 10,
        "winning_trades": 6,
        "losing_trades": 4,
        "win_rate": 60.0,
        "total_pnl": 500.0,
        "max_drawdown": 100.0,
        "avg_trade_pnl": 50.0,
        "best_trade": 120.0,
        "worst_trade": -40.0,
        "candle_count": 5000,
        "date_range": "2024-01-01 to 2024-06-30",
        "execution_time_ms": 123.45,
        "strategy_name": "Test SMA Cross",
        "timeframe": "5min",
        "mode": "quick",
        "symbols": ["RELIANCE", "TCS"],
    },
    "trades": [{"trade_no": 1, "entry_time": "2024-01-01T09:15:00", "entry_price": 100, "exit_time": "2024-01-01T09:20:00", "exit_price": 101, "pnl": 100, "pnl_pct": 1.0, "exit_reason": "TARGET"}],
    "per_symbol": {},
    "equity_curve": [{"time": "2024-01-01T09:15:00", "equity": 0, "symbol": "RELIANCE"}],
    "had_candles_parquet": False,
}

def _make_mock_redis():
    """Create a pure dict-backed mock that mimics the redis.Redis API we use."""
    store = {}
    sets = {}  # set_key -> set of members

    mock = MagicMock()

    def _get(key):
        return store.get(key)

    def _setex(key, ttl, value):
        store[key] = value

    def _delete(key):
        store.pop(key, None)

    def _sadd(key, *members):
        if key not in sets:
            sets[key] = set()
        sets[key].update(members)

    def _smembers(key):
        return sets.get(key, set())

    mock.get.side_effect = _get
    mock.setex.side_effect = _setex
    mock.delete.side_effect = _delete
    mock.sadd.side_effect = _sadd
    mock.smembers.side_effect = _smembers
    return mock, store, sets


def _patch_redis(mock_redis):
    """Context-like helper — patches `_get_redis_client` to return our mock."""
    return patch("app.core.backtest_cache._get_redis_client", return_value=mock_redis)


# ── Tests ────────────────────────────────────────────────────────────────────

class TestEffectiveDateResolution:
    """Ensure the cache key builder mirrors the engine's date logic."""

    def test_explicit_dates_returned_as_is(self):
        f, t = _resolve_effective_dates("2024-01-01", "2024-12-31", "quick")
        assert f == "2024-01-01"
        assert t == "2024-12-31"

    def test_quick_mode_defaults_to_180_days(self):
        today = date.today()
        f, t = _resolve_effective_dates("", "", "quick")
        assert t == today.isoformat()
        assert f == (today - timedelta(days=180)).isoformat()

    def test_full_mode_defaults_to_3_years(self):
        today = date.today()
        f, t = _resolve_effective_dates("", "", "full")
        assert t == today.isoformat()
        assert f == (today - timedelta(days=365 * 3)).isoformat()

    def test_from_defaults_to_mode_when_to_explicit(self):
        today = date.today()
        f, t = _resolve_effective_dates("", today.isoformat(), "quick")
        assert t == today.isoformat()
        assert f == (today - timedelta(days=180)).isoformat()

    def test_invalid_dates_fallback_to_today_and_mode(self):
        today = date.today()
        f, t = _resolve_effective_dates("not-a-date", "also-bad", "quick")
        assert t == today.isoformat()
        assert f == (today - timedelta(days=180)).isoformat()


class TestCacheKeyDeterminism:
    """Same input must always produce the identical key."""

    def _call(self, **overrides):
        d = dict(SAMPLE_STRATEGY)
        d.update(overrides)
        return build_cache_key(
            strategy_dict=d,
            strategy_id="s-001",
            mode=overrides.get("mode", "quick"),
            symbols=d["symbols"],
            timeframe=d["timeframe"],
            backtest_from=d.get("backtest_from"),
            backtest_to=d.get("backtest_to"),
        )

    @patch("app.core.backtest_cache._parquet_mtimes", return_value=[])
    def test_same_inputs_same_key(self, _mt):
        assert self._call() == self._call()

    @patch("app.core.backtest_cache._parquet_mtimes", return_value=[])
    def test_different_name_different_key(self, _mt):
        k1 = SAMPLE_STRATEGY.copy()
        k2 = SAMPLE_STRATEGY.copy()
        k2["name"] = "Different Name"
        assert build_cache_key(SAMPLE_STRATEGY, "s-001", "quick", k1["symbols"], k1["timeframe"], k1.get("backtest_from"), k1.get("backtest_to")) != \
               build_cache_key(k2, "s-001", "quick", k2["symbols"], k2["timeframe"], k2.get("backtest_from"), k2.get("backtest_to"))

    @patch("app.core.backtest_cache._parquet_mtimes", return_value=[])
    def test_different_timeframe_different_key(self, _mt):
        d = SAMPLE_STRATEGY.copy()
        d["timeframe"] = "15min"
        assert build_cache_key(SAMPLE_STRATEGY, "s-001", "quick", SAMPLE_STRATEGY["symbols"], SAMPLE_STRATEGY["timeframe"], SAMPLE_STRATEGY.get("backtest_from"), SAMPLE_STRATEGY.get("backtest_to")) != \
               build_cache_key(d, "s-001", "quick", d["symbols"], d["timeframe"], d.get("backtest_from"), d.get("backtest_to"))

    @patch("app.core.backtest_cache._parquet_mtimes", return_value=["RELIANCE:1730000000"])
    def test_parquet_mtime_changes_key_changes(self, _mt):
        k1 = build_cache_key(SAMPLE_STRATEGY, "s-001", "quick", SAMPLE_STRATEGY["symbols"], SAMPLE_STRATEGY["timeframe"], SAMPLE_STRATEGY.get("backtest_from"), SAMPLE_STRATEGY.get("backtest_to"))
        with patch("app.core.backtest_cache._parquet_mtimes", return_value=["RELIANCE:1730000001"]):
            k2 = build_cache_key(SAMPLE_STRATEGY, "s-001", "quick", SAMPLE_STRATEGY["symbols"], SAMPLE_STRATEGY["timeframe"], SAMPLE_STRATEGY.get("backtest_from"), SAMPLE_STRATEGY.get("backtest_to"))
        assert k1 != k2

    @patch("app.core.backtest_cache._parquet_mtimes", return_value=[])
    def test_mode_change_changes_key(self, _mt):
        d = SAMPLE_STRATEGY.copy()
        d["mode"] = "full"
        assert build_cache_key(SAMPLE_STRATEGY, "s-001", "quick", SAMPLE_STRATEGY["symbols"], SAMPLE_STRATEGY["timeframe"], SAMPLE_STRATEGY.get("backtest_from"), SAMPLE_STRATEGY.get("backtest_to")) != \
               build_cache_key(SAMPLE_STRATEGY, "s-001", "full", SAMPLE_STRATEGY["symbols"], SAMPLE_STRATEGY["timeframe"], SAMPLE_STRATEGY.get("backtest_from"), SAMPLE_STRATEGY.get("backtest_to"))


class TestCacheRoundTrip:
    """get/set with mock Redis must store and retrieve correctly."""

    def test_set_and_get(self):
        mock_redis, store, _ = _make_mock_redis()
        with patch("app.core.backtest_cache._get_redis_client", return_value=mock_redis):
            assert set_cached_backtest("bt:key123", SAMPLE_CACHE_PAYLOAD)
            result = get_cached_backtest("bt:key123")
            assert result is not None
            assert result["summary"]["total_trades"] == 10

    def test_get_returns_none_for_missing_key(self):
        mock_redis, store, _ = _make_mock_redis()
        with patch("app.core.backtest_cache._get_redis_client", return_value=mock_redis):
            assert get_cached_backtest("bt:nonexistent") is None


class TestPurgeAndInvalidate:
    """Purging via strategy_id index must delete registered cache keys."""

    def test_register_and_purge(self):
        mock_redis, store, sets = _make_mock_redis()
        with patch("app.core.backtest_cache._get_redis_client", return_value=mock_redis):
            k1 = "bt:aaaa"
            k2 = "bt:bbbb"
            set_cached_backtest(k1, {"summary": {"a": 1}})
            set_cached_backtest(k2, {"summary": {"b": 2}})
            register_cache_key_for_strategy("s-001", k1)
            register_cache_key_for_strategy("s-001", k2)

            # Both keys stored
            assert k1 in store
            assert k2 in store

            # Purge
            count = purge_backtest_cache("s-001")
            assert count == 2
            assert k1 not in store
            assert k2 not in store


class TestDeterministicBacktestId:
    """Same cache key must yield the same backtest_id."""

    def test_stable_id(self):
        id1 = build_deterministic_backtest_id("bt:example")
        id2 = build_deterministic_backtest_id("bt:example")
        assert id1 == id2
        assert len(id1) == 10

    def test_different_keys_different_ids(self):
        assert build_deterministic_backtest_id("bt:aaa") != build_deterministic_backtest_id("bt:bbb")


class TestArtifactRebuild:
    """rebuild_artifacts_from_cache must create the expected JSON files."""

    def test_rebuild_creates_files(self, tmp_path):
        bt_dir = tmp_path / "abc123"
        rebuild_artifacts_from_cache("abc123", tmp_path, SAMPLE_CACHE_PAYLOAD)

        assert (bt_dir / "summary.json").exists()
        assert (bt_dir / "trades.json").exists()
        assert (bt_dir / "per_symbol.json").exists()
        assert (bt_dir / "equity_curve.json").exists()

        import json
        summary = json.loads((bt_dir / "summary.json").read_text())
        assert summary["total_trades"] == 10
