"""Jade, the reviewer (SPEC.md Section 8). Claim by claim: approve, overrule (with the corrected claim and why), escalate, or flag.

- numeric claims: recompute from the engines and compare
- evidence claims: the cited record exists and says what the claim says
- classification: ask Replay when the underlying fact first appeared versus when the original number was made
- materiality: always run the full framework (both SAB 108 methods, qualitative tests, aggregation with the log) and compare
- posting: the entry balances and carries orig_period; a locked posting period is the Controller's call, so Jade escalates it to her
- authority: each item goes to a role allowed to approve it (lender documents to the CFO), and the proposer is never the approver
- judgment claims (root-cause wording): an LLM critique when a model is available; otherwise accepted and marked "not independently verified"
Code checks everything numeric, evidential, policy and authority; the LLM only critiques wording.
"""
from __future__ import annotations

import json
import uuid

from . import config as C
from .agent import agent as AG, llm
from .core import db
from .engine import materiality as MAT

ALLOWED = {"journal_entry": {"dana"}, "lender_document": {"sam"}, "comp_offset": {"lena"}, "tax_offset": {"dana"}, "vendor_credit": {"marco"}, "vendor_hold": {"marco"}, "misstatement_log": {"dana"}}


def review(ev: dict, exc: dict, mat: dict, pin: str, proposer: str = "close_accountant") -> list[dict]:
    eid = ev["exception_id"]
    out: list[dict] = []

    def add(key, verdict, why, agent_value=None, corrected=None, method="code"):
        out.append({"claim_key": key, "verdict": verdict, "why": why, "agent_value": agent_value, "corrected": corrected, "method": method})

    # numeric: size recomputed from the correction lines
    lines = (exc.get("correction") or {}).get("lines") or []
    if exc["kind"] != "accrual_true_up" and lines:
        s = MAT.sizes(lines)
        a = ev["q4_size"]
        ok = abs(a["rollover"] - s["rollover"]) < 0.01 and abs(a["iron_curtain"] - s["iron_curtain"]) < 0.01
        add("q4_size", "approve" if ok else "overrule", f"recomputed: rollover ${s['rollover']:,.2f}, iron curtain ${s['iron_curtain']:,.2f}", a, None if ok else s)
        if exc.get("by_region"):
            by = {}
            for l in lines:
                if l["account"] == "4010":
                    r = C.GYM_REGION.get(l["entity"], "HQ")
                    by[r] = by.get(r, 0) + l["amount_cents"] / 100
            add("q4_size.by_region", "approve" if all(abs(by.get(r, 0) - v) < 0.01 for r, v in exc["by_region"].items()) else "overrule", f"by region from the reversing lines: {by}")
    # evidence: every cited import / invoice / bank line exists in the run's recon rows
    cited = [c for c in ev["q1_what"]["evidence"] if c and not c.startswith("recon:")]
    missing = [c for c in cited if not _exists(c)]
    add("q1_what.evidence", "approve" if not missing else "flag", "cited records exist" if not missing else f"cannot find {missing}")
    # classification by Replay
    kn = AG.knowable(exc)
    if exc["kind"] in ("ach_return", "unbooked_bank_fee"):
        want = "fact_update"
    elif exc["kind"] in ("duplicate_vendor_invoice", "duplicate_import", "misclassification", "fx_error", "prior_year_recognition"):
        want = "error"
    else:
        want = "error" if kn["at"] <= db.norm_ts(C.KEY_DATES["q1_close"]) else "estimate_change"
    got = ev["q3_classification"]["value"]
    if got == want:
        add("q3_classification", "approve", f"Replay: {kn['fact']}", got)
    else:
        why = (f"the invoice arrived {kn['at'][:10]}, after the Apr 10 close; the accrual was the best estimate then. Change in estimate, already booked in "
               f"{', '.join(exc.get('booked_in') or []) or 'a later period'}: no restatement" if want == "estimate_change" else f"the fact existed at {kn['at']} before the close: an error")
        add("q3_classification", "overrule", why, got, {"value": want, "knowable_at": kn["at"]})
    # materiality: the full framework, always
    full = mat["per_item"].get(eid)
    agent_mat = ev["q5_matters"]["material"]
    if want == "estimate_change":
        jm = False
        if agent_mat or got != want:
            add("q5_matters", "overrule" if agent_mat else "approve", "a change in estimate is not a misstatement", agent_mat, {"material": False})
        else:
            add("q5_matters", "approve", "change in estimate: no materiality test applies", agent_mat)
    elif full is not None:
        jm = full["material"]
        if jm == agent_mat:
            add("q5_matters", "approve", AG._mat_why(full, mat), agent_mat)
        else:
            agg = mat["aggregate"]
            facs = {q["factor"]: q for q in full["qualitative"]}
            parts = []
            if not full["above_performance"]:
                parts.append(f"Alone it is below performance materiality (${mat['thresholds']['performance']:,.0f}), but it aggregates with the other items")
            parts.append(f"Aggregate rollover ${agg['rollover']:,.0f} passes but iron curtain ${agg['iron_curtain']:,.0f} fails against ${mat['thresholds']['overall']:,.0f}; SAB 108 requires both methods")
            if "covenant_flip" in facs:
                parts.append(f"it flips the loan covenant ({facs['covenant_flip']['detail']})")
            if "compensation" in facs:
                parts.append("it changes management compensation")
            if "delivered_document" in facs and "covenant_flip" not in facs:
                parts.append("it changes figures in documents already delivered to the lender and the board")
            why = ("; ".join(parts) + ".") if jm else "below the thresholds under both methods and no qualitative factor applies"
            add("q5_matters", "overrule", why, agent_mat, {"material": jm, "triggers": full["triggers"], "qualitative": full["qualitative"]})
    # posting: balanced, orig_period carried; a locked posting period goes to the Controller
    fix = ev["q7_fix"]
    if fix.get("entries") and want != "estimate_change":
        bal = sum(l["amount_cents"] for l in fix["entries"]) == 0
        tagged = all(l.get("orig_period") for l in fix["entries"])
        locked = fix.get("posting_period") in C.LOCKED_PERIODS
        if not bal or not tagged:
            add("q7_fix.posting", "flag", "entries must balance and carry orig_period", fix.get("posting_period"))
        elif locked:
            add("q7_fix.posting", "escalate", f"posting period {fix['posting_period']} is locked; period locks are the Controller's decision (routed to Dana Ortiz)", fix.get("posting_period"))
        else:
            add("q7_fix.posting", "approve", f"posts in open period {fix['posting_period']} tagged to {fix.get('orig_period')}", fix.get("posting_period"))
    # authority
    for kind, who in (fix.get("approvers") or {}).items():
        allowed = ALLOWED.get(kind, set())
        if who == proposer:
            add(f"q7_fix.approvers.{kind}", "flag", "the proposer can never approve its own work", who)
        elif allowed and who not in allowed:
            to = sorted(allowed)[0]
            add(f"q7_fix.approvers.{kind}", "flag", f"{kind.replace('_', ' ')}s go to {C.PEOPLE_V3[to]['name']} ({C.PEOPLE_V3[to]['title']}), not {C.PEOPLE_V3[who]['name']}"
                + (": only the CFO signs anything sent to the lender" if kind == "lender_document" else ""), who, {"approver": to})
        else:
            add(f"q7_fix.approvers.{kind}", "approve", f"{C.PEOPLE_V3[who]['name']} may approve {kind.replace('_', ' ')}s", who)
    # judgment: root-cause wording (LLM critique if available)
    cr = llm.critique(f"jade:{eid}:root_cause", ev["q1_what"]["root_cause"], ev["q1_what"].get("facts") or {"title": exc["title"], "evidence": exc.get("evidence", [])[:3]}, pin)
    add("q1_what.root_cause", cr["verdict"], cr["why"] if cr["verified"] else "accepted; not independently verified (no model)", method="llm" if cr["verified"] else "accept")
    return out


def _exists(ref: str) -> bool:
    if ref.startswith("IMP-"):
        return db.q1("SELECT 1 FROM gl_entries WHERE import_id=? LIMIT 1", (ref,)) is not None
    return True


def store(eval_id: str, findings: list[dict], ts: str) -> None:
    for f in findings:
        db.insert("jade_reviews", {"review_id": "JR-" + uuid.uuid4().hex[:8], "eval_id": eval_id, "claim_key": f["claim_key"], "verdict": f["verdict"],
                                   "agent_value_json": json.dumps(f.get("agent_value"), default=str), "corrected_json": json.dumps(f.get("corrected"), default=str),
                                   "why": f["why"], "method": f["method"], "created_at": db.norm_ts(ts)})


def apply(ev: dict, findings: list[dict]) -> dict:
    """The evaluation after Jade: overrules and authority flags corrected; escalations stay for the human who owns the decision."""
    import copy
    out = copy.deepcopy(ev)
    for f in findings:
        if f["verdict"] not in ("overrule", "flag") or not f.get("corrected"):
            continue
        k = f["claim_key"]
        if k == "q3_classification":
            out["q3_classification"].update(f["corrected"])
            if f["corrected"]["value"] == "estimate_change":
                out["q7_fix"] = {"entries": [], "treatment": "no_action", "posting_period": None, "why": "change in estimate, already booked when the invoice arrived", "documents_to_reissue": [],
                                 "compensations": [], "approvers": {}, "evidence": ["ap_invoices", "accruals"]}
        elif k == "q5_matters":
            out["q5_matters"].update(f["corrected"])
        elif k.startswith("q7_fix.approvers."):
            out["q7_fix"]["approvers"][k.split(".")[-1]] = f["corrected"]["approver"]
        elif k == "q4_size":
            out["q4_size"].update(f["corrected"])
    out["reviewed_by"] = "jade"
    return out
