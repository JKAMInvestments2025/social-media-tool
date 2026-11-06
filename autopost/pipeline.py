"""The approval state machine.

queued -> title_pending -> content_pending -> image_pending -> scheduled
Any stage can end in rejected / failed. One item is in front of the approver at a time.
Replies: a number picks a title, YES approves, SKIP drops the item, REDO regenerates,
and any other text is treated as an edit instruction (or, at the title stage, a custom title).
"""
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

    # ---------- discovery ----------
    def discover(self):
        cands = [c for c in sources.gather(self.cfg, self.fetch) if not self.db.seen(c["url"])]
        if not cands:
            print("[discover] no new candidates")
            return 0
        cands = cands[: self.cfg.max_candidates]
        n = 0
        for i in llmmod.rank(self.llm, self.cfg, cands, self.cfg.posts_per_run):
            c = cands[i]
            self.db.mark_seen(c["url"])
            text = sources.article_text(c["url"], self.fetch)
            self.db.add_item(url=c["url"], source_title=c["title"], summary=c["summary"], article_text=text)
            n += 1
        self.advance()
        return n

    # ---------- flow ----------
    def advance(self):
        """Start the next queued item if nobody is waiting on the approver."""
        if self.db.active():
            return
        item = self.db.next_queued()
        if item:
            self._propose_titles(item)

    def _propose_titles(self, item, feedback=""):
        try:
            titles = llmmod.titles(self.llm, self.cfg, item, feedback)
        except Exception as e:
            return self._fail(item, e)
        self.db.update(item["id"], titles=titles, state="title_pending")
        opts = "\n".join(f"{i}. {t}" for i, t in enumerate(titles, 1))
        self._say(item, f"📰 New post #{item['id']}\nSource: {item['source_title']}\n{item['url']}\n\n"
                        f"Pick a title:\n{opts}\n\nReply 1-{len(titles)}, send your own title, REDO for new options, or SKIP.")

    def _draft_body(self, item, feedback=""):
        try:
            body = llmmod.body(self.llm, self.cfg, item, feedback)
        except Exception as e:
            return self._fail(item, e)
        self.db.update(item["id"], body=body, state="content_pending", revisions=(item["revisions"] or 0) + 1)
        item = self.db.item(item["id"])
        warn = compliance.flags(body)
        self._say(item, f"✍️ Draft for #{item['id']}\n\n{item['title']}\n\n{body}\n"
                        + (f"\n⚠️ Compliance flags: {', '.join(warn)}\n" if warn else "")
                        + "\nYES to approve text, or reply with edit instructions. REDO / SKIP also work.")

    def _make_image(self, item, feedback=""):
        try:
            prompt = llmmod.image_prompt(self.llm, self.cfg, item, feedback)
            path = images.generate(self.cfg, prompt, item["id"], (item["revisions"] or 0))
        except Exception as e:
            return self._fail(item, e)
        self.db.update(item["id"], image_prompt=prompt, image_path=path, state="image_pending", revisions=(item["revisions"] or 0) + 1)
        item = self.db.item(item["id"])
        media = self.public_url(path) if path and self.cfg.public_base_url else None
        self._say(item, f"🖼 Image for #{item['id']}\n(prompt: {prompt[:200]})\n\nYES to schedule, or describe changes. REDO / SKIP also work."
                  + ("" if media or not path else f"\n[image saved locally: {path}; set public_base_url to send it here]"), media)

    def _finish(self, item):
        body = compliance.with_disclaimer(item["body"], self.cfg.disclaimer)
        slot = self.next_slot()
        post = {"title": item["title"], "text": body, "link": item["url"], "image_path": item["image_path"],
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

    # ---------- replies ----------
    def handle_reply(self, text):
        item = self.db.active()
        if not item:
            self.wa.send("Nothing is waiting for approval right now.")
            return
        self.db.log(item["id"], "in", text)
        t, low = text.strip(), text.strip().lower()
        if low in NO:
            self.db.update(item["id"], state="rejected")
            self._say(item, f"🗑 #{item['id']} skipped.")
            return self.advance()
        st = item["state"]
        if st == "title_pending":
            if low in REDO:
                return self._propose_titles(item, "The previous options were rejected; offer different angles.")
            if low.isdigit() and 1 <= int(low) <= len(item["titles"]):
                title = item["titles"][int(low) - 1]
            elif len(t) <= 150:
                title = t
            else:
                return self._say(item, "That's too long for a title (150 chars max). Pick a number or send a shorter one.")
            self.db.update(item["id"], title=title)
            return self._draft_body(self.db.item(item["id"]))
        if st == "content_pending":
            if low in YES:
                return self._make_image(item)
            return self._draft_body(item, "" if low in REDO else t)
        if st == "image_pending":
            if low in YES:
                return self._finish(item)
            return self._make_image(item, "" if low in REDO else t)

    # ---------- helpers ----------
    def _say(self, item, text, media=None):
        self.db.log(item["id"], "out", text)
        self.wa.send(text, media)

    def _fail(self, item, err):
        print(f"[pipeline] item {item['id']} failed: {err}")
        self.db.update(item["id"], state="failed", error=str(err)[:500])
        self._say(item, f"⚠️ #{item['id']} failed: {str(err)[:200]}")
        self.advance()
