"""Weekly batch approval flow (two WhatsApp touchpoints per post, one YES to approve).

 1. MENU    one message lists N proposed headlines  -> reply "1 3 5", "all", or "none"
 2. REVIEW  for each pick, ONE message with title + text + image -> reply YES to schedule

States: proposed -> selected -> review_pending -> scheduled   (or rejected / failed)

Review replies: YES | SKIP | REDO (new text + image) | "image: <change>" (image only)
                | "title: <new title>" | any other text = edit instruction for the text.
"""
import re
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from . import compliance, images, llm as llmmod, sources, vista, whatsapp

YES = {"yes", "y", "ok", "approve", "approved", "👍", "✅", "go"}
NO = {"no", "skip", "reject", "n", "stop", "❌"}
REDO = {"redo", "retry", "again", "regenerate"}


class Pipeline:
    def __init__(self, cfg, db, llm=None, wa=None, vista_client=None, fetch=None, public_url=None):
        self.cfg, self.db = cfg, db
        self.llm = llm or llmmod.make(cfg)
        self.wa = wa or whatsapp.make(cfg)
        self.vista = vista_client or vista.make(cfg)
        self.fetch = fetch
        self.public_url = public_url or (lambda path: f"{cfg.public_base_url.rstrip('/')}/media/{path.split('/')[-1]}")

    # ---------- weekly batch ----------
    def discover(self):
        if self.db.active() or self.db.next_selected():
            self.wa.send("Last batch is still open, so I haven't started a new one. Reply to finish it (or SKIP items).")
            return 0
        cands = [c for c in sources.gather(self.cfg, self.fetch) if not self.db.seen(c["url"])][: self.cfg.max_candidates]
        if not cands:
            print("[discover] no new candidates")
            return 0
        ids = []
        for i in llmmod.rank(self.llm, self.cfg, cands, self.cfg.batch_size):
            c = cands[i]
            self.db.mark_seen(c["url"])
            item = {"url": c["url"], "source_title": c["title"], "summary": c["summary"],
                    "article_text": sources.article_text(c["url"], self.fetch)}
            try:
                titles = llmmod.titles(self.llm, self.cfg, item)
            except Exception as e:
                print(f"[discover] titles failed for {c['url']}: {e}")
                continue
            ids.append(self.db.add_item(**item, titles=titles, title=titles[0], state="proposed"))
        if not ids:
            return 0
        lines = []
        for n, i in enumerate(ids, 1):
            it = self.db.item(i)
            lines.append(f"{n}. {it['title']}\n   ↳ {it['source_title'][:80]}")
        self._say(None, f"📰 This week's {len(ids)} story ideas:\n\n" + "\n".join(lines)
                  + '\n\nWhich should I write up? Reply e.g. "1 3 5", "all", or "none".')
        return len(ids)

    # ---------- reply routing ----------
    def handle_reply(self, text):
        item = self.db.active()
        if not item:
            self.wa.send("Nothing is waiting for approval right now.")
            return
        self.db.log(item["id"], "in", text)
        if item["state"] == "proposed":
            return self._menu_reply(text)
        return self._review_reply(item, text)

    def _menu_reply(self, text):
        low = text.strip().lower()
        proposed = self.db.proposed()
        if low in ("all", "everything"):
            picks = set(range(1, len(proposed) + 1))
        elif low in NO or low == "none":
            picks = set()
        else:
            picks = {int(n) for n in re.findall(r"\d+", low) if 1 <= int(n) <= len(proposed)}
            if not picks:
                return self.wa.send(f'Reply with story numbers like "1 3", "all", or "none" (1-{len(proposed)}).')
        for n, it in enumerate(proposed, 1):
            self.db.update(it["id"], state="selected" if n in picks else "rejected")
        self.wa.send(f"👍 Writing up {len(picks)} post(s); I'll send them one at a time." if picks else "OK, nothing selected this week.")
        self.advance()

    def _review_reply(self, item, text):
        t, low = text.strip(), text.strip().lower()
        if low in YES:
            return self._finish(item)
        if low in NO:
            self.db.update(item["id"], state="rejected")
            self._say(item, f"🗑 #{item['id']} skipped.")
            return self.advance()
        if low in REDO:
            return self._draft(item, redo=True)
        m = re.match(r"(image|title)\s*:\s*(.+)", t, re.I | re.S)
        if m and m.group(1).lower() == "title":
            self.db.update(item["id"], title=m.group(2).strip()[:150])
            return self._review_message(self.db.item(item["id"]))
        if m:
            return self._draft(item, image_feedback=m.group(2).strip(), keep_body=True)
        return self._draft(item, body_feedback=t)

    # ---------- drafting ----------
    def advance(self):
        """Draft the next selected post once the approver is free."""
        if self.db.active():
            return
        item = self.db.next_selected()
        if item:
            self._draft(item)

    def _draft(self, item, redo=False, body_feedback="", image_feedback="", keep_body=False):
        try:
            if not keep_body:
                body = llmmod.body(self.llm, self.cfg, item, body_feedback)
                self.db.update(item["id"], body=body)
                item = self.db.item(item["id"])
            if not (body_feedback and item["image_path"]) or redo or image_feedback:
                prompt = llmmod.image_prompt(self.llm, self.cfg, item, image_feedback)
                rev = (item["revisions"] or 0) + 1
                path = images.generate(self.cfg, prompt, item["id"], rev)
                self.db.update(item["id"], image_prompt=prompt, image_path=path)
            self.db.update(item["id"], state="review_pending", revisions=(item["revisions"] or 0) + 1)
        except Exception as e:
            return self._fail(item, e)
        self._review_message(self.db.item(item["id"]))

    def _review_message(self, item):
        warn = compliance.flags(item["body"])
        path = item["image_path"]
        media = self.public_url(path) if path and self.cfg.public_base_url else None
        self._say(item, f"✍️ Post #{item['id']} — review\n\n*{item['title']}*\n\n{item['body']}\n"
                  + (f"\n⚠️ Compliance flags: {', '.join(warn)}\n" if warn else "")
                  + (f"\n[image saved locally: {path}; set public_base_url to send it here]\n" if path and not media else "")
                  + '\nYES = schedule · SKIP · REDO · "image: <change>" · "title: <new>" · or type edit instructions.', media)
        self.db.update(item["id"], state="review_pending")

    # ---------- scheduling ----------
    def _finish(self, item):
        flagged = compliance.flags(item["body"])
        if flagged:
            return self._say(item, f"⚠️ Can't schedule: flagged wording ({', '.join(flagged)}). Edit the text first.")
        slot = self.next_slot()
        post = {"title": item["title"], "text": compliance.with_disclaimer(item["body"], self.cfg.disclaimer),
                "link": item["url"], "image_path": item["image_path"],
                "image_url": self.public_url(item["image_path"]) if item["image_path"] and self.cfg.public_base_url else None,
                "profile_ids": self.cfg.vista_profile_ids, "schedule_time": slot.strftime("%Y-%m-%d %H:%M")}
        try:
            ref = self.vista.schedule(post)
        except Exception as e:
            return self._fail(item, e)
        self.db.update(item["id"], state="scheduled", scheduled_for=post["schedule_time"], vista_ref=ref)
        self._say(item, f"✅ #{item['id']} scheduled in Vista Social for {post['schedule_time']} ({self.cfg.timezone}).")
        self.advance()

    def next_slot(self):
        tz = ZoneInfo(self.cfg.timezone)
        now, taken = datetime.now(tz), self.db.scheduled_times()
        for day in range(0, 60):
            for t in sorted(self.cfg.post_times):
                h, m = map(int, t.split(":"))
                cand = (now + timedelta(days=day)).replace(hour=h, minute=m, second=0, microsecond=0)
                if cand > now + timedelta(minutes=15) and cand.strftime("%Y-%m-%d %H:%M") not in taken:
                    return cand
        raise RuntimeError("no free posting slot")

    def _say(self, item, text, media=None):
        if item:
            self.db.log(item["id"], "out", text)
        self.wa.send(text, media)

    def _fail(self, item, err):
        print(f"[pipeline] item {item['id']} failed: {err}")
        self.db.update(item["id"], state="failed", error=str(err)[:500])
        self._say(item, f"⚠️ #{item['id']} failed: {str(err)[:200]}")
        self.advance()
