import urllib.request, json
message = "A" * 10000 
if len(message) > 4000:
    message = message[:3900] + "\nTRUNCATED"
print(len(message))
