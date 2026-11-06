"""Webhook server: receives WhatsApp replies, serves generated images, runs the daily schedule."""
import json
import threading
import time
import urllib.parse
from datetime import datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from zoneinfo import ZoneInfo

from . import whatsapp

LOCK = threading.Lock()


def norm(num):
    return "".join(ch for ch in (num or "") if ch.isdigit())


def make_handler(cfg, pipe):
    class H(BaseHTTPRequestHandler):
        def _reply(self, code, body="ok", ctype="text/plain", raw=None):
            data = raw if raw is not None else body.encode()
            self.send_response(code)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)

        def log_message(self, *a):
            pass

        def do_GET(self):
            path = urllib.parse.urlparse(self.path).path
            if path == "/health":
                return self._reply(200)
            if path.startswith("/media/"):
                f = (cfg.data_dir / "media" / path.split("/")[-1])
                if f.is_file() and f.suffix == ".png" and f.parent == cfg.data_dir / "media":
                    return self._reply(200, ctype="image/png", raw=f.read_bytes())
            self._reply(404, "not found")

        def do_POST(self):
            path = urllib.parse.urlparse(self.path).path
            n = int(self.headers.get("Content-Length") or 0)
            body = self.rfile.read(n).decode()
            if path == "/whatsapp":
                params = {k: v[0] for k, v in urllib.parse.parse_qs(body, keep_blank_values=True).items()}
                if cfg.whatsapp_provider == "twilio":
                    url = cfg.public_base_url.rstrip("/") + "/whatsapp"
                    if not whatsapp.valid_twilio_signature(cfg.secret("TWILIO_AUTH_TOKEN"), url, params, self.headers.get("X-Twilio-Signature")):
                        return self._reply(403, "bad signature")
                if norm(params.get("From", "").replace("whatsapp:", "")) != norm(cfg.approver):
                    return self._reply(403, "unknown sender")
                text = params.get("Body", "")
                threading.Thread(target=_locked, args=(pipe.handle_reply, text), daemon=True).start()
                return self._reply(200, "<Response/>", "text/xml")
            if path == "/admin/run" and cfg.admin_token and self.headers.get("Authorization") == "Bearer " + cfg.admin_token:
                threading.Thread(target=_locked, args=(pipe.discover,), daemon=True).start()
                return self._reply(202, "started")
            self._reply(404, "not found")

    return H


def _locked(fn, *a):
    with LOCK:
        try:
            fn(*a)
        except Exception as e:
            print("[server] error:", e)


def scheduler(cfg, pipe):
    tz, last = ZoneInfo(cfg.timezone), None
    while True:
        now = datetime.now(tz)
        key = now.strftime("%Y-%m-%d %H:%M")
        day = now.strftime("%a").lower()[:3]
        if day in [d.lower()[:3] for d in cfg.run_days] and now.strftime("%H:%M") in cfg.run_times and key != last:
            last = key
            _locked(pipe.discover)
        time.sleep(20)


def serve(cfg, pipe):
    threading.Thread(target=scheduler, args=(cfg, pipe), daemon=True).start()
    srv = ThreadingHTTPServer(("0.0.0.0", cfg.port), make_handler(cfg, pipe))
    print(f"[server] listening on :{cfg.port}; runs {cfg.run_days} at {cfg.run_times} {cfg.timezone}")
    srv.serve_forever()
