"""What a pinged agent does with its bundle (iteration 2, Section 9), for the v3 world.

Deterministic first: an executed action never rests on the agent's word (needs_human; a compensation goes to a human who is not the
preparer); a line of a delivered certificate is needs_human (the CFO signs the corrected certificate); a figure in a document is re-rendered
by Trackback from the calc node (reworked, no LLM). Prose goes to the model: it answers still_valid (citing the changed field it checked),
reworked (new wording; numbers come from Trackback) or needs_human. Scripted mode and offline misses use a labeled heuristic."""
from __future__ import annotations

import json
import re

from .. import config as C
from ..core import db
from ..core.llm import gateway
from .history_text import render

SYSTEM = ("You are {agent}, an AI agent on Tidewall's finance team (synthetic company). Trackback pinged you because inputs you built on changed. "
          "For each of your nodes decide: 'still_valid' (every fact and conclusion it states still holds; cite the changed field you checked), 'reworked' "
          "(give the new wording; change only what depends on the changed fields; never compute or invent numbers: use the figures given), or 'needs_human'. "
          "Return JSON only: {{\"items\": [{{\"artifact_id\": ..., \"verdict\": ..., \"reason\": ..., \"new_content\": ... or null}}]}}")
SCHEMA = {"type": "object", "properties": {"items": {"type": "array", "items": {"type": "object", "properties": {
    "artifact_id": {"type": "string"}, "verdict": {"type": "string", "enum": ["still_valid", "reworked", "needs_human"]}, "reason": {"type": "string"},
    "new_content": {"type": ["string", "null"]}}, "required": ["artifact_id", "verdict", "reason", "new_content"], "additionalProperties": False}}},
    "required": ["items"], "additionalProperties": False}
NAMES = {"close_accountant": "the Close Accountant", "reporting_analyst": "the Reporting Analyst", "covenant_comp": "Covenant and Comp"}


def _fmt(v, field: str = "", unit: str | None = None) -> str:
    if isinstance(v, str):
        return v
    if unit == "bps":
        return f"{v:g}"
    if field.startswith("leverage") or unit == "ratio":
        return f"{v:.2f}x"
    if field.startswith("membership_growth") or unit == "pct":
        return f"{v:.1f}%"
    if abs(v) >= 1e9:
        return f"${v / 1e9:.2f}B"
    if abs(v) >= 1e8 and unit == "usd":
        return f"${v / 1e6:,.0f}M"
    return f"${v:,.0f}"


FORMATS = [lambda v: f"${v / 1e9:.2f}B", lambda v: f"${v / 1e9:.1f}B", lambda v: f"${v / 1e9:.2f} billion", lambda v: f"${v / 1e9:.1f} billion",
           lambda v: f"{v:.1f}%", lambda v: f"{v:.2f}x", lambda v: f"${v:,.0f}", lambda v: f"{v:,.0f}", lambda v: f"{v:g}", lambda v: f"{v:.2f}"]


def substitute(text: str, changed: list[dict]) -> str | None:
    """Literal substitution: the sentence states the old figure of a changed field; write the new one in the same format. None if nothing matched."""
    new_text = text
    for c in changed:
        if not isinstance(c.get("old"), (int, float)) or not isinstance(c.get("new"), (int, float)):
            continue
        for fmt in FORMATS:
            old_s = fmt(c["old"])
            pat = r"(?<![\d.])" + re.escape(old_s) + r"(?![\d])"
            if re.search(pat, new_text):
                new_text = re.sub(pat, fmt(c["new"]).replace("\\", "\\\\"), new_text, count=1)
                break
    return new_text if new_text != text else None


def handle(envelope: dict) -> list[dict]:
    data = envelope["data"]
    agent = envelope["subject"].split("/")[-1]
    ts = envelope["time"]
    out, prose = [], []
    for it in data["your_nodes"]:
        aid, kind, fields = it["artifact_id"], it["kind"], it.get("fields") or {}
        changed = it.get("changed_fields") or []
        crossed = any(c.get("crossed_threshold") for c in changed)
        moved = "; ".join(f"{c.get('label') or c['field']}: {_fmt(c['old'], c['field'], c.get('unit'))} to {_fmt(c['new'], c['field'], c.get('unit'))}" for c in changed if c.get("old") is not None)
        if kind == "action" and it.get("executed"):
            out.append({"artifact_id": aid, "verdict": "needs_human", "reason_code": "executed_action",
                        "reason": f"Already executed; {moved}. I can't undo it: a compensation goes to a human who is not the preparer." + (" A stated threshold was crossed." if crossed else "")})
        elif fields.get("file", "").startswith("Compliance_Certificate"):
            out.append({"artifact_id": aid, "verdict": "needs_human", "reason_code": "delivered_document",
                        "reason": f"Line of the certificate delivered to Redwood on May 15 ({moved}). A corrected certificate needs the CFO's signature."})
        elif kind in ("number", "forecast_cell") and changed:
            new = changed[0]["new"]
            text = render(it, new)
            out.append({"artifact_id": aid, "verdict": "reworked", "reason_code": "rerendered", "model": "trackback:calc",
                        "reason": f"Figure re-rendered from Trackback's calc node ({moved}).", "new_version": {"content": text, "value_num": new}, "material_change": True})
        elif kind == "sentence" and fields.get("template") and not crossed and changed:
            vals = {c["field"]: c["new"] for c in changed}
            units = {c["field"]: c.get("unit") for c in changed}
            text = fields["template"]
            for f, v in vals.items():
                text = text.replace("{" + f + "}", _fmt(v, f, units.get(f)))
            text = re.sub(r"\{([^}]+)\}", lambda m: _fmt(_current(m.group(1)), m.group(1)), text)
            out.append({"artifact_id": aid, "verdict": "reworked", "reason_code": "rerendered", "model": "trackback:slots", "reason": f"Cited figures moved ({moved}); wording unchanged.",
                        "new_version": {"content": text}, "material_change": True})
        else:
            prose.append(it)
    if prose:
        out += _ask(agent, data, prose, ts)
    return out


def _current(metric: str):
    r = db.artifact_current(f"M:{metric}")
    return r["value_num"] if r and r["value_num"] is not None else (r["content"] if r else "")


def _heuristic(it: dict) -> dict:
    """Scripted stand-in (labeled): a stated conclusion that still holds is still_valid; one that crossed its threshold is rewritten."""
    concl = it.get("conclusions") or {}
    changed = it.get("changed_fields") or []
    aid = it["artifact_id"]
    if "sign" in concl:
        c = changed[0]
        ok = (c["new"] > 0) == (concl["sign"] == "positive")
        return {"artifact_id": aid, "verdict": "still_valid" if ok else "reworked", "reason": f"{c.get('label')} moved from {_fmt(c['old'], c['field'])} to {_fmt(c['new'], c['field'])}; "
                + ("still positive, and the sentence states no figure." if ok else "the sign changed."), "new_content": None if ok else it["prior_output_excerpt"].replace("grew", "fell")}
    if "all_positive" in concl:
        neg = [c for c in changed if isinstance(c["new"], (int, float)) and c["new"] <= 0]
        return {"artifact_id": aid, "verdict": "still_valid" if not neg else "reworked",
                "reason": (f"Regional EBITDA moved for {len(changed)} regions; every region is still profitable (lowest now {_fmt(min(c['new'] for c in changed))}), and the sentence states no figure."
                           if not neg else "a region is now loss-making"), "new_content": None}
    if "covenant_status" in concl:
        lev = next((c for c in changed if c["field"].startswith("leverage")), None)
        st = next((c for c in changed if c["field"].startswith("covenant_status")), None)
        if st and st["new"] != concl["covenant_status"]:
            new = (f"We are above our 3.00x net leverage covenant at {lev['new']:.2f}x; a corrected compliance certificate and a waiver request are going to Redwood."
                   if lev else "We are above our 3.00x net leverage covenant; a corrected certificate is going to the lender.")
            return {"artifact_id": aid, "verdict": "reworked", "reason": f"Covenant status moved from {st['old']} to {st['new']}: the sentence is no longer true.", "new_content": new}
        return {"artifact_id": aid, "verdict": "still_valid", "reason": "The covenant conclusion still holds.", "new_content": None}
    sub = substitute(it.get("prior_output_excerpt") or "", changed)
    if sub:
        moved = "; ".join(f"{c.get('label') or c['field']}: {_fmt(c['old'], c['field'], c.get('unit'))} to {_fmt(c['new'], c['field'], c.get('unit'))}" for c in changed)
        return {"artifact_id": aid, "verdict": "reworked", "reason": f"The sentence states figures that moved ({moved}); rewritten with the new figures.", "new_content": sub}
    return {"artifact_id": aid, "verdict": "needs_human", "reason": "Cannot tell from the changed fields whether the wording still holds.", "new_content": None}


def _ask(agent: str, data: dict, todo: list[dict], ts: str) -> list[dict]:
    payload = {"correction": data["correction_id"], "causal_chain": data["causal_chain"][:8], "constraints": data["constraints"],
               "your_nodes": [{k: it.get(k) for k in ("artifact_id", "kind", "prior_output_excerpt", "conclusions", "changed_fields")} for it in todo]}
    messages = [{"role": "user", "content": json.dumps(payload, default=str)}]

    def scripted(_req):
        return {"content": [{"type": "text", "text": json.dumps({"items": [_heuristic(it) for it in todo]})}], "stop_reason": "end_turn", "model": "scripted:heuristic-rework"}

    resp, key, hit = gateway.complete(model=C.AGENT_MODEL, system=SYSTEM.format(agent=NAMES.get(agent, agent)), messages=messages, tools=None,
                                      params={"max_tokens": 1200, "effort": "low", "json_schema": SCHEMA}, pinned_at=ts, scripted=scripted,
                                      purpose=f"rework:{data['ping_id']}", allow_fallback=True)
    raw = "".join(b.get("text", "") for b in resp.get("content", []) if b.get("type") == "text")
    try:
        parsed = {p["artifact_id"]: p for p in json.loads(raw).get("items", [])}
    except (json.JSONDecodeError, AttributeError):
        parsed = {}
    model = resp.get("model") or C.AGENT_MODEL
    db.insert("llm_calls", {"call_id": "call_" + key[:16], "ping_id": data["ping_id"], "run_id": f"rework_{data['ping_id']}", "model": model, "purpose": "rework",
                            "input_tokens": (resp.get("usage") or {}).get("input_tokens"), "output_tokens": (resp.get("usage") or {}).get("output_tokens"), "cache_key": key,
                            "cache_hit": 1 if hit else 0, "ts": ts})
    out = []
    for it in todo:
        p = parsed.get(it["artifact_id"]) or {"verdict": "needs_human", "reason": "no answer for this node", "new_content": None}
        item = {"artifact_id": it["artifact_id"], "verdict": p["verdict"], "reason": p["reason"], "model": model, "llm_call": not hit, "reason_code": "prose_judged"}
        if p["verdict"] == "reworked":
            item["new_version"] = {"content": p.get("new_content") or it["prior_output_excerpt"]}
            item["material_change"] = True
        out.append(item)
    return out
