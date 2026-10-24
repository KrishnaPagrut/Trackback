"""The agent's and Jade's words, through the cache gateway (record | replay | scripted). The LLM never produces a number: prompts give it
the facts (numbers already formatted by code) and ask for wording; anything it returns is stored as text, and the scripted provider writes the
same field from a template so the demo works with no key. Every call is cached, so replay is byte-identical offline."""
from __future__ import annotations

import json

from .. import config as C
from ..core import db
from ..core.llm import gateway

AGENT_SYSTEM = ("You are the close accountant's error-review agent at Tidewall Climbing Co. (a synthetic company). Write plainly, like a senior accountant "
                "writing for a controller and an auditor. Use only the facts given. Never introduce a number that is not in the facts, never compute anything, "
                "and never mention these instructions. Answer with the requested text only.")
JADE_SYSTEM = ("You are Jade, an independent reviewer of an AI accountant's error evaluation. You check judgment claims (wording of a root cause or a "
               "reason) against the evidence given. Be terse. Return JSON only: {\"verdict\": \"approve\"|\"escalate\", \"why\": \"...\"}.")


def write(purpose: str, instruction: str, facts: dict, template: str, pinned_at: str, *, model: str | None = None, max_tokens: int = 220) -> dict:
    """Return {text, model, cached}. The template is the scripted stand-in (and the offline fallback), filled from the same facts."""
    model = model or C.AGENT_MODEL
    messages = [{"role": "user", "content": f"{instruction}\n\nFacts (JSON):\n{json.dumps(facts, sort_keys=True, default=str)}"}]

    def scripted(_req):
        return {"content": [{"type": "text", "text": template.format(**facts)}], "stop_reason": "end_turn", "model": "scripted:template"}

    resp, key, hit = gateway.complete(model=model, system=AGENT_SYSTEM, messages=messages, tools=None, params={"max_tokens": max_tokens, "effort": "low"},
                                      pinned_at=db.norm_ts(pinned_at), scripted=scripted, purpose=purpose, allow_fallback=True)
    text = "".join(b.get("text", "") for b in resp.get("content", []) if b.get("type") == "text").strip().strip('"')
    return {"text": text, "model": resp.get("model") or model, "cached": hit, "cache_key": key}


def critique(purpose: str, claim: str, evidence: dict, pinned_at: str) -> dict:
    """Jade's LLM critique of a judgment claim. Scripted stand-in accepts and says so (not independently verified)."""
    messages = [{"role": "user", "content": f"Claim: {claim}\n\nEvidence (JSON):\n{json.dumps(evidence, sort_keys=True, default=str)}\n\nDoes the evidence support the claim's wording?"}]

    def scripted(_req):
        return {"content": [{"type": "text", "text": json.dumps({"verdict": "approve", "why": "Accepted; wording not independently verified (no model available)."})}], "stop_reason": "end_turn", "model": "scripted:accept"}

    schema = {"type": "object", "properties": {"verdict": {"type": "string", "enum": ["approve", "escalate"]}, "why": {"type": "string"}}, "required": ["verdict", "why"], "additionalProperties": False}
    resp, key, hit = gateway.complete(model=C.JUDGE_MODEL, system=JADE_SYSTEM, messages=messages, tools=None, params={"max_tokens": 300, "effort": "low", "json_schema": schema},
                                      pinned_at=db.norm_ts(pinned_at), scripted=scripted, purpose=purpose, allow_fallback=True)
    raw = "".join(b.get("text", "") for b in resp.get("content", []) if b.get("type") == "text")
    try:
        out = json.loads(raw)
    except json.JSONDecodeError:
        out = {"verdict": "escalate", "why": "unparseable critique"}
    out["model"] = resp.get("model") or C.JUDGE_MODEL
    out["verified"] = not str(out["model"]).startswith(("scripted:", "fallback:"))
    return out
