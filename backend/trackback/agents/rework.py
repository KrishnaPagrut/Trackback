"""What a pinged agent does: a rework run pinned at the wave's transaction time. It gets its seat, the causal chain and its suspect
nodes (prior output, fields read, changed fields with old/new/threshold crossings), and answers per node: still_valid (with a
reason citing the changed field), reworked (new content; numbers never computed by the model) or needs_human.

Deterministic escalation happens here too: executed actions always get needs_human (a compensation is always proposed), a
crossed covenant/comp threshold is needs_human, a failed tie-out turns a rework into needs_human. Everything goes through the
LLM cache so the demo replays offline; in scripted/replay-miss mode a deterministic heuristic stands in (labeled)."""
from __future__ import annotations

import json
import re

from .. import config
from ..core import db, judge as J
from ..core.conclusions import boolean_part, conclusion_state
from ..core.domain import get_domain
from ..core.llm import gateway
from .base import SEATS

SYSTEM = ("You are the agent named below. Trackback has pinged you because inputs you built on changed. For each of your nodes decide: "
          "'still_valid' (every fact and conclusion your output states still holds; cite the changed field you checked), 'reworked' (give the new content; "
          "change only wording whose truth depends on the changed fields; never compute or invent numbers, Trackback supplies them), or 'needs_human' "
          "(ambiguous, conflicting, or an executed action that must be compensated). Re-derive from the new inputs; do not paraphrase the old output. "
          "Return JSON only: {\"items\": [{\"artifact_id\": ..., \"verdict\": ..., \"reason\": ..., \"new_content\": ... or null, \"confidence\": 0..1}]}")
SCHEMA = {"type": "object", "properties": {"items": {"type": "array", "items": {"type": "object", "properties": {
    "artifact_id": {"type": "string"}, "verdict": {"type": "string", "enum": ["still_valid", "reworked", "needs_human"]}, "reason": {"type": "string"},
    "new_content": {"type": ["string", "null"]}, "confidence": {"type": "number"}}, "required": ["artifact_id", "verdict", "reason", "new_content", "confidence"], "additionalProperties": False}}},
    "required": ["items"], "additionalProperties": False}



_SIGN_FLIPS = [("headroom", "shortfall"), ("surplus", "deficit"), ("gain", "loss"), ("profit", "loss"), ("favorable", "unfavorable")]
_FLIPS = [("remain within", "are above"), ("remains within", "is above"), ("within", "above"), ("below", "above"), ("under", "over"),
          ("fell", "rose"), ("decreased", "increased"), ("declined", "grew"), ("down", "up"), ("ahead of", "behind"), ("beat", "missed")]



def _render_slots(it: dict) -> str | None:
    """The sentence's slot template rendered with the new values of its cited artifacts (None when it has no template)."""
    from ..core import db as _db
    from .prose import render_template
    art = _db.artifact_current(it["artifact_id"])
    fields = json.loads(art["fields_json"]) if art is not None and art["fields_json"] else {}
    if not fields.get("template"):
        return None
    vals = {c["field"]: c.get("new") for c in it.get("changed_fields", []) if c.get("new") is not None}
    return render_template(fields["template"], vals, fallback=art["content"] or "")

def _scripted_rewrite(it: dict, fallback: str | None) -> str | None:
    """Scripted stand-in for a reworked sentence (labeled scripted:heuristic-rework): re-render the prior version's numeric slots
    with the new values, and if a stated conclusion crossed its threshold, flip the comparative phrase. The real model writes
    the sentence itself in record mode."""
    from ..core import db as _db
    from .prose import render_template
    art = _db.artifact_current(it["artifact_id"])
    fields = json.loads(art["fields_json"]) if art is not None and art["fields_json"] else {}
    text = fallback or (art["content"] if art is not None else "") or ""
    text = text.split(" [conclusion no longer holds")[0].split(" (corrected)")[0]
    if fields.get("template"):
        text = render_template(fields["template"], {c["field"]: c.get("new") for c in it["changed_fields"] if c.get("new") is not None}, fallback=text)
    if any(c.get("crossed_threshold") for c in it["changed_fields"]):
        for a, b in _FLIPS:
            if re.search(r"\b" + re.escape(a) + r"\b", text):
                text = re.sub(r"\b" + re.escape(a) + r"\b", b, text, count=1)
                break
    # a cited figure that changed sign: the noun flips too (slots render magnitudes)
    if any(c.get("old") is not None and c.get("new") is not None and (c["old"] > 0) != (c["new"] > 0) and c["new"] != 0 for c in it["changed_fields"]):
        for a, b in _SIGN_FLIPS:
            if re.search(r"\b" + re.escape(a) + r"\b", text):
                text = re.sub(r"\b" + re.escape(a) + r"\b", b, text, count=1)
                break
    return text

def handle_ping(envelope: dict) -> list[dict]:
    data = envelope["data"]
    agent = envelope["subject"].split("/")[-1]
    ts = envelope["time"]
    items = data["your_nodes"]
    run_id = f"rework_{data['ping_id']}"
    if db.q1("SELECT 1 FROM runs WHERE run_id=?", (run_id,)) is None:
        db.insert("runs", {"run_id": run_id, "agent": agent, "task": f"rework for {data['correction_id']} wave {data['wave']}", "pinned_at": ts, "mode": gateway.mode(), "status": "running",
                           "started_at": ts, "finished_at": None, "turns": 0, "note": None, "trigger": "ping", "ping_id": data["ping_id"], "goal": None, "deliverables_json": None,
                           "model": config.AGENT_MODEL, "prompt_version": "v2"})
        db.commit()
    # deterministic escalations first: executed actions and threshold crossings never rest on the agent's word
    forced: dict[str, dict] = {}
    for it in items:
        crossed = any(c.get("crossed_threshold") for c in it["changed_fields"])
        if it["kind"] == "action" and it.get("executed"):
            forced[it["artifact_id"]] = {"artifact_id": it["artifact_id"], "verdict": "needs_human", "reason_code": "executed_action",
                                         "reason": "Executed action with a changed input: a compensation is proposed for a human who is not the preparer." + (" A stated threshold was crossed." if crossed else "")}
        elif it["kind"] == "action":
            forced[it["artifact_id"]] = {"artifact_id": it["artifact_id"], "verdict": "needs_human", "reason_code": "redraft", "reason": "Proposal not yet executed; re-draft from the corrected inputs."}
    todo = [it for it in items if it["artifact_id"] not in forced]
    answered: list[dict] = list(forced.values())
    if todo:
        # literal-number precheck (no model): a sentence that states a figure that changed is reworked by substitution
        for it in list(todo):
            if it["kind"] == "sentence":
                # every cited artifact figure re-renders through the sentence's slots first; the literal precheck then catches claim
                # figures (and anything the slots missed), so a sentence with three moved numbers comes back with all three moved
                rendered = _render_slots(it)
                base_text = rendered or it["prior_output_excerpt"]
                sub = J.precheck(base_text, [{"id": c["field"], "old": c["old"], "new": c["new"]} for c in it["changed_fields"] if c.get("old") is not None and c.get("new") is not None])
                if sub or (rendered and rendered != it["prior_output_excerpt"]):
                    text = sub["rewrite"] if sub else rendered
                    moved = [f"{c['field']}: {c['old']:g} -> {c['new']:g}" for c in it["changed_fields"] if c.get("old") is not None and c.get("new") is not None]
                    answered.append({"artifact_id": it["artifact_id"], "verdict": "reworked", "reason_code": "prose_judged", "model": "precheck:literal-substitution",
                                     "reason": (f"Stated {sub['found']}; the supporting value is now {sub['replacement']}." if sub else "Cited figures moved; re-rendered in place.") + (f" Moved: {'; '.join(moved)}" if moved else ""),
                                     "new_version": {"content": text + f" (corrected {ts[:10]}; see {data['correction_id']})"}, "material_change": True})
                    todo.remove(it)
    if todo:
        answered.extend(_ask_model(agent, data, todo, ts, run_id))
    # tie-outs on reworked outputs
    dom = get_domain()
    for a in answered:
        if a["verdict"] == "reworked" and a.get("new_version", {}).get("value_num") is not None:
            checks = dom.tie_out_checks([{"artifact_id": a["artifact_id"], "kind": "number", "value_num": a["new_version"]["value_num"], "formula": None}])
            if any(not c["ok"] for c in checks):
                a.update(verdict="needs_human", reason_code="tie_out_failed", reason=a.get("reason", "") + " Tie-out failed.")
    db.get_conn().execute("UPDATE runs SET status='done', finished_at=?, turns=1 WHERE run_id=?", (ts, run_id))
    db.commit()
    return answered


def _ask_model(agent: str, data: dict, todo: list[dict], ts: str, run_id: str) -> list[dict]:
    system = f"Agent: {agent}. Seat: {SEATS.get(agent, '')}\n\n{SYSTEM}"
    payload = {"correction": data["correction_id"], "wave": data["wave"], "causal_chain": data["causal_chain"], "constraints": data["constraints"],
               "your_nodes": [{k: it[k] for k in ("artifact_id", "kind", "prior_output_excerpt", "prior_value", "conclusions", "line_item", "period", "fields_read", "changed_fields")} for it in todo]}
    messages = [{"role": "user", "content": json.dumps(payload, default=str)}]
    params = {"max_tokens": 1500, "effort": "low", "json_schema": SCHEMA}

    def scripted(_req):
        out = []
        for it in todo:
            h = J._heuristic(it["prior_output_excerpt"], [{"id": c["field"], "value": c.get("old")} for c in it["changed_fields"]],
                             [{"id": c["field"], "value": c.get("new"), "conclusion_changed": c.get("crossed_threshold")} for c in it["changed_fields"]], it.get("conclusions"))
            v = {"invalidated": "reworked", "unaffected": "still_valid", "needs_review": "needs_human"}[h["verdict"]]
            new_content = h.get("proposed_rewrite") if v == "reworked" else None
            if v == "reworked" and it.get("kind") == "sentence":
                new_content = _scripted_rewrite(it, new_content)
            out.append({"artifact_id": it["artifact_id"], "verdict": v, "reason": h["rationale"], "new_content": new_content, "confidence": h["confidence"]})
        return {"content": [{"type": "text", "text": json.dumps({"items": out})}], "stop_reason": "end_turn", "model": "scripted:heuristic-rework"}

    resp, key, hit = gateway.complete(model=config.AGENT_MODEL, system=system, messages=messages, tools=None, params=params, pinned_at=ts, scripted=scripted, purpose=f"rework:{run_id}", allow_fallback=True)
    raw = "".join(b.get("text", "") for b in resp.get("content", []) if b.get("type") == "text")
    try:
        parsed = json.loads(raw).get("items", [])
    except json.JSONDecodeError:
        parsed = []
    model = resp.get("model") or config.AGENT_MODEL
    db.insert("llm_calls", {"call_id": "call_" + key[:16], "ping_id": data["ping_id"], "run_id": run_id, "model": model, "purpose": "rework",
                            "input_tokens": (resp.get("usage") or {}).get("input_tokens"), "output_tokens": (resp.get("usage") or {}).get("output_tokens"), "cache_key": key, "cache_hit": 1 if hit else 0, "ts": ts})
    by_id = {p.get("artifact_id"): p for p in parsed}
    out = []
    for it in todo:
        p = by_id.get(it["artifact_id"])
        if p is None:
            out.append({"artifact_id": it["artifact_id"], "verdict": "needs_human", "reason_code": "no_answer", "reason": "The agent did not answer for this node.", "model": model, "llm_call": not hit}); continue
        verdict = p.get("verdict", "needs_human")
        if float(p.get("confidence", 1.0)) < 0.6:
            verdict = "needs_human"
        item = {"artifact_id": it["artifact_id"], "verdict": verdict, "reason": p.get("reason", ""), "model": model, "llm_call": not hit, "reason_code": "prose_judged"}
        if verdict == "reworked":
            item["new_version"] = {"content": p.get("new_content") or it["prior_output_excerpt"]}
            item["material_change"] = True
        out.append(item)
    return out
