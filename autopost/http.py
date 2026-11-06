"""Tiny stdlib HTTP helper (keeps the project dependency-free)."""
import json
import urllib.error
import urllib.request


class HttpError(RuntimeError):
    def __init__(self, status, body):
        super().__init__(f"HTTP {status}: {body[:300]}")
        self.status = status


def request(method, url, *, headers=None, json_body=None, data=None, timeout=60, raw=False):
    h = {"User-Agent": "jkam-autopost/1.0", **(headers or {})}
    if json_body is not None:
        data = json.dumps(json_body).encode()
        h["Content-Type"] = "application/json"
    req = urllib.request.Request(url, data=data, headers=h, method=method)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            body = r.read()
    except urllib.error.HTTPError as e:
        raise HttpError(e.code, e.read().decode("utf-8", "replace")) from None
    if raw:
        return body
    text = body.decode("utf-8", "replace")
    try:
        return json.loads(text)
    except ValueError:
        return text
