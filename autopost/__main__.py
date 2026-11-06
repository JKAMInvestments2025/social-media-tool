import argparse

from . import config, db, pipeline, server


def main():
    ap = argparse.ArgumentParser(prog="autopost")
    ap.add_argument("--config", default="config.toml")
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("serve", help="run webhook server + daily scheduler")
    sub.add_parser("run", help="discover articles now and start the approval flow")
    r = sub.add_parser("reply", help="simulate a WhatsApp reply (console provider)")
    r.add_argument("text")
    sub.add_parser("status", help="list items")
    a = ap.parse_args()
    cfg = config.load(a.config)
    d = db.DB(cfg.data_dir / "autopost.db")
    p = pipeline.Pipeline(cfg, d)
    if a.cmd == "serve":
        server.serve(cfg, p)
    elif a.cmd == "run":
        print(f"queued {p.discover()} item(s)")
    elif a.cmd == "reply":
        p.handle_reply(a.text)
    else:
        for i in d.items():
            print(f"#{i['id']:<3} {i['state']:<16} {i['title'] or i['source_title']}  {i['scheduled_for'] or ''}")


main()
