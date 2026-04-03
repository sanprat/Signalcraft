"""
Backtest result cache backed by Redis.

Key design:
- Cache key includes strategy payload hash, not just strategy_id
- Deterministic backtest_id derived from the cache key hash
- Parquet file mtimes baked into the key to invalidate on data refresh
- Redis hit rebuilds missing disk artifacts from cached payload
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
from datetime import date, timedelta
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

import redis

from app.core.strategy_engine_v2 import DATA_DIR, TIMEFRAME_MAP

logger = logging.getLogger(__name__)

# ── Version markers ─────────────────────────────────────────────────────────
BACKTEST_ENGINE_VERSION = "v2.1"
BACKTEST_CACHE_TTL_SECONDS = 24 * 3600  # 24 hours

# ── Redis client (lazy init with timeouts) ───────────────────────────────────
REDIS_URL = os.getenv("REDIS_URL", "redis://redis:6379/2")  # dedicated DB 2

_redis_client: Optional[redis.Redis] = None
_redis_init_attempted = False


def _get_redis_client() -> Optional[redis.Redis]:
    """Lazily initialize Redis with explicit timeouts to avoid import blocking."""
    global _redis_client, _redis_init_attempted
    if _redis_init_attempted:
        return _redis_client
    _redis_init_attempted = True
    try:
        client = redis.Redis.from_url(
            REDIS_URL,
            decode_responses=True,
            socket_connect_timeout=2,
            socket_timeout=3,
            retry_on_timeout=True,
        )
        client.ping()
        _redis_client = client
        logger.info("Redis connected for backtest caching")
    except Exception:
        _redis_client = None
        logger.warning("Redis unavailable for backtest caching; cache will be a no-op")
    return _redis_client


# ── Cache key builder ────────────────────────────────────────────────────────


def _parquet_mtimes(symbols: list[str], timeframe: str) -> list[str]:
    """
    Return sorted list of parquet file mtimes for every symbol.
    If a file doesn't exist, its entry is simply skipped so the key stays
    stable even when data is sparse (and changes when files appear).
    """
    mtimes: list[str] = []
    tf_file = TIMEFRAME_MAP.get(timeframe, timeframe)
    for sym in sorted(symbols):
        p = DATA_DIR / "NIFTY500" / sym / f"{tf_file}.parquet"
        if p.exists():
            mtimes.append(f"{sym}:{p.stat().st_mtime:.0f}")
    return mtimes


def _normalize_strategy_payload(strategy_dict: dict) -> bytes:
    """
    Produce a deterministic JSON bytes representation:
    - Sort keys
    - Strip volatile fields that shouldn't affect the cache
    """
    stripped = {k: v for k, v in strategy_dict.items() if k != "strategy_id"}
    return json.dumps(stripped, sort_keys=True, default=str).encode()


def _resolve_effective_dates(backtest_from: str, backtest_to: str, mode: str) -> Tuple[str, str]:
    """
    Mirror the engine's date resolution so the cache key matches the actual
    data range used. The engine always defaults to date.today() and uses
    mode-based offsets when explicit dates are absent.
    """
    to_date = date.today()
    from_date = None

    try:
        to_date = date.fromisoformat(backtest_to) if backtest_to else date.today()
    except ValueError:
        to_date = date.today()

    try:
        from_date = date.fromisoformat(backtest_from) if backtest_from else None
    except ValueError:
        from_date = None

    if from_date is None:
        from_date = to_date - timedelta(days=180 if mode == "quick" else 365 * 3)

    return from_date.isoformat(), to_date.isoformat()

def build_cache_key(
    strategy_dict: dict,
    strategy_id: Optional[str],
    mode: str,
    symbols: list[str],
    timeframe: str,
    backtest_from: Optional[str] = None,
    backtest_to: Optional[str] = None,
) -> str:
    """
    Build a stable cache key that changes when:
    - strategy payload changes (content hash)
    - any symbol's parquet file is updated (mtime)
    - date range changes
    - engine version changes (invalidates old cache automatically)
    """
    payload_hash = hashlib.sha256(
        _normalize_strategy_payload(strategy_dict)
    ).hexdigest()[:16]

    mtimes = _parquet_mtimes(symbols, timeframe)
    mtimes_tag = ",".join(mtimes) if mtimes else "no_data"

    id_tag = (
        strategy_id
        or hashlib.sha256(
            json.dumps(strategy_dict, sort_keys=True).encode()
        ).hexdigest()[:8]
    )

    # Resolve the effective date range exactly as the engine does.
    # Critical: without it, two runs with empty dates key identically
    # despite the engine sliding their windows forward by one day each time.
    effective_from, effective_to = _resolve_effective_dates(
        backtest_from or "", backtest_to or "", mode
    )

    raw_key = (
        f"backtest:v2:{BACKTEST_ENGINE_VERSION}:{id_tag}:"
        f"{payload_hash}:{mode}:{effective_from}:{effective_to}:{timeframe}:{mtimes_tag}"
    )
    # Hash the full key so Redis doesn't blow up on long keys
    key_hash = hashlib.sha256(raw_key.encode()).hexdigest()[:24]
    return f"bt:{key_hash}"


def build_deterministic_backtest_id(cache_key: str) -> str:
    """Derive a stable backtest_id from the cache key — first 10 hex chars."""
    return hashlib.sha256(cache_key.encode()).hexdigest()[:10]


# ── Redis accessors ──────────────────────────────────────────────────────────


def get_cached_backtest(cache_key: str) -> Optional[Dict[str, Any]]:
    """Return cached backtest payload or None."""
    client = _get_redis_client()
    if not client:
        return None
    try:
        raw = client.get(cache_key)
        if raw is None:
            return None
        data = json.loads(raw)
        logger.info("[Cache] HIT  key=%s", cache_key[:32])
        return data
    except Exception as e:
        logger.warning("[Cache] Read error: %s", e)
        return None


def set_cached_backtest(
    cache_key: str, payload: Dict[str, Any], ttl: int = BACKTEST_CACHE_TTL_SECONDS
) -> bool:
    """Store backtest payload in Redis. Returns False on failure."""
    client = _get_redis_client()
    if not client:
        return False
    try:
        client.setex(cache_key, ttl, json.dumps(payload, default=str))
        logger.info(
            "[Cache] SET  key=%s ttl=%ss size=%d",
            cache_key[:32],
            ttl,
            len(json.dumps(payload, default=str)),
        )
        return True
    except Exception as e:
        logger.warning("[Cache] Write error: %s", e)
        return False


def purge_backtest_cache(strategy_id: str) -> int:
    """
    Remove cached backtest entries when a strategy is modified.
    Uses a Redis SET index keyed by strategy_id for efficient
    purge without scanning all keys.
    """
    client = _get_redis_client()
    if not client:
        return 0
    set_key = f"bt:strategies:{strategy_id}"
    members = client.smembers(set_key)
    count = 0
    for cache_key in members:
        client.delete(cache_key)
        count += 1
    client.delete(set_key)
    if count:
        logger.info("[Cache] PURGED %d entries for strategy %s", count, strategy_id)
    return count


def register_cache_key_for_strategy(strategy_id: str, cache_key: str) -> None:
    """Register a cache key under a strategy_id set for later purge."""
    if not strategy_id:
        return
    client = _get_redis_client()
    if not client:
        return
    try:
        client.sadd(f"bt:strategies:{strategy_id}", cache_key)
    except Exception as e:
        logger.warning("[Cache] Could not register cache key: %s", e)


# ── Artifact rebuild ────────────────────────────────────────────────────────


def rebuild_artifacts_from_cache(
    backtest_id: str,
    backtests_dir: Path,
    cached_payload: Dict[str, Any],
) -> Path:
    """
    Reconstruct disk artifacts (summary.json, trades.json, etc.) from
    the cached payload when Redis has data but the files on disk were lost.
    Returns the backtest directory path.
    """
    backtest_dir = backtests_dir / backtest_id
    backtest_dir.mkdir(parents=True, exist_ok=True)

    summary = cached_payload.get("summary", {})
    equity_points = cached_payload.get("equity_curve", [])

    (backtest_dir / "summary.json").write_text(json.dumps(summary, indent=2))

    # Restore trades
    trades = cached_payload.get("trades", [])
    (backtest_dir / "trades.json").write_text(json.dumps(trades, indent=2))

    # Restore per_symbol
    per_symbol = cached_payload.get("per_symbol", {})
    (backtest_dir / "per_symbol.json").write_text(
        json.dumps(per_symbol, indent=2, default=str)
    )

    # Restore equity curve
    (backtest_dir / "equity_curve.json").write_text(json.dumps(equity_points, indent=2))

    # Candles parquet needs real data files; skip rebuild — candles endpoint
    # will return empty if parquet data is missing.
    candles_path = backtest_dir / "candles.parquet"
    if cached_payload.get("had_candles_parquet") and not candles_path.exists():
        logger.warning(
            "[Cache] Cached payload had candles.parquet but file missing; "
            "rebuilding requires candle data reload from parquet files."
        )

    logger.info("[Cache] Rebuilt artifacts for %s in %s", backtest_id, backtest_dir)
    return backtest_dir


def assemble_cache_payload(
    summary: dict,
    trades: list,
    per_symbol: dict,
    equity_curve: list,
    has_candles_parquet: bool,
) -> Dict[str, Any]:
    """Build the complete payload to store in Redis for later replay."""
    return {
        "summary": summary,
        "trades": trades,
        "per_symbol": per_symbol,
        "equity_curve": equity_curve,
        "had_candles_parquet": has_candles_parquet,
    }
