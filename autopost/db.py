import json
import sqlite3
import time

ACTIVE = ("title_pending", "content_pending", "image_pending")

SCHEMA = """
CREATE TABLE IF NOT EXISTS items(
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  state TEXT NOT NULL,
  url TEXT, source_title TEXT, summary TEXT, article_text TEXT,
  titles TEXT, title TEXT, body TEXT, image_prompt TEXT, image_path TEXT,
  scheduled_for TEXT, vista_ref TEXT, error TEXT, revisions INTEGER DEFAULT 0,
  created REAL, updated REAL);
CREATE TABLE IF NOT EXISTS seen(url TEXT PRIMARY KEY, ts REAL);
CREATE TABLE IF NOT EXISTS log(id INTEGER PRIMARY KEY AUTOINCREMENT, item_id INTEGER, direction TEXT, text TEXT, ts REAL);
"""


class DB:
    def __init__(self, path):
        self.c = sqlite3.connect(path, check_same_thread=False, isolation_level=None)
        self.c.row_factory = sqlite3.Row
        self.c.executescript(SCHEMA)

    def add_item(self, **kw):
        now = time.time()
        kw.setdefault("state", "queued")
        cols = list(kw) + ["created", "updated"]
        vals = [json.dumps(v) if isinstance(v, (list, dict)) else v for v in kw.values()] + [now, now]
        cur = self.c.execute(f"INSERT INTO items({','.join(cols)}) VALUES({','.join('?' * len(cols))})", vals)
        return cur.lastrowid

    def update(self, item_id, **kw):
        kw["updated"] = time.time()
        sets = ",".join(f"{k}=?" for k in kw)
        vals = [json.dumps(v) if isinstance(v, (list, dict)) else v for v in kw.values()]
        self.c.execute(f"UPDATE items SET {sets} WHERE id=?", vals + [item_id])

    def item(self, item_id):
        r = self.c.execute("SELECT * FROM items WHERE id=?", (item_id,)).fetchone()
        return self._row(r)

    def active(self):
        q = ",".join("?" * len(ACTIVE))
        r = self.c.execute(f"SELECT * FROM items WHERE state IN ({q}) ORDER BY id LIMIT 1", ACTIVE).fetchone()
        return self._row(r)

    def next_queued(self):
        return self._row(self.c.execute("SELECT * FROM items WHERE state='queued' ORDER BY id LIMIT 1").fetchone())

    def items(self, state=None):
        q, a = ("SELECT * FROM items WHERE state=? ORDER BY id DESC", (state,)) if state else ("SELECT * FROM items ORDER BY id DESC", ())
        return [self._row(r) for r in self.c.execute(q, a)]

    def scheduled_times(self):
        return {r[0] for r in self.c.execute("SELECT scheduled_for FROM items WHERE state='scheduled'")}

    def seen(self, url):
        return self.c.execute("SELECT 1 FROM seen WHERE url=?", (url,)).fetchone() is not None

    def mark_seen(self, url):
        self.c.execute("INSERT OR IGNORE INTO seen VALUES(?,?)", (url, time.time()))

    def log(self, item_id, direction, text):
        self.c.execute("INSERT INTO log(item_id,direction,text,ts) VALUES(?,?,?,?)", (item_id, direction, text, time.time()))

    @staticmethod
    def _row(r):
        if r is None:
            return None
        d = dict(r)
        if d.get("titles"):
            d["titles"] = json.loads(d["titles"])
        return d
