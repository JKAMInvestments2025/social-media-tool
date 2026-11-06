"""Guardrails for an investment firm. Flags language regulators dislike and enforces a disclaimer."""
import re

RISKY = [r"guarantee[ds]?", r"risk[- ]free", r"can'?t lose", r"no risk", r"sure thing",
         r"double your money", r"get rich", r"100% (?:return|profit)", r"you should (?:buy|sell)", r"act now"]
_RX = [re.compile(p, re.I) for p in RISKY]


def flags(text):
    return sorted({m.group(0).lower() for rx in _RX for m in rx.finditer(text)})


def with_disclaimer(body, disclaimer):
    if not disclaimer or disclaimer.strip() in body:
        return body
    return f"{body.rstrip()}\n\n{disclaimer.strip()}"
