# Weekly Index Options Data Readiness & Ingestion Design

**Date:** 2026-04-14  
**Status:** Draft  
**Phase:** 1 - Core Implementation

---

## 1. Overview

Build the data pipeline for weekly index options on NIFTY, BANKNIFTY, and FINNIFTY using Dhan as the canonical source. Phase 1 focuses on core infrastructure: audit, historical ingestion, and current-week live data.

## 2. Data Architecture

### 2.1 Storage Layout

```
data/
├── underlying/{INDEX}/{interval}.parquet
│   └── time, open, high, low, close, volume
├── candles/{INDEX}/{CE|PE}/{interval}/dhan_ec{0|1|2|...}_{strike}.parquet
│   └── time, open, high, low, close, volume, oi, iv, spot
└── optionchain/{INDEX}/{expiry}/YYYYMMDD_HHMMSS.parquet  (optional)
    └── snapshot_time, expiry, strike, option_type, last_price, ...
```

### 2.2 Schema Extensions

Current parquet schema (6 columns):
- time, open, high, low, close, volume

Extended schema (9 columns):
- time, open, high, low, close, volume, oi, iv, spot

**Decision:** Keep strike in filename (`dhan_ec{expiry_code}_{strike}.parquet`), not as repeated column.

---

## 3. Components

### 3.1 VPS Readiness Audit Script

**Location:** `data-scripts/options_audit.py`

**Responsibilities:**
1. Resolve data root (`data/` or environment-configured path)
2. Verify presence of:
   - Underlying data for NIFTY, BANKNIFTY, FINNIFTY
   - Options CE and PE directories for 1min, 5min, 15min
3. Summarize:
   - Earliest/latest timestamps per file group
   - Number of strike files per index/type/interval
   - Presence of ec0, ec1, ec2, ... expiry families
   - Sample overlap between underlying and options timestamps
4. Produce verdict: `ready`, `partially_ready`, `not_ready`

**Readiness Rules (v1):**
- ✅ Underlying exists for the chosen timeframe
- ✅ Both CE and PE exist
- ✅ Expired weekly data exists across multiple expiries (≥2)
- ⚠️ Current-week ec0 exists or can be filled daily — **requires updater implementation**
- ✅ Timestamps overlap during market hours (9:15-15:30 IST)

**Verdict Logic:**
- `not_ready`: Missing underlying OR missing CE/PE directories
- `partially_ready`: Has underlying + CE/PE but no expired history, OR ec0 only without live updater
- `ready`: Underlying + CE/PE + ≥2 expired expiries + ec0 updater wired + timestamp overlap

### 3.2 Dhan Historical Options Ingestion

**Changes to `dhan_client.py`:**

1. Update `REQUIRED_DATA`:
```python
REQUIRED_DATA = ["open", "high", "low", "close", "volume", "oi", "iv", "spot", "strike"]
```

2. Normalize response from `data.ce` or `data.pe`:
   - Handle missing arrays gracefully (default to 0 or empty)
   - Parse oi, iv, spot fields when returned

3. Preserve absolute strike from Dhan response, group by strike for filenames

4. Keep `expiryFlag="WEEK"` for v1

**Backfill Policy:**
- Phase 1: Backfill 26 expiries first
- Phase 2: Expand to 52 expiries once stable
- Download range: ATM-10 to ATM+10 (21 strikes per index)

### 3.3 Current-Week Live Data Updater

**Changes:**
- Resolve current active expiry via `POST /v2/optionchain/expirylist` (new endpoint)
- Continue downloading into `dhan_ec0_{strike}.parquet`
- Run after market close (16:00 IST) and optionally during market hours
- **Do not merge** ec0 into expired ec1+ files (keep separate for continuity)

### 3.4 Optional Expirylist Integration (NEW)

**New method in `dhan_client.py`:**
- `get_expiry_list(index: str)` → returns list of active expiries
- Use for current-week expiry resolution
- Use for validation of live chain jobs

**Dhan API Payload (CORRECTED):**
```python
def get_expiry_list(self, index: str) -> list:
    payload = {
        "UnderlyingScrip": SECURITY_IDS[index],
        "UnderlyingSeg": "IDX_I"
    }
    # Returns: {"data": {"expiryDates": ["2025-04-24", "2025-05-01", ...]}}
```

**Critical: Canonical Schema Across All Writers**

The oi, iv, spot schema extension must be consistent across ALL write paths:
- `data-scripts/parquet_writer.py`
- `data-scripts/daily_updater.py`
- `data-scripts/dhan_bulk_loader.py`

**Single canonical row schema:**
```python
OPTIONS_SCHEMA = pa.schema([
    ("time",   pa.timestamp("s", tz="Asia/Kolkata")),
    ("open",   pa.float32()),
    ("high",   pa.float32()),
    ("low",    pa.float32()),
    ("close",  pa.float32()),
    ("volume", pa.int64()),
    ("oi",     pa.float64()),      # Open Interest
    ("iv",     pa.float32()),      # Implied Volatility (decimal, e.g., 0.15 = 15%)
    ("spot",   pa.float32()),      # Underlying spot price
])
```

**Backtest Reader Compatibility:**
- Existing loaders must tolerate extra columns (oi, iv, spot)
- Use pyarrow schema evolution: existing readers continue working with 6-column files
- New readers can access oi/iv/spot when available

### 3.5 Optional Option Chain Snapshots (DEFERRED)

Not included in Phase 1. Can be added later for OI/IV/Greeks-based strategies.

---

## 4. API Endpoints

### 4.1 POST /v2/charts/rollingoption

**Current payload:**
```python
{
    "exchangeSegment": "NSE_FNO",
    "instrument": "OPTIDX",
    "securityId": 13,  # NIFTY
    "expiryFlag": "WEEK",
    "strike": "ATM",
    "drvOptionType": "CALL",
    "interval": "1",
    "requiredData": ["open", "high", "low", "close", "volume", "strike"],
    "fromDate": "2025-01-01",
    "toDate": "2025-01-31"
}
```

**Updated payload (Phase 1):**
```python
{
    "exchangeSegment": "NSE_FNO",
    "instrument": "OPTIDX",
    "securityId": 13,
    "expiryFlag": "WEEK",
    "strike": "ATM",
    "drvOptionType": "CALL",
    "interval": "1",
    "requiredData": ["open", "high", "low", "close", "volume", "oi", "iv", "spot", "strike"],
    "fromDate": "2025-01-01",
    "toDate": "2025-01-31",
    "expiryCode": 1  # 1=nearest expired, 2=second nearest, etc.
}
```

### 4.2 POST /v2/optionchain/expirylist (NEW)

```python
def get_expiry_list(self, index: str) -> list:
    payload = {
        "securityId": SECURITY_IDS[index],
        "exchangeSegment": "NSE_FNO",
        "instrument": "OPTIDX"
    }
    # Returns: {"data": {"expiryDates": ["2025-04-24", "2025-05-01", ...]}}
```

---

## 5. Implementation Order

**Phase 1 Order:**

1. **dhan_client.py** — normalization for oi, iv, spot + get_expiry_list()
2. **Shared options parquet schema** — canonical schema used by all writers
3. **options_audit.py** — VPS readiness audit script
4. **Tests** — audit, ingestion, backtest compatibility

**Do not implement:**
- Option chain snapshots (deferred to v2)
- New strategy engine features (price-only for v1)

---

## 6. Assumptions

- Dhan API provides oi, iv, spot for expired options
- Strategy v1 remains price-only (OHLCV-based)
- No DB storage - continue using parquet
- Memory tools unavailable in current session (use .agent-memory-rules.md convention)
