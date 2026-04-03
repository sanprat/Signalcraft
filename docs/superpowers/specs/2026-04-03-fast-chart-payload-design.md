# Fast Chart Payload Design

Date: 2026-04-03
Status: Draft
Author: Claude Code

## Problem

The backtest results page (`/backtest/[id]`) loads slowly because it fetches candles page-by-page (500 per request) in a sequential loop. For a full year of 5-minute candles, this can mean 100+ sequential round trips before the chart renders.

The Redis backtest cache already works — repeated runs return the same deterministic `backtest_id`. The remaining latency is entirely in chart data delivery.

## Solution Overview

Introduce a prebuilt `chart.json` artifact saved alongside backtest results on first creation, and a single `GET /api/backtest/{id}/chart` endpoint that serves it. The frontend replaces the paginated candle loop with one fetch, and caches the payload in `sessionStorage` by `backtest_id` for instant reopen.

## Architecture

### Components

```
backtests/{backtest_id}/
├── summary.json          (existing)
├── trades.json           (existing)
├── candles.parquet       (existing)
└── chart.json            (NEW — smart-range candles + annotations)
```

### Data Flow

1. **Cache miss** (first run): backtest engine computes results → saves `summary.json`, `trades.json`, `candles.parquet` → builds `chart.json`
2. **Cache hit** (Redis return): `strategy_v2.py` restores artifacts → checks `chart.json` exists → rebuilds if missing or stale
3. **Frontend load**: `GET /api/backtest/{id}/chart` → returns complete render-ready payload in one call

## Back-end Changes

### 1. `_build_chart_payload()` Function

**Location**: New function in `backend/app/routers/strategy_v2.py`

**Inputs**:
- `backtest_dir: Path` — `backtests/{id}/`
- Reads `trades.json`, `candles.parquet`

**Logic**:

1. Load trades from `trades.json`
2. Determine timeframe (intraday vs daily)
3. Compute smart range:
   - **Has trades**: `from = first_entry_time - buffer`, `to = last_exit_time + buffer`
   - **No trades**: fallback to last 90 days from latest candle
4. Buffers:
   - Intraday timeframes: ±5 trading days
   - Daily timeframes: ±20 candles
   - No trades: 90 days
5. If smart range exceeds 5000 candles:
   - Always include the entire trade window
   - Split remaining budget symmetrically before/after the window
   - Prefer including candles around trades over arbitrary head/tail
6. Query bounded candles from DuckDB:
   ```sql
   SELECT time, open, high, low, close, volume
   FROM read_parquet('{path}')
   WHERE time BETWEEN ? AND ?
   ORDER BY time
   ```
7. Build annotations from trades (BUY/SELL markers):
   ```json
   {
     "time": <trade_time_epoch_ms>,
     "value": <price>,
     "text": "BUY 1",
     "color": "#059669",
     "backgroundColor": "#ECFDF5",
     "side": "below"
   }
   ```
8. Save to `chart.json` (atomic write: `chart.json.tmp` → rename)

**Timezone guarantee**: All `time`, `display_from`, `display_to`, `full_from`, `full_to` values are ISO 8601 strings in `Asia/Kolkata` timezone. Apply `tz_convert("Asia/Kolkata")` before output.

### 2. `chart.json` Schema

```json
{
  "backtest_id": "abc123def4",
  "generated_at": "2026-04-03T10:30:00Z",
  "trade_count": 15,
  "symbol": "RELIANCE",
  "timeframe": "5m",
  "display_from": "2026-02-10T09:15:00+05:30",
  "display_to": "2026-04-05T15:30:00+05:30",
  "full_from": "2026-01-01T09:15:00+05:30",
  "full_to": "2026-04-05T15:30:00+05:30",
  "is_partial": true,
  "has_more_left": true,
  "has_more_right": true,
  "candles": {
    "time": ["2026-02-10T09:15:00+05:30", ...],
    "open": [1234.56, ...],
    "high": [1240.00, ...],
    "low": [1230.00, ...],
    "close": [1238.00, ...],
    "volume": [10000, ...]
  },
  "annotations": [
    {
      "time": 1739009700000,
      "value": 1234.56,
      "text": "BUY 1",
      "color": "#059669",
      "backgroundColor": "#ECFDF5",
      "side": "below"
    }
  ]
}
```

**Fields**:
- `backtest_id`: The deterministic ID, useful for debugging and cache validation
- `generated_at`: UTC timestamp when chart.json was built, for debugging
- `trade_count`: Number of trades in this backtest (0 is valid)
- `symbol`: Display symbol name(s)
- `timeframe`: Canonical app form (e.g., `5m`, not `5min`) — frontend normalizes at chart component boundary
- `display_from` / `display_to`: The visible range of candles in this payload
- `full_from` / `full_to`: The full data range available in `candles.parquet`
- `is_partial`: Whether this payload contains a subset of available data
- `has_more_left` / `has_more_right`: Whether older/newer candles can be loaded
- `candles`: Columnar JSON arrays of OHLCV data, times in `Asia/Kolkata`
- `annotations`: Precomputed entry/exit markers with KLineChart-compatible styling

### 3. `GET /api/backtest/{id}/chart` Endpoint

**Router**: `backend/app/routers/backtest.py`

**Query Parameters**:
- `full` (optional, boolean): If `1`, return full range instead of smart range
  - Rebuilds `chart.json` if only the smart-range version exists
  - Same response shape as default, with `is_partial: false`, `has_more_left: false`, `has_more_right: false`

**Response codes**:
- `200`: Chart payload (success)
- `404`: `backtests/{id}/` directory, `candles.parquet`, or `trades.json` not found

**Staleness check**: Serve existing `chart.json` if both `trades.json` and `candles.parquet` have `mtime <= chart.json`'s `mtime`. Otherwise rebuild.

### 4. Build Integration in `strategy_v2.py`

**On cache miss** (lines ~346-420):
- After saving `summary.json`, `trades.json`, `equity_curve.json`, `per_symbol.json`, `candles.parquet`
- Call `_build_chart_payload(backtest_dir)` to create `chart.json`

**On cache hit** (lines ~285-330):
- After `rebuild_artifacts_from_cache()` restores summary/trades
- Check `chart.json` exists in `backtest_dir`:
  - If missing: call `_build_chart_payload()` to rebuild from restored artifacts
  - If stale (trades/candles newer than chart): rebuild

### 5. No-trades Behavior

- When `trades.json` is empty or contains no trades:
  - Build `chart.json` with fallback range (last 90 days from latest candle)
  - `annotations: []` — empty array, not null
  - `trade_count: 0`
  - Frontend renders candle chart without trade markers (no error)

### 6. Atomic Write Pattern

- Write to `chart.json.tmp`
- `os.rename(tmp_path, chart_path)` — atomic on POSIX
- Prevents partial reads if concurrent requests rebuild near the same time

## Front-end Changes

### 1. `frontend/app/backtest/[id]/page.tsx` — `BacktestChart` Component

**Before**: Paginated `while(true)` loop fetching 500 candles at a time from `/api/backtest/{id}/candles`

**After**: Single fetch to `/api/backtest/{id}/chart`

```typescript
const response = await fetch(`${API}/api/backtest/${backtestId}/chart`)
const chartData = await response.json()
setCandles(normalizeCandles(chartData.candles))
setAnnotations(chartData.annotations)
setFullRangeAvailable(!chartData.is_partial)  // or via ?full=1
```

**Full chart load**: User clicks "Load Full Chart" → fetch `/api/backtest/{id}/chart?full=1`

### 2. `sessionStorage` Caching

**Key**: `chart_{backtest_id}`

**On mount**:
1. Check `sessionStorage.getItem('chart_{id}')`
2. If present and valid JSON with required fields → hydrate immediately → render chart with no network call
3. On fetch success → `sessionStorage.setItem('chart_{id}', JSON.stringify(data))`

**Only fetch from server when**:
- `sessionStorage` miss (first visit of tab session)
- `?full=1` button clicked (Load Full Chart)
- Cached payload is malformed (missing `candles` or `annotations` key)

**No background refresh** for cache hits — `backtest_id` is deterministic and the artifact is immutable for that key. Background refresh adds network churn and can cause visible flicker/repaint.

### 3. UI Changes

- Show "Load Full Chart" button when `is_partial: true` and `has_more_left || has_more_right`
- Button text: "Load Full Range" or similar
- While full chart loads, show loading indicator on chart area

## Error Handling

| Scenario | Backend Response | Frontend Behavior |
|----------|-----------------|-------------------|
| No `backtests/{id}/` | 404 | Show "Backtest not found" |
| No `candles.parquet` | 404 `{error: "no_chart_data"}` | Show "Chart data unavailable" |
| No `trades.json` | 404 (treat as missing backtest) | Show "Backtest data unavailable" |
| Empty trades | 200 with `annotations: []` | Show chart without trade markers |
| `?full=1` too large | 200 (uncapped) | Show full chart, may take longer |
| Malformed `chart.json` | Rebuild and serve | Transparent, no user-facing error |

## Performance Targets

- **Initial chart load**: < 500ms for smart-range payload (typical ~1000-3000 candles)
- **SessionStorage reopen**: < 50ms (instant hydrate, no network)
- **Full chart load**: Same as current paginated approach, but single request instead of loop

## Migration Path

- Legacy `/api/backtest/{id}/candles` endpoint remains untouched for backward compatibility
- New `/api/backtest/{id}/chart` is additive
- `?full=1` mode is a new optional query parameter
- Existing `BacktestChart` component is replaced, not modified

## Files to Modify

**Backend**:
- `backend/app/routers/strategy_v2.py` — add `_build_chart_payload()`, integrate into cache hit/miss paths
- `backend/app/routers/backtest.py` — add `GET /{backtest_id}/chart` endpoint

**Frontend**:
- `frontend/app/backtest/[id]/page.tsx` — replace `BacktestChart` component paginated fetch with single chart endpoint + sessionStorage

## Future Considerations (Out of Scope)

- Server-side compression (gzip/brotli for chart payload)
- Redis caching of chart payloads for hot backtests
- Incremental candle loading via `?after=<time>&limit=N`
- WebSocket real-time chart updates
