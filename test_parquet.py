from datetime import date
import os
from collections import defaultdict
import pyarrow.parquet as pq
import pandas as pd

for index_name in ["BANKNIFTY", "FINNIFTY", "NIFTY"]:
    print(f"\n======== {index_name} ========")
    for opt in ["CE", "PE"]:
        for interval in ["15min", "5min", "1min"]:
            base_dir = f"data-scripts/data/candles/{index_name}/{opt}/{interval}"
            if not os.path.exists(base_dir):
                continue
                
            files = os.listdir(base_dir)
            if not files:
                continue
                
            total_rows = 0
            expiry_to_dates = defaultdict(list)
            for f in files:
                if f.endswith(".parquet") and "ec" in f:
                    ec_part = f.split("_")[1] # ec10
                    ec = int(ec_part.replace("ec", ""))
                    filepath = os.path.join(base_dir, f)
                    try:
                        df = pq.read_table(filepath).to_pandas()
                        if not df.empty:
                            total_rows += len(df)
                            min_time = df["time"].min()
                            max_time = df["time"].max()
                            expiry_to_dates[ec].append((min_time, max_time))
                    except Exception:
                        pass
                        
            print(f"  [{opt} {interval}] Files: {len(files)} | Rows: {total_rows} | Expiries: {len(expiry_to_dates)}")
            if len(expiry_to_dates) > 0:
                summary = {}
                for ec, dates in expiry_to_dates.items():
                    overall_min = min(d[0] for d in dates)
                    overall_max = max(d[1] for d in dates)
                    summary[ec] = {"min_date": str(overall_min), "max_date": str(overall_max)}
                
                exp_list = sorted(summary.keys())
                print(f"    Available ECs: {exp_list}")
                print(f"    EC {exp_list[-1]} range: {summary[exp_list[-1]]['min_date']} to {summary[exp_list[-1]]['max_date']}")

