import pandas as pd
import yfinance as yf
import os
import pytz

def backfill_underlying():
    indices = {
        'BANKNIFTY': '^NSEBANK',
        'FINNIFTY': '^CNXFIN'
    }
    
    # We will backfill for 2020 and 2021
    start_date = '2020-01-01'
    end_date = '2022-01-01'  # yfinance end_date is exclusive
    
    base_dir = '/Users/sanim/Downloads/sunny/Python/AIML/Pybankers/Pytrader/data/underlying'
    
    for name, symbol in indices.items():
        print(f"\\n--- Backfilling {name} ({symbol}) ---")
        
        # Download 5min and 15min data for last 60 days max with yfinance, but yf limits intraday data to 60 days.
        # Wait, yfinance only gives intraday data (1m, 5m, 15m) for the last 60 days.
        # We cannot get 2020-2021 *intraday* data from yfinance.
        # Only daily data is available for that far back.
        
        # We need to fetch Daily (1d) to ensure we have something, or note that we can't backfill intraday.
        print(f"yfinance restricts intraday data to the last 60 days. Checking daily data...")
        df_daily = yf.download(symbol, start=start_date, end=end_date, interval='1d')
        
        if df_daily.empty:
            print(f"No daily data found for {symbol}.")
            continue
            
        print(f"Fetched {len(df_daily)} daily rows for {name}.")
        print(f"Since yfinance doesn't provide 5m/15m data for 2020-2021, we can only save this as 1d data or notify the user.")

if __name__ == '__main__':
    backfill_underlying()
