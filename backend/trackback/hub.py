"""The trackback hub in v3 (iteration 2, Sections 6 to 9): after the ripple, one ping per owning agent per wave, one notice per person.

- Agents get a CloudEvents ping (HMAC-signed, refusal-checked against the consumption receipts the hub recorded at read time) bundling
  every node they own that the ripple invalidated or marked suspect: traced lines they wrote, their own work products, their executed
  actions. They answer still_valid (with a reason), reworked (new version) or needs_human.
- People get an inbox notice for the lines they typed (routed to an out-of-office delegate when needed). Notices are not pings: only agents
  answer through the protocol.
- Skipped: agent work whose inputs did not move materially gets no ping and shows "skipped, no material change".
- Caps from v2 apply: one ping per agent per wave, MAX_WAVES, MAX_HOPS, no self-pings, an LLM-call budget per event.
Agent self-revisions (S1), coalesced corrections (S2) and upstream challenges (S3) go through the same doors.
"""
from __future__ import annotations

import json
from collections import defaultdict
from datetime import date

from . import config as C
from .agent import rework
from .core import db, graph as G, pings as P

AGENTS = ("close_accountant", "covenant_comp", "reporting_analyst")
ORDER = {"close_accountant": 1, "covenant_comp": 2, "reporting_analyst": 3}


def delegate_for(person: str, ts: str) -> tuple[str, str | None]:
    p = C.PEOPLE_V3.get(person, {})
    ooo = p.get("ooo")
    if ooo and ooo[0] <= ts[:10] <= ooo[1]:
        return p["delegate"], f"{p['name']} is out of office {date.fromisoformat(ooo[0]):%b %d} to {date.fromisoformat(ooo[1]):%b %d}; routed to {C.PEOPLE_V3[p['delegate']]['name']}"
    return person, None


def _receipt(aid: str, version: int, metric: str) -> dict | None:
    r = db.q1("SELECT consumed_artifact_id, consumed_version, consumed_sha256 FROM consumption_receipts WHERE consumer_artifact_id=? AND consumer_version=? AND consumed_artifact_id=?",
              (aid, version, f"M:{metric}"))
    return {"artifact_id": r["consumed_artifact_id"], "version": r["consumed_version"], "sha256": r["consumed_sha256"]} if r else None


def _node(aid: str, changed: list[dict], hop: int) -> dict | None:
    art = db.artifact_current(aid)
    if art is None:
        return None
    fields = json.loads(art["fields_json"]) if art["fields_json"] else {}
    consumed = next((x for x in (_receipt(aid, art["version"], c["field"]) for c in changed) if x), None)
    executed = bool(db.q1("SELECT 1 FROM actions WHERE artifact_id=? AND state IN ('executed','compensation_proposed')", (aid,)))
    reads = [json.loads(r["fields_read_json"] or "[]") for r in G.receipts_for_consumer(aid, art["version"])]
    return {"artifact_id": aid, "node_kind": art["node_kind"], "kind": art["kind"], "prior_version": art["version"], "prior_output_excerpt": (art["content"] or "")[:400],
            "prior_value": art["value_num"], "conclusions": json.loads(art["conclusions_json"]) if art["conclusions_json"] else None, "line_item": art["line_item"],
            "period": art["period"], "fields_read": sorted({x for r in reads for x in r}) or ["value"], "changed_fields": changed, "consumed": consumed, "hop": hop,
            "executed": executed, "fields": fields}


def _changed_for(entry: dict, metrics: dict | None = None) -> list[dict]:
    """The fields that moved for one node: what the ripple said about it, plus every other calc node its receipts show it read that moved."""
    metrics = metrics or {}
    out = list(entry.get("changed_fields") or [])
    m = entry.get("metric")
    if not out and m and entry.get("old") is not None:
        crossed = entry.get("reason") == "conclusion_flipped"
        out = [{"field": m, "label": (metrics.get(m) or {}).get("label", m), "unit": (metrics.get(m) or {}).get("unit"), "old": entry["old"], "new": entry["new"],
                "delta": None if isinstance(entry["old"], str) else entry["new"] - entry["old"], "crossed_threshold": crossed}]
    art = db.artifact_current(entry["item_id"])
    if art is not None:
        have = {c["field"] for c in out}
        for r in G.receipts_for_consumer(entry["item_id"], art["version"]):
            mid = r["consumed_artifact_id"][2:] if r["consumed_artifact_id"].startswith("M:") else None
            mm = metrics.get(mid) if mid else None
            if mm and mm["changed"] and mid not in have:
                out.append({"field": mid, "label": mm["label"], "unit": mm.get("unit"), "old": mm["old"], "new": mm["new"], "delta": None if isinstance(mm["old"], str) else mm["new"] - mm["old"],
                            "crossed_threshold": mm["conclusion_old"] != mm["conclusion_new"]})
    for c in out:
        if c.get("label") in (None, c["field"]) and c["field"] in metrics:
            c["label"] = metrics[c["field"]]["label"]
        if not c.get("unit") and c["field"] in metrics:
            c["unit"] = metrics[c["field"]].get("unit")
    return out


def is_agent(owner: str | None) -> bool:
    if not owner or owner in C.PEOPLE_V3:
        return False
    r = db.q1("SELECT ping_endpoint FROM agents WHERE agent_id=?", (owner,))
    return bool(r and r["ping_endpoint"])


def bundles(ripple: dict) -> tuple[dict[str, list[dict]], dict[str, list[dict]], list[dict]]:
    """(agent -> nodes, person -> lines, skipped agent nodes) from one ripple."""
    agents: dict[str, list[dict]] = defaultdict(list)
    people: dict[str, list[dict]] = defaultdict(list)
    for iid, v in ripple["items"].items():
        if v["verdict"] != "invalidated":
            continue
        owner = v.get("owner") or "unknown"
        if not is_agent(owner):
            people[owner].append({"item_id": iid, **v})
        elif v.get("link_status") != "derived":
            agents[owner].append({"item_id": iid, **v})
    for nid, v in ripple.get("agent_nodes", {}).items():
        if v["verdict"] == "suspect":
            agents[v["owner"]].append({"item_id": nid, **v})
    for aid, v in ripple["actions"].items():
        if v["verdict"] == "invalidated" and is_agent(v.get("owner")):
            agents[v["owner"]].append({"item_id": aid, **v})
    skipped = [{"node_id": n, **v} for n, v in ripple.get("agent_nodes", {}).items() if v.get("skipped")]
    return dict(agents), dict(people), skipped


def causal_chain(ripple: dict) -> list[dict]:
    c = ripple["correction"]
    chain = [{"node": c["id"], "kind": "correction", "summary": c.get("title", "")[:160]}]
    for mid, m in sorted(ripple["metrics"].items(), key=lambda kv: kv[1]["depth"]):
        if m["changed"] and (m["depth"] >= 1 or mid.startswith(("ttm_", "revenue@", "membership"))):
            chain.append({"node": f"calc:{mid}", "old": m["old"], "new": m["new"], "crossed": m["conclusion_old"] != m["conclusion_new"]})
    return chain[:14]


def dispatch(ripple: dict, ts: str, wave_no: int = 1, handler=None, people_notices: bool = True) -> dict:
    """Send the wave: one ping per agent (dependency order), one notice per person. Returns the wave summary."""
    corr = ripple["correction"]["id"]
    ts = db.norm_ts(ts)
    agents, people, skipped = bundles(ripple)
    wave_id = f"wave_{corr}_{wave_no}"
    if wave_no > P.MAX_WAVES:
        db.log_event("wave_cap", f"{corr}: wave {wave_no} would exceed MAX_WAVES={P.MAX_WAVES}; escalated to a human", actor="trackback:hub", ts=ts, correction_id=corr)
        return {"wave_id": wave_id, "escalated": "wave_cap", "pings": [], "notices": [], "skipped": skipped}
    if db.q1("SELECT 1 FROM waves WHERE wave_id=?", (wave_id,)) is None:
        db.insert("waves", {"wave_id": wave_id, "correction_id": corr, "wave_no": wave_no, "started_at": ts, "finished_at": None, "status": "running", "seeds_json": json.dumps(ripple.get("seeds", [])), "stats_json": None})
    chain = causal_chain(ripple)
    out_pings, llm_calls = [], 0
    root = None
    for agent in sorted(agents, key=lambda a: ORDER.get(a, 9)):
        nodes = [n for n in (_node(e["item_id"], _changed_for(e, ripple["metrics"]), ORDER.get(agent, 1)) for e in agents[agent]) if n]
        if not nodes:
            continue
        env = P.build_ping(correction_id=corr, wave_id=wave_id, wave_no=wave_no, target_agent_id=agent, hop=ORDER.get(agent, 1), causal_chain=chain, items=nodes, root_ping_id=root, ts=ts)
        env["tbwave_id"] = wave_id
        rec = P.enqueue(env, ts)
        root = root or env["data"]["ping_id"]
        if rec.get("refusal"):
            out_pings.append({"agent": agent, "ping_id": rec["ping_id"], "state": "refused", "refusal": rec["refusal"], "items": []})
            continue
        if rec.get("duplicate"):
            out_pings.append({"agent": agent, "ping_id": rec["ping_id"], "state": rec["state"], "duplicate": True, "items": []})
            continue
        P.deliver(rec["ping_id"], ts)
        if llm_calls >= P.MAX_LLM_CALLS_PER_EVENT:
            resp = [{"artifact_id": n["artifact_id"], "verdict": "needs_human", "reason": "LLM call budget for this event exhausted"} for n in nodes]
        else:
            resp = (handler or rework.handle)(env)
            llm_calls += sum(1 for r in resp if r.get("llm_call"))
        st = P.respond(rec["ping_id"], resp, ts)
        for r in resp:
            if r["verdict"] == "reworked" and r.get("new_version"):
                art = db.artifact_current(r["artifact_id"])
                db.close_tx("artifacts", "artifact_id", r["artifact_id"], ts, " AND version=?", (art["version"],))
                v = G.new_artifact(artifact_id=r["artifact_id"], kind=art["kind"], run_id=f"ping:{rec['ping_id']}", pinned_at=ts, period=art["period"], line_item=art["line_item"],
                                   content=r["new_version"].get("content", art["content"]), value_num=r["new_version"].get("value_num", art["value_num"]), formula=None,
                                   conclusions=json.loads(art["conclusions_json"]) if art["conclusions_json"] else None, agent_id=agent, origin="rework", reason=r.get("reason"),
                                   fields=json.loads(art["fields_json"]) if art["fields_json"] else None, world=art["world"])
                _carry_edges(r["artifact_id"], art["version"], v)
                r["new_version_no"] = v
        out_pings.append({"agent": agent, "ping_id": rec["ping_id"], "state": st["state"], "hop": ORDER.get(agent, 1),
                          "items": [{k: r.get(k) for k in ("artifact_id", "verdict", "reason", "model", "new_version", "reason_code")} for r in resp]})
    notices = []
    if people_notices:
        for person, lines in people.items():
            to, why = delegate_for(person, ts)
            notices.append(_notice(corr, person, to, why, lines, ts))
    stats = {"pings": len(out_pings), "agents_pinged": [p["agent"] for p in out_pings], "notices": len(notices), "skipped": len(skipped), "llm_calls": llm_calls}
    db.get_conn().execute("UPDATE waves SET finished_at=?, status='done', stats_json=? WHERE wave_id=?", (ts, json.dumps(stats), wave_id))
    db.log_event("wave_done", f"{corr} wave {wave_no}: {len(out_pings)} pings ({', '.join(stats['agents_pinged']) or 'none'}), {len(notices)} notices, {len(skipped)} skipped, {llm_calls} LLM calls",
                 actor="trackback:hub", ts=ts, correction_id=corr, detail={"pings": out_pings, "notices": notices})
    db.commit()
    return {"wave_id": wave_id, "pings": out_pings, "notices": notices, "skipped": skipped, "stats": stats}


def _carry_edges(artifact_id: str, old_version: int, new_version: int) -> None:
    """A reworked version rests on the same inputs, at their current versions (so the next ripple reaches it, and its receipts are fresh)."""
    for e in G.supporters_of(artifact_id, old_version):
        sv = e["supporter_version"]
        if e["supporter_kind"] == "artifact":
            cur = db.artifact_current(e["supporter_id"])
            sv = str(cur["version"]) if cur else sv
        G.add_edge(consumer_id=artifact_id, consumer_version=new_version, supporter_kind=e["supporter_kind"], supporter_id=e["supporter_id"], supporter_version=sv,
                   dep_kind=e["dep_kind"], capture=e["capture"])


def _notice(corr: str, person: str, to: str, why: str | None, lines: list[dict], ts: str) -> dict:
    aid = f"NOTICE-{corr}-{person}"
    files = sorted({l.get("file") for l in lines if l.get("file")})
    summary = f"{len(lines)} line(s) you made rest on numbers that changed: " + "; ".join(
        f"{l.get('locator')} {l.get('label', '')[:40]}: {_v(l.get('old'))} to {_v(l.get('new'))}" for l in lines[:6]) + (" ..." if len(lines) > 6 else "")
    if db.q1("SELECT 1 FROM actions WHERE action_id=?", (aid,)) is None:
        G.new_action(action_id=aid, artifact_id=aid, kind="notice", params={"lines": [l["item_id"] for l in lines], "files": files, "owner": person, "routed_because": why},
                     run_id=f"wave:{corr}", proposer="trackback", approver_role=C.PEOPLE_V3.get(to, {}).get("role", to), created_at=ts)
        db.get_conn().execute("UPDATE actions SET world='tidewall', assignee=?, exception_id=?, summary=? WHERE action_id=?", (to, corr, summary, aid))
        if why:
            db.log_event("reassigned", why, actor="trackback:hub", ts=ts, correction_id=corr)
    return {"notice_id": aid, "owner": person, "to": to, "routed_because": why, "files": files, "lines": [l["item_id"] for l in lines], "summary": summary}


def _v(x) -> str:
    if isinstance(x, str) or x is None:
        return str(x)
    return f"{x:.4f}" if abs(x) < 10 else f"{x:,.2f}"


# ---------------------------------------------------------------------------------------------- S1: an agent revises its own work
def revise(artifact_id: str, *, agent: str, new_value: float, reason: str, ts: str, handler=None) -> dict:
    """An agent revises its own output. Consumers (by receipt) are bundled per owner; the reviser is never pinged about its own node."""
    from .core import pings as PP
    art = db.artifact_current(artifact_id)
    ts = db.norm_ts(ts)
    db.close_tx("artifacts", "artifact_id", artifact_id, ts, " AND version=?", (art["version"],))
    v = G.new_artifact(artifact_id=artifact_id, kind=art["kind"], run_id=f"revision:{agent}", pinned_at=ts, period=art["period"], line_item=art["line_item"],
                       content=f"{(art['content'] or '').split(':')[0]}: ${new_value:,.0f}", value_num=new_value, formula=None, conclusions=None, agent_id=agent,
                       origin="agent_revision", reason=reason, node_kind=art["node_kind"])
    corr = f"S1-{artifact_id}"
    consumers = [r for r in db.q("SELECT * FROM consumption_receipts WHERE consumed_artifact_id=? AND consumed_version=?", (artifact_id, art["version"]))]
    by_agent: dict[str, list[dict]] = defaultdict(list)
    for r in consumers:
        cur = db.artifact_current(r["consumer_artifact_id"])
        if cur is None or cur["version"] != r["consumer_version"] or cur["agent_id"] == agent:
            continue
        by_agent[cur["agent_id"]].append({"artifact_id": cur["artifact_id"], "changed": [{"field": artifact_id, "label": "June utilities accrual", "old": art["value_num"], "new": new_value,
                                                                                       "delta": new_value - art["value_num"], "crossed_threshold": False}]})
    pings = []
    for target, nodes in by_agent.items():
        items = []
        for n in nodes:
            nd = _node(n["artifact_id"], n["changed"], 1)
            rc = db.q1("SELECT consumed_version, consumed_sha256 FROM consumption_receipts WHERE consumer_artifact_id=? AND consumer_version=? AND consumed_artifact_id=?",
                       (n["artifact_id"], nd["prior_version"], artifact_id))
            nd["consumed"] = {"artifact_id": artifact_id, "version": rc["consumed_version"], "sha256": rc["consumed_sha256"]}
            items.append(nd)
        env = PP.build_ping(correction_id=corr, wave_id=f"wave_{corr}_1", wave_no=1, target_agent_id=target, hop=1,
                            causal_chain=[{"node": corr, "kind": "agent_revision", "summary": reason}, {"node": artifact_id, "from": f"v{art['version']}", "to": f"v{v}", "old": art["value_num"], "new": new_value}],
                            items=items, root_ping_id=None, ts=ts)
        env["tbwave_id"] = f"wave_{corr}_1"
        rec = PP.enqueue(env, ts)
        PP.deliver(rec["ping_id"], ts)
        resp = (handler or rework.handle)(env)
        PP.respond(rec["ping_id"], resp, ts)
        for r in resp:
            if r["verdict"] == "reworked" and r.get("new_version"):
                cur = db.artifact_current(r["artifact_id"])
                db.close_tx("artifacts", "artifact_id", r["artifact_id"], ts, " AND version=?", (cur["version"],))
                nv = G.new_artifact(artifact_id=r["artifact_id"], kind=cur["kind"], run_id=f"ping:{rec['ping_id']}", pinned_at=ts, period=cur["period"], line_item=cur["line_item"],
                                    content=r["new_version"]["content"], value_num=r["new_version"].get("value_num"), formula=None, conclusions=None, agent_id=target, origin="rework", reason=r["reason"])
                G.add_edge(consumer_id=r["artifact_id"], consumer_version=nv, supporter_kind="artifact", supporter_id=artifact_id, supporter_version=str(v), dep_kind="numeric", capture="tool_log")
        pings.append({"agent": target, "ping_id": rec["ping_id"], "items": [{k: r.get(k) for k in ("artifact_id", "verdict", "reason")} for r in resp]})
    not_pinged = []
    for other in AGENTS:
        if other != agent and other not in by_agent:
            q1 = db.q("SELECT artifact_id, period FROM artifacts WHERE agent_id=? AND tx_to=? AND (period LIKE '2026Q1%' OR period='2026Q1')", (other, C.TX_CURRENT))
            not_pinged.append({"agent": other, "reason": "different_period" if q1 else "not_a_dependent",
                               "why": f"none of its work consumed {artifact_id}; its Q1 work rests on Q1 figures, and this revision is for {art['period']}" if q1 else f"none of its work consumed {artifact_id}"})
    db.log_event("agent_revision", f"{agent} revised {artifact_id} (v{art['version']} to v{v}): {reason}; pinged {', '.join(p['agent'] for p in pings) or 'nobody'}",
                 actor=agent, ts=ts, correction_id=corr, detail={"pings": pings, "not_pinged": not_pinged})
    db.commit()
    return {"correction_id": corr, "artifact_id": artifact_id, "old": art["value_num"], "new": new_value, "version": v, "pings": pings, "not_pinged": not_pinged}


# ---------------------------------------------------------------------------------------------- S3: a downstream agent disputes upstream work
def challenge(from_agent: str, target_artifact_id: str, reason: str, ts: str) -> dict:
    from .core import waves as W
    out = W.file_challenge(from_agent, target_artifact_id, reason, ts)
    G.new_action(action_id=f"CHAL-{out['challenge_id']}", artifact_id=target_artifact_id, kind="upstream_challenge", params={"from": from_agent, "reason": reason},
                 run_id=f"challenge:{out['challenge_id']}", proposer=from_agent, approver_role="controller", created_at=ts)
    db.get_conn().execute("UPDATE actions SET world='tidewall', assignee='dana', summary=? WHERE action_id=?",
                          (f"{from_agent.replace('_', ' ').title()} challenges {target_artifact_id}: {reason} (no wave starts unless you approve)", f"CHAL-{out['challenge_id']}"))
    db.commit()
    return {**out, "to": "dana", "wave_started": False}
