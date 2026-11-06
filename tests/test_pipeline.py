import tempfile
import unittest
from pathlib import Path

from autopost import compliance, db, pipeline, sources, whatsapp
from autopost.config import Config

RSS = """<rss><channel>
<item><title>Fed holds rates</title><link>https://ex.com/a</link><description>&lt;p&gt;Rates steady&lt;/p&gt;</description><pubDate>{d}</pubDate></item>
<item><title>Old news</title><link>https://ex.com/old</link><description>x</description><pubDate>Mon, 01 Jan 2024 00:00:00 GMT</pubDate></item>
</channel></rss>"""


class FakeVista:
    def __init__(self): self.posts = []
    def schedule(self, post): self.posts.append(post); return "ref1"


def build(tmp):
    from email.utils import format_datetime
    from datetime import datetime, timezone
    cfg = Config(feeds=["f1"], llm_provider="fake", image_provider="fake", data_dir=Path(tmp),
                 vista_profile_ids=["p1"], approver="+1555")
    fetch = lambda u: RSS.format(d=format_datetime(datetime.now(timezone.utc))) if u == "f1" else "<p>" + "Long article paragraph about rates. " * 5 + "</p>"
    v, wa = FakeVista(), whatsapp.Console(cfg)
    p = pipeline.Pipeline(cfg, db.DB(Path(tmp) / "t.db"), wa=wa, vista_client=v, fetch=fetch)
    return cfg, p, v, wa


class Flow(unittest.TestCase):
    def test_batch_flow(self):
        with tempfile.TemporaryDirectory() as tmp:
            cfg, p, v, wa = build(tmp)
            self.assertEqual(p.discover(), 1)                      # old article filtered out
            self.assertIn("story ideas", wa.sent[-1][0])
            p.handle_reply("banana")                               # invalid menu reply is re-asked
            self.assertEqual(p.db.active()["state"], "proposed")
            p.handle_reply("1")
            it = p.db.active()
            self.assertEqual(it["state"], "review_pending")        # title + text + image in ONE message
            self.assertTrue(it["image_path"] and it["body"])
            p.handle_reply("make it shorter")                      # text edit keeps the image
            self.assertEqual(p.db.active()["image_path"], it["image_path"])
            p.handle_reply("title: Custom headline")
            self.assertEqual(p.db.active()["title"], "Custom headline")
            p.handle_reply("image: add a bull")
            self.assertNotEqual(p.db.active()["image_path"], it["image_path"])
            self.assertEqual(v.posts, [])                          # nothing scheduled before YES
            p.handle_reply("YES")
            self.assertEqual(len(v.posts), 1)
            post = v.posts[0]
            self.assertIn("Not investment advice", post["text"])
            self.assertEqual(post["title"], "Custom headline")
            self.assertEqual(p.db.items()[0]["state"], "scheduled")

    def test_none_skip_dedup_and_open_batch(self):
        with tempfile.TemporaryDirectory() as tmp:
            cfg, p, v, wa = build(tmp)
            p.discover()
            self.assertEqual(p.discover(), 0)                      # open batch blocks a new one
            p.handle_reply("none")
            self.assertEqual(p.db.items()[0]["state"], "rejected")
            self.assertEqual(p.discover(), 0)                      # same URL never reused
            self.assertEqual(v.posts, [])

    def test_flagged_text_cannot_be_scheduled(self):
        with tempfile.TemporaryDirectory() as tmp:
            cfg, p, v, wa = build(tmp)
            p.discover(); p.handle_reply("all")
            p.db.update(p.db.active()["id"], body="Guaranteed returns!")
            p.handle_reply("yes")
            self.assertEqual(v.posts, [])

    def test_slots_not_double_booked(self):
        with tempfile.TemporaryDirectory() as tmp:
            cfg, p, v, wa = build(tmp)
            s1 = p.next_slot()
            i = p.db.add_item(state="scheduled", scheduled_for=s1.strftime("%Y-%m-%d %H:%M"))
            self.assertNotEqual(p.next_slot(), s1)

    def test_compliance(self):
        self.assertEqual(compliance.flags("Guaranteed returns, risk-free!"), ["guaranteed", "risk-free"])
        self.assertEqual(compliance.flags("Diversify."), [])
        d = "Not advice."
        self.assertEqual(compliance.with_disclaimer("x " + d, d), "x " + d)

    def test_twilio_signature(self):
        import base64, hashlib, hmac
        params = {"Body": "1", "From": "whatsapp:+1555"}
        payload = "https://h/whatsapp" + "Body1" + "Fromwhatsapp:+1555"
        sig = base64.b64encode(hmac.new(b"tok", payload.encode(), hashlib.sha1).digest()).decode()
        self.assertTrue(whatsapp.valid_twilio_signature("tok", "https://h/whatsapp", params, sig))
        self.assertFalse(whatsapp.valid_twilio_signature("tok", "https://h/whatsapp", params, "bad"))

    def test_feed_parse_atom(self):
        atom = '<feed xmlns="http://www.w3.org/2005/Atom"><entry><title>T</title><link href="https://a/b"/><updated>2099-01-01T00:00:00Z</updated></entry></feed>'
        self.assertEqual(sources.parse_feed(atom)[0]["url"], "https://a/b")


if __name__ == "__main__":
    unittest.main()
