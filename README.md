# JKAM AutoPost

Finds interesting news, drafts a social post, and walks it through **WhatsApp approvals** (title → text → image) before scheduling it in **Vista Social**. Pure Python 3.11+ standard library — nothing to install.

```
Monday: RSS + Google News → Claude ranks → 5 headlines ─▶ WhatsApp #1: reply "1 3 5"
Then, per pick: Claude writes post + image prompt → OpenAI image
   ─▶ WhatsApp #2 (one message: title + text + image): YES
   → compliance check + disclaimer → Vista Social (next free slot)
```

## Quick start (no API keys)
```bash
cp config.example.toml config.toml
# in config.toml set: llm_provider="fake", image_provider="fake"
python -m autopost run                 # starts the flow; "WhatsApp" messages print to the console
python -m autopost reply all           # pick stories from the menu
python -m autopost reply "shorter"     # edit the text (image is kept)
python -m autopost reply yes           # approve -> scheduled (dry run)
python -m autopost status
python -m unittest discover -s tests
```

## Replies
| Message | Accepted replies |
|---|---|
| Weekly menu | `1 3 5`, `all`, `none` |
| Post review | `YES` (schedule), `SKIP`, `REDO` (new text + image), `image: <change>`, `title: <new title>`, or any other text = edit instruction for the text |

## Going live
1. **Keys** → `.env` (see `.env.example`): Anthropic, OpenAI (images), Twilio (WhatsApp).
2. **WhatsApp**: set `whatsapp_provider="twilio"`, `approver` (your number), `public_base_url`; point the Twilio WhatsApp webhook to `https://<host>/whatsapp`. Requests are signature-checked and only the approver's number is accepted. Images are sent via `public_base_url/media/...`.
3. **Vista Social** (`vista_mode`):
   - `vista_webhook` — recommended: a Make/Zapier scenario receives our JSON (`title,text,link,image_url,profile_ids,schedule_time`) and runs Vista's *Schedule Post* action. No API add-on needed.
   - `vista_api` — Vista's paid API. **The JSON field names and base URL in `autopost/vista.py` are unverified**; check them against your Vista API docs first.
   - `dry_run` — logs only (default).
4. Run `python -m autopost serve` (runs on `run_days` at `run_times`; `POST /admin/run` with the admin token triggers it manually). Host anywhere that has a public HTTPS URL.

## Safeguards
One post is reviewed at a time; an unfinished batch blocks the next; articles are never reused; nothing is scheduled without your final YES; risky phrases ("guaranteed", "risk-free"…) are flagged in the draft; the disclaimer is always appended; every message is logged in SQLite (`data/autopost.db`) as an audit trail.
