"""Forward propagation: claim diff -> structural seeds -> Kahn walk with early cutoff, materiality and conclusion checks ->
prose to the judge -> actions to compensation -> unprovable for retractions. Every finding is written in one transaction.

Walk semantics (see DECISIONS.md): early_cutoff (identical value) stops the walk; below_materiality clears the node but still passes
the new value to its children so aggregates are tested honestly (SAB 99 aggregation); conclusion_unchanged passes the value too.
Only current artifact versions are evaluated (one finding per artifact id)."""
from __future__ import annotations

import json
from collections import defaultdict, deque
from typing import Any

from .. import config
from . import db, graph, judge as J
from . import compensation
from .conclusions import boolean_part, conclusion_state
from .domain import get_domain
from .formula import FormulaError, evaluate

REASON_LABEL = {
    "value_changed": "value changed", "conclusion_flipped": "conclusion flipped", "early_cutoff": "recomputed: identical value",
    "below_materiality": "below materiality", "conclusion_unchanged": "conclusion unchanged", "different_period": "different period",
    "different_line_item": "different line item", "claim_unchanged": "did not consume the corrected claims", "prose_judged": "prose judged",
    "estimate_change": "estimate change: correct as of what was knowable", "supporter_retracted": "source retracted, no replacement",
    "supporters_cleared": "every supporter cleared", "parameters_within_materiality": "parameters within materiality",
    "rerendered": "cited figure moved; re-rendered in place by Trackback (no ping)",
}



_CARRY_REASONS = ("value_changed", "below_materiality", "conclusion_unchanged", "conclusion_flipped")


def _effective_input(artifact_id: str, version: int) -> float | None:
    """The value an input currently carries: the latest recompute of that version by an earlier correction (a cell kept at its
    version under a below-materiality or conclusion-unchanged verdict still carries its recomputed value forward), else the stored value."""
    f = db.q1("SELECT new_value FROM impact_findings WHERE artifact_id=? AND artifact_version=? AND new_value IS NOT NULL AND reason IN (?,?,?,?) ORDER BY rowid DESC LIMIT 1",
              (artifact_id, version, *_CARRY_REASONS))
    if f is not None:
        return f["new_value"]
    row = db.q1("SELECT value_num FROM artifacts WHERE artifact_id=? AND version=?", (artifact_id, version))
    return row["value_num"] if row else None

def propagate(correction_id: str, ts: str | None = None, *, dry_run: bool = False, defer_agents: bool = False, seeds_override: dict | None = None,
              extra_ids: list[str] | None = None) -> dict[str, Any]:
    """defer_agents: judgment/prose/action nodes are not judged here; they come back as verdict 'suspect' for the wave scheduler to
    bundle into pings (one per owning agent). seeds_override: an agent revision/retraction of one artifact instead of a claim diff."""
    corr = dict(db.q1("SELECT * FROM corrections WHERE correction_id=?", (correction_id,)))
    ts = db.norm_ts(ts or corr["tx_time"])
    ids = [correction_id] + list(extra_ids or [])
    diffs = [dict(r) for cid_ in ids for r in db.q("SELECT * FROM claim_diffs WHERE correction_id=?", (cid_,))]
    corr_by_id = {cid_: dict(db.q1("SELECT * FROM corrections WHERE correction_id=?", (cid_,))) for cid_ in ids}
    claim_corr = {d["claim_id"]: corr_by_id[d["correction_id"]] for d in diffs}   # coalesced waves: each claim keeps its own correction's kind and knowable_at
    dom = get_domain()
    exclude_agent = (seeds_override or {}).get("exclude_agent")
    changed = {d["claim_id"]: d for d in diffs if d["change"] in ("changed", "removed")}
    unchanged = {d["claim_id"]: d for d in diffs if d["change"] == "unchanged"}
    old_val = {c: (graph.claim_value(d["old_cv"]) if d["old_cv"] else None) for c, d in changed.items()}
    new_val = {c: (graph.claim_value(d["new_cv"]) if d["new_cv"] else None) for c, d in changed.items()}
    meta = {c: (graph.claim_info(c) or {}) for c in changed}
    knowable = corr["knowable_at"]

    # ---- structural seeds: current artifacts whose recorded supporters include a changed claim (any version of it)
    seeds: dict[str, set[str]] = defaultdict(set)
    touched_unchanged: set[str] = set()
    revised_values: dict[str, float | None] = {}
    if seeds_override:  # an agent revised (or retracted) one artifact: its consumers are the seeds, with the new value given
        rid = seeds_override["artifact"]
        revised_values[rid] = seeds_override.get("new_value")
        for e in graph.consumers_of_artifact(rid):
            if _is_current(e["consumer_id"], e["consumer_version"]):
                seeds[e["consumer_id"]].add(f"artifact:{rid}")
    for cid in changed:
        for e in _consumers_of_claim(cid):
            seeds[e["consumer_id"]].add(cid)
    for cid in unchanged:
        for e in _consumers_of_claim(cid):
            touched_unchanged.add(e["consumer_id"])

    # ---- naive baseline B1: every artifact of a run that read the corrected version
    sources = [corr["source_id"]] + [db.q1("SELECT source_id FROM corrections WHERE correction_id=?", (x,))["source_id"] for x in (extra_ids or [])]
    naive_runs = {r["run_id"] for src in sources for r in db.q("SELECT DISTINCT r.run_id FROM reads r JOIN source_versions sv ON sv.version_id=r.source_version_id WHERE sv.source_id=? AND r.http_status=200 AND r.pinned_at<=?", (src, ts))}
    naive = {r["artifact_id"] for r in db.q("SELECT artifact_id FROM artifacts WHERE run_id IN (%s) AND tx_from<=?" % ",".join("?" * len(naive_runs)), (*naive_runs, ts))} if naive_runs else set()
    naive |= set(seeds)

    # ---- subgraph of descendants (current versions) + topological order
    nodes: dict[str, dict] = {}
    kids: dict[str, set[str]] = defaultdict(set)
    hop: dict[str, int] = {k: 0 for k in seeds}
    q = deque(seeds.keys())
    while q:
        aid = q.popleft()
        if aid in nodes:
            continue
        nodes[aid] = graph.artifact_dict(db.artifact_current(aid))
        for e in graph.consumers_of_artifact(aid):
            child = e["consumer_id"]
            if not _is_current(child, e["consumer_version"]):
                continue
            kids[aid].add(child)
            hop[child] = min(hop.get(child, 10**6), hop[aid] + 1)
            q.append(child)
    indeg = {n: 0 for n in nodes}
    for src, ks in kids.items():
        for k in ks:
            if k in indeg:
                indeg[k] += 1
    ready = deque(sorted([n for n, d in indeg.items() if d == 0], key=lambda n: (hop[n], n)))
    topo: list[str] = []
    while ready:
        n = ready.popleft(); topo.append(n)
        for k in sorted(kids.get(n, ())):
            indeg[k] -= 1
            if indeg[k] == 0:
                ready.append(k)

    findings: dict[str, dict] = {}
    new_values: dict[str, float | None] = dict(revised_values)
    new_versions: dict[str, int] = {}
    dirty: set[str] = set(seeds)
    if seeds_override and seeds_override.get("retracted"):
        new_values[seeds_override["artifact"]] = None

    def base(aid: str) -> dict:
        art = nodes[aid] if aid in nodes else graph.artifact_dict(db.artifact_current(aid))
        f = {"artifact_id": aid, "artifact_version": art["version"], "kind": art["kind"], "hop": hop.get(aid, 0), "old_value": art["value_num"], "new_value": None,
             "line_item": art["line_item"], "period": art["period"], "lot": art["lot"], "content": art["content"], "run_id": art["run_id"], "pinned_at": art["pinned_at"]}
        f["knowable_after_pin"] = bool(art["pinned_at"] and knowable > db.norm_ts(art["pinned_at"]))
        f["agent_id"] = art.get("agent_id")
        cc = {}
        for e in graph.supporters_of(aid, art["version"]):
            if e["supporter_kind"] == "claim" and e["supporter_id"] in changed:
                cc[e["supporter_id"]] = {"old": old_val[e["supporter_id"]], "new": new_val[e["supporter_id"]], "label": _claim_label(e["supporter_id"])}
        if cc:
            f["changed_claims"] = cc
        return f

    for aid in topo:
        if aid not in dirty:
            continue
        art = nodes[aid]
        f = base(aid)
        sup = graph.supporters_of(aid, art["version"])
        parent_findings = {e["supporter_id"]: findings.get(e["supporter_id"]) for e in sup if e["supporter_kind"] == "artifact"}
        if any(pf and pf["verdict"] == "unprovable" for pf in parent_findings.values()):
            f.update(verdict="unprovable", reason="supporter_retracted"); findings[aid] = f
            for k in kids.get(aid, ()):
                dirty.add(k)
            continue
        # domain rule (finance: ASC 250, an estimate change never reaches back into a closed period), judged per the corrections that reach this node
        reaching = {claim_corr[e["supporter_id"]]["correction_id"] for e in sup if e["supporter_kind"] == "claim" and e["supporter_id"] in claim_corr} or set(ids)
        kinds = {corr_by_id[c]["kind"] for c in reaching}
        node_kind = "estimate" if kinds == {"estimate"} else corr["kind"]
        node_knowable = max(corr_by_id[c]["knowable_at"] for c in reaching)
        pre = dom.unaffected_reason({"period": art["period"], "line_item": art["line_item"], "kind": art["kind"]}, {"kind": node_kind, "knowable_at": node_knowable})
        if pre:
            f.update(verdict="unaffected", reason=pre, detail={"knowable_at": node_knowable}); findings[aid] = f; continue

        if art["kind"] in ("number", "forecast_cell"):
            formula = art["formula"] or {}
            values: dict[str, float | None] = {}
            for alias, ref in (formula.get("inputs") or {}).items():
                if ref["kind"] == "claim":
                    values[alias] = new_val[ref["id"]] if ref["id"] in changed else graph.claim_value(ref["version"])
                else:
                    if ref["id"] in new_values:
                        values[alias] = new_values[ref["id"]]
                    else:
                        values[alias] = _effective_input(ref["id"], int(ref["version"]))
            if any(v is None for v in values.values()):
                f.update(verdict="unprovable", reason="supporter_retracted", detail={"missing": [a for a, v in values.items() if v is None]}); findings[aid] = f
                for k in kids.get(aid, ()):
                    dirty.add(k)
                continue
            try:
                nv = evaluate(formula.get("expr", "x"), values)
            except FormulaError as e:
                f.update(verdict="needs_review", reason="prose_judged", detail={"error": str(e)}); findings[aid] = f; continue
            verdict, reason, detail = dom.evaluate_number({"line_item": art["line_item"], "kind": art["kind"]}, art["value_num"], nv, art["conclusions"])
            f.update(verdict=verdict, reason=reason, new_value=nv, detail=detail)
            if reason != "early_cutoff":
                new_values[aid] = nv
                for k in kids.get(aid, ()):
                    dirty.add(k)
            if verdict == "invalidated" and not dry_run:
                new_versions[aid] = _recalc_version(art, nv, formula, changed, new_versions, ts, correction_id)
            findings[aid] = f

        elif art["kind"] == "sentence" and defer_agents:
            # field-level relevance: suspect only if a materially changed input (invalidated supporter, changed claim, reworked upstream prose) was read
            material_in = [e["supporter_id"] for e in sup if (e["supporter_kind"] == "claim" and e["supporter_id"] in changed) or
                           (e["supporter_kind"] == "artifact" and findings.get(e["supporter_id"], {}).get("verdict") in ("invalidated", "suspect", "unprovable"))]
            slot_changes = {e["supporter_id"]: new_values[e["supporter_id"]] for e in sup if e["supporter_kind"] == "artifact" and e["supporter_id"] in new_values and findings.get(e["supporter_id"], {}).get("verdict") == "unaffected"}
            if not material_in:
                if slot_changes and not dry_run:
                    rendered = _rerender(art, slot_changes, ts, correction_id)
                    if rendered:   # a cited figure moved in display: the old sentence is superseded by Trackback's re-render (no LLM, no ping)
                        f.update(verdict="invalidated", reason="rerendered", detail={"rerendered": rendered}, new_version_no=rendered,
                                 proposed_rewrite=((cur_r := db.artifact_current(aid)) and cur_r["content"]) or None, judge_model="trackback:slot-rerender")
                    else:
                        f.update(verdict="unaffected", reason="conclusion_unchanged", detail={"rerendered": None})
                else:
                    f.update(verdict="unaffected", reason="supporters_cleared" if any(e["supporter_kind"] == "artifact" and e["supporter_id"] in findings for e in sup) else "fields_not_read")
                findings[aid] = f; continue
            if exclude_agent and art.get("agent_id") == exclude_agent and aid == (seeds_override or {}).get("artifact"):
                findings[aid] = f; continue
            f.update(verdict="suspect", reason="pending_ping", material_inputs=material_in)
            findings[aid] = f
            for k in kids.get(aid, ()):
                dirty.add(k)
        elif art["kind"] == "sentence":
            old_facts, new_facts, changed_facts, flipped = [], [], [], False
            for e in sup:
                sid = e["supporter_id"]
                if e["supporter_kind"] == "claim":
                    if sid in changed:
                        lab = _claim_label(sid)
                        old_facts.append({"id": sid, "label": lab, "value": old_val[sid]}); new_facts.append({"id": sid, "label": lab, "value": new_val[sid]})
                        changed_facts.append({"id": sid, "old": old_val[sid], "new": new_val[sid]})
                else:
                    pf = findings.get(sid)
                    if not pf or pf.get("new_value") is None or pf["reason"] == "early_cutoff":
                        if pf and pf["verdict"] == "invalidated" and pf["kind"] == "sentence":
                            changed_facts.append({"id": sid, "old": None, "new": None})
                        continue
                    cited = db.q1("SELECT value_num, line_item FROM artifacts WHERE artifact_id=? AND version=?", (sid, int(e["supporter_version"])))
                    ov = cited["value_num"] if cited else pf["old_value"]
                    fl = pf["reason"] == "conclusion_flipped"
                    flipped = flipped or fl
                    old_facts.append({"id": sid, "label": pf["line_item"], "value": ov})
                    new_facts.append({"id": sid, "label": pf["line_item"], "value": pf["new_value"], "conclusion_changed": fl})
                    if ov is None or abs(float(ov) - float(pf["new_value"])) > 1e-9:
                        changed_facts.append({"id": sid, "old": ov, "new": pf["new_value"]})
            if not changed_facts:
                f.update(verdict="unaffected", reason="supporters_cleared"); findings[aid] = f; continue
            sub = J.precheck(art["content"], [c for c in changed_facts if c["old"] is not None])
            if sub:
                f.update(verdict="invalidated", reason="prose_judged", judge_model="precheck:literal-substitution",
                         judge_rationale=f"Sentence states {sub['found']}; the supporting value is now {sub['replacement']}.",
                         proposed_rewrite=sub["rewrite"] + f" (corrected {ts[:10]}; see {correction_id})")
            else:
                res = J.judge({"content": art["content"], "period": art["period"], "line_item": art["line_item"], "conclusions": art["conclusions"]}, old_facts, new_facts, ts)
                f.update(verdict=res["verdict"], reason="prose_judged", judge_model=res["model"], judge_rationale=res["rationale"], proposed_rewrite=res.get("proposed_rewrite"), cache_key=res.get("cache_key"))
            f["conclusion_flipped"] = flipped
            if f["verdict"] == "invalidated":
                for k in kids.get(aid, ()):
                    dirty.add(k)
            findings[aid] = f

        elif art["kind"] == "action" and defer_agents:
            material_in = [e["supporter_id"] for e in sup if (e["supporter_kind"] == "claim" and e["supporter_id"] in changed) or
                           (e["supporter_kind"] == "artifact" and findings.get(e["supporter_id"], {}).get("verdict") in ("invalidated", "suspect", "unprovable"))]
            concl = art["conclusions"]
            if concl and art["formula"] and (art["formula"].get("value_from") in new_values):
                src = art["formula"]["value_from"]; pf = findings.get(src)
                ov, nv = (pf["old_value"] if pf and pf.get("old_value") is not None else art["value_num"]), new_values[src]
                oc, nc = conclusion_state(ov, concl), conclusion_state(nv, concl)
                f.update(old_value=ov, new_value=nv, detail={"old_conclusion": oc, "new_conclusion": nc})
                if boolean_part(oc) == boolean_part(nc):  # the action asserts a conclusion; if it holds, the action stands (calculation attached), no ping
                    f.update(verdict="unaffected", reason="conclusion_unchanged"); findings[aid] = f; continue
            if not material_in:
                preasons = {findings[e["supporter_id"]]["reason"] for e in sup if e["supporter_kind"] == "artifact" and e["supporter_id"] in findings}
                f.update(verdict="unaffected", reason="conclusion_unchanged" if "conclusion_unchanged" in preasons else "parameters_within_materiality"); findings[aid] = f; continue
            f.update(verdict="suspect", reason="pending_ping", material_inputs=material_in)
            findings[aid] = f
        elif art["kind"] == "action":
            action = db.q1("SELECT * FROM actions WHERE artifact_id=?", (aid,))
            inval = [pf for pf in parent_findings.values() if pf and pf["verdict"] == "invalidated"]
            direct_claim = [e for e in sup if e["supporter_kind"] == "claim" and e["supporter_id"] in changed]
            concl = art["conclusions"]
            decided = False
            if concl and art["formula"] and (art["formula"].get("value_from") in new_values):
                src = art["formula"]["value_from"]
                pf = findings.get(src)
                ov, nv = (pf["old_value"] if pf and pf.get("old_value") is not None else art["value_num"]), new_values[src]
                oc, nc = conclusion_state(ov, concl), conclusion_state(nv, concl)
                ob, nb = boolean_part(oc), boolean_part(nc)
                f.update(old_value=ov, new_value=nv, detail={"old_conclusion": oc, "new_conclusion": nc})
                if ob == nb:
                    f.update(verdict="unaffected", reason="conclusion_unchanged"); decided = True
                else:
                    f.update(verdict="invalidated", reason="conclusion_flipped"); decided = True
            if not decided:
                if inval or direct_claim:
                    lead = next((pf for pf in inval if pf["kind"] in ("number", "forecast_cell")), inval[0] if inval else None)
                    reason = lead["reason"] if (lead and lead["kind"] in ("number", "forecast_cell") and lead["reason"] == "conclusion_flipped") else "value_changed"
                    f.update(verdict="invalidated", reason=reason, old_value=lead["old_value"] if lead else art["value_num"], new_value=lead["new_value"] if lead else None)
                else:
                    reasons = {pf["reason"] for pf in parent_findings.values() if pf}
                    f.update(verdict="unaffected", reason="conclusion_unchanged" if "conclusion_unchanged" in reasons else "parameters_within_materiality")
            if f["verdict"] == "invalidated" and action is not None and not dry_run:
                compensate_action(correction_id, art, f, ts, parent_findings=parent_findings)
            findings[aid] = f

    # ---- touched but structurally cleared: consumed only unchanged claims of the corrected document (and their direct consumers)
    bfs = deque()
    for aid in sorted(touched_unchanged):
        if aid not in findings:
            f = base(aid); f.update(verdict="unaffected", reason="claim_unchanged", new_value=f["old_value"]); findings[aid] = f
            bfs.append((aid, 0))
    while bfs:  # descendants that rest only on untouched claims are cleared for the same structural reason
        aid, h = bfs.popleft()
        for e in graph.consumers_of_artifact(aid):
            c = e["consumer_id"]
            if c not in findings and _is_current(c, e["consumer_version"]):
                g = base(c); g.update(verdict="unaffected", reason="claim_unchanged", new_value=g["old_value"], hop=h + 1); findings[c] = g
                bfs.append((c, h + 1))
    # ---- naive-set artifacts never reached: different period / line item (structural; shown as cleared with the reason)
    changed_months = {(m.get("period_start") or "")[:7] for m in meta.values()}
    for aid in sorted(naive - set(findings)):
        art = graph.artifact_dict(db.artifact_current(aid))
        if art["kind"] == "action":
            continue
        reason = dom.unaffected_reason({"period": art["period"], "line_item": art["line_item"], "kind": art["kind"]}, {"changed_months": sorted(changed_months)}) or "different_line_item"
        f = base(aid); f.update(verdict="unaffected", reason=reason, new_value=f["old_value"]); findings[aid] = f

    # ---- correction-level materiality
    claim_delta = max([abs((new_val[c] or 0) - (old_val[c] or 0)) for c in changed if old_val.get(c) is not None and new_val.get(c) is not None] or [0.0])
    recomputed = [abs(f["detail"]["delta"]) for f in findings.values() if f["kind"] == "number" and isinstance(f.get("detail"), dict) and "delta" in f["detail"] and not dom.line_profile(f)["ratio"]]
    cells = [abs(f["detail"]["delta"]) for f in findings.values() if f["kind"] == "forecast_cell" and isinstance(f.get("detail"), dict) and "delta" in f["detail"]]
    total_delta = max(recomputed) if recomputed else (max(cells) if cells else claim_delta)
    flips = any(f["reason"] == "conclusion_flipped" and _qualitative(f, dom) for f in findings.values())
    prior_year = any((meta[c].get("period_start") or "9999") < "2026-01-01" for c in changed)
    verdict = dom.correction_verdict(corr, total_delta, flips, prior_year)
    out = {"correction_id": correction_id, "tx_time": ts, "kind": corr["kind"], "knowable_at": knowable, "materiality_verdict": verdict, "total_delta": total_delta,
           "changed_claims": [{"claim_id": c, "old": old_val[c], "new": new_val[c], **meta[c]} for c in changed],
           "n_unchanged_claims": len(unchanged), "naive_count": len(naive), "naive_set": sorted(naive),
           "findings": sorted(findings.values(), key=lambda f: (f["hop"], f["artifact_id"])), "counts": _counts(findings.values())}
    if dry_run or defer_agents:
        out["_write_ctx"] = {"new_versions": new_versions, "meta": meta, "verdict": verdict, "total_delta": total_delta}
        return out
    write_findings(correction_id, findings, out, ts)
    return out


def write_findings(correction_id: str, findings: dict, out: dict, ts: str) -> None:
    """Every finding of a wave in one transaction; statuses; the correction-level verdict; the domain's unbooked log."""
    ctx = out.get("_write_ctx") or {}
    new_versions = ctx.get("new_versions", {})
    corr = dict(db.q1("SELECT * FROM corrections WHERE correction_id=?", (correction_id,)))
    dom = get_domain()
    verdict = ctx.get("verdict") or out.get("materiality_verdict")
    with db.tx() as conn:
        for f in findings.values():
            if f["verdict"] == "suspect":
                f["verdict"], f["reason"] = "needs_review", "ping_pending"
            db.insert("impact_findings", {"correction_id": correction_id, "artifact_id": f["artifact_id"], "artifact_version": f["artifact_version"], "verdict": f["verdict"], "reason": f["reason"],
                                          "old_value": f.get("old_value"), "new_value": f.get("new_value"), "judge_model": f.get("judge_model"), "judge_rationale": f.get("judge_rationale"),
                                          "cache_key": f.get("cache_key"), "hop": f["hop"], "proposed_rewrite": f.get("proposed_rewrite")})
            if f["verdict"] == "invalidated":
                st = "superseded" if (f["artifact_id"] in new_versions or f.get("new_version_no")) else "stale"
                conn.execute("UPDATE artifacts SET status=? WHERE artifact_id=? AND version=? AND status<>?", (st, f["artifact_id"], f["artifact_version"], st))
            elif f["verdict"] in ("needs_review", "unprovable"):
                st = "suspect" if f["verdict"] == "needs_review" else "unprovable"
                conn.execute("UPDATE artifacts SET status=? WHERE artifact_id=? AND version=? AND status<>?", (st, f["artifact_id"], f["artifact_version"], st))
        conn.execute("UPDATE corrections SET materiality_verdict=? WHERE correction_id=?", (verdict, correction_id))
    total_delta = ctx.get("total_delta", out.get("total_delta", 0.0))
    if corr["kind"] == "error" and total_delta and total_delta > 0 and hasattr(dom, "log_unbooked"):
        meta = ctx.get("meta") or {}
        lines = ",".join(sorted({(m or {}).get("line_item") or "" for m in meta.values()} - {""}))
        dom.log_unbooked(correction_id, corr["booking_period"] or ts[:7], lines, total_delta, verdict != "log", f"{verdict}: {(corr['note'] or '')[:160]}", ts)
    c = _counts(findings.values())
    db.log_event("correction_applied", f"{correction_id}: naive {out.get('naive_count')}; Trackback {c['invalidated']} invalidated, {c['unaffected']} cleared, {c['needs_review']} need review, {c['unprovable']} unprovable ({verdict})",
                 actor="trackback:engine", ts=ts, correction_id=correction_id, detail={"counts": c, "materiality_verdict": verdict})
    db.commit()


def compensate_action(correction_id: str, art: dict, f: dict, ts: str, parent_findings: dict | None = None) -> None:
    """Executed action with a changed input: propose the domain's compensation (never auto-execute). Proposals not yet approved become stale."""
    dom = get_domain()
    action = db.q1("SELECT * FROM actions WHERE artifact_id=?", (art["artifact_id"],))
    if action is None:
        return
    inval = []
    for pf in (parent_findings or {}).values():
        if pf and pf.get("verdict") == "invalidated":
            if "kind" not in pf or "line_item" not in pf:
                cur = db.artifact_current(pf["artifact_id"]); pf = {**pf, "kind": cur["kind"], "line_item": cur["line_item"]}
            inval.append(pf)
    if not inval and parent_findings is None:
        inval = [x for x in [db.q1("SELECT * FROM impact_findings WHERE correction_id=? AND artifact_id=?", (correction_id, e["supporter_id"])) for e in graph.supporters_of(art["artifact_id"], art["version"]) if e["supporter_kind"] == "artifact"] if x]
        inval = [dict(x) | {"kind": (db.artifact_current(x["artifact_id"]) or {"kind": "number"})["kind"], "line_item": (db.artifact_current(x["artifact_id"]) or {"line_item": None})["line_item"]} for x in inval if x["verdict"] == "invalidated"]
    exact = [pf for pf in inval if pf.get("kind") in ("number", "forecast_cell") and dom.line_profile(pf)["exact"] and pf.get("new_value") is not None and pf.get("old_value") is not None]
    totals = [pf for pf in exact if pf["artifact_id"].endswith("_total")]
    basis = totals if totals else exact  # a summed artifact already carries the whole overpayment; never double count it with its parts
    delta = sum(pf["new_value"] - pf["old_value"] for pf in basis) if basis else ((f["new_value"] - f["old_value"]) if (f.get("new_value") is not None and f.get("old_value") is not None) else None)
    if action["state"] in ("executed", "approved", "compensation_proposed"):
        f["compensation"] = compensation.propose(correction_id, action, {**f, "delta": delta, "artifact_version": art["version"]}, ts)
    elif action["state"] in ("proposed", "blocked"):
        graph.set_action_state(action["action_id"], "stale", ts)
        f["compensation"] = {"kind": "redraft", "note": "proposal not yet approved; re-draft from the corrected source"}


def _rerender(art: dict, slot_changes: dict, ts: str, correction_id: str) -> int | None:
    """Numeric slots: a sentence whose cited figures moved without a material change is re-rendered by Trackback, no ping, no LLM."""
    fields = json.loads(art.get("fields_json") or "{}") if isinstance(art.get("fields_json"), str) else (art.get("fields") or {})
    template = fields.get("template")
    if not template:
        return None
    from ..agents.prose import render_template
    text = render_template(template, {k: v for k, v in slot_changes.items()}, fallback=art["content"])
    if text == art["content"]:
        return None
    db.close_tx("artifacts", "artifact_id", art["artifact_id"], ts, " AND version=?", (art["version"],))
    v = graph.new_artifact(artifact_id=art["artifact_id"], kind="sentence", run_id=f"correction:{correction_id}", pinned_at=ts, period=art["period"], line_item=art["line_item"],
                           content=text, value_num=None, formula=None, conclusions=art["conclusions"], status="valid", tx_from=ts, agent_id=art.get("agent_id"), origin="rerender",
                           reason=f"numeric slots re-rendered for {correction_id}", fields=fields)
    for e in graph.supporters_of(art["artifact_id"], art["version"]):
        sv = e["supporter_version"]
        if e["supporter_kind"] == "artifact":
            cur = db.artifact_current(e["supporter_id"]); sv = str(cur["version"]) if cur else sv
        graph.add_edge(consumer_id=art["artifact_id"], consumer_version=v, supporter_kind=e["supporter_kind"], supporter_id=e["supporter_id"], supporter_version=sv, dep_kind=e["dep_kind"], capture=e["capture"])
    return v


def _recalc_version(art: dict, new_val: float, formula: dict, changed: dict, new_versions: dict, ts: str, correction_id: str) -> int:
    inputs = {}
    for alias, ref in (formula.get("inputs") or {}).items():
        if ref["kind"] == "claim" and ref["id"] in changed and changed[ref["id"]]["new_cv"]:
            inputs[alias] = {"kind": "claim", "id": ref["id"], "version": changed[ref["id"]]["new_cv"]}
        elif ref["kind"] == "artifact" and ref["id"] in new_versions:
            inputs[alias] = {"kind": "artifact", "id": ref["id"], "version": str(new_versions[ref["id"]])}
        else:
            inputs[alias] = ref
    db.close_tx("artifacts", "artifact_id", art["artifact_id"], ts, " AND version=?", (art["version"],))
    v = graph.new_artifact(artifact_id=art["artifact_id"], kind=art["kind"], run_id=f"correction:{correction_id}", pinned_at=ts, period=art["period"], line_item=art["line_item"],
                           content=((art["content"] or "").split(" [recalculated")[0] + f" [recalculated {ts[:10]} for {correction_id}]").strip(), value_num=new_val,
                           formula={"expr": formula.get("expr", "x"), "inputs": inputs}, conclusions=art["conclusions"], status="valid", tx_from=ts,
                           agent_id=art.get("agent_id"), origin="source_correction", reason=f"recomputed by Trackback for {correction_id}")
    for alias, ref in inputs.items():
        graph.add_edge(consumer_id=art["artifact_id"], consumer_version=v, supporter_kind=ref["kind"], supporter_id=ref["id"], supporter_version=ref["version"], dep_kind="numeric", capture="structured")
    return v


def _consumers_of_claim(claim_id: str) -> list[dict]:
    out = []
    for e in db.q("SELECT * FROM justifications WHERE supporter_kind='claim' AND supporter_id=?", (claim_id,)):
        if _is_current(e["consumer_id"], e["consumer_version"]):
            out.append(dict(e))
    return out


def _is_current(artifact_id: str, version: int) -> bool:
    cur = db.artifact_current(artifact_id)
    return cur is not None and int(cur["version"]) == int(version)





def _qualitative(f: dict, dom) -> bool:
    art = db.artifact_current(f["artifact_id"])
    concl = json.loads(art["conclusions_json"]) if art is not None and art["conclusions_json"] else {}
    return bool(dom.is_qualitative_flip({"line_item": f.get("line_item")}, concl))


def _claim_label(cid: str) -> str:
    i = graph.claim_info(cid) or {}
    return f"{i.get('line_item')} {i.get('entity') or ''} {(i.get('period_start') or '')[:7]}".strip()


def _counts(findings) -> dict:
    c = {"invalidated": 0, "unaffected": 0, "needs_review": 0, "unprovable": 0, "suspect": 0}
    for f in findings:
        c[f["verdict"]] = c.get(f["verdict"], 0) + 1
    return c
