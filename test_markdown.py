import urllib.request, json, urllib.error
import os

token = "7050309908:AAGoJ_qK1UqKx" # dummy fake token
chat = "123"

# Read actual token from real env so we don't get 401
if os.path.exists(".env"):
    with open(".env") as f:
        for l in f:
            if "TELEGRAM_BOT_TOKEN=" in l: token = l.strip().split("=")[1]
            if "TELEGRAM_CHAT_ID=" in l: chat = l.strip().split("=")[1]

url = f"https://api.telegram.org/bot{token}/sendMessage"
payload = {"chat_id": chat, "text": "```\nunclosed markdown", "parse_mode": "Markdown"}
data = json.dumps(payload).encode("utf-8")
request = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"})
try:
    urllib.request.urlopen(request)
except urllib.error.HTTPError as e:
    print("HTTPError:", e.code, e.reason)
    print(e.read().decode())
