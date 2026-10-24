"""LLM judge for prose edges only. Structured JSON: verdict, rationale, proposed rewrite. Different model from the writer.
Deterministic precheck first: if the sentence literally contains the old displayed number, propose the substitution."""
from __future__ import annotations

import json
import re
from typing import Any

from .. import config
from . import db
from .llm import gateway

SYSTEM = ("You are an independent reviewer of finance commentary. Given a sentence, the facts it rested on (old values) and the corrected facts (new values), "
          "decide whether the sentence is now wrong. Rules: a sentence is 'invalidated' if a number it states no longer holds within its displayed precision, or a "
          "qualitative claim (direction, comparison, compliance) no longer holds. It is 'unaffected' if every stated fact still holds after the correction. "
          "Use 'needs_review' when you are not confident. Return JSON only: {\"verdict\": ..., \"rationale\": ..., \"proposed_rewrite\": ..., \"confidence\": 0..1}.")
SCHEMA = {"type": "object", "properties": {"verdict": {"type": "string", "enum": ["invalidated", "unaffected", "needs_review"]}, "rationale": {"type": "string"},
                                           "proposed_rewrite": {"type": "string"}, "confidence": {"type": "number"}}, "required": ["verdict", "rationale", "proposed_rewrite", "confidence"], "additionalProperties": False}


def _displays(v: float | None) -> list[str]:
    if v is None:
        return []
    out = set()
    a = abs(v)
    out.add(f"{v:,.0f}"); out.add(f"{a:,.0f}")
    out.add(f"{v:.1f}"); out.add(f"{a:.1f}"); out.add(f"{v:.2f}"); out.add(f"{a:.2f}")
    if a >= 1e9:
        out.add(f"{a/1e9:.1f}B"); out.add(f"{a/1e9:.2f}B")
    if a >= 1e6:
        out.add(f"{a/1e6:.1f}M"); out.add(f"{a/1e6:.2f}M")
    if a >= 1e3:
        out.add(f"{a/1e3:.0f}k"); out.add(f"{a/1e3:.1f}k")
    if a < 1000:
        out.add(f"{a:.0f}%"); out.add(f"{a:.1f}%")
    return sorted(out, key=len, reverse=True)


def precheck(text: str, changed: list[dict]) -> dict | None:
    """changed: [{id, old, new}] for numeric supporters whose value changed. Returns a substitution proposal if an old number appears literally."""
    for c in changed:
        if c.get("old") is None or c.get("new") is None:
            continue
        for d in _displays(c["old"]):
            if not d:
                continue
            m = re.search(r"(?<![\d.])" + re.escape(d) + r"(?![\d])", text)
            if m:
                nd = _fmt_like(d, c["old"], c["new"])
                if nd != d:
                    return {"found": d, "replacement": nd, "supporter": c["id"], "rewrite": text[:m.start()] + nd + text[m.end():]}
    return None


def _fmt_like(sample: str, old: float, new: float) -> str:
    a = abs(new)
    dec = len(sample.split('.')[1]) - 1 if '.' in sample else 0
    if sample.endswith("B") and a < 1e9:   # keep the sample's precision but step the unit down when the value shrinks past it
        return f"{a/1e6:.{max(0, dec - 1)}f}M"
    if sample.endswith("M") and a < 1e6:
        return f"{a/1e3:.{max(0, dec - 1)}f}k"
    if sample.endswith("B"):
        return f"{a/1e9:.{len(sample.split('.')[1]) - 1 if '.' in sample else 0}f}B"
    if sample.endswith("M"):
        return f"{a/1e6:.{len(sample.split('.')[1]) - 1 if '.' in sample else 0}f}M"
    if sample.endswith("k"):
        return f"{a/1e3:.{len(sample.split('.')[1]) - 1 if '.' in sample else 0}f}k"
    if sample.endswith("%"):
        return f"{a:.{len(sample.split('.')[1]) - 1 if '.' in sample else 0}f}%"
    if "." in sample:
        return f"{a:,.{len(sample.split('.')[1])}f}"
    return f"{a:,.0f}"


def judge(sentence: dict, old_facts: list[dict], new_facts: list[dict], pinned_at: str, scripted_hint: str | None = None) -> dict:
    """old_facts/new_facts: [{id, label, value}]. Returns {verdict, rationale, proposed_rewrite, confidence, model, cache_key}."""
    text = sentence["content"]
    user = {"sentence": text, "period": sentence.get("period"), "line_item": sentence.get("line_item"), "stated_conclusions": sentence.get("conclusions"),
            "facts_when_written": old_facts, "facts_now": new_facts}
    messages = [{"role": "user", "content": json.dumps(user, default=str)}]
    params = {"max_tokens": 600, "effort": "low", "json_schema": SCHEMA}

    def scripted(_req):
        return {"content": [{"type": "text", "text": json.dumps(_heuristic(text, old_facts, new_facts, sentence.get("conclusions")))}], "stop_reason": "end_turn",
                "model": "scripted:heuristic-judge"}

    resp, key, hit = gateway.complete(model=config.JUDGE_MODEL, system=SYSTEM, messages=messages, tools=None, params=params, pinned_at=pinned_at, scripted=scripted, purpose="judge", allow_fallback=True)
    raw = "".join(b.get("text", "") for b in resp.get("content", []) if b.get("type") == "text")
    try:
        out = json.loads(raw)
    except json.JSONDecodeError:
        out = {"verdict": "needs_review", "rationale": "judge returned non-JSON", "proposed_rewrite": text, "confidence": 0.0}
    if float(out.get("confidence", 1.0)) < 0.6:
        out["verdict"] = "needs_review"
    out["model"] = resp.get("model") or config.JUDGE_MODEL
    out["cache_key"] = key
    return out


def _heuristic(text: str, old_facts: list[dict], new_facts: list[dict], conclusions: dict | None) -> dict:
    """Scripted-mode stand-in for the judge (deterministic). Mirrors the rules in SYSTEM."""
    newmap = {f["id"]: f for f in new_facts}
    changed = [{"id": f["id"], "old": f["value"], "new": newmap[f["id"]]["value"]} for f in old_facts
               if f["id"] in newmap and f["value"] is not None and newmap[f["id"]]["value"] is not None and abs(float(f["value"]) - float(newmap[f["id"]]["value"])) > 1e-9]
    sub = precheck(text, changed)
    if sub:
        return {"verdict": "invalidated", "rationale": f"The sentence states {sub['found']} which no longer holds ({sub['supporter']} is now {sub['replacement']}).",
                "proposed_rewrite": sub["rewrite"] + " (corrected)", "confidence": 0.9}
    for c in changed:
        f = newmap[c["id"]]
        if f.get("conclusion_changed"):
            return {"verdict": "invalidated", "rationale": f"A stated conclusion about {c['id']} flipped after the correction.", "proposed_rewrite": text + " [conclusion no longer holds; rewrite needed]", "confidence": 0.85}
    if changed:
        return {"verdict": "unaffected", "rationale": "Supporting values moved but every number and conclusion the sentence states still holds at its displayed precision.",
                "proposed_rewrite": text, "confidence": 0.8}
    return {"verdict": "unaffected", "rationale": "No supporting fact the sentence cites changed.", "proposed_rewrite": text, "confidence": 0.95}
