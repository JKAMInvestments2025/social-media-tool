"""Find candidate articles from RSS/Atom feeds and Google News searches; fetch article text."""
import re
import urllib.parse
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
from html.parser import HTMLParser

from . import http


def _txt(el, *names):
    for n in names:
        for child in el.iter():
            if child.tag.split("}")[-1] == n and (child.text or "").strip():
                return child.text.strip()
    return ""


def _date(s):
    if not s:
        return None
    try:
        d = parsedate_to_datetime(s)
    except (TypeError, ValueError):
        try:
            d = datetime.fromisoformat(s.replace("Z", "+00:00"))
        except ValueError:
            return None
    return d if d.tzinfo else d.replace(tzinfo=timezone.utc)


def parse_feed(xml_text):
    root = ET.fromstring(xml_text)
    out = []
    for e in root.iter():
        if e.tag.split("}")[-1] not in ("item", "entry"):
            continue
        link = _txt(e, "link")
        if not link:
            for c in e:
                if c.tag.split("}")[-1] == "link" and c.get("href"):
                    link = c.get("href")
        out.append({"title": _strip(_txt(e, "title")), "url": link,
                    "summary": _strip(_txt(e, "description", "summary", "content"))[:600],
                    "published": _date(_txt(e, "pubDate", "published", "updated", "date"))})
    return out


def _strip(s):
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", s or "")).strip()


def gather(cfg, fetch=None):
    fetch = fetch or (lambda u: http.request("GET", u, timeout=20, raw=True).decode("utf-8", "replace"))
    urls = list(cfg.feeds) + [
        "https://news.google.com/rss/search?q=" + urllib.parse.quote(q + " when:2d") + "&hl=en-US&gl=US&ceid=US:en"
        for q in cfg.search_queries]
    cutoff = datetime.now(timezone.utc) - timedelta(days=cfg.max_article_age_days)
    seen, out = set(), []
    for u in urls:
        try:
            entries = parse_feed(fetch(u))
        except Exception as e:  # one bad feed must not stop the run
            print(f"[sources] {u}: {e}")
            continue
        for a in entries:
            if not a["url"] or not a["title"] or a["url"] in seen:
                continue
            if a["published"] and a["published"] < cutoff:
                continue
            seen.add(a["url"])
            out.append(a)
    return out[: cfg.max_candidates * 3]


class _Text(HTMLParser):
    SKIP = {"script", "style", "nav", "footer", "header", "aside", "form", "noscript"}

    def __init__(self):
        super().__init__()
        self.skip, self.parts = 0, []

    def handle_starttag(self, tag, attrs):
        if tag in self.SKIP:
            self.skip += 1

    def handle_endtag(self, tag):
        if tag in self.SKIP and self.skip:
            self.skip -= 1

    def handle_data(self, data):
        if not self.skip and len(data.strip()) > 40:
            self.parts.append(data.strip())


def article_text(url, fetch=None, limit=6000):
    try:
        html = fetch(url) if fetch else http.request("GET", url, timeout=20, raw=True).decode("utf-8", "replace")
    except Exception as e:
        print(f"[sources] could not fetch {url}: {e}")
        return ""
    p = _Text()
    p.feed(html)
    return " ".join(p.parts)[:limit]
