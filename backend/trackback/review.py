"""Jade, the reviewer, and the agent's playbook.

The agent's judgment calls on a correction (what kind of change it is, whether it matters, where to book the fix, who approves it)
come from a versioned playbook. Playbook v1 carries four weaknesses junior accountants have. Jade checks every claim against the
engines: Memento for when the fact first existed, the materiality memo plus the graph for the qualitative triggers, the period
locks, the compensation menu's approver roles. She approves, overrules (with the corrected claim and why) or escalates. Numbers are
never written by a model here; every claim carries the evidence it rests on.

Lessons (lessons.py) turn an overrule into a named check; an active check replaces the weak path in the playbook, prospectively.
"""
from __future__ import annotations

import json
from typing import Any

from . import config, db
from .domains.finance import materiality as M

MATERIAL_VERDICTS = {"escalate", "book_and_evaluate", "little_r", "big_r"}
CHECKS = ("classify_by_knowable_at", "materiality_full_framework", "post_in_open_period", "route_by_authority")
# the broad, wrong generalization a rejection can suggest; the regression gate exists to catch it
BAD_CHECKS = ("locked_period_means_estimate",)
CLAIMS = ("classification", "materiality", "posting", "routing")

ROLE_WORD = {"controller": "the Controller", "cfo": "the CFO", "ap": "AP", "hr": "HR", "vp_sales": "VP Sales", "editor": "the editor", "pm": "the PM"}


def _money(x: float | None) -> str:
    return "—" if x is None else f"${abs(x):,.0f}"


def _locked(period: str | None) -> bool:
    if not period:
        return False
    r = db.q1("SELECT locked FROM periods WHERE period=?", (period,))
    return bool(r and r["locked"])


# ------------------------------------------------------------------ the facts of a case (all from the database, none typed)
def case_facts(correction_id: str) -> dict[str, Any] | None:
    corr = db.q1("SELECT * FROM corrections WHERE correction_id=?", (correction_id,))
    if corr is None:
        return None
    corr = dict(corr)
    changed = [dict(r) for r in db.q("SELECT c.line_item, c.period_start, c.entity, cd.old_cv, cd.new_cv FROM claim_diffs cd JOIN claims c ON c.claim_id=cd.claim_id WHERE cd.correction_id=?", (correction_id,))]
    booking = corr.get("booking_period") or db.norm_ts(corr["tx_time"])[:7]
    periods = sorted({c["period_start"][:7] for c in changed if c.get("period_start") and c["period_start"][:7] < booking})
    orig_period = periods[-1] if periods else None
    findings = [dict(r) for r in db.q("SELECT f.*, a.kind, a.line_item, a.pinned_at, a.agent_id FROM impact_findings f JOIN artifacts a ON a.artifact_id=f.artifact_id AND a.version=f.artifact_version WHERE f.correction_id=?", (correction_id,))]
    hop0 = [f for f in findings if f["hop"] == 0]
    original_made_at = min((db.norm_ts(f["pinned_at"]) for f in hop0 if f.get("pinned_at")), default=None)
    moved = [abs((f["new_value"] or 0) - (f["old_value"] or 0)) for f in findings if f["verdict"] == "invalidated" and f["kind"] == "number" and f["old_value"] is not None and f["new_value"] is not None]
    if not moved:
        for c in changed:
            o = db.q1("SELECT value_num FROM claim_versions WHERE claim_version_id=?", (c["old_cv"],)) if c.get("old_cv") else None
            n = db.q1("SELECT value_num FROM claim_versions WHERE claim_version_id=?", (c["new_cv"],)) if c.get("new_cv") else None
            if o and n and o["value_num"] is not None and n["value_num"] is not None:
                moved.append(abs(n["value_num"] - o["value_num"]))
    moved0 = [abs((f["new_value"] or 0) - (f["old_value"] or 0)) for f in hop0 if f["verdict"] == "invalidated" and f["kind"] == "number" and f["old_value"] is not None and f["new_value"] is not None]
    size = max(moved0) if moved0 else (max(moved) if moved else 0.0)   # the direct move, before it compounds downstream
    flips = []
    for f in findings:
        if f["reason"] != "conclusion_flipped":
            continue
        a = db.q1("SELECT conclusions_json FROM artifacts WHERE artifact_id=? AND version=?", (f["artifact_id"], f["artifact_version"]))
        cj = (a["conclusions_json"] or "") if a else ""
        f["qualitative"] = ("covenant_max" in cj) or ("tiers" in cj) or "leverage" in (f.get("line_item") or "")
        flips.append(f)
    comps = [dict(r) for r in db.q("SELECT action_id, kind, approver_role, params_json FROM actions WHERE run_id=? AND kind<>'journal_entry'", (f"correction:{correction_id}",))]
    for c in comps:
        c["params"] = json.loads(c.pop("params_json") or "{}")
    delivered = sorted({"lender" if "cert_send" in f["artifact_id"] else "board" if "deck_publish" in f["artifact_id"] else "payroll" if ("bonus" in f["artifact_id"] or "commission" in f["artifact_id"]) else "tax authority" if "tax_payment" in f["artifact_id"] else "customer"
                        for f in findings if f["kind"] == "action" and f["verdict"] == "invalidated" and not f["artifact_id"].startswith("comp_")})
    thresholds = M.memo()
    unbooked = M.aggregate_unbooked(booking[:4])
    knowable = db.norm_ts(corr["knowable_at"]) if corr.get("knowable_at") else None
    src_ver = db.q1("SELECT version_id, tx_from FROM source_versions WHERE source_id=? AND version_id=?", (corr["source_id"], corr["new_version"]))
    return {
        "correction_id": correction_id, "source_id": corr["source_id"], "note": corr.get("note") or "", "tx_time": db.norm_ts(corr["tx_time"]),
        "kind": corr["kind"], "knowable_at": knowable, "original_made_at": original_made_at, "booking_period": booking, "orig_period": orig_period,
        "orig_locked": _locked(orig_period), "booking_locked": _locked(booking), "line_items": sorted({c["line_item"] for c in changed if c.get("line_item")}),
        "size": size, "n_findings": len(findings), "n_invalidated": sum(1 for f in findings if f["verdict"] == "invalidated"),
        "flips": [{"artifact_id": f["artifact_id"], "old": f["old_value"], "new": f["new_value"], "line_item": f["line_item"], "qualitative": f["qualitative"]} for f in flips],
        "comps": comps, "delivered": delivered, "engine_verdict": corr.get("materiality_verdict"), "thresholds": thresholds,
        "unbooked": {"n": unbooked["n"], "total": unbooked["total"]}, "source_version": dict(src_ver) if src_ver else None,
    }


def signature(facts: dict) -> list[str]:
    """Feature tokens a lesson is remembered by: the shape of the case, not its numbers."""
    t = {f"kind:{facts['kind']}"}
    t.update(f"line:{li}" for li in facts["line_items"][:6])
    th = facts["thresholds"]
    if facts["orig_locked"]:
        t.add("closed_period")
    if facts["knowable_at"] and facts["original_made_at"]:
        t.add("knowable_before" if facts["knowable_at"] <= facts["original_made_at"] else "knowable_after")
    if any(f["qualitative"] for f in facts["flips"]):
        t.add("flips_covenant")
    elif facts["flips"]:
        t.add("flips_conclusion")
    if facts["size"] > th["quarterly_performance"]:
        t.add("above_performance")
    if facts["size"] <= th["clearly_trivial"]:
        t.add("trivial")
    t.update(f"delivered:{d}" for d in facts["delivered"])
    t.update(f"comp:{c['kind']}" for c in facts["comps"])
    t.update(f"approver:{r}" for c in facts["comps"] for r in (c["approver_role"] or "").split("+") if r)
    return sorted(t)


# ------------------------------------------------------------------ truth, from the engines
def truth(facts: dict) -> dict[str, Any]:
    th = facts["thresholds"]
    quals = []
    if any(f["qualitative"] for f in facts["flips"]):
        quals.append("flips a stated conclusion (covenant compliance)")
    if any(c["kind"] in ("offset_next_bonus", "offset_next_commission") for c in facts["comps"]):
        quals.append("changes compensation already paid")
    if "lender" in facts["delivered"]:
        quals.append("a document delivered to the lender rests on it")
    if "board" in facts["delivered"]:
        quals.append("a document delivered to the board rests on it")
    agg = facts["unbooked"]["total"] + (facts["size"] if facts["kind"] == "error" else 0.0)
    material = facts["engine_verdict"] in MATERIAL_VERDICTS   # the engine already folds the qualitative flips in (escalate)
    return {
        "classification": "error" if facts["kind"] == "error" else "new information",
        "material": material, "qualitative": quals,
        "tests": {"annual_5pct": facts["size"] >= th["annual"], "performance": facts["size"] > th["quarterly_performance"], "clearly_trivial": facts["size"] <= th["clearly_trivial"],
                  "aggregate_with_log": agg, "aggregate_exceeds_performance": agg > th["quarterly_performance"]},
        "posting_period": facts["booking_period"],
        "approvers": sorted({r for c in facts["comps"] for r in (c["approver_role"] or "controller").split("+")} | {"controller"}),
    }


# ------------------------------------------------------------------ the playbook: v1 weaknesses, lifted by active checks
def playbook_version(active: set[str]) -> str:
    n = len(active & set(CHECKS))
    return "v2" if n == len(CHECKS) else ("v1" if n == 0 else f"v1+{n}")


def playbook_claims(facts: dict, active: set[str]) -> dict[str, Any]:
    th = facts["thresholds"]
    tr = truth(facts)
    out: dict[str, Any] = {}
    # 1. classification
    if "locked_period_means_estimate" in active and facts["orig_locked"]:
        out["classification"] = {"value": "new information", "basis": "the period is locked, so the item is treated as a change in estimate (lesson: locked period means estimate)", "check": "locked_period_means_estimate"}
    elif "classify_by_knowable_at" in active:
        out["classification"] = {"value": tr["classification"], "basis": _timing_text(facts), "check": "classify_by_knowable_at"}
    elif facts["orig_locked"]:
        out["classification"] = {"value": "error", "basis": f"the service period {facts['orig_period']} is closed, so the item is treated as an error (v1: service period, not arrival date)", "check": None}
    else:
        out["classification"] = {"value": tr["classification"], "basis": "open period: " + _timing_text(facts), "check": None}
    # 2. materiality
    if "materiality_full_framework" in active:
        out["materiality"] = {"value": tr["material"], "basis": _framework_text(facts, tr), "check": "materiality_full_framework"}
    else:
        out["materiality"] = {"value": facts["size"] >= th["annual"], "basis": f"{_money(facts['size'])} against the {_money(th['annual'])} annual threshold (5% of budgeted pretax); no other test run (v1)", "check": None}
    # 3. posting
    if "post_in_open_period" in active:
        out["posting"] = {"value": facts["booking_period"], "orig_period": facts["orig_period"], "basis": "first open period, tagged to the original period" if facts["orig_period"] and facts["orig_period"] != facts["booking_period"] else "the period is open", "check": "post_in_open_period"}
    else:
        p = facts["orig_period"] or facts["booking_period"]
        out["posting"] = {"value": p, "orig_period": facts["orig_period"], "basis": "dated into the period the item belongs to (v1)", "check": None}
    # 4. routing
    if "route_by_authority" in active:
        out["routing"] = {"value": tr["approvers"], "basis": "each item to the role the approval matrix names", "check": "route_by_authority"}
    else:
        out["routing"] = {"value": ["controller"], "basis": "everything to the Controller (v1)", "check": None}
    return out


def _timing_text(facts: dict) -> str:
    if facts["knowable_at"] and facts["original_made_at"]:
        rel = "before" if facts["knowable_at"] <= facts["original_made_at"] else "after"
        return f"the fact existed at {facts['knowable_at'][:16]}, {rel} the original number was made at {facts['original_made_at'][:16]} (Memento)"
    return "no earlier artifact rests on it"


def _framework_text(facts: dict, tr: dict) -> str:
    th = facts["thresholds"]; t = tr["tests"]
    parts = [f"{_money(facts['size'])} vs annual {_money(th['annual'])}: {'over' if t['annual_5pct'] else 'under'}",
             f"vs performance {_money(th['quarterly_performance'])}: {'over' if t['performance'] else 'under'}"]
    if facts["unbooked"]["n"]:
        parts.append(f"aggregate with {facts['unbooked']['n']} unbooked item{'s' if facts['unbooked']['n'] != 1 else ''} on the log {_money(t['aggregate_with_log'])}")
    parts += tr["qualitative"]
    return "; ".join(parts)


# ------------------------------------------------------------------ Jade
def jade_review(facts: dict, claims: dict) -> dict[str, Any]:
    tr = truth(facts)
    th = facts["thresholds"]
    out: dict[str, Any] = {}
    # classification: Memento says when the fact first existed vs when the original number was made
    ev = []
    if facts["source_version"]:
        ev.append(f"memento:{facts['source_version']['version_id']}")
    if facts["original_made_at"]:
        ev.append(f"original artifacts pinned {facts['original_made_at'][:16]}")
    if facts["knowable_at"]:
        ev.append(f"knowable {facts['knowable_at'][:16]}")
    c = claims["classification"]
    out["classification"] = _verdict(c["value"] == tr["classification"], c["value"], tr["classification"],
                                     ("The fact existed before the original number was made: an error under ASC 250." if tr["classification"] == "error" else
                                      f"The information arrived {facts['knowable_at'][:10] if facts['knowable_at'] else 'later'}, after the original number was made{(' on ' + facts['original_made_at'][:10]) if facts['original_made_at'] else ''}: new information, not an error. The service period is beside the point."), ev)
    # materiality: both quantitative tests, the aggregate, the qualitative triggers from the graph
    m = claims["materiality"]
    why = _framework_text(facts, tr)
    out["materiality"] = _verdict(bool(m["value"]) == tr["material"], "material" if m["value"] else "immaterial", "material" if tr["material"] else "immaterial",
                                  (f"Material: {why}." if tr["material"] else f"Not material: {why}."), [f"materiality memo: annual {_money(th['annual'])}, performance {_money(th['quarterly_performance'])}, trivial {_money(th['clearly_trivial'])}"] + [f"finding:{f['artifact_id']}" for f in facts["flips"]] + [f"compensation:{c['action_id']}" for c in facts["comps"]])
    # posting: the period must be open; out-of-period entries carry the original period
    p = claims["posting"]
    locked = _locked(p["value"])
    out["posting"] = _verdict(not locked, p["value"], tr["posting_period"],
                              (f"Period {p['value']} is locked (policy C-1). Book in {tr['posting_period']} with an out-of-period tag to {facts['orig_period']}; restate the lender package separately." if locked else f"Period {p['value']} is open."),
                              [f"periods:{p['value']}:{'locked' if locked else 'open'}"])
    # routing: an approver whose role allows it, never the proposer
    r = claims["routing"]
    missing = [x for x in tr["approvers"] if x not in r["value"]]
    out["routing"] = _verdict(not missing, r["value"], tr["approvers"],
                              (f"{', '.join(ROLE_WORD.get(x, x) for x in missing)} must approve: " + "; ".join(f"{c['kind'].replace('_', ' ')} → {ROLE_WORD.get(c['approver_role'], c['approver_role'])}" for c in facts["comps"] if c["approver_role"] != "controller") + "." if missing else "Every item goes to a role the approval matrix allows; the proposer is never the approver."),
                              [f"approval matrix: {c['kind']} → {c['approver_role']}" for c in facts["comps"]] or ["approval matrix: journal entries → controller"])
    # the size claim is numeric: recomputed, never argued
    out["size"] = {"verdict": "approve", "agent": facts["size"], "jade": facts["size"], "why": f"Recomputed from {facts['n_findings']} findings ({facts['n_invalidated']} invalidated): largest move {_money(facts['size'])}.", "evidence": [f"findings:{facts['correction_id']}"]}
    n_over = sum(1 for k in CLAIMS if out[k]["verdict"] == "overrule")
    out["summary"] = {"approved": len(CLAIMS) - n_over, "overruled": n_over, "overruled_claims": [k for k in CLAIMS if out[k]["verdict"] == "overrule"]}
    return out


def _verdict(ok: bool, agent, jade, why: str, evidence: list[str]) -> dict:
    return {"verdict": "approve" if ok else "overrule", "agent": agent, "jade": jade, "why": why, "evidence": evidence}


# ------------------------------------------------------------------ one Error Evaluation per correction, stored
def evaluate(correction_id: str, ts: str | None = None, *, store: bool = True) -> dict[str, Any] | None:
    from . import lessons as L
    facts = case_facts(correction_id)
    if facts is None:
        return None
    ts = db.norm_ts(ts or facts["tx_time"])
    active = L.active_checks(ts)
    sig = signature(facts)
    recalled = L.recall(sig, exclude_case=correction_id, at=ts)
    claims = playbook_claims(facts, active)
    jade = jade_review(facts, claims)
    ev = {"correction_id": correction_id, "ts": ts, "playbook_version": playbook_version(active), "active_checks": sorted(active), "claims": claims, "jade": jade,
          "recalled": recalled, "signature": sig, "facts": {k: facts[k] for k in ("kind", "knowable_at", "original_made_at", "booking_period", "orig_period", "orig_locked", "size", "flips", "comps", "delivered", "engine_verdict", "thresholds", "unbooked", "line_items", "note")},
          "headline": headline(facts, claims, jade)}
    if store:
        if db.q1("SELECT 1 FROM evaluations WHERE correction_id=?", (correction_id,)):
            db.get_conn().execute("DELETE FROM evaluations WHERE correction_id=?", (correction_id,))
        db.insert("evaluations", {"correction_id": correction_id, "ts": ts, "playbook_version": ev["playbook_version"], "active_checks_json": db.dumps(ev["active_checks"]), "claims_json": db.dumps(claims),
                                  "jade_json": db.dumps(jade), "recalled_json": db.dumps(recalled), "summary_json": db.dumps({**jade["summary"], "headline": ev["headline"]}), "facts_json": db.dumps({**ev["facts"], "signature": sig})})
        for k in jade["summary"]["overruled_claims"]:
            L.propose_from_overrule(k, correction_id, jade[k], sig, ts)
        db.log_event("jade_review", f"Jade reviewed {correction_id} under playbook {ev['playbook_version']}: {jade['summary']['approved']} approved, {jade['summary']['overruled']} overruled" + (f" ({', '.join(jade['summary']['overruled_claims'])})" if jade["summary"]["overruled"] else ""),
                     actor="jade", ts=ts, correction_id=correction_id, detail={"overruled": jade["summary"]["overruled_claims"], "playbook": ev["playbook_version"], "recalled": [r["lesson_id"] for r in recalled]})
        db.commit()
    return ev


def headline(facts: dict, claims: dict, jade: dict) -> dict[str, Any]:
    """The one-line version for Stage mode: what the agent said, what Jade said, in plain words with the real numbers."""
    th = facts["thresholds"]
    over = jade["summary"]["overruled_claims"]
    if "materiality" in over:
        reasons = []
        if facts["size"] > th["quarterly_performance"]:
            reasons.append(f"over the {_money(th['quarterly_performance'])} performance threshold")
        lev = next((f for f in facts["flips"] if f.get("qualitative") and (f.get("line_item") == "leverage" or "leverage" in f["artifact_id"])), None)
        if lev:
            reasons.append(f"leverage {lev['old']:.2f}x → {lev['new']:.2f}x crosses the covenant")
        elif any(f.get("qualitative") for f in facts["flips"]):
            reasons.append("a stated conclusion flips")
        if any(c["kind"] in ("offset_next_bonus", "offset_next_commission") for c in facts["comps"]):
            reasons.append("bonuses already paid change")
        if "lender" in facts["delivered"]:
            reasons.append("the lender already has the certificate")
        return {"claim": "materiality", "agent": f"Immaterial: {_money(facts['size'])} is under the {_money(th['annual'])} annual threshold.", "jade": "Material: " + "; ".join(reasons[:3]) + ".", "verdict": "overruled"}
    if "classification" in over:
        return {"claim": "classification", "agent": f"{claims['classification']['value'].capitalize()}: {claims['classification']['basis']}.", "jade": jade["classification"]["why"], "verdict": "overruled"}
    if "routing" in over:
        return {"claim": "routing", "agent": "Send everything to the Controller.", "jade": jade["routing"]["why"], "verdict": "overruled"}
    if "posting" in over:
        return {"claim": "posting", "agent": f"Book it in {claims['posting']['value']}.", "jade": jade["posting"]["why"], "verdict": "overruled"}
    return {"claim": None, "agent": f"{claims['classification']['value'].capitalize()}, {'material' if claims['materiality']['value'] else 'not material'}, book in {claims['posting']['value']}.", "jade": "Every claim checks out.", "verdict": "approved"}


def load(correction_id: str) -> dict[str, Any] | None:
    r = db.q1("SELECT * FROM evaluations WHERE correction_id=?", (correction_id,))
    if r is None:
        return None
    d = dict(r)
    out = {"correction_id": d["correction_id"], "ts": d["ts"], "playbook_version": d["playbook_version"], "active_checks": json.loads(d["active_checks_json"] or "[]"),
           "claims": json.loads(d["claims_json"] or "{}"), "jade": json.loads(d["jade_json"] or "{}"), "recalled": json.loads(d["recalled_json"] or "[]"),
           "facts": json.loads(d["facts_json"] or "{}")}
    s = json.loads(d["summary_json"] or "{}")
    out["headline"] = s.get("headline")
    return out


def load_all() -> list[dict[str, Any]]:
    return [x for x in (load(r["correction_id"]) for r in db.q("SELECT correction_id FROM evaluations ORDER BY ts")) if x]
