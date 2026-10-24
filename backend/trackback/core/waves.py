"""Waves: one correction event (or agent revision) -> one wave. Deterministic first (the engine recomputes every calc node),
then one ping per affected agent per wave, in dependency order. Agents answer still_valid / reworked / needs_human. Caps and
guards: MAX_WAVES=2 per root correction, MAX_HOPS=6, no self-pings, one ping per agent per wave, oscillation guard on content
hashes, MAX_LLM_CALLS_PER_EVENT. Agents can't create pings; an upstream challenge goes to a human."""
from __future__ import annotations

import json
import uuid
from collections import defaultdict
from typing import Any, Callable

from .. import config
from . import db, graph, pings as P, propagate as PR
from .domain import get_domain

Handler = Callable[[dict], list[dict]]   # envelope -> response items



def _slot_fields(artifact_id: str, version: int, content: str | None, kind: str) -> dict | None:
    """Numeric slots for a sentence written by an agent (rework or self-revision): the figures it cites from its artifact
    supporters become slots, so a later non-material move re-renders the sentence instead of pinging the agent again."""
    if kind != "sentence" or not content:
        return None
    from ..agents.prose import templatize
    vals = {}
    for e in graph.supporters_of(artifact_id, version):
        if e["supporter_kind"] == "artifact":
            cur = db.artifact_current(e["supporter_id"])
            if cur is not None and cur["value_num"] is not None:
                vals[e["supporter_id"]] = cur["value_num"]
    return {"template": templatize(content, vals)} if vals else None

def run_wave(correction_id: str, ts: str | None = None, *, handler: Handler | None = None, seeds_override: dict | None = None,
             wave_no: int | None = None, root_ping_id: str | None = None, dry_run: bool = False, extra_ids: list[str] | None = None) -> dict[str, Any]:
    """Deterministic pass (calc nodes recomputed, judgment/prose/action nodes marked suspect by field relevance), then pings."""
    corr = dict(db.q1("SELECT * FROM corrections WHERE correction_id=?", (correction_id,)))
    ts = db.norm_ts(ts or corr["tx_time"])
    P.ensure_agents()
    prior_waves = db.q1("SELECT COUNT(*) n FROM waves WHERE correction_id=?", (correction_id,))["n"]
    wave_no = wave_no or (prior_waves + 1)
    wave_id = f"wave_{correction_id}_{wave_no}"
    if wave_no > P.MAX_WAVES:
        db.log_event("wave_cap", f"{correction_id}: wave {wave_no} would exceed MAX_WAVES={P.MAX_WAVES}; escalated to a human", actor="trackback:hub", ts=ts, correction_id=correction_id)
        db.commit()
        return {"correction_id": correction_id, "wave_no": wave_no, "escalated": "wave_cap", "pings": [], "findings": []}
    if not dry_run:
        db.insert("waves", {"wave_id": wave_id, "correction_id": correction_id, "wave_no": wave_no, "started_at": ts, "finished_at": None, "status": "running",
                            "seeds_json": db.dumps(seeds_override), "stats_json": None})
        db.commit()
    # 1. deterministic pass: the iteration-1 walk, with prose/action verdicts deferred to the owning agents
    result = PR.propagate(correction_id, ts, dry_run=dry_run, defer_agents=True, seeds_override=seeds_override, extra_ids=extra_ids)
    if extra_ids:
        result["coalesced"] = [correction_id] + list(extra_ids)
    findings = {f["artifact_id"]: f for f in result["findings"]}
    suspects = [f for f in result["findings"] if f.get("verdict") == "suspect"]
    # 2. bundle suspects per owning agent, dispatched in order of each agent's lowest hop
    bundles: dict[str, list[dict]] = defaultdict(list)
    for f in sorted(suspects, key=lambda f: (f["hop"], f["artifact_id"])):
        art = db.artifact_current(f["artifact_id"])
        agent = art["agent_id"] if art is not None and art["agent_id"] else "close_accountant"
        if agent == "trackback":
            continue
        bundles[agent].append(_item(f, art, findings))
    order = sorted(bundles, key=lambda a: min(i["hop"] for i in bundles[a]))
    chain = _causal_chain(result, findings)
    out_pings: list[dict] = []
    llm_calls = 0
    for agent in order:
        items = bundles[agent]
        hop = min(i["hop"] for i in items) + 1
        env = P.build_ping(correction_id=correction_id, wave_id=wave_id, wave_no=wave_no, target_agent_id=agent, hop=hop, causal_chain=chain, items=items,
                           root_ping_id=root_ping_id, ts=ts)
        env["tbwave_id"] = wave_id
        if dry_run:
            out_pings.append({"agent": agent, "n_items": len(items), "items": [i["artifact_id"] for i in items], "hop": hop, "dry_run": True})
            for i in items:
                findings[i["artifact_id"]]["verdict"] = "needs_review"; findings[i["artifact_id"]]["reason"] = "ping_pending"
            continue
        rec = P.enqueue(env, ts)
        root_ping_id = root_ping_id or env["data"]["ping_id"]
        if rec.get("refusal"):
            out_pings.append({"agent": agent, "ping_id": rec["ping_id"], "state": "refused", "refusal": rec["refusal"], "hop": hop, "items": [{"artifact_id": i["artifact_id"], "verdict": "refused", "reason": rec["refusal"]} for i in items]})
            for i in items:
                _finalize(findings[i["artifact_id"]], "needs_review", "ping_refused:" + rec["refusal"], correction_id, ts)
            continue
        P.deliver(rec["ping_id"], ts)
        handler = handler or _default_handler
        if llm_calls >= P.MAX_LLM_CALLS_PER_EVENT:
            items_resp = [{"artifact_id": i["artifact_id"], "verdict": "needs_human", "reason": "LLM call budget for this event exhausted"} for i in items]
        else:
            items_resp = handler(env)
            llm_calls += sum(1 for r in items_resp if r.get("llm_call"))
        resp = P.respond(rec["ping_id"], items_resp, ts)
        out_pings.append({"agent": agent, "ping_id": rec["ping_id"], "state": resp["state"], "items": [{k: r.get(k) for k in ("artifact_id", "verdict", "reason")} for r in items_resp], "hop": hop})
        # 3. apply the verdicts
        for r in items_resp:
            f = findings.get(r["artifact_id"])
            if f is None:
                continue
            art = db.artifact_current(r["artifact_id"])
            verdict = r["verdict"]
            if verdict == "still_valid":
                _finalize(f, "unaffected", r.get("reason_code") or "prose_judged", correction_id, ts, rationale=r.get("reason"), model=r.get("model"))
                for it in items:
                    if it["artifact_id"] == r["artifact_id"] and it.get("consumed"):
                        graph.add_receipt(consumer_id=r["artifact_id"], consumer_version=art["version"], consumed_id=it["consumed"]["artifact_id"],
                                          consumed_version=int(it["consumed"]["current_version"]), fields_read=it.get("fields_read") or ["value"], run_id=f"ping:{rec['ping_id']}", agent_id=agent, ts=ts)
            elif verdict == "reworked":
                newv = r.get("new_version") or {}
                prior_hashes = {x["content_hash"] for x in db.q("SELECT content_hash FROM artifacts WHERE artifact_id=?", (r["artifact_id"],))}
                new_hash = graph.content_hash(newv.get("value_num"), newv.get("content"), newv.get("conclusions"))
                if new_hash in prior_hashes and new_hash != art["content_hash"]:
                    _finalize(f, "needs_review", "oscillation", correction_id, ts, rationale="rework reproduced an earlier version's content (A->B->A)", model=r.get("model"))
                    continue
                if art["kind"] == "action":
                    _finalize(f, "invalidated", r.get("reason_code") or "value_changed", correction_id, ts, rationale=r.get("reason"), model=r.get("model"), rewrite=newv.get("content"))
                    PR.compensate_action(correction_id, art, f, ts, parent_findings=_parents(art, findings))
                else:
                    db.close_tx("artifacts", "artifact_id", r["artifact_id"], ts, " AND version=?", (art["version"],))
                    v = graph.new_artifact(artifact_id=r["artifact_id"], kind=art["kind"], run_id=f"ping:{rec['ping_id']}", pinned_at=ts, period=art["period"], line_item=art["line_item"],
                                           content=newv.get("content", art["content"]), value_num=newv.get("value_num", art["value_num"]), formula=json.loads(art["formula"]) if art["formula"] else None,
                                           conclusions=newv.get("conclusions") or (json.loads(art["conclusions_json"]) if art["conclusions_json"] else None), status="valid", tx_from=ts,
                                           agent_id=agent, origin="rework", reason=r.get("reason"),
                                           fields=_slot_fields(r["artifact_id"], art["version"], newv.get("content", art["content"]), art["kind"]))
                    for e in graph.supporters_of(r["artifact_id"], art["version"]):
                        sv = e["supporter_version"]
                        if e["supporter_kind"] == "artifact":
                            cur = db.artifact_current(e["supporter_id"]); sv = str(cur["version"]) if cur else sv
                        else:
                            cv = db.claim_version_current(e["supporter_id"]); sv = cv["claim_version_id"] if cv else sv
                        graph.add_edge(consumer_id=r["artifact_id"], consumer_version=v, supporter_kind=e["supporter_kind"], supporter_id=e["supporter_id"], supporter_version=sv, dep_kind=e["dep_kind"], capture=e["capture"])
                    _finalize(f, "invalidated", r.get("reason_code") or "prose_judged", correction_id, ts, rationale=r.get("reason"), model=r.get("model"), rewrite=newv.get("content"), new_version=v)
                    f["reworked_version"] = v
            else:
                _finalize(f, "needs_review", r.get("reason_code") or "needs_human", correction_id, ts, rationale=r.get("reason"), model=r.get("model"))
                if art["kind"] == "action":
                    PR.compensate_action(correction_id, art, f, ts, parent_findings=_parents(art, findings))
                    if f.get("compensation"):
                        # an executed action with a changed input is invalid; the reason stays the numeric one, the compensation rides on the finding
                        d = f.get("detail") or {}
                        inval = [pf for pf in _parents(art, findings).values() if pf and pf.get("verdict") == "invalidated"]
                        lead = next((pf for pf in inval if pf.get("kind") in ("number", "forecast_cell")), None)
                        flipped = (d.get("old_conclusion") is not None and PR.boolean_part(d["old_conclusion"]) != PR.boolean_part(d.get("new_conclusion"))) or \
                                  (lead is not None and lead.get("reason") == "conclusion_flipped")
                        f["verdict"], f["reason"] = "invalidated", ("conclusion_flipped" if flipped else "value_changed")
                        f["compensation_proposed"] = True
    # 4. nodes downstream of a still-suspect/needs_review node wait (blocked subtree): left as 'needs_review: upstream_pending' by propagate
    if not dry_run:
        PR.write_findings(correction_id, findings, result, ts)
        db.get_conn().execute("UPDATE waves SET finished_at=?, status=?, stats_json=? WHERE wave_id=?",
                              (ts, "done", db.dumps({"pings": len(out_pings), "suspects": len(suspects), "llm_calls": llm_calls, "counts": PR._counts(findings.values())}), wave_id))
        for x in (extra_ids or []):  # coalesced corrections share the wave's verdicts; each keeps its own reach and its own materiality verdict
            solo = PR.propagate(x, ts, dry_run=True, defer_agents=True)
            reach = {sf["artifact_id"] for sf in solo["findings"]}
            sub = {k: v for k, v in findings.items() if k in reach}
            solo["_write_ctx"] = {**(solo.get("_write_ctx") or {}), "new_versions": (result.get("_write_ctx") or {}).get("new_versions", {})}
            PR.write_findings(x, sub, solo, ts)
        db.log_event("wave_done", f"{correction_id}{(' + ' + ' + '.join(extra_ids)) if extra_ids else ''} wave {wave_no}: {len(suspects)} suspect nodes, {len(out_pings)} pings ({', '.join(p['agent'] for p in out_pings) or 'none'}), {llm_calls} LLM calls",
                     actor="trackback:hub", ts=ts, correction_id=correction_id, detail={"pings": out_pings})
        db.commit()
    result["findings"] = sorted(findings.values(), key=lambda f: (f["hop"], f["artifact_id"]))
    result["counts"] = PR._counts(findings.values())
    result["pings"] = out_pings
    result["wave_no"] = wave_no
    result["wave_id"] = wave_id
    result["llm_calls"] = llm_calls
    return result


def _item(f: dict, art, findings: dict) -> dict:
    """One suspect node for the agent's bundle: prior output, fields read, changed fields with old/new/threshold crossings, the consumed version."""
    changed = []
    consumed = None
    for e in graph.supporters_of(f["artifact_id"], art["version"]):
        if e["supporter_kind"] == "artifact":
            pf = findings.get(e["supporter_id"])
            if pf and pf.get("new_value") is not None and pf.get("old_value") is not None and abs(pf["new_value"] - pf["old_value"]) > 1e-9:
                changed.append({"field": e["supporter_id"], "old": pf["old_value"], "new": pf["new_value"], "delta": pf["new_value"] - pf["old_value"], "crossed_threshold": pf.get("reason") == "conclusion_flipped"})
                cur = db.artifact_current(e["supporter_id"])
                consumed = {"artifact_id": e["supporter_id"], "version": int(e["supporter_version"]), "current_version": cur["version"] if cur else None,
                            "sha256": (db.q1("SELECT content_hash FROM artifacts WHERE artifact_id=? AND version=?", (e["supporter_id"], int(e["supporter_version"]))) or {"content_hash": None})["content_hash"]}
            elif pf and pf.get("verdict") == "invalidated" and pf.get("kind") == "sentence":
                changed.append({"field": e["supporter_id"], "old": None, "new": None, "note": "upstream sentence reworked"})
        else:
            cf = f.get("changed_claims") or {}
            if e["supporter_id"] in cf:
                c = cf[e["supporter_id"]]
                changed.append({"field": e["supporter_id"], "old": c.get("old"), "new": c.get("new"), "delta": (c["new"] - c["old"]) if c.get("old") is not None and c.get("new") is not None else None, "claim": True, "label": c.get("label")})
    fields_read = [r["fields_read_json"] for r in graph.receipts_for_consumer(f["artifact_id"], art["version"])]
    return {"artifact_id": f["artifact_id"], "node_kind": art["node_kind"] or graph.NODE_KIND.get(art["kind"], art["kind"]), "kind": art["kind"], "prior_version": art["version"],
            "prior_output_excerpt": (art["content"] or "")[:400], "prior_value": art["value_num"], "conclusions": json.loads(art["conclusions_json"]) if art["conclusions_json"] else None,
            "line_item": art["line_item"], "period": art["period"], "fields_read": sorted({x for fj in fields_read for x in json.loads(fj or "[]")}) or ["value"],
            "changed_fields": changed, "consumed": consumed, "hop": f["hop"], "executed": _executed(f["artifact_id"])}


def _parents(art, findings: dict) -> dict:
    return {e["supporter_id"]: findings.get(e["supporter_id"]) for e in graph.supporters_of(art["artifact_id"], art["version"]) if e["supporter_kind"] == "artifact"}


def _executed(artifact_id: str) -> bool:
    a = db.q1("SELECT state FROM actions WHERE artifact_id=?", (artifact_id,))
    return bool(a and a["state"] in ("executed", "approved", "compensation_proposed"))


def _causal_chain(result: dict, findings: dict) -> list[dict]:
    chain = [{"node": result["correction_id"], "kind": "correction", "summary": (db.q1("SELECT note FROM corrections WHERE correction_id=?", (result["correction_id"],)) or {"note": ""})["note"][:160]}]
    for c in result.get("changed_claims", [])[:8]:
        chain.append({"node": f"claim:{c.get('line_item')}:{c.get('entity') or ''}:{(c.get('period_start') or '')[:7]}", "old": c.get("old"), "new": c.get("new"), "from": "v_old", "to": "v_new"})
    for f in sorted(findings.values(), key=lambda f: f["hop"]):
        if f.get("verdict") == "invalidated" and f.get("kind") in ("number", "forecast_cell") and f.get("new_value") is not None:
            chain.append({"node": f"calc:{f['artifact_id']}", "old": f["old_value"], "new": f["new_value"], "crossed": f.get("reason") == "conclusion_flipped"})
    return chain[:14]


def _finalize(f: dict, verdict: str, reason: str, correction_id: str, ts: str, rationale: str | None = None, model: str | None = None, rewrite: str | None = None, new_version: int | None = None) -> None:
    f["verdict"] = verdict; f["reason"] = reason
    if rationale:
        f["judge_rationale"] = rationale
    if model:
        f["judge_model"] = model
    if rewrite:
        f["proposed_rewrite"] = rewrite
    if new_version:
        f["new_version_no"] = new_version


def _default_handler(envelope: dict) -> list[dict]:
    from ..agents import rework
    return rework.handle_ping(envelope)


# ---- agent self-revisions, retractions and upstream challenges (Sections 6.2 and 8) ----------------------------------------------
def publish_version(artifact_id: str, *, agent_id: str, content: str | None, value_num: float | None, conclusions: dict | None, reason: str, ts: str,
                    origin: str = "agent_revision", approved_by: str | None = None, retract: bool = False) -> dict:
    """An agent revises its own output (or retracts it). Propagation is identical to a source correction, seeded at this artifact;
    the revising agent is never pinged about the node it just wrote."""
    art = db.artifact_current(artifact_id)
    if art is None:
        raise KeyError(artifact_id)
    correction_id = f"REV-{artifact_id}-{uuid.uuid4().hex[:4]}"
    ts = db.norm_ts(ts)
    db.close_tx("artifacts", "artifact_id", artifact_id, ts, " AND version=?", (art["version"],))
    keep_formula = (not retract) and value_num is None and art["formula"] is not None  # an asserted value replaces the formula; a prose/action revision keeps its inputs
    v = graph.new_artifact(artifact_id=artifact_id, kind=art["kind"], run_id=f"revision:{agent_id}", pinned_at=ts, period=art["period"], line_item=art["line_item"],
                           fields=None if retract else _slot_fields(artifact_id, art["version"], content, art["kind"]),
                           content=None if retract else content, value_num=None if retract else (value_num if value_num is not None else art["value_num"]),
                           formula=json.loads(art["formula"]) if keep_formula else None,
                           conclusions=conclusions, status="retracted" if retract else "valid", tx_from=ts, agent_id=agent_id, origin="retraction" if retract else origin, reason=reason, approved_by=approved_by)
    if not retract:
        for e in graph.supporters_of(artifact_id, art["version"]):
            graph.add_edge(consumer_id=artifact_id, consumer_version=v, supporter_kind=e["supporter_kind"], supporter_id=e["supporter_id"], supporter_version=e["supporter_version"], dep_kind=e["dep_kind"], capture=e["capture"])
    db.insert("corrections", {"correction_id": correction_id, "source_id": f"artifact:{artifact_id}", "old_version": str(art["version"]), "new_version": str(v), "kind": "fact_update",
                              "knowable_at": ts, "materiality_verdict": None, "booking_period": None, "tx_time": ts, "note": f"{'retraction' if retract else 'agent revision'} by {agent_id}: {reason}"})
    db.log_event("agent_revision" if not retract else "retraction", f"{agent_id} {'retracted' if retract else 'revised'} {artifact_id} (v{art['version']} -> v{v}): {reason}", actor=agent_id, ts=ts, correction_id=correction_id)
    db.commit()
    res = run_wave(correction_id, ts, seeds_override={"artifact": artifact_id, "old_version": art["version"], "new_version": v, "old_value": art["value_num"], "new_value": None if retract else value_num, "retracted": retract, "exclude_agent": agent_id})
    res["new_version"] = v
    return res


def file_challenge(from_agent_id: str, target_artifact_id: str, reason: str, ts: str) -> dict:
    """A downstream agent disputes an upstream output. It never becomes a ping: a human decides, and only an approved challenge opens a wave."""
    cid = "chal_" + uuid.uuid4().hex[:8]
    db.insert("upstream_challenges", {"challenge_id": cid, "from_agent_id": from_agent_id, "target_artifact_id": target_artifact_id, "reason": reason, "state": "open",
                                      "created_at": db.norm_ts(ts), "decided_by": None, "decided_at": None, "correction_id": None})
    db.insert("outbox", {"kind": "challenge.filed", "payload_json": db.dumps({"challenge_id": cid, "from": from_agent_id, "target": target_artifact_id, "reason": reason}), "created_at": db.norm_ts(ts), "sent_at": None, "ping_id": None})
    db.log_event("upstream_challenge", f"{from_agent_id} challenges {target_artifact_id}: {reason} (to the Controller; no wave started)", actor=from_agent_id, ts=ts)
    db.commit()
    return {"challenge_id": cid, "state": "open"}
