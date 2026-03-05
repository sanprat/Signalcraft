import os
import pandas as pd
import numpy as np
from scipy.signal import argrelextrema
import pyarrow.parquet as pq
from typing import Any

def sanitize_native(obj: Any) -> Any:
    """Recursively converts numpy types to native Python types for JSON serialization."""
    if isinstance(obj, dict):
        return {k: sanitize_native(v) for k, v in obj.items()}
    elif isinstance(obj, (list, tuple)):
        return [sanitize_native(i) for i in obj]
    elif isinstance(obj, np.bool_):
        return bool(obj)
    elif hasattr(obj, "item"): # Handles numpy scalars
        val = obj.item()
        if isinstance(val, (float, int)):
            if not np.isfinite(val):
                return None
        return val
    elif isinstance(obj, float):
        if not np.isfinite(obj):
            return None
    return obj

# =========================================================
# Screener 1: Minervini Trend Template
# =========================================================
def minervini_trend_template(df, params=None):
    p = {
        'sma_50': 50, 'sma_150': 150, 'sma_200': 200, 'sma_200_lookback': 22,
        'rs_min': 70, 'pct_above_52w_low': 25, 'pct_below_52w_high': 25
    }
    if params: p.update(params)
    
    close = df['Close']
    if len(close) < p['sma_200'] + p['sma_200_lookback']:
        return {"screener": "minervini_trend_template", "pass": False, "error": "Not enough data"}

    sma50 = close.rolling(p['sma_50']).mean()
    sma150 = close.rolling(p['sma_150']).mean()
    sma200 = close.rolling(p['sma_200']).mean()
    
    high52w = df['High'].rolling(252).max().iloc[-1]
    low52w = df['Low'].rolling(252).min().iloc[-1]
    
    c = close.iloc[-1]
    s50 = sma50.iloc[-1]
    s150 = sma150.iloc[-1]
    s200 = sma200.iloc[-1]
    s200_past = sma200.iloc[-(p['sma_200_lookback'] + 1)] if len(sma200) > p['sma_200_lookback'] else s200
    
    cond1 = c > s200
    cond2 = s200 > s200_past
    cond3 = s150 > s200
    cond4 = s50 > s150
    cond5 = s50 > s200
    cond6 = c > s50
    cond7 = c >= low52w * (1 + p['pct_above_52w_low'] / 100)
    cond8 = c >= high52w * (1 - p['pct_below_52w_high'] / 100)
    
    # Note: RS rating logic requires universe context, we'll approximate with 12m perf for now or handle at universe level
    # Since we are doing symbol-by-symbol, we assume passing the other strict technicals is sufficient,
    # or we can compute it if passed universe perf. We will compute a pseudo RS here.
    perf_12m = (c - close.iloc[-252]) / close.iloc[-252] if len(close) >= 252 else 0
    # True RS ranking is done outside, we'll just return the perf_12m for external ranking
    
    passed = all([cond1, cond2, cond3, cond4, cond5, cond6, cond7, cond8])
    
    return {
        "screener": "minervini_trend_template",
        "pass": bool(passed),
        "sma_50": round(float(s50), 2),
        "sma_150": round(float(s150), 2),
        "sma_200": round(float(s200), 2),
        "pct_above_52w_low": round(float((c - low52w) / low52w * 100), 2),
        "pct_below_52w_high": round(float((high52w - c) / high52w * 100), 2),
        "perf_12m": round(float(perf_12m * 100), 2)
    }

# =========================================================
# Screener 2: Minervini VCP
# =========================================================
def detect_vcp(df, params=None):
    p = {
        'swing_order': 5, 'min_contractions': 2, 'max_contractions': 4,
        'max_last_contraction_pct': 10, 'pivot_proximity_pct': 3,
        'lookback': 252 # 1 year
    }
    if params: p.update(params)
    
    if len(df) < p['lookback']:
        return {"screener": "vcp", "pass": False, "error": "Not enough data"}

    # Focus on recent data for VCP base formation
    recent_df = df.tail(p['lookback'])
    highs_idx = argrelextrema(recent_df['High'].values, np.greater, order=p['swing_order'])[0]
    lows_idx  = argrelextrema(recent_df['Low'].values,  np.less,    order=p['swing_order'])[0]
    
    contractions = []
    # Convert local recent_df indices to values
    for h in highs_idx:
        subsequent_lows = lows_idx[lows_idx > h]
        if len(subsequent_lows) == 0:
            continue
        l = subsequent_lows[0]
        h_val = recent_df['High'].iloc[h]
        l_val = recent_df['Low'].iloc[l]
        depth_pct = (h_val - l_val) / h_val * 100
        avg_vol = recent_df['Volume'].iloc[h:l+1].mean()
        contractions.append({'depth_pct': float(depth_pct), 'avg_vol': float(avg_vol)})
        
    if not contractions:
        return {"screener": "vcp", "pass": False, "num_contractions": 0}

    depths = [c['depth_pct'] for c in contractions]
    vols   = [c['avg_vol']   for c in contractions]
    
    # We care about the sequence of the LAST N contractions
    # If more than max, we take the last max_contractions to see if they form a base
    num_found = len(contractions)
    active_depths = depths[-p['max_contractions']:]
    active_vols = vols[-p['max_contractions']:]
    
    contracting_depth  = all(active_depths[i] > active_depths[i+1] for i in range(len(active_depths)-1)) if len(active_depths) > 1 else False
    contracting_volume = all(active_vols[i] > active_vols[i+1] for i in range(len(active_vols)-1)) if len(active_vols) > 1 else False
    
    last_depth_ok = active_depths[-1] < p['max_last_contraction_pct'] if active_depths else False
    
    pivot = recent_df['High'].iloc[highs_idx[-1]] if len(highs_idx) > 0 else None
    c = recent_df['Close'].iloc[-1]
    near_pivot = abs(c - pivot) / pivot * 100 < p['pivot_proximity_pct'] if pivot else False
    
    passed = (
        p['min_contractions'] <= len(active_depths) <= p['max_contractions']
        and contracting_depth
        and contracting_volume
        and last_depth_ok
        and near_pivot
    )
    
    return {
        "screener": "vcp",
        "pass": bool(passed),
        "num_contractions": len(active_depths),
        "total_peaks_found": num_found,
        "contraction_depths_pct": [round(d, 2) for d in active_depths],
        "pivot_price": round(float(pivot), 2) if pivot else None,
        "near_pivot": bool(near_pivot),
        "last_contraction_pct": round(active_depths[-1], 2) if active_depths else None
    }

# =========================================================
# Screener 3: IBD CAN SLIM Technicals
# =========================================================
def ibd_canslim(df, params=None):
    p = {
        'pct_below_52w_high': 15, 'avg_volume_min': 400000, 
        'base_length_min_weeks': 5, 'base_depth_max_pct': 33,
        'lookback': 252 # 1 year
    }
    if params: p.update(params)
    
    if len(df) < p['lookback']:
        return {"screener": "ibd_canslim_technical", "pass": False}
        
    recent_df = df.tail(p['lookback'])
    high52w = recent_df['High'].max()
    avg_vol_50d = recent_df['Volume'].rolling(50).mean().iloc[-1]
    c = recent_df['Close'].iloc[-1]
    
    # 5 weeks base approx 25 trading days
    base_window = df.tail(p['base_length_min_weeks'] * 5)
    base_high = base_window['High'].max()
    base_low  = base_window['Low'].min()
    depth_pct = (base_high - base_low) / base_high * 100
    length_weeks = len(base_window) / 5
    
    cond1 = c >= high52w * (1 - p['pct_below_52w_high'] / 100)
    cond2 = avg_vol_50d >= p['avg_volume_min']
    cond3 = length_weeks >= p['base_length_min_weeks'] and depth_pct <= p['base_depth_max_pct']
    
    passed = all([cond1, cond2, cond3])
    
    return {
        "screener": "ibd_canslim_technical",
        "pass": bool(passed),
        "pct_below_52w_high": round((high52w - c)/high52w * 100, 2),
        "avg_volume_50d": int(avg_vol_50d),
        "base_depth_pct": round(depth_pct, 2),
        "base_length_weeks": round(length_weeks, 1)
    }

# =========================================================
# Screener 4: Weinstein Stage 2
# =========================================================
def weinstein_stage2(df, params=None):
    p = {'lookback': 252}
    if params: p.update(params)

    if len(df) < p['lookback']:
        return {"screener": "weinstein_stage2", "pass": False}
        
    recent_df = df.tail(p['lookback'])
    # Convert daily to weekly equivalent (SMA 150 = 30 weeks)
    sma150 = recent_df['Close'].rolling(150).mean()
    price = df['Close'].iloc[-1]
    ma_now = sma150.iloc[-1]
    # 4 weeks ago ~ 20 trading days
    ma_4w = sma150.iloc[-20] if len(sma150) > 20 else ma_now
    
    cond1 = price > ma_now
    cond2 = ma_now >= ma_4w
    
    # Check if price was below MA in last 252 days (52 weeks) 
    past_year = df['Close'].iloc[-252:]
    past_ma = sma150.iloc[-252:]
    was_below = any(past_year < past_ma)
    
    vol_10w_avg = df['Volume'].rolling(50).mean().iloc[-1] # approx
    vol_this_week = df['Volume'].iloc[-5:].mean()
    vol_confirmed = vol_this_week > vol_10w_avg
    
    stage = "Stage 1 - Basing"
    if cond1 and cond2: stage = "Stage 2 - Advancing"
    elif price > ma_now and ma_now < ma_4w: stage = "Stage 3 - Topping"
    elif price < ma_now and ma_now < ma_4w: stage = "Stage 4 - Declining"
    
    passed = (stage == "Stage 2 - Advancing") and was_below and vol_confirmed
    
    return {
        "screener": "weinstein_stage2",
        "pass": bool(passed),
        "stage": stage,
        "close": round(price, 2),
        "sma_30w": round(ma_now, 2),
        "ma_rising": bool(cond2),
        "breakout_volume_confirmed": bool(vol_confirmed)
    }

# =========================================================
# Screener 5: EMA Crossover
# =========================================================
def ema_crossover(df, params=None):
    p = {'fast': 50, 'slow': 200, 'signal': 'golden', 'lookback': 3}
    if params: p.update(params)
    
    if len(df) < p['slow']:
        return {"screener": "ema_crossover", "pass": False}
        
    ema_fast = df['Close'].ewm(span=p['fast'], adjust=False).mean()
    ema_slow = df['Close'].ewm(span=p['slow'], adjust=False).mean()
    diff = ema_fast - ema_slow
    
    lb = p['lookback']
    if p['signal'] == 'golden':
        crossed = any(diff.iloc[-lb-1:-1] <= 0) and diff.iloc[-1] > 0
    else:
        crossed = any(diff.iloc[-lb-1:-1] >= 0) and diff.iloc[-1] < 0
        
    return {
        "screener": "ema_crossover",
        "pass": bool(crossed),
        "signal_type": p['signal'],
        "ema_fast": round(ema_fast.iloc[-1], 2),
        "ema_slow": round(ema_slow.iloc[-1], 2)
    }

# =========================================================
# Screener 6: RSI Momentum
# =========================================================
def rsi_scanner(df, params=None):
    p = {'period': 14, 'mode': 'momentum', 'threshold': 50, 'lookback': 3}
    if params: p.update(params)
    
    if len(df) < p['period']:
        return {"screener": "rsi_momentum", "pass": False}
        
    delta = df['Close'].diff()
    gain = delta.clip(lower=0).rolling(p['period']).mean()
    loss = (-delta.clip(upper=0)).rolling(p['period']).mean()
    rs = gain / loss
    rsi = 100 - (100 / (1 + rs))
    
    current_rsi = rsi.iloc[-1]
    lb = p['lookback']
    recent_rsi = rsi.iloc[-lb-1:-1]
    
    if p['mode'] == 'momentum':
        passed = current_rsi > p['threshold'] and any(recent_rsi <= p['threshold'])
    else: # oversold_recovery
        passed = current_rsi > 30 and any(recent_rsi <= 30)
        
    return {
        "screener": "rsi_momentum",
        "pass": bool(passed),
        "mode": p['mode'],
        "rsi_current": round(current_rsi, 2) if not np.isnan(current_rsi) else None
    }

# =========================================================
# Screener 7: 52-Week High Breakout
# =========================================================
def breakout_52w(df, params=None):
    p = {'lookback': 252, 'vol_mult': 1.5, 'buffer': 0.5}
    if params: p.update(params)
    
    if len(df) < p['lookback']:
        return {"screener": "breakout_52w_high", "pass": False}
        
    high_52w = df['High'].rolling(p['lookback']).max().iloc[-1]
    avg_vol_50 = df['Volume'].rolling(50).mean().iloc[-1]
    close = df['Close'].iloc[-1]
    vol = df['Volume'].iloc[-1]
    
    near_high = close >= high_52w * (1 - p['buffer'] / 100)
    vol_ok = vol > avg_vol_50 * p['vol_mult']
    
    passed = near_high and vol_ok
    return {
        "screener": "breakout_52w_high",
        "pass": bool(passed),
        "52w_high": round(high_52w, 2),
        "pct_from_high": round((high_52w - close)/high_52w * 100, 2),
        "volume_ratio": round(vol / avg_vol_50, 2) if avg_vol_50 else 0
    }

# =========================================================
# Screener 8: MACD Crossover
# =========================================================
def macd_scanner(df, params=None):
    p = {'fast': 12, 'slow': 26, 'signal': 9, 'mode': 'bullish', 'lookback': 3}
    if params: p.update(params)
    
    if len(df) < p['slow']:
        return {"screener": "macd_crossover", "pass": False}
        
    ema_fast = df['Close'].ewm(span=p['fast'], adjust=False).mean()
    ema_slow = df['Close'].ewm(span=p['slow'], adjust=False).mean()
    macd_line = ema_fast - ema_slow
    signal_line = macd_line.ewm(span=p['signal'], adjust=False).mean()
    
    diff = macd_line - signal_line
    lb = p['lookback']
    if p['mode'] == 'bullish':
        crossed = diff.iloc[-1] > 0 and any(diff.iloc[-lb-1:-1] <= 0)
    else:
        crossed = diff.iloc[-1] < 0 and any(diff.iloc[-lb-1:-1] >= 0)
        
    return {
        "screener": "macd_crossover",
        "pass": bool(crossed),
        "signal_type": p['mode'],
        "macd_line": round(macd_line.iloc[-1], 2),
        "signal_line": round(signal_line.iloc[-1], 2),
        "histogram": round(diff.iloc[-1], 2)
    }

# =========================================================
# Screener 9: Bollinger Band Squeeze
# =========================================================
def bollinger_squeeze(df, params=None):
    p = {'period': 20, 'std': 2, 'squeeze_pct': 5, 'direction': 'bullish'}
    if params: p.update(params)
    
    if len(df) < p['period']:
        return {"screener": "bollinger_squeeze", "pass": False}
        
    sma = df['Close'].rolling(p['period']).mean()
    stddev = df['Close'].rolling(p['period']).std()
    upper = sma + p['std'] * stddev
    lower = sma - p['std'] * stddev
    width_pct = (upper - lower) / sma * 100
    
    in_squeeze = width_pct.iloc[-6:-1].lt(p['squeeze_pct']).all()
    expanding = width_pct.iloc[-1] > width_pct.iloc[-4]
    bullish_dir = df['Close'].iloc[-1] > sma.iloc[-1]
    
    passed = in_squeeze and expanding
    if p['direction'] == 'bullish': passed = passed and bullish_dir
    elif p['direction'] == 'bearish': passed = passed and not bullish_dir
    
    return {
        "screener": "bollinger_squeeze",
        "pass": bool(passed),
        "band_width_pct": round(float(width_pct.iloc[-1]), 2),
        "expanding": bool(expanding),
        "direction": "bullish" if bullish_dir else "bearish"
    }

# =========================================================
# Screener 10: Volume Surge
# =========================================================
def volume_surge(df, params=None):
    p = {'period': 50, 'multiplier': 2.0, 'min_avg': 500000, 'direction': 'up', 'min_move': 1.0}
    if params: p.update(params)
    
    if len(df) < p['period']:
        return {"screener": "volume_surge", "pass": False}
        
    avg_vol = df['Volume'].rolling(p['period']).mean()
    vol_ratio = df['Volume'].iloc[-1] / avg_vol.iloc[-1]
    price_chg = (df['Close'].iloc[-1] - df['Close'].iloc[-2]) / df['Close'].iloc[-2] * 100
    
    surge_ok = vol_ratio >= p['multiplier']
    liquid_ok = avg_vol.iloc[-1] >= p['min_avg']
    move_ok = abs(price_chg) >= p['min_move']
    
    dir_ok = True
    if p['direction'] == 'up': dir_ok = price_chg > 0
    if p['direction'] == 'down': dir_ok = price_chg < 0
    
    passed = surge_ok and liquid_ok and move_ok and dir_ok
    return {
        "screener": "volume_surge",
        "pass": bool(passed),
        "volume_ratio": round(vol_ratio, 2),
        "price_change_pct": round(price_chg, 2),
        "direction": "up" if price_chg > 0 else "down"
    }

# =========================================================
# Screener 11: ADX Trend Strength
# =========================================================
def adx_scanner(df, params=None):
    p = {'period': 14, 'min_adx': 25, 'direction': 'bullish'}
    if params: p.update(params)
    
    if len(df) < p['period']:
        return {"screener": "adx_trend_strength", "pass": False}
        
    high, low, close = df['High'], df['Low'], df['Close']
    tr = pd.concat([high - low, (high - close.shift()).abs(), (low - close.shift()).abs()], axis=1).max(axis=1)
    dm_plus = ((high - high.shift()) > (low.shift() - low)).astype(float) * (high - high.shift()).clip(lower=0)
    dm_minus = ((low.shift() - low) > (high - high.shift())).astype(float) * (low.shift() - low).clip(lower=0)

    atr = tr.ewm(span=p['period'], adjust=False).mean()
    di_plus = 100 * dm_plus.ewm(span=p['period'], adjust=False).mean() / atr
    di_minus = 100 * dm_minus.ewm(span=p['period'], adjust=False).mean() / atr
    dx = 100 * (di_plus - di_minus).abs() / (di_plus + di_minus)
    adx = dx.ewm(span=p['period'], adjust=False).mean()
    
    strong_trend = adx.iloc[-1] >= p['min_adx']
    bullish_dir = di_plus.iloc[-1] > di_minus.iloc[-1]
    
    passed = strong_trend
    if p['direction'] == 'bullish': passed = passed and bullish_dir
    elif p['direction'] == 'bearish': passed = passed and not bullish_dir
    
    return {
        "screener": "adx_trend_strength",
        "pass": bool(passed),
        "adx": round(float(adx.iloc[-1]), 2),
        "trend_direction": "bullish" if bullish_dir else "bearish"
    }

# =========================================================
# Screener 12: Darvas Box Breakout
# =========================================================
def darvas_box(df, params=None):
    p = {'formation': 10, 'ceiling_tol': 1.0, 'vol_mult': 1.5, 'lookback': 252}
    if params: p.update(params)
    
    if len(df) < p['lookback']:
        return {"screener": "darvas_box", "pass": False}
        
    recent = df.tail(p['lookback']).copy()
    avg_vol = df['Volume'].rolling(50).mean().iloc[-1]
    
    box_ceiling = recent['High'].rolling(p['formation']).max()
    box_floor = recent['Low'].rolling(p['formation']).min()
    
    latest_ceiling = box_ceiling.iloc[-2]
    latest_floor = box_floor.iloc[-2]
    close_today = recent['Close'].iloc[-1]
    vol_today = recent['Volume'].iloc[-1]
    
    last_n_highs = recent['High'].iloc[-p['formation']-1:-1]
    box_valid = all(h <= latest_ceiling * (1 + p['ceiling_tol']/100) for h in last_n_highs)
    box_depth = (latest_ceiling - latest_floor) / latest_ceiling * 100
    
    breakout = close_today > latest_ceiling
    vol_ok = vol_today > avg_vol * p['vol_mult']
    depth_ok = box_depth >= 3
    
    passed = box_valid and breakout and vol_ok and depth_ok
    return {
        "screener": "darvas_box",
        "pass": bool(passed),
        "box_depth_pct": round(float(box_depth), 2),
        "breakout_confirmed": bool(breakout),
        "volume_ratio": round(vol_today / avg_vol, 2) if avg_vol else 0
    }

# =========================================================
# Runner
# =========================================================
SCREENERS = {
    'minervini_trend_template': minervini_trend_template,
    'vcp': detect_vcp,
    'ibd_canslim': ibd_canslim,
    'weinstein_stage2': weinstein_stage2,
    'ema_crossover': ema_crossover,
    'rsi_momentum': rsi_scanner,
    'breakout_52w': breakout_52w,
    'macd_crossover': macd_scanner,
    'bollinger_squeeze': bollinger_squeeze,
    'volume_surge': volume_surge,
    'adx_strength': adx_scanner,
    'darvas_box': darvas_box
}

def load_symbol_data(symbol: str) -> pd.DataFrame:
    base_dir = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
    file_path = os.path.join(base_dir, "data", "candles", "NIFTY500", symbol, "1D.parquet")
    if not os.path.exists(file_path):
        return None
    try:
        df = pq.read_table(file_path).to_pandas()
        # Ensure correct column naming (capitalized)
        rename_map = {}
        for c in df.columns:
            if c.lower() in ['open', 'high', 'low', 'close', 'volume']:
                rename_map[c] = c.capitalize()
        if rename_map:
            df = df.rename(columns=rename_map)
        return df
    except Exception as e:
        print(f"Error loading {symbol}: {e}")
        return None

def run_screener(screener_id: str, symbol: str, params=None):
    df = load_symbol_data(symbol)
    if df is None or df.empty:
        return {"screener": screener_id, "pass": False, "error": "No data"}
    
    func = SCREENERS.get(screener_id)
    if not func:
        return {"screener": screener_id, "pass": False, "error": "Unknown screener"}
        
    try:
        res = func(df, params)
        res['symbol'] = symbol
        return sanitize_native(res)
    except Exception as e:
        return {"screener": screener_id, "pass": False, "error": str(e), "symbol": symbol}
