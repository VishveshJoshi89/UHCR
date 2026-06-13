import urllib.request
import json

data = {
    "prompt": "Explain UHCR",
    "n_predict": 100
}

req = urllib.request.Request(
    "http://127.0.0.1:8080/completion",
    data=json.dumps(data).encode(),
    headers={"Content-Type": "application/json"}
)

with urllib.request.urlopen(req) as response:
    print(response.read().decode())