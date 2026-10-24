"""The lessons memory: how the agent learns from its mistakes.

A mistake signal is never the agent grading itself: Jade overrules a claim, or a person rejects a draft. Each signal becomes a
proposed lesson, a named check with the rule, the evidence (which cases, what was claimed, what was right) and the shape of the
case it came from (its signature), so similar cases recall it later. A lesson changes how a control operates, so it needs the
Controller's approval and applies prospectively only; before it activates, a regression gate re-runs every evaluated case with
the lesson on and rejects it if any previously passing claim fails.
"""
from __future__ import annotations

import json
from typing import Any

from . import config, db

CATALOG: dict[str, dict[str, str]] = {
    "materiality_full_framework": {
        "mistake_kind": "materiality", "lesson_id": "L-materiality",
        "rule": "Never conclude immaterial without both SAB 108 methods, the performance threshold, the aggregate with the misstatement log and the qualitative tests from the graph.",
        "guidance": "A correction under the 5% rule can still flip a covenant, change compensation already paid, or sit in a document the lender holds. Run the full framework before writing 'immaterial'.",
        "enforcement": "playbook check: materiality claim computed by the full framework"},
    "classify_by_knowable_at": {
        "mistake_kind": "classification", "lesson_id": "L-classification",
        "rule": "Classify by when the information arrived (Memento: knowable_at against when the original number was made), never by the service period.",
        "guidance": "An invoice for March that arrived after the close is a change in estimate; one that sat in the inbox before the close is an error. The period on the invoice does not decide it.",
        "enforcement": "playbook check: classification from Memento timestamps"},
    "post_in_open_period": {
        "mistake_kind": "posting", "lesson_id": "L-posting",
        "rule": "Post corrections in the first open period with an out-of-period tag to the original period; never date an entry into a locked period.",
        "guidance": "Q1 is locked after the close (policy C-1). The fix goes in the open month, tagged to March, and the lender package is restated separately.",
        "enforcement": "playbook check: posting period = first open period, orig_period carried"},
    "route_by_authority": {
        "mistake_kind": "routing", "lesson_id": "L-routing",
        "rule": "Route each item to the role the approval matrix names: lender documents to the CFO, compensation offsets to HR or VP Sales with the Controller informed, vendor and collection items to AP.",
        "guidance": "The Controller cannot sign for the lender or for payroll; sending everything to one inbox is a routing error even when she would have forwarded it.",
        "enforcement": "playbook check: approvers from the compensation menu"},
    "locked_period_means_estimate": {
        "mistake_kind": "classification", "lesson_id": "L-locked-means-estimate",
        "rule": "If the period is locked, treat the item as a change in estimate and book it prospectively.",
        "guidance": "A broad reading of the Controller's rejection: she said not to touch Q1, so nothing in Q1 is an error. (This confuses where the fix is booked with what the item is.)",
        "enforcement": "playbook check: classification override when the period is locked"},
}
ROLE_WORD = {"controller": "the Controller", "cfo": "the CFO", "ap": "AP", "hr": "HR", "vp_sales": "VP Sales"}


def _row(r) -> dict[str, Any]:
    d = dict(r)
    d["evidence"] = json.loads(d.pop("evidence_json") or "[]")
    d["gate"] = json.loads(d.pop("gate_json") or "null")
    d["cases"] = sorted({e["case_id"] for e in d["evidence"]})
    cat = CATALOG.get(d["check_name"], {})
    d["guidance"] = d.get("guidance") or cat.get("guidance")
    d["enforcement"] = cat.get("enforcement")
    return d


def all_lessons() -> list[dict[str, Any]]:
    return [_row(r) for r in db.q("SELECT * FROM lessons ORDER BY created_at")]


def get(lesson_id: str) -> dict[str, Any] | None:
    r = db.q1("SELECT * FROM lessons WHERE lesson_id=?", (lesson_id,))
    return _row(r) if r else None


def active_checks(at: str | None = None) -> set[str]:
    """Checks active at `at`; with no time, the current state. A lesson applies from its approval onwards, never backwards."""
    if at is None:
        return {r["check_name"] for r in db.q("SELECT check_name FROM lessons WHERE status='active'")}
    return {r["check_name"] for r in db.q("SELECT check_name FROM lessons WHERE status='active' AND valid_from<=?", (db.norm_ts(at),))}


def _event(lesson_id: str, ts: str, kind: str, actor: str, detail: Any = None) -> None:
    db.insert("lesson_events", {"lesson_id": lesson_id, "ts": db.norm_ts(ts), "kind": kind, "actor": actor, "detail_json": db.dumps(detail)})


def propose(check_name: str, case_id: str, evidence: dict, signature: list[str], ts: str, proposed_by: str) -> dict[str, Any]:
    """One lesson per check; a second signal for the same check adds evidence instead of a duplicate."""
    cat = CATALOG[check_name]
    lid = cat["lesson_id"]
    item = {"case_id": case_id, "ts": db.norm_ts(ts), "signal": proposed_by, "signature": signature, **evidence}
    row = db.q1("SELECT * FROM lessons WHERE lesson_id=?", (lid,))
    if row is None:
        db.insert("lessons", {"lesson_id": lid, "created_at": db.norm_ts(ts), "mistake_kind": cat["mistake_kind"], "check_name": check_name, "rule": cat["rule"], "guidance": cat["guidance"],
                              "evidence_json": db.dumps([item]), "status": "proposed", "proposed_by": proposed_by, "approved_by": None, "approved_at": None, "valid_from": None, "gate_json": None})
        _event(lid, ts, "proposed", proposed_by, {"case_id": case_id})
        db.log_event("lesson_proposed", f"Lesson {lid} proposed from {case_id} by {proposed_by}: {cat['rule'][:90]}", actor=proposed_by, ts=ts, correction_id=case_id, detail={"lesson_id": lid, "check": check_name})
    else:
        ev = json.loads(row["evidence_json"] or "[]")
        if not any(e["case_id"] == case_id for e in ev):
            ev.append(item)
            db.get_conn().execute("UPDATE lessons SET evidence_json=? WHERE lesson_id=?", (db.dumps(ev), lid))
            _event(lid, ts, "evidence_added", proposed_by, {"case_id": case_id})
    db.commit()
    return get(lid)  # type: ignore[return-value]


def propose_from_overrule(claim: str, case_id: str, verdict: dict, signature: list[str], ts: str) -> dict[str, Any] | None:
    check = {"materiality": "materiality_full_framework", "classification": "classify_by_knowable_at", "posting": "post_in_open_period", "routing": "route_by_authority"}.get(claim)
    if not check:
        return None
    return propose(check, case_id, {"claimed": verdict["agent"], "correct": verdict["jade"], "why": verdict["why"]}, signature, ts, "jade")


def signal_rejection(case_id: str, action_id: str, approver: str, reason: str, ts: str) -> list[dict[str, Any]]:
    """A person said no to a draft. The narrow lesson and the broad over-generalization are both proposed; the gate decides."""
    from . import review
    facts = review.case_facts(case_id)
    sig = review.signature(facts) if facts else []
    out = []
    if "lock" in (reason or "").lower():
        a = db.q1("SELECT params_json FROM actions WHERE action_id=?", (action_id,))
        p = json.loads(a["params_json"]) if a else {}
        ev = {"claimed": p.get("posting_period"), "correct": facts["booking_period"] if facts else None, "why": f"{approver}: {reason}", "action_id": action_id}
        out.append(propose("post_in_open_period", case_id, ev, sig, ts, f"human:{approver}"))
        out.append(propose("locked_period_means_estimate", case_id, {**ev, "claimed": "error", "correct": "new information (broad reading)"}, sig, ts, f"human:{approver}"))
    return out


# ------------------------------------------------------------------ recall: similar past mistakes
def recall(signature: list[str], *, exclude_case: str | None = None, at: str | None = None, limit: int = 3) -> list[dict[str, Any]]:
    """Lessons whose source cases look like this one (Jaccard over feature tokens). Returned with the best-matching case and score."""
    at = db.norm_ts(at or config.DEMO_NOW)
    s = set(signature)
    out = []
    for l in all_lessons():
        if l["created_at"] > at or l["check_name"] in ("locked_period_means_estimate",) and l["status"] != "active":
            continue
        best = None
        for e in l["evidence"]:
            if e["case_id"] == exclude_case or e.get("ts", "") > at:
                continue
            t = set(e.get("signature") or [])
            if not t:
                continue
            j = len(s & t) / len(s | t) if s | t else 0.0
            if len(s & t) < 2:
                continue
            if best is None or j > best[0]:
                best = (j, e["case_id"], sorted(s & t))
        if best and best[0] >= 0.25:
            out.append({"lesson_id": l["lesson_id"], "check_name": l["check_name"], "status": l["status"], "rule": l["rule"], "score": round(best[0], 2), "from_case": best[1], "shared": best[2],
                        "applied": l["status"] == "active" and (l["valid_from"] or "") <= at})
    out.sort(key=lambda x: -x["score"])
    return out[:limit]


# ------------------------------------------------------------------ the regression gate and approval
def _cases() -> list[str]:
    return [r["correction_id"] for r in db.q("SELECT correction_id FROM evaluations WHERE correction_id NOT LIKE 'REV-%' AND correction_id<>'LYFT_TYPO' ORDER BY ts")]


def _passes(facts: dict, active: set[str]) -> dict[str, bool]:
    from . import review
    claims = review.playbook_claims(facts, active)
    j = review.jade_review(facts, claims)
    return {k: j[k]["verdict"] == "approve" for k in review.CLAIMS}


def gate(lesson_id: str, ts: str | None = None, *, baseline: set[str] | None = None, cases: list[str] | None = None, store: bool = True) -> dict[str, Any]:
    """Re-run every evaluated case with the lesson on. Rejected if any claim that passed before fails now."""
    from . import review
    l = get(lesson_id)
    if l is None:
        raise KeyError(lesson_id)
    ts = db.norm_ts(ts or config.DEMO_NOW)
    base = set(baseline) if baseline is not None else active_checks(ts)
    cand = base | {l["check_name"]}
    rows = []
    for cid in (cases or _cases()):
        facts = review.case_facts(cid)
        if not facts:
            continue
        before, after = _passes(facts, base), _passes(facts, cand)
        rows.append({"case_id": cid, "before": before, "after": after,
                     "newly_failing": [k for k in before if before[k] and not after[k]], "newly_passing": [k for k in before if not before[k] and after[k]]})
    nf = [(r["case_id"], k) for r in rows for k in r["newly_failing"]]
    npass = [(r["case_id"], k) for r in rows for k in r["newly_passing"]]
    res = {"ran_at": ts, "cases": len(rows), "claims": len(rows) * 4, "pass_before": sum(sum(r["before"].values()) for r in rows), "pass_after": sum(sum(r["after"].values()) for r in rows),
           "newly_failing": [{"case_id": c, "claim": k} for c, k in nf], "newly_passing": [{"case_id": c, "claim": k} for c, k in npass], "passed": not nf, "baseline": sorted(base)}
    if store:
        db.get_conn().execute("UPDATE lessons SET gate_json=? WHERE lesson_id=?", (db.dumps(res), lesson_id))
        _event(lesson_id, ts, "gate_passed" if res["passed"] else "gate_failed", "trackback:gate", {"newly_failing": res["newly_failing"], "newly_passing": len(npass)})
        if not res["passed"] and l["status"] == "proposed":
            db.get_conn().execute("UPDATE lessons SET status='rejected_by_gate' WHERE lesson_id=?", (lesson_id,))
            db.log_event("lesson_rejected", f"Lesson {lesson_id} rejected by the regression gate: {len(nf)} previously passing claim(s) would fail ({', '.join(f'{c}:{k}' for c, k in nf[:4])})", actor="trackback:gate", ts=ts, detail=res)
        db.commit()
    return res


def approve(lesson_id: str, approver: str, ts: str | None = None) -> dict[str, Any]:
    """The Controller approves; the gate runs first if it has not. Rejected lessons stay rejected. Prospective from `ts`."""
    l = get(lesson_id)
    if l is None:
        raise KeyError(lesson_id)
    ts = db.norm_ts(ts or config.DEMO_NOW)
    if approver != config.PEOPLE["controller"]:
        raise PermissionError(f"lessons change how controls operate; only the Controller ({config.PEOPLE['controller']}) approves them")
    if l["status"] == "active":
        return l
    g = l["gate"] or gate(lesson_id, ts)
    if not g["passed"]:
        return get(lesson_id)  # type: ignore[return-value]
    db.get_conn().execute("UPDATE lessons SET status='active', approved_by=?, approved_at=?, valid_from=? WHERE lesson_id=?", (approver, ts, ts, lesson_id))
    _event(lesson_id, ts, "approved", approver, {"valid_from": ts})
    db.log_event("lesson_approved", f"Lesson {lesson_id} approved by {approver}, active from {ts[:16]} (prospective): {l['rule'][:80]}", actor=approver, ts=ts, detail={"lesson_id": lesson_id, "gate": g})
    db.commit()
    return get(lesson_id)  # type: ignore[return-value]


def approve_pending(approver: str, ts: str | None = None) -> list[dict[str, Any]]:
    """The Controller's one-click review of everything proposed: each lesson goes through the gate, passes activate, failures are rejected."""
    out = []
    for l in all_lessons():
        if l["status"] == "proposed":
            out.append(approve(l["lesson_id"], approver, ts))
    return out


def playbook() -> dict[str, Any]:
    from . import review
    act = active_checks()
    ls = all_lessons()
    return {"version": review.playbook_version(act), "active_checks": sorted(act), "checks": list(review.CHECKS),
            "lessons": {"proposed": sum(1 for l in ls if l["status"] == "proposed"), "active": sum(1 for l in ls if l["status"] == "active"), "rejected_by_gate": sum(1 for l in ls if l["status"] == "rejected_by_gate")},
            "weaknesses": [{"check": c, "lifted": c in act, "rule": CATALOG[c]["rule"]} for c in review.CHECKS]}
