import duckdb
import pandas as pd
con = duckdb.connect()
df = pd.DataFrame({'time': [pd.Timestamp('2026-04-15 03:45:00')]})
print("Input naive:")
print(df)
res = con.execute("SELECT time::TIMESTAMPTZ as tz_time FROM df").df()
print("\nTIMESTAMPTZ cast:")
print(res)
print(res['tz_time'])
res_bucket = con.execute("SELECT TIME_BUCKET(INTERVAL 5 MINUTES, time::TIMESTAMPTZ, 'Asia/Kolkata') as b_time FROM df").df()
print("\nbucket:")
print(res_bucket)
