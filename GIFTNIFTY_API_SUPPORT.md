# GIFT NIFTY Historical OHLC Data via Dhan API

## ✅ **YES - GIFT NIFTY OHLC Historical Data IS Available!**

### Key Findings

| Aspect | Status | Details |
|--------|--------|---------|
| **Intraday OHLC** | ✅ **AVAILABLE** | 1min, 5min, 15min intervals (up to 88 days per request) |
| **Daily OHLC** | ❌ **NOT AVAILABLE** | Historical daily endpoint doesn't support GIFT NIFTY |
| **Security ID** | ✅ **5024** | Found in Dhan instrument master |
| **Exchange Segment** | ✅ **IDX_I** | Same as NIFTY, BANKNIFTY, FINNIFTY |
| **Instrument Type** | ✅ **INDEX** | Standard index instrument |
| **Data Availability** | ✅ **From Oct 2023** | GIFT NIFTY launched in July 2023 |

---

## API Configuration

### Dhan Client Setup

```python
from dhan_client import DhanClient

client = DhanClient(
    client_id="YOUR_CLIENT_ID",
    access_token="YOUR_ACCESS_TOKEN"
)

# GIFT NIFTY is now supported!
candles = client.get_intraday_candles(
    security_id="5024",              # GIFT NIFTY security ID
    exchange_segment="IDX_I",        # Index segment
    instrument="INDEX",
    interval="15min",                # 1min, 5min, or 15min
    from_datetime="2024-01-15 09:15:00",
    to_datetime="2024-01-15 15:30:00",
    oi=False
)
```

### Security ID Reference

```python
SECURITY_IDS = {
    "NIFTY":      13,
    "BANKNIFTY":  25,
    "FINNIFTY":   27,
    "GIFTNIFTY": 5024,  # ✅ NEW: GIFT NIFTY
}
```

---

## API Endpoints Tested

### ✅ Intraday Endpoint (WORKS)

**Endpoint:** `POST /v2/charts/intraday`

**Request:**
```json
{
  "securityId": "5024",
  "exchangeSegment": "IDX_I",
  "instrument": "INDEX",
  "interval": "15",
  "oi": false,
  "fromDate": "2024-01-15 09:15:00",
  "toDate": "2024-01-15 15:30:00"
}
```

**Response:**
```json
{
  "timestamp": [1705291200.0, 1705292100.0, ...],
  "open": [22107.0, 22080.0, ...],
  "high": [22109.5, 22087.5, ...],
  "low": [...],
  "close": [...],
  "volume": [...]
}
```

**Result:** ✅ **24 candles** returned for Jan 15, 2024 (15-minute interval)

---

### ❌ Historical Daily Endpoint (DOESN'T WORK)

**Endpoint:** `POST /v2/charts/historical`

**Request:**
```json
{
  "securityId": "5024",
  "exchangeSegment": "IDX_I",
  "instrument": "INDEX",
  "expiryCode": 0,
  "fromDate": "2024-01-01",
  "toDate": "2024-01-31"
}
```

**Response:**
```json
{
  "errorType": "Input_Exception",
  "errorCode": "DH-905",
  "errorMessage": "Missing required fields, bad values for parameters etc."
}
```

**Result:** ❌ **Not supported** - Daily historical endpoint doesn't work for GIFT NIFTY

---

## Usage Examples

### Download GIFT NIFTY Intraday Data

```bash
# Using the updated dhan_client.py
python -c "
from dhan_client import DhanClient
client = DhanClient('YOUR_CLIENT_ID', 'YOUR_ACCESS_TOKEN')

# Get 15-min GIFT NIFTY data
candles = client.get_intraday_candles(
    security_id='5024',
    exchange_segment='IDX_I',
    instrument='INDEX',
    interval='15min',
    from_datetime='2024-01-01 09:15:00',
    to_datetime='2024-01-31 15:30:00'
)

print(f'Got {len(candles)} candles')
"
```

### Download Spot Data Script

The `download_spot_data.py` script can now be updated to include GIFTNIFTY:

```python
INDICES = {
    "NIFTY":     {"id": "13", "start": date(2020, 1, 1)},
    "BANKNIFTY": {"id": "25", "start": date(2022, 1, 1)},
    "FINNIFTY":  {"id": "27", "start": date(2022, 1, 1)},
    "GIFTNIFTY": {"id": "5024", "start": date(2023, 10, 1)},  # NEW
}
```

---

## Technical Details

### GIFT NIFTY Instrument Master Data

From Dhan's instrument master CSV:

| Field | Value |
|-------|-------|
| **EXCH_ID** | NSE |
| **SEGMENT** | I (Index) |
| **SECURITY_ID** | 5024 |
| **INSTRUMENT** | INDEX |
| **UNDERLYING_SECURITY_ID** | 5024 |
| **UNDERLYING_SYMBOL** | GIFTNIFTY |
| **SYMBOL_NAME** | GIFTNIFTY |
| **DISPLAY_NAME** | Gift Nifty |

### Trading Hours

GIFT NIFTY trades for **~21 hours/day** on NSE International Exchange (GIFT City):
- **Session 1:** 6:30 AM - 3:40 PM IST
- **Session 2:** 4:35 PM - 2:45 AM IST (next day)

For regular market hours filtering, use **9:15 AM - 3:30 PM IST**.

---

## Limitations

1. **Daily OHLC not available** - Only intraday data (1min, 5min, 15min) is supported
2. **88-day limit per request** - Must chunk requests for longer date ranges
3. **Rate limiting** - 1 request per second recommended
4. **Data starts Nov 2023** - GIFT NIFTY launched July 2023, but API data available from November 20, 2023 onwards

## Downloaded Data Summary (as of March 2, 2026)

| Interval | Candles | Date Range | File Size |
|----------|---------|------------|-----------|
| **1min** | 186,001 | 2023-11-20 → 2026-02-27 | 2.70 MB |
| **5min** | 37,730 | 2023-11-20 → 2026-02-27 | 0.69 MB |
| **15min** | 12,935 | 2023-11-20 → 2026-02-27 | 0.29 MB |

**Location:** `data/underlying/GIFTNIFTY/`

---

## Recommendations

### For Daily OHLC Data

Since the historical daily endpoint doesn't work for GIFT NIFTY:

1. **Aggregate from intraday** - Use 15-min candles to create daily OHLCV
2. **Contact Dhan support** - Request daily historical data support at `help@dhan.co`
3. **Alternative sources** - Consider other data providers for daily GIFT NIFTY data

### For Intraday Analysis

✅ **Fully supported!** Use the updated `dhan_client.py` with:
- Security ID: **5024**
- Exchange Segment: **IDX_I**
- Instrument: **INDEX**

---

## Verification Test

Run the test script to verify:

```bash
cd /Users/sanim/Downloads/sunny/Python/AIML/Pybankers/Pytrader
bash data-scripts/test_gift_nifty.sh
```

Expected output:
```
✓ SUCCESS for ID 5024!
  Got 24 candles
```

---

## References

- **Dhan API Docs:** https://dhanhq.co/docs/v2/
- **Instrument Master:** https://images.dhan.co/api-data/api-scrip-master-detailed.csv
- **GIFT NIFTY Info:** https://dhan.co/indices/gift-nifty-share-price/
- **Announcement:** https://www.linkedin.com/posts/dhanhq_madefortrade-activity-7209784278451179520-gE9L

---

**Last Updated:** March 2, 2026  
**Verified By:** API testing with live Dhan credentials
