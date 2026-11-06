"""WhatsApp transport. 'twilio' for production; 'console' prints messages (replies via CLI/HTTP)."""
import base64
import hashlib
import hmac
import urllib.parse

from . import http


class Console:
    def __init__(self, cfg):
        self.sent = []

    def send(self, text, media_url=None):
        self.sent.append((text, media_url))
        print(f"\n--- WhatsApp -> approver ---\n{text}" + (f"\n[image: {media_url}]" if media_url else "") + "\n----------------------------")


class Twilio:
    def __init__(self, cfg):
        self.cfg = cfg

    def send(self, text, media_url=None):
        sid, tok = self.cfg.secret("TWILIO_ACCOUNT_SID"), self.cfg.secret("TWILIO_AUTH_TOKEN")
        form = {"From": "whatsapp:" + self.cfg.secret("TWILIO_WHATSAPP_FROM"), "To": "whatsapp:" + self.cfg.approver, "Body": text[:1500]}
        if media_url:
            form["MediaUrl"] = media_url
        auth = base64.b64encode(f"{sid}:{tok}".encode()).decode()
        http.request("POST", f"https://api.twilio.com/2010-04-01/Accounts/{sid}/Messages.json",
                     headers={"Authorization": "Basic " + auth}, data=urllib.parse.urlencode(form).encode())


def make(cfg):
    return Twilio(cfg) if cfg.whatsapp_provider == "twilio" else Console(cfg)


def valid_twilio_signature(auth_token, url, params, signature):
    """https://www.twilio.com/docs/usage/security#validating-requests"""
    payload = url + "".join(k + params[k] for k in sorted(params))
    digest = base64.b64encode(hmac.new(auth_token.encode(), payload.encode(), hashlib.sha1).digest()).decode()
    return hmac.compare_digest(digest, signature or "")
