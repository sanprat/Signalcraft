import urllib.request, json, urllib.error
url = "https://api.telegram.org/bot/sendMessage"
payload = {"chat_id": "123", "text": "A" * 3900}
data = json.dumps(payload).encode("utf-8")
request = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"})
try:
    urllib.request.urlopen(request)
except urllib.error.HTTPError as e:
    print("HTTPError:", e.code, e.reason)
