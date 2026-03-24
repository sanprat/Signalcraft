"""
backtest_engine.py — DuckDB-powered backtesting engine.

Queries Parquet candle files, simulates entry/exit logic per strategy,
returns trade records and summary statistics.
"""

import duckdb
import pandas as pd
from datetime import datetime, date, timedelta
from pathlib import Path
from typing import Optional, Dict, List
import logging
import os
import re

logger = logging.getLogger(__name__)

# Path to Parquet data — works inside Docker (/app/data/candles) and locally
DATA_DIR = Path(
    os.environ.get(
        "CANDLE_DATA_DIR", Path(__file__).parent.parent.parent / "data" / "candles"
    )
)

# Path to underlying spot data for ATM strike calculation
UNDERLYING_DIR = (
    Path(
        os.environ.get(
            "CANDLE_DATA_DIR", Path(__file__).parent.parent.parent / "data" / "candles"
        )
    ).parent
    / "underlying"
)

# Strike offset mapping
STRIKE_OFFSET_MAP = {
    "ATM": 0,
    "OTM1": 1,
    "OTM2": 2,
    "OTM3": 3,
    "ITM1": -1,
    "ITM2": -2,
    "ITM3": -3,
}

# Strike price step for each index
STRIKE_STEP = {
    "NIFTY": 50,
    "BANKNIFTY": 100,
    "FINNIFTY": 50,
}


def _build_parquet_glob(index: str, option_type: str, timeframe: str) -> str:
    """Build glob path for the relevant Parquet files."""
    tf = timeframe  # "5min" / "15min"
    if option_type == "BOTH":
        # We'll query CE and PE separately and merge
        return None
    base = DATA_DIR / index / option_type / tf
    return str(base / "*.parquet")


def load_underlying_spot(
    index: str,
    timeframe: str,
    from_date: date,
    to_date: date,
) -> pd.DataFrame:
    """
    Load underlying spot index data for ATM strike calculation.
    File path: UNDERLYING_DIR / {index} / {timeframe}.parquet
    """
    parquet_path = UNDERLYING_DIR / index / f"{timeframe}.parquet"
    logger.info(f"[OPTIONS] Looking for underlying spot data at: {parquet_path}")

    if not parquet_path.exists():
        logger.warning(
            f"[OPTIONS] MISSING underlying data: {parquet_path} not found. "
            f"Options backtesting requires: data/underlying/{index}/{timeframe}.parquet"
        )
        return pd.DataFrame(columns=["time", "close"])

    try:
        df = duckdb.query(f"""
            SELECT time, close
            FROM read_parquet('{parquet_path}')
            WHERE time >= '{from_date}'
              AND time <= '{to_date} 23:59:59'
            ORDER BY time
        """).df()
        logger.info(
            f"[OPTIONS] Loaded {len(df)} rows of underlying spot data for {index}"
        )
    except Exception as e:
        logger.error(f"DuckDB error for underlying {index}/{timeframe}: {e}")
        return pd.DataFrame(columns=["time", "close"])

    df["time"] = pd.to_datetime(df["time"], utc=True).dt.tz_convert("Asia/Kolkata")
    return df.reset_index(drop=True)


def get_atm_strike(spot_price: float, index: str) -> int:
    """
    Calculate ATM strike based on spot price and index strike step.
    e.g. spot=22345 → ATM=22350 for NIFTY (step=50)
    """
    step = STRIKE_STEP.get(index, 50)
    return round(spot_price / step) * step


def get_target_strike(atm_strike: int, strike_type: str, index: str) -> int:
    """
    Calculate target strike based on ATM strike and strike type offset.
    e.g. ATM=22350, OTM1 → 22400 (for NIFTY)
    """
    step = STRIKE_STEP.get(index, 50)
    offset = STRIKE_OFFSET_MAP.get(strike_type, 0)
    return atm_strike + (offset * step)


def get_available_strikes(
    index: str,
    option_type: str,
    timeframe: str,
) -> Dict[int, Path]:
    """
    Scan directory and return mapping of strike → parquet file path.
    File pattern: dhan_ec[01]_{strike}.parquet
    """
    parquet_dir = DATA_DIR / index / option_type / timeframe
    logger.info(f"[OPTIONS] Scanning for strike files in: {parquet_dir}")

    if not parquet_dir.exists():
        logger.warning(
            f"[OPTIONS] MISSING options directory: {parquet_dir} not found. "
            f"Options backtesting requires: data/candles/{index}/{option_type}/{timeframe}/dhan_ec*_*.parquet"
        )
        return {}

    strikes = {}
    for f in parquet_dir.glob("dhan_ec*_[0-9]*.parquet"):
        # Extract strike from filename: dhan_ec0_22500.parquet → 22500
        match = re.search(r"dhan_ec[01]_(\d+)\.parquet$", f.name)
        if match:
            strike = int(match.group(1))
            strikes[strike] = f

    logger.info(f"[OPTIONS] Found {len(strikes)} strike files in {parquet_dir}")
    return strikes


def find_nearest_strike(
    available_strikes: List[int],
    target_strike: int,
) -> int:
    """
    Find the nearest available strike to the target strike.
    Returns the closest strike from available options.
    """
    if not available_strikes:
        return target_strike

    return min(available_strikes, key=lambda s: abs(s - target_strike))


def load_equity_candles(
    symbol: str,
    timeframe: str,
    from_date: date,
    to_date: date,
) -> pd.DataFrame:
    """
    Load OHLCV candles for an equity stock from Parquet.
    File path: DATA_DIR / NIFTY500 / {symbol} / {timeframe}.parquet
    """
    parquet_path = DATA_DIR / "NIFTY500" / symbol / f"{timeframe}.parquet"
    if not parquet_path.exists():
        logger.warning(f"No Parquet file: {parquet_path}")
        return pd.DataFrame(columns=["time", "open", "high", "low", "close", "volume"])

    try:
        df = duckdb.query(f"""
            SELECT time, open, high, low, close, volume
            FROM read_parquet('{parquet_path}')
            WHERE time >= '{from_date}'
              AND time <= '{to_date} 23:59:59'
            ORDER BY time
        """).df()
    except Exception as e:
        logger.error(f"DuckDB error for equity {symbol}/{timeframe}: {e}")
        return pd.DataFrame(columns=["time", "open", "high", "low", "close", "volume"])

    df["time"] = pd.to_datetime(df["time"], utc=True)
    # Convert from UTC to IST for market hours filtering
    df["time"] = df["time"].dt.tz_convert("Asia/Kolkata")
    # Apply market-hours filter only for intraday timeframes (9:15 IST to 15:30 IST)
    if timeframe != "1D":
        df = df[
            (df["time"].dt.hour > 9)
            | ((df["time"].dt.hour == 9) & (df["time"].dt.minute >= 15))
        ]
        df = df[
            (df["time"].dt.hour < 15)
            | ((df["time"].dt.hour == 15) & (df["time"].dt.minute <= 30))
        ]
    return df.reset_index(drop=True)


def load_candles(
    index: str,
    option_type: str,
    timeframe: str,
    from_date: date,
    to_date: date,
    strike_type: str = "ATM",
) -> pd.DataFrame:
    """
    Load OHLCV candles from Parquet for FnO options.

    Dynamically determines the correct strike file based on:
    1. Underlying spot index price (to calculate ATM strike)
    2. Strike type offset (ATM, OTM1, ITM1, etc.)
    3. Available strike files in the directory

    Returns DataFrame sorted by time with market hours only (9:15–15:30).
    """
    opt_types = ["CE", "PE"] if option_type == "BOTH" else [option_type]
    dfs = []

    logger.info(
        f"[OPTIONS] Starting load_candles for {index}/{option_type}/{timeframe} ({from_date} to {to_date})"
    )

    # Step 1: Load underlying spot data to calculate ATM strikes over time
    logger.info(f"[OPTIONS] Step 1: Loading underlying spot data for {index}")
    underlying_df = load_underlying_spot(index, timeframe, from_date, to_date)

    if underlying_df.empty:
        logger.warning(
            f"[OPTIONS] FAILED: No underlying data for {index}. "
            f"Options backtesting requires: data/underlying/{index}/{timeframe}.parquet"
        )
        return pd.DataFrame(columns=["time", "open", "high", "low", "close", "volume"])

    # Step 2: Get available strike files for each option type (CE and/or PE)
    # Build a dict: option_type -> {strike -> parquet_path}
    all_available_strikes: Dict[str, Dict[int, Path]] = {}

    for opt in opt_types:
        available_map = get_available_strikes(index, opt, timeframe)
        if not available_map:
            logger.warning(
                f"[OPTIONS] FAILED: No options strike files found for {index}/{opt}/{timeframe}. "
                f"Options backtesting requires: data/candles/{index}/{opt}/{timeframe}/dhan_ec*_*.parquet"
            )
            continue
        all_available_strikes[opt] = available_map
        logger.info(
            f"[OPTIONS] Found {len(available_map)} strikes for {index}/{opt}/{timeframe}"
        )

    if not all_available_strikes:
        logger.warning(
            f"[OPTIONS] FAILED: No options data available for {index}/{option_type}/{timeframe}"
        )
        return pd.DataFrame(columns=["time", "open", "high", "low", "close", "volume"])

    # Log available strikes for each option type
    for opt, strikes_map in all_available_strikes.items():
        if strikes_map:
            strikes = list(strikes_map.keys())
            logger.info(
                f"Available strikes for {index}/{opt}/{timeframe}: {min(strikes)}-{max(strikes)}"
            )

    # Step 3: For each candle in underlying data, determine target strike and load option data
    # Group by (option_type, strike) to minimize file reads
    # Structure: {option_type: {strike: [times]}}
    strike_to_candles: Dict[str, Dict[int, list]] = {
        opt: {} for opt in all_available_strikes
    }

    for _, spot_row in underlying_df.iterrows():
        spot_time = spot_row["time"]
        spot_close = float(spot_row["close"])

        # Calculate ATM strike based on spot price
        atm_strike = get_atm_strike(spot_close, index)

        # Calculate target strike based on strike type
        target_strike = get_target_strike(atm_strike, strike_type, index)

        # For each option type (CE and/or PE), find nearest available strike
        for opt in opt_types:
            if opt not in all_available_strikes or not all_available_strikes[opt]:
                continue

            available_strikes = list(all_available_strikes[opt].keys())
            nearest_strike = find_nearest_strike(available_strikes, target_strike)

            if nearest_strike not in strike_to_candles[opt]:
                strike_to_candles[opt][nearest_strike] = []

            strike_to_candles[opt][nearest_strike].append(spot_time)

    # Step 4: Load option data for each (option_type, strike) combination
    for opt, strike_map in strike_to_candles.items():
        for strike, times in strike_map.items():
            min_time = min(times)
            max_time = max(times)

            # Get the parquet file for this strike
            parquet_file = all_available_strikes[opt].get(strike)
            if not parquet_file:
                continue

            try:
                df_strike = duckdb.query(f"""
                    SELECT time, open, high, low, close, volume
                    FROM read_parquet('{parquet_file}')
                    WHERE time >= '{min_time}'
                      AND time <= '{max_time} 23:59:59'
                    ORDER BY time
                """).df()

                if not df_strike.empty:
                    df_strike["time"] = pd.to_datetime(df_strike["time"], utc=True)
                    df_strike["time"] = df_strike["time"].dt.tz_convert("Asia/Kolkata")
                    df_strike["option_type"] = opt
                    df_strike["strike"] = strike
                    dfs.append(df_strike)
                    logger.debug(
                        f"Loaded {len(df_strike)} candles for {opt} strike {strike}"
                    )

            except Exception as e:
                logger.error(f"DuckDB error for {index}/{opt}/{strike}: {e}")

    if not dfs:
        logger.warning(f"No option data loaded for {index}/{option_type}/{timeframe}")
        return pd.DataFrame(columns=["time", "open", "high", "low", "close", "volume"])

    result = pd.concat(dfs).sort_values("time").reset_index(drop=True)

    # Apply market-hours filter only for intraday timeframes (9:15 IST to 15:30 IST)
    if timeframe != "1D":
        result = result[
            (result["time"].dt.hour > 9)
            | ((result["time"].dt.hour == 9) & (result["time"].dt.minute >= 15))
        ]
        result = result[
            (result["time"].dt.hour < 15)
            | ((result["time"].dt.hour == 15) & (result["time"].dt.minute <= 30))
        ]

    return result.reset_index(drop=True)


def compute_indicators(df: pd.DataFrame, entry_conditions: list) -> pd.DataFrame:
    """Compute all indicator values needed for entry/exit signals."""
    for cond in entry_conditions:
        ind = cond["indicator"]
        params = cond.get("params", {})

        if ind == "EMA_CROSS":
            fast = params.get("fast", 9)
            slow = params.get("slow", 21)
            df[f"ema_{fast}"] = df["close"].ewm(span=fast, adjust=False).mean()
            df[f"ema_{slow}"] = df["close"].ewm(span=slow, adjust=False).mean()
            df["signal_ema_cross"] = (df[f"ema_{fast}"] > df[f"ema_{slow}"]) & (
                df[f"ema_{fast}"].shift(1) <= df[f"ema_{slow}"].shift(1)
            )

        elif ind == "RSI_LEVEL":
            period = params.get("period", 14)
            level = params.get("level", 50)
            delta = df["close"].diff()
            gain = delta.clip(lower=0).rolling(period).mean()
            loss = (-delta.clip(upper=0)).rolling(period).mean()
            rs = gain / loss.replace(0, 1e-10)
            df["rsi"] = 100 - (100 / (1 + rs))
            df["signal_rsi"] = (df["rsi"] > level) & (df["rsi"].shift(1) <= level)

        elif ind == "SUPERTREND":
            period = params.get("period", 7)
            mult = params.get("multiplier", 3.0)
            hl2 = (df["high"] + df["low"]) / 2
            tr = pd.concat(
                [
                    df["high"] - df["low"],
                    (df["high"] - df["close"].shift()).abs(),
                    (df["low"] - df["close"].shift()).abs(),
                ],
                axis=1,
            ).max(axis=1)
            atr = tr.rolling(period).mean()
            upper = hl2 + mult * atr
            lower = hl2 - mult * atr
            df["supertrend"] = lower
            df["signal_supertrend"] = df["close"] > df["supertrend"]

    return df


def simulate_strategy(df: pd.DataFrame, strategy: dict) -> list[dict]:
    """
    Walk candle-by-candle and simulate entry/exit logic.
    Returns list of trade records.
    """
    exit_cond = strategy["exit_conditions"]
    risk = strategy["risk"]
    target_pct = exit_cond.get("target_pct")
    sl_pct = exit_cond.get("stoploss_pct")
    trailing_sl_pct = exit_cond.get("trailing_sl_pct")
    time_exit = exit_cond.get("time_exit")  # e.g. "15:15"

    # Total quantity = quantity_lots × lot_size (user provides both)
    quantity = risk.get("quantity_lots", 1) * risk.get("lot_size", 1)

    trades = []
    in_trade = False
    entry_price = 0.0
    entry_time = None
    trade_no = 0
    daily_trades = {}
    daily_loss = {}
    highest_price = 0.0

    for i, row in df.iterrows():
        bar_date = row["time"].date()
        bar_time = row["time"].strftime("%H:%M")

        # Reset daily counters
        if bar_date not in daily_trades:
            daily_trades[bar_date] = 0
            daily_loss[bar_date] = 0.0

        if in_trade:
            pnl_pct = (row["close"] - entry_price) / entry_price * 100
            highest_price = max(highest_price, row["high"])
            exit_reason = None

            # Time-based exit
            if time_exit and bar_time >= time_exit:
                exit_reason = "TIME"
            # Target
            elif target_pct and pnl_pct >= target_pct:
                exit_reason = "TARGET"
            # Trailing SL
            elif trailing_sl_pct:
                drawdown_from_peak = (
                    (highest_price - row["close"]) / highest_price * 100
                )
                if drawdown_from_peak >= trailing_sl_pct:
                    exit_reason = "TRAILING"
            # Stop loss
            elif sl_pct and pnl_pct <= -sl_pct:
                exit_reason = "SL"

            if exit_reason:
                pnl = (row["close"] - entry_price) * quantity
                trades.append(
                    {
                        "trade_no": trade_no,
                        "entry_time": entry_time.isoformat(),
                        "entry_price": round(entry_price, 2),
                        "exit_time": row["time"].isoformat(),
                        "exit_price": round(row["close"], 2),
                        "pnl": round(pnl, 2),
                        "pnl_pct": round(pnl_pct, 2),
                        "exit_reason": exit_reason,
                    }
                )
                daily_loss[bar_date] = daily_loss.get(bar_date, 0) + min(pnl, 0)
                in_trade = False
                if (
                    not strategy["risk"].get("reentry_after_sl", False)
                    and exit_reason == "SL"
                ):
                    continue

        if not in_trade:
            # Check daily limits
            if daily_trades.get(bar_date, 0) >= risk.get("max_trades_per_day", 3):
                continue
            if abs(daily_loss.get(bar_date, 0)) >= risk.get("max_loss_per_day", 5000):
                continue

            # Check entry signal (simplified: any signal column true)
            signal_cols = [c for c in df.columns if c.startswith("signal_")]
            if signal_cols:
                entry_conditions = strategy.get("entry_conditions", [])
                logic = (
                    entry_conditions[0].get("logic", "AND")
                    if entry_conditions
                    else "AND"
                )
                if logic == "AND":
                    triggered = all(row.get(c, False) for c in signal_cols)
                else:
                    triggered = any(row.get(c, False) for c in signal_cols)
            else:
                triggered = False

            if triggered:
                in_trade = True
                entry_price = row["close"]
                entry_time = row["time"]
                highest_price = entry_price
                daily_trades[bar_date] = daily_trades.get(bar_date, 0) + 1
                trade_no += 1

    return trades


def compute_summary(
    trades: list[dict],
    candle_count: int,
    from_date: date,
    to_date: date,
    backtest_id: str,
    strategy_id: str,
) -> dict:
    """Compute summary statistics from trade list."""
    if not trades:
        return {
            "backtest_id": backtest_id,
            "strategy_id": strategy_id,
            "total_trades": 0,
            "winning_trades": 0,
            "losing_trades": 0,
            "win_rate": 0.0,
            "total_pnl": 0.0,
            "max_drawdown": 0.0,
            "avg_trade_pnl": 0.0,
            "best_trade": 0.0,
            "worst_trade": 0.0,
            "candle_count": candle_count,
            "date_range": f"{from_date} to {to_date}",
        }

    pnls = [t["pnl"] for t in trades]
    wins = [p for p in pnls if p > 0]
    losses = [p for p in pnls if p <= 0]

    # Equity curve for drawdown
    equity = 0.0
    peak = 0.0
    max_dd = 0.0
    for p in pnls:
        equity += p
        peak = max(peak, equity)
        dd = peak - equity
        max_dd = max(max_dd, dd)

    return {
        "backtest_id": backtest_id,
        "strategy_id": strategy_id,
        "total_trades": len(trades),
        "winning_trades": len(wins),
        "losing_trades": len(losses),
        "win_rate": round(len(wins) / len(trades) * 100, 1),
        "total_pnl": round(sum(pnls), 2),
        "max_drawdown": round(max_dd, 2),
        "avg_trade_pnl": round(sum(pnls) / len(trades), 2),
        "best_trade": round(max(pnls), 2),
        "worst_trade": round(min(pnls), 2),
        "candle_count": candle_count,
        "date_range": f"{from_date} to {to_date}",
    }


def run_backtest(strategy: dict, backtest_id: str) -> dict:
    """Main entry point — run backtest for single or multiple stocks."""
    from_date = (
        date.fromisoformat(strategy.get("backtest_from"))
        if strategy.get("backtest_from")
        else (date.today() - timedelta(days=180))
    )
    to_date = (
        date.fromisoformat(strategy.get("backtest_to"))
        if strategy.get("backtest_to")
        else date.today()
    )

    asset_type = strategy.get("asset_type", "EQUITY")

    # Support multi-stock strategies: get symbols list or fallback to single symbol
    symbols = strategy.get("symbols", [])
    if not symbols and strategy.get("symbol"):
        symbols = [strategy.get("symbol", "RELIANCE")]

    all_trades = []
    all_candles = []
    all_summaries = []

    if asset_type == "EQUITY":
        # Run backtest for each symbol
        for idx, symbol in enumerate(symbols):
            df = load_equity_candles(
                symbol=symbol,
                timeframe=strategy["timeframe"],
                from_date=from_date,
                to_date=to_date,
            )

            if df.empty:
                continue

            df = compute_indicators(df, strategy.get("entry_conditions", []))
            trades = simulate_strategy(df, strategy)

            # Add symbol to each trade
            for trade in trades:
                trade["symbol"] = symbol

            all_trades.extend(trades)

            # Collect candles (only for first symbol or combine all)
            if idx == 0 or len(symbols) == 1:
                df_copy = df.copy()
                df_copy["symbol"] = symbol
                all_candles.append(df_copy)

            # Compute per-symbol summary
            symbol_summary = compute_summary(
                trades,
                len(df),
                from_date,
                to_date,
                backtest_id,
                strategy["strategy_id"],
            )
            symbol_summary["symbol"] = symbol
            all_summaries.append(symbol_summary)

    else:
        # F&O strategy (single index)
        df = load_candles(
            index=strategy["index"],
            option_type=strategy["option_type"],
            timeframe=strategy["timeframe"],
            from_date=from_date,
            to_date=to_date,
            strike_type=strategy.get("strike_type", "ATM"),
        )

        if df.empty:
            # Provide detailed error information for options backtesting
            logger.error(
                f"[OPTIONS] Backtest failed: No candle data loaded. "
                f"Index={strategy.get('index')}, "
                f"OptionType={strategy.get('option_type')}, "
                f"Timeframe={strategy.get('timeframe')}. "
                f"Required files:\n"
                f"  1. data/underlying/{strategy.get('index')}/{strategy.get('timeframe')}.parquet\n"
                f"  2. data/candles/{strategy.get('index')}/{strategy.get('option_type')}/{strategy.get('timeframe')}/dhan_ec*_*.parquet"
            )
            return {
                "summary": {
                    **compute_summary(
                        [], 0, from_date, to_date, backtest_id, strategy["strategy_id"]
                    ),
                    "error": "MISSING_OPTIONS_DATA",
                    "error_message": (
                        f"Options data not found for {strategy.get('index')}/{strategy.get('option_type')}. "
                        f"Options backtesting requires two data files:\n"
                        f"1. Underlying spot: data/underlying/{strategy.get('index')}/{strategy.get('timeframe')}.parquet\n"
                        f"2. Options strikes: data/candles/{strategy.get('index')}/{strategy.get('option_type')}/{strategy.get('timeframe')}/dhan_ec*_*.parquet"
                    ),
                    "missing_data": {
                        "underlying": f"data/underlying/{strategy.get('index')}/{strategy.get('timeframe')}.parquet",
                        "options": f"data/candles/{strategy.get('index')}/{strategy.get('option_type')}/{strategy.get('timeframe')}/",
                    },
                },
                "trades": [],
            }

        df = compute_indicators(df, strategy.get("entry_conditions", []))
        trades = simulate_strategy(df, strategy)
        all_trades = trades
        all_candles = [df]
        all_summaries = [
            compute_summary(
                trades,
                len(df),
                from_date,
                to_date,
                backtest_id,
                strategy["strategy_id"],
            )
        ]

    # Combine all candles
    if all_candles:
        combined_candles = pd.concat(all_candles, ignore_index=True)
    else:
        combined_candles = pd.DataFrame()

    # Use first summary or combine summaries
    if len(all_summaries) == 1:
        final_summary = all_summaries[0]
    else:
        # Aggregate summaries for multi-stock
        total_trades = sum(s["total_trades"] for s in all_summaries)
        winning_trades = sum(s["winning_trades"] for s in all_summaries)
        losing_trades = sum(s["losing_trades"] for s in all_summaries)
        total_pnl = sum(s["total_pnl"] for s in all_summaries)
        all_pnls = [t["pnl"] for t in all_trades]

        final_summary = {
            "backtest_id": backtest_id,
            "strategy_id": strategy["strategy_id"],
            "symbols": symbols,  # List of symbols
            "total_trades": total_trades,
            "winning_trades": winning_trades,
            "losing_trades": losing_trades,
            "win_rate": round(winning_trades / total_trades * 100, 1)
            if total_trades > 0
            else 0,
            "total_pnl": round(total_pnl, 2),
            "max_drawdown": max(s["max_drawdown"] for s in all_summaries)
            if all_summaries
            else 0,
            "avg_trade_pnl": round(total_pnl / total_trades, 2)
            if total_trades > 0
            else 0,
            "best_trade": round(max(all_pnls), 2) if all_pnls else 0,
            "worst_trade": round(min(all_pnls), 2) if all_pnls else 0,
            "candle_count": len(combined_candles),
            "date_range": f"{from_date} to {to_date}",
            "per_symbol_summaries": all_summaries,
        }

    return {
        "summary": final_summary,
        "trades": all_trades,
        "candles": combined_candles,
    }
