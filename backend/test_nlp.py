from app.services.nlp_engine import parse_query

queries = [
    "Buy when the 14-period RSI drops below 30",
    "Price crosses above 200 SMA",
    "Relative Strength Index is less than 40 and MACD crosses above signal",
    "Close > EMA(20) and volume > 100000"
]

for q in queries:
    print(f"\nQuery: {q}")
    print(parse_query(q))
