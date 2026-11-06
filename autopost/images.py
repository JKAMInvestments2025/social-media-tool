import base64
import zlib
import struct

from . import http


def _png(w=1024, h=1024, rgb=(11, 42, 102)):
    row = b"\x00" + bytes(rgb) * w
    raw = zlib.compress(row * h)
    def chunk(t, d):
        c = struct.pack(">I", len(d)) + t + d
        return c + struct.pack(">I", zlib.crc32(t + d) & 0xFFFFFFFF)
    return (b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", w, h, 8, 2, 0, 0, 0))
            + chunk(b"IDAT", raw) + chunk(b"IEND", b""))


def generate(cfg, prompt, item_id, rev):
    """Returns path of a saved PNG, or None when image_provider == 'none'."""
    if cfg.image_provider == "none":
        return None
    out = cfg.data_dir / "media" / f"{item_id}-{rev}.png"
    out.parent.mkdir(parents=True, exist_ok=True)
    if cfg.image_provider == "fake":
        out.write_bytes(_png(64, 64))
        return str(out)
    r = http.request("POST", "https://api.openai.com/v1/images/generations",
                     headers={"Authorization": "Bearer " + cfg.secret("OPENAI_API_KEY")},
                     json_body={"model": cfg.openai_image_model, "prompt": prompt, "size": "1024x1024", "n": 1}, timeout=180)
    d = r["data"][0]
    out.write_bytes(base64.b64decode(d["b64_json"]) if d.get("b64_json") else http.request("GET", d["url"], raw=True))
    return str(out)
