"""Schedule an approved post in Vista Social.

Modes
  dry_run        log what would be sent (default; safe)
  vista_webhook  POST JSON to a Make/Zapier catch-hook that runs Vista Social's "Schedule Post" action
                 (works on plans without the API add-on; Make needs Advanced+)
  vista_api      Vista Social's own API (paid add-on). Endpoints POST /v2/posts/save and /v2/media/create are
                 documented by Vista, but the exact JSON field names below are UNVERIFIED -- confirm them against
                 your account's API docs before relying on this mode.
"""
import base64
import json

from . import http

API_BASE = "https://vistasocial.com/api"  # TODO(verify): base URL from your Vista API docs


class DryRun:
    def __init__(self, cfg):
        self.cfg = cfg

    def schedule(self, post):
        print("[vista:dry_run] would schedule:", json.dumps(post, indent=2))
        return "dry-run"


class Webhook:
    def __init__(self, cfg):
        self.cfg = cfg

    def schedule(self, post):
        url = self.cfg.secret("VISTA_WEBHOOK_URL")
        r = http.request("POST", url, json_body=post)
        return str(r)[:100]


class Api:
    def __init__(self, cfg):
        self.cfg = cfg
        self.h = {"Authorization": "Bearer " + cfg.secret("VISTA_API_KEY")}

    def schedule(self, post):
        media_ids = []
        if post.get("image_path"):
            img = base64.b64encode(open(post["image_path"], "rb").read()).decode()
            m = http.request("POST", f"{API_BASE}/v2/media/create", headers=self.h,
                             json_body={"file_name": "post.png", "content_base64": img})
            media_ids.append(m.get("id"))
        r = http.request("POST", f"{API_BASE}/v2/posts/save", headers=self.h, json_body={
            "profile_ids": post["profile_ids"], "text": post["text"], "media_ids": media_ids,
            "schedule_time": post["schedule_time"], "status": "scheduled"})
        return str(r.get("id", r))


def make(cfg):
    return {"vista_api": Api, "vista_webhook": Webhook}.get(cfg.vista_mode, DryRun)(cfg)
