"""Learning from mistakes (SPEC.md Section 11). Mistake signals are never the agent grading itself: Jade overrules, a human rejects or edits
a draft, a flagged difference is dismissed as noise, a cleared item turns out affected, a lineage link is corrected, a case fails.

Each mistake becomes a proposed lesson (kind, rule, the case evidence, how it is enforced). Lessons that can be checks change the playbook;
the rest are guidance text. Governance: proposed lessons need Dana's approval (they apply prospectively), and before activation the whole
scorecard is rerun with the lesson; a lesson that makes any previously passing case fail is rejected, and the result is shown.
"""
from __future__ import annotations

import json
import uuid

from .agent import playbook as PB
from .core import db

SIGNAL_TO_LESSON = {
    ("jade", "q5_matters"): "materiality_framework",
    ("jade", "q3_classification"): "classify_by_knowable_at",
    ("human", "journal_entry_rejected"): "post_in_open_period",
    ("jade", "q7_fix.approvers.lender_document"): "lender_documents_to_cfo",
}


def mistakes_from(results: list[dict]) -> list[dict]:
    """Mistake signals from a scorecard run (Jade's overrules and flags, a simulated Controller's rejections)."""
    out = []
    for r in results:
        for f in r.get("jade", []):
            if f["verdict"] in ("overrule", "flag", "escalate") and (("jade", f["claim_key"]) in SIGNAL_TO_LESSON):
                out.append({"case": r["case"], "signal": "jade", "claim": f["claim_key"], "why": f["why"], "lesson": SIGNAL_TO_LESSON[("jade", f["claim_key"])]})
            if f["verdict"] == "escalate" and f["claim_key"] == "q7_fix.posting":
                out.append({"case": r["case"], "signal": "human", "claim": "journal_entry_rejected", "why": "Q1 is locked. Book it in June with an out-of-period tag.", "lesson": "post_in_open_period"})
    return out


def propose(mistakes: list[dict], ts: str, world: str = "tidewall", extra: list[str] | None = None) -> list[str]:
    """One proposed lesson per mistake kind (plus any extra candidates a person typed). Returns lesson ids."""
    ids = []
    by: dict[str, list[dict]] = {}
    for m in mistakes:
        by.setdefault(m["lesson"], []).append(m)
    for key in list(by) + [k for k in (extra or []) if k not in by]:
        p = PB.LESSON_PATCHES[key]
        lid = f"LS-{key}"
        if db.q1("SELECT 1 FROM lessons WHERE lesson_id=?", (lid,)):
            ids.append(lid)
            continue
        ev = by.get(key, [{"case": "X3", "signal": "human", "why": "a person generalized from X3"}])
        db.insert("lessons", {"lesson_id": lid, "world": world, "mistake_kind": key, "source": ev[0]["signal"], "rule": p["rule"], "evidence_json": json.dumps(ev[:6]),
                              "enforcement": "playbook check: " + ".".join(p["path"]), "status": "proposed", "gate_json": None, "proposed_at": db.norm_ts(ts), "decided_by": None,
                              "decided_at": None, "playbook_version": None})
        ids.append(lid)
    db.commit()
    return ids


def gate(lesson_id: str, run_scorecard, baseline_keys: list[str]) -> dict:
    """Rerun the whole scorecard with the lesson added; reject it if any previously passing case fails."""
    key = db.q1("SELECT mistake_kind FROM lessons WHERE lesson_id=?", (lesson_id,))["mistake_kind"]
    before = run_scorecard(baseline_keys)
    after = run_scorecard(baseline_keys + [key])
    broke = sorted(c for c, ok in before["passed"].items() if ok and not after["passed"].get(c, False))
    fixed = sorted(c for c, ok in after["passed"].items() if ok and not before["passed"].get(c, False))
    res = {"lesson": key, "passed_before": sum(before["passed"].values()), "passed_after": sum(after["passed"].values()), "cases": len(after["passed"]),
           "broke": broke, "fixed": fixed, "result": "pass" if not broke else "fail"}
    db.get_conn().execute("UPDATE lessons SET gate_json=?, status=? WHERE lesson_id=?", (json.dumps(res), "gate_passed" if not broke else "gate_failed", lesson_id))
    db.commit()
    return res


def approve(lesson_id: str, by: str, ts: str) -> dict:
    row = db.q1("SELECT * FROM lessons WHERE lesson_id=?", (lesson_id,))
    if row["status"] != "gate_passed":
        return {"lesson_id": lesson_id, "approved": False, "why": f"status is {row['status']}: only gate-passed lessons can be approved"}
    db.get_conn().execute("UPDATE lessons SET status='active', decided_by=?, decided_at=? WHERE lesson_id=?", (by, db.norm_ts(ts), lesson_id))
    db.log_event("lesson_approved", f"{by} approved lesson {row['mistake_kind']}: {row['rule']} (applies prospectively)", actor=by, ts=ts)
    db.commit()
    return {"lesson_id": lesson_id, "approved": True, "playbook": PB.current()["version"]}


def listing() -> list[dict]:
    out = []
    for r in db.q("SELECT * FROM lessons ORDER BY proposed_at, lesson_id"):
        d = dict(r)
        d["evidence"] = json.loads(d.pop("evidence_json") or "[]")
        d["gate"] = json.loads(d.pop("gate_json") or "null")
        out.append(d)
    return out
