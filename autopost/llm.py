"""Claude does ranking, titles, copywriting and image prompts. 'fake' provider is for tests/offline demos."""
import json
import re

from . import http


def _json(text):
    m = re.search(r"\{.*\}|\[.*\]", text, re.S)
    return json.loads(m.group(0) if m else text)


class Anthropic:
    def __init__(self, cfg):
        self.cfg = cfg

    def complete(self, system, user, max_tokens=1500):
        r = http.request("POST", "https://api.anthropic.com/v1/messages", headers={
            "x-api-key": self.cfg.secret("ANTHROPIC_API_KEY"), "anthropic-version": "2023-06-01"},
            json_body={"model": self.cfg.anthropic_model, "max_tokens": max_tokens, "system": system,
                       "messages": [{"role": "user", "content": user}]})
        return "".join(b.get("text", "") for b in r["content"])


class Fake:
    """Deterministic stand-in so the whole flow can be exercised without API keys."""
    def complete(self, system, user, max_tokens=1500):
        if "RANK" in system:
            return json.dumps({"picks": [0]})
        if "TITLES" in system:
            return json.dumps({"titles": ["Fed holds rates: what it means for your portfolio",
                                          "Three things investors should watch this week",
                                          "Rates steady, volatility lingers"]})
        if "BODY" in system:
            return json.dumps({"body": "The Fed held rates steady. Here is what long-term investors should keep in mind: "
                                       "stay diversified, review your time horizon, and avoid reacting to headlines. #investing #markets"})
        return json.dumps({"prompt": "Clean editorial illustration of a balanced scale with coins and a rising line chart, navy and gold palette, no text"})


def make(cfg):
    return Fake() if cfg.llm_provider == "fake" else Anthropic(cfg)


def _ctx(cfg):
    return (f"You write for JKAM Investments, an investment firm. Audience: {cfg.audience}. Voice: {cfg.voice}. "
            "Never promise returns, give personalized advice, or use hype. Plain text only.")


def rank(llm, cfg, candidates, n):
    listing = "\n".join(f"{i}. {c['title']} — {c['summary'][:200]}" for i, c in enumerate(candidates))
    out = llm.complete(
        f"RANK. {_ctx(cfg)} Topics of interest: {cfg.topics}. Pick the {n} most interesting, timely, "
        "and useful articles for our audience; prefer distinct stories and credible sources. "
        'Reply ONLY JSON: {"picks":[indices]}', listing)
    picks = [i for i in _json(out).get("picks", []) if isinstance(i, int) and 0 <= i < len(candidates)]
    return list(dict.fromkeys(picks))[:n] or list(range(min(n, len(candidates))))


def titles(llm, cfg, item, feedback=""):
    out = llm.complete(
        f"TITLES. {_ctx(cfg)} Write 3 distinct, compelling post headlines (max 90 chars each). "
        'Reply ONLY JSON: {"titles":["..",".."]}',
        f"Article: {item['source_title']}\nSummary: {item['summary']}\nText: {(item['article_text'] or '')[:3000]}\n{feedback}")
    return [t.strip() for t in _json(out)["titles"]][:3]


def body(llm, cfg, item, feedback=""):
    out = llm.complete(
        f"BODY. {_ctx(cfg)} Write a social post (60-120 words) under the approved headline. Add insight, not just a summary; "
        "end with a question or takeaway and 2-3 hashtags. Do not include the headline or a disclaimer (added later). "
        'Reply ONLY JSON: {"body":".."}',
        f"Headline: {item['title']}\nArticle: {item['source_title']}\nSource URL: {item['url']}\n"
        f"Text: {(item['article_text'] or item['summary'])[:3500]}\nPrevious draft: {item.get('body') or ''}\nRevision request: {feedback}")
    return _json(out)["body"].strip()


def image_prompt(llm, cfg, item, feedback=""):
    out = llm.complete(
        "IMAGE. Write a prompt for an AI image generator: a clean, professional, on-brand editorial image for this post. "
        "No text, logos, real people, or stock tickers in the image. "
        'Reply ONLY JSON: {"prompt":".."}',
        f"Headline: {item['title']}\nPost: {item['body']}\nPrevious prompt: {item.get('image_prompt') or ''}\nRevision request: {feedback}")
    return _json(out)["prompt"].strip()
