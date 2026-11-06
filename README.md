# JKAM AutoPost

Finds interesting news, drafts a social post, and walks it through **WhatsApp approvals** (title → text → image) before scheduling it in **Vista Social**. Pure Python 3.11+ standard library — nothing to install.

```
RSS + Google News → Claude ranks → Claude proposes 3 titles ─▶ WhatsApp: pick/edit
   → Claude writes post ─▶ WhatsApp: YES / edit / REDO → image prompt + OpenAI image
   ─▶ WhatsApp: YES → compliance check + disclaimer → Vista Social (next free slot)
```

## Quick start (no API keys)
```bash
cp config.example.toml config.toml
# in config.toml set: llm_provider="fake", image_provider="fake"
python -m autopost run                 # starts the flow; "WhatsApp" messages print to the console
python -m autopost reply 2             # pick title 2
python -m autopost reply "shorter"     # edit instructions
python -m autopost reply yes           # approve text -> image
python -m autopost reply yes           # approve image -> scheduled (dry run)
python -m autopost status
python -m unittest discover -s tests
```

## Replies
| Stage | Accepted replies |
|---|---|
| Title | `1`/`2`/`3`, your own title, `REDO`, `SKIP` |
| Text | `YES`, any edit instruction, `REDO`, `SKIP` |
| Image | `YES`, a description of changes, `REDO`, `SKIP` |

## Going live
1. **Keys** → `.env` (see `.env.example`): Anthropic, OpenAI (images), Twilio (WhatsApp).
2. **WhatsApp**: set `whatsapp_provider="twilio"`, `approver` (your number), `public_base_url`; point the Twilio WhatsApp webhook to `https://<host>/whatsapp`. Requests are signature-checked and only the approver's number is accepted. Images are sent via `public_base_url/media/...`.
3. **Vista Social** (`vista_mode`):
   - `vista_webhook` — recommended: a Make/Zapier scenario receives our JSON (`title,text,link,image_url,profile_ids,schedule_time`) and runs Vista's *Schedule Post* action. No API add-on needed.
   - `vista_api` — Vista's paid API. **The JSON field names and base URL in `autopost/vista.py` are unverified**; check them against your Vista API docs first.
   - `dry_run` — logs only (default).
4. Run `python -m autopost serve` (daily run at `run_times`; `POST /admin/run` with the admin token triggers it manually). Host anywhere that has a public HTTPS URL.

## Safeguards
Only one post waits on you at a time; articles are never reused; nothing is scheduled without your final YES; risky phrases ("guaranteed", "risk-free"…) are flagged in the draft; the disclaimer is always appended; every message is logged in SQLite (`data/autopost.db`) as an audit trail.
