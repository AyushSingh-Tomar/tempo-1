import json
from urllib.error import HTTPError
from urllib.request import Request, urlopen

endpoint = "https://ai-proxy.lab.epam.com/openai/deployments/gpt-5-mini-2025-08-07/chat/completions?api-version=2025-04-01-preview"
payload = {
    "messages": [{"role": "user", "content": "Say hello"}],
    "temperature": 0,
    "max_completion_tokens": 100,
}
req = Request(
    endpoint,
    data=json.dumps(payload).encode("utf-8"),
    headers={
        "Content-Type": "application/json",
        "Api-Key": "dial-quqjvxl582cjet80z6vbzxv4d1g",
    },
    method="POST",
)

try:
    with urlopen(req, timeout=30) as r:
        print(r.status)
        print(r.read().decode("utf-8"))
except HTTPError as e:
    print("status", e.code)
    body = e.read().decode("utf-8", errors="replace")
    print(body)
