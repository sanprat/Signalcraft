"""
Debug script: run a SMA(20) crosses_above SMA(50) strategy on RELIANCE 5min data
and print the first few trades for comparison with TradingView.
"""

import sys
import os

# Ensure the backend project root is importable
sys.path.insert(0, os.path.dirname(__file__))

import pandas as pd

# Check data dirs for RELIANCE 5min parquet
data_dirs = [
    os.path.join(os.path.dirname(__file__), "data", "candles"),
    os.path.join(os.path.dirname(__file__), "data", "candles", "NIFTY500"),
    "/app/data/candles/NIFTY500",
    os.path.join(os.path.dirname(__file__), "..", "..", "data", "candles", "NIFTY500"),
]

parquet_path = None
for ddir in data_dirs:
    candidate = os.path.join(ddir, "RELIANCE", "5min.parquet")
    if os.path.exists(candidate):
        parquet_path = candidate
        break

# Also check if there is a broader search that finds any RELIANCE 5min file
if parquet_path is None:
    import subprocess
    result = subprocess.run(
        ["find", os.path.dirname(os.path.dirname(__file__)), "-path", "*/RELIANCE/5min.parquet", "-type", "f"],
        capture_output=True, text=True
    )
    if result.stdout.strip():
        parquet_path = result.stdout.strip().split("\n")[0]

if parquet_path is None:
    print("No data found")
    sys.exit(0)

print(f"Using data: {parquet_path}")

# Load parquet
df = pd.read_parquet(parquet_path)

# Normalize columns
if "__index_level_0__" in df.columns:
    df = df.rename(columns={"__index_level_0__": "time"})
if "time" not in df.columns:
    df = df.reset_index().rename(columns={df.index.name: "time"})

ensure_cols = ["time", "open", "high", "low", "close", "volume"]
for c in ensure_cols:
    if c not in df.columns:
        df[c] = 0

df["time"] = pd.to_datetime(df["time"], utc=True)
df["time"] = df["time"].dt.tz_convert("Asia/Kolkata")
df = df.sort_values("time").reset_index(drop=True)

# Filter market hours for intraday
df = df[
    (df["time"].dt.hour > 9)
    | ((df["time"].dt.hour == 9) & (df["time"].dt.minute >= 15))
]
df = df[
    (df["time"].dt.hour < 15)
    | ((df["time"].dt.hour == 15) & (df["time"].dt.minute <= 30))
]
df = df.reset_index(drop=True)

print(f"Loaded {len(df)} intraday candles")
if len(df) < 51:
    print("Not enough data for SMA(50) warm-up")
    sys.exit(0)

# Compute indicators
df["sma_20"] = df["close"].rolling(20).mean()
df["sma_50"] = df["close"].rolling(50).mean()

# Forward-fill NaNs (matching what strategy_engine_v2 does)
df = df.ffill()

# Strategy parameters
stop_loss_pct = 0.02   # 2%
target_pct = 0.05      # 5%
quantity = 10
max_trades_per_day = 3
max_loss_per_day = 500

# Run simulation
trades = []
in_trade = False
entry_price = 0.0
entry_time = None
trade_no = 0
daily_trades = {}
daily_loss = {}

for idx, row in df.iterrows():
    bar_date = row["time"].date()

    if bar_date not in daily_trades:
        daily_trades[bar_date] = 0
        daily_loss[bar_date] = 0.0

    # Exit check
    if in_trade:
        pnl_pct_val = (row["close"] - entry_price) / entry_price
        exit_reason = None

        if pnl_pct_val <= -stop_loss_pct:
            exit_reason = "SL"
            exit_price = entry_price * (1 - stop_loss_pct)
        elif pnl_pct_val >= target_pct:
            exit_reason = "TARGET"
            exit_price = entry_price * (1 + target_pct)

        if exit_reason:
            pnl = (exit_price - entry_price) * quantity
            trade_no += 1
            trades.append({
                "trade_no": trade_no,
                "entry_time": entry_time,
                "exit_time": row["time"],
                "entry_price": entry_price,
                "exit_price": exit_price,
                "pnl": pnl,
                "exit_reason": exit_reason,
            })
            in_trade = False
            daily_loss[bar_date] += min(pnl, 0)

    # Entry check
    if not in_trade:
        if daily_trades[bar_date] >= max_trades_per_day:
            continue
        if abs(daily_loss[bar_date]) >= max_loss_per_day:
            continue

        # SMA20 crosses_above SMA50: current bar SMA20 > SMA50 and previous bar SMA20 <= SMA50
        if idx > 0:
            prev = df.iloc[idx - 1]
            sma20_cur = row["sma_20"]
            sma50_cur = row["sma_50"]
            sma20_prev = prev["sma_20"]
            sma50_prev = prev["sma_50"]

            if sma20_cur > sma50_cur and sma20_prev <= sma50_prev:
                in_trade = True
                entry_price = row["close"]
                entry_time = row["time"]
                daily_trades[bar_date] += 1

# Close any remaining open trade at last bar
if in_trade and not df.empty:
    last_row = df.iloc[-1]
    pnl = (last_row["close"] - entry_price) * quantity
    trade_no += 1
    trades.append({
        "trade_no": trade_no,
        "entry_time": entry_time,
        "exit_time": last_row["time"],
        "entry_price": entry_price,
        "exit_price": last_row["close"],
        "pnl": pnl,
        "exit_reason": "END_OF_TEST",
    })

print(f"Total trades: {len(trades)}")
print()
print("First 5 trades:")
print(f"{'#':>3s}  {'entry_time':<24s}  {'exit_time':<24s}  {'exit_reason':<12s}  {'pnl':>10s}")
print("-" * 82)
for t in trades[:5]:
    print(f"{t['trade_no']:3d}  {str(t['entry_time']):<24s}  {str(t['exit_time']):<24s}  {t['exit_reason']:<12s}  {t['pnl']:10.2f}")
