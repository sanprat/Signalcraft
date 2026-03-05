import os
import json
from typing import Optional, List, Dict, Any
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
import logging
import redis
from concurrent.futures import ProcessPoolExecutor, as_completed

from app.services.screener import SCREENERS, load_symbol_data, run_screener

router = APIRouter(prefix="/api/screeners", tags=["screeners"])
logger = logging.getLogger(__name__)

# Initialize Redis client. Assumes a service named 'redis' or localhost in dev.
REDIS_URL = os.getenv("REDIS_URL", "redis://pystock_redis:6379/1") # matching the redis service in docker-compose if exists, else fallback
try:
    # Try pystock_redis (from docker ps) or fallback to redis
    redis_client = redis.Redis.from_url(REDIS_URL, decode_responses=True)
except Exception as e:
    redis_client = None
    logger.warning(f"Failed to connect to Redis: {e}")

class ScreenerRequest(BaseModel):
    screener_ids: List[str]  # Support multiple screeners
    params: Optional[Dict[str, dict]] = None  # Map screener_id -> params

@router.get("/list")
def get_screeners_list():
    """
    Returns a list of all available screeners with their default parameters.
    """
    return {
        "screeners": [
            {"id": "minervini_trend_template", "name": "Minervini Trend Template", "params": {
                "sma_50": 50, "sma_150": 150, "sma_200": 200, "sma_200_lookback": 22,
                "rs_min": 70, "pct_above_52w_low": 25, "pct_below_52w_high": 25
            }},
            {"id": "vcp", "name": "Minervini VCP", "params": {
                "swing_order": 5, "min_contractions": 2, "max_contractions": 4,
                "max_last_contraction_pct": 10, "pivot_proximity_pct": 3, "lookback": 252
            }},
            {"id": "ibd_canslim", "name": "IBD CAN SLIM (Technical)", "params": {
                "pct_below_52w_high": 15, "avg_volume_min": 400000,
                "base_length_min_weeks": 5, "base_depth_max_pct": 33, "lookback": 252
            }},
            {"id": "weinstein_stage2", "name": "Stan Weinstein Stage 2", "params": {
                "lookback": 252
            }},
            {"id": "ema_crossover", "name": "EMA Crossover (50/200)", "params": {
                "fast": 50, "slow": 200, "signal": "golden", "lookback": 3
            }},
            {"id": "rsi_momentum", "name": "RSI Momentum", "params": {
                "period": 14, "mode": "momentum", "threshold": 50, "lookback": 3
            }},
            {"id": "breakout_52w", "name": "52-Week High Breakout", "params": {
                "lookback": 252, "vol_mult": 1.5, "buffer": 0.5
            }},
            {"id": "macd_crossover", "name": "MACD Crossover", "params": {
                "fast": 12, "slow": 26, "signal": 9, "mode": "bullish", "lookback": 3
            }},
            {"id": "bollinger_squeeze", "name": "Bollinger Band Squeeze", "params": {
                "period": 20, "std": 2, "squeeze_pct": 5, "direction": "bullish"
            }},
            {"id": "volume_surge", "name": "Volume Surge", "params": {
                "period": 50, "multiplier": 2.0, "min_avg": 500000, "direction": "up", "min_move": 1.0
            }},
            {"id": "adx_strength", "name": "ADX Trend Strength", "params": {
                "period": 14, "min_adx": 25, "direction": "bullish"
            }},
            {"id": "darvas_box", "name": "Darvas Box Breakout", "params": {
                "formation": 10, "ceiling_tol": 1.0, "vol_mult": 1.5, "lookback": 252
            }}
        ]
    }

def _run_single_screener(args):
    screener_id, symbol, params = args
    return run_screener(screener_id, symbol, params)


@router.post("/run")
def run_screener_on_universe(req: ScreenerRequest):
    """
    Runs one or more screeners against all Nifty 500 stocks locally using parquet files.
    Returns stocks that pass ALL selected screeners (intersection).
    """
    # Validate all screener IDs
    for screener_id in req.screener_ids:
        if screener_id not in SCREENERS:
            raise HTTPException(status_code=400, detail=f"Invalid screener_id: {screener_id}")

    # Build cache key from all screener IDs and params
    cache_key = f"screener_results:{'+'.join(sorted(req.screener_ids))}"
    if req.params:
        cache_key += f":{json.dumps(req.params, sort_keys=True)}"

    try:
        if redis_client:
            cached_data = redis_client.get(cache_key)
            if cached_data:
                logger.info(f"Returning cached results for {cache_key}")
                return json.loads(cached_data)
    except Exception as e:
        logger.warning(f"Redis cache read error: {e}")

    base_dir = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
    nifty500_dir = os.path.join(base_dir, "data", "candles", "NIFTY500")

    if not os.path.exists(nifty500_dir):
        logger.error(f"NIFTY500 directory not found: {nifty500_dir}")
        raise HTTPException(status_code=500, detail="Nifty 500 data missing")

    symbols = [
        d for d in os.listdir(nifty500_dir)
        if os.path.isdir(os.path.join(nifty500_dir, d))
    ]

    # Run all screeners for all stocks
    # Structure: {symbol: [result1, result2, ...]}
    symbol_results: Dict[str, List[dict]] = {}

    for sym in symbols:
        sym_results = []
        for screener_id in req.screener_ids:
            params = (req.params or {}).get(screener_id, None)
            res = run_screener(screener_id, sym, params)
            res['screener_id'] = screener_id  # Tag with screener ID
            sym_results.append(res)
        symbol_results[sym] = sym_results

    # Filter to only stocks that pass ALL screeners
    results = []
    for sym, sym_results in symbol_results.items():
        all_passed = all(r.get("pass", False) for r in sym_results)
        if all_passed:
            # Combine all results into one record
            combined = {"symbol": sym, "pass": True, "screeners_passed": len(req.screener_ids)}
            for res in sym_results:
                # Add all metrics from each screener (prefix with screener name to avoid collisions)
                screener_prefix = res.get("screener_id", "unknown")
                for k, v in res.items():
                    if k not in ["screener", "pass", "error", "symbol"]:
                        combined[f"{screener_prefix}_{k}"] = v
            results.append(combined)

    # Sort results based on primary screener (first one)
    primary = req.screener_ids[0]
    if primary == "rsi_momentum":
        results.sort(key=lambda x: x.get("rsi_momentum_rsi_current", 0), reverse=True)
    elif primary == "minervini_trend_template":
        results.sort(key=lambda x: x.get("minervini_trend_template_perf_12m", 0), reverse=True)

    final_response = {"results": results, "count": len(results)}

    # Save to Redis Cache for 1 hour
    try:
        if redis_client:
            redis_client.setex(cache_key, 3600, json.dumps(final_response))
            logger.info(f"Cached results for {cache_key}")
    except Exception as e:
        logger.warning(f"Redis cache write error: {e}")

    return final_response
