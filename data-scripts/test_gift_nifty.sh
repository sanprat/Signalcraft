#!/bin/bash
# test_gift_nifty.sh - Test GIFT NIFTY security IDs

TOKEN="eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzUxMiJ9.eyJpc3MiOiJkaGFuIiwicGFydG5lcklkIjoiIiwiZXhwIjoxNzcyNDQ0MjgzLCJpYXQiOjE3NzIzNTc4ODMsInRva2VuQ29uc3VtZXJUeXBlIjoiU0VMRiIsIndlYmhvb2tVcmwiOiIiLCJkaGFuQ2xpZW50SWQiOiIxMTEwNTU3ODk2In0.WK6asDPtQ1q0yA9yvmNE5IN6ZvF-JNorZYAtyeKPt05HkzFTA-jIRPel5A0V57ACQDEB3g1WZweNpUCO8sDMcg"
CLIENT="1110557896"

echo "=========================================="
echo "  GIFT NIFTY SECURITY ID TEST"
echo "=========================================="

# Test known working NIFTY first
echo -e "\n[BASELINE] Testing NIFTY (securityId=13)..."
curl -s -X POST "https://api.dhan.co/v2/charts/intraday" \
  -H "access-token: $TOKEN" \
  -H "client-id: $CLIENT" \
  -H "Content-Type: application/json" \
  -d '{"securityId":"13","exchangeSegment":"IDX_I","instrument":"INDEX","interval":"15","oi":false,"fromDate":"2024-01-15 09:15:00","toDate":"2024-01-15 15:30:00"}' > /tmp/nifty_test.json

if grep -q '"timestamp"' /tmp/nifty_test.json; then
    echo "✓ NIFTY works (baseline established)"
else
    echo "✗ NIFTY failed - check API"
    cat /tmp/nifty_test.json
fi

# Test various security IDs for GIFT NIFTY
echo -e "\n[TESTING] GIFT NIFTY candidates..."

for id in 26000 26009 26037 26050 26069 100 200; do
    echo -e "\n--- Testing securityId: $id ---"
    curl -s -X POST "https://api.dhan.co/v2/charts/intraday" \
      -H "access-token: $TOKEN" \
      -H "client-id: $CLIENT" \
      -H "Content-Type: application/json" \
      -d "{\"securityId\":\"$id\",\"exchangeSegment\":\"IDX_I\",\"instrument\":\"INDEX\",\"interval\":\"15\",\"oi\":false,\"fromDate\":\"2024-01-15 09:15:00\",\"toDate\":\"2024-01-15 15:30:00\"}" > /tmp/test_$id.json
    
    if grep -q '"timestamp"' /tmp/test_$id.json; then
        echo "✓ SUCCESS for ID $id!"
        python3 -c "import json; d=json.load(open('/tmp/test_$id.json')); print(f'  Got {len(d.get(\"timestamp\",[]))} candles')" 2>/dev/null
    else
        echo "✗ Failed:"
        head -c 200 /tmp/test_$id.json
    fi
done

# Test NSE_IX exchange segment
echo -e "\n[TESTING] NSE_IX exchange segment..."
for id in 13 26000; do
    echo -e "\n--- Testing securityId: $id on NSE_IX ---"
    curl -s -X POST "https://api.dhan.co/v2/charts/intraday" \
      -H "access-token: $TOKEN" \
      -H "client-id: $CLIENT" \
      -H "Content-Type: application/json" \
      -d "{\"securityId\":\"$id\",\"exchangeSegment\":\"NSE_IX\",\"instrument\":\"INDEX\",\"interval\":\"15\",\"oi\":false,\"fromDate\":\"2024-01-15 09:15:00\",\"toDate\":\"2024-01-15 15:30:00\"}" > /tmp/test_nseix_$id.json
    
    if grep -q '"timestamp"' /tmp/test_nseix_$id.json; then
        echo "✓ SUCCESS for ID $id on NSE_IX!"
    else
        echo "✗ Failed:"
        head -c 200 /tmp/test_nseix_$id.json
    fi
done

echo -e "\n=========================================="
echo "  TEST COMPLETE"
echo "=========================================="
